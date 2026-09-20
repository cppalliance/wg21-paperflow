#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Model-profile loading and resolution.

A profile is bound to a MODEL IDENTITY, not to a service slot: a pod can be
renamed, moved or duplicated (``alliance-pod`` and ``h200x8-deepseek-v4-pro``
are two running instances of one model), so the slot name is provenance while
the model name is identity. ``resolve_profile`` therefore accepts a profile id,
a model identity, or a service name that is first translated to its model
identity through ``SERVICES.toml``.

Resolution is fail-closed in both directions: an unknown model raises
:class:`ProfileNotFoundError` (never a silent fallback to whichever profile
happens to exist), and a model matched by two profiles raises
:class:`ProfileAmbiguousError` rather than picking one. When no selector is
given, the default profile (``deepseek-v4``) is loaded.

``SERVICES.toml`` is read with stdlib ``tomllib``, not through
``pipeline.services``. That loader returns backend objects whose credentials are
private by design, and importing it would put the LLM framework into whisker's
deterministic core, which the root import-linter contracts forbid.

Each profile ships a single ``rules.toml`` containing the full contract (rules,
thresholds, applicability predicates) with model-specific values baked directly
into the definitions, plus the profile metadata (identity, certification,
weaknesses, probes). There is no overlay or merge step.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from functools import lru_cache
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from types import MappingProxyType

from whisker.det.llm_readability.contract import (
    COMBINED_TOP_KEYS,
    CONSTRUCT_DIR,
    CONTRACT_PACKAGE,
    DEFAULT_PROFILE_ID,
    SUPPORTED_SCHEMA_VERSION,
    ContractError,
    ContractSchemaError,
    canonical_hash,
    parse_contract,
)
from whisker.det.llm_readability.models import (
    CERTIFICATION_STATUSES,
    METHODS,
    KnownWeakness,
    ModelProfile,
    ProfileProbe,
    ResolvedContract,
    RuleOverride,
    TableContract,
)

__all__ = [
    "ProfileAmbiguousError",
    "ProfileError",
    "ProfileNotFoundError",
    "SERVICES_FILENAME",
    "available_profiles",
    "find_services_toml",
    "load_combined",
    "load_profile",
    "normalize_identity",
    "parse_profile",
    "profile_text",
    "resolve_contract",
    "resolve_profile",
    "resolved_core_only",
    "service_model_identity",
]

PROFILE_RESOURCE_NAME = "rules.toml"
SERVICES_FILENAME = "SERVICES.toml"

# The machine-readable reason code a caller can key on when no profile matched.
# Deliberately the same string the plan and the reports use.
PROFILE_MISSING_CODE = "profile_missing"


class ProfileError(ContractError):
    """Base class for profile resolution and merge failures."""


class ProfileNotFoundError(ProfileError):
    """No profile matched the requested id, model identity or service."""

    code = PROFILE_MISSING_CODE


class ProfileAmbiguousError(ProfileError):
    """More than one profile claimed the same model identity."""


# -- resource discovery --------------------------------------------------------


def _profiles_root() -> Traversable:
    return resources.files(CONTRACT_PACKAGE)


def available_profiles(construct: str = CONSTRUCT_DIR) -> tuple[str, ...]:
    """Return every packaged profile id, sorted."""
    root = _profiles_root()
    if not root.is_dir():
        return ()
    found: list[str] = []
    for entry in root.iterdir():
        if entry.is_dir() and (entry / construct / PROFILE_RESOURCE_NAME).is_file():
            found.append(entry.name)
    return tuple(sorted(found))


def profile_text(profile_id: str, construct: str = CONSTRUCT_DIR) -> str:
    """Return the raw ``rules.toml`` text for ``profile_id``."""
    resource = _profiles_root() / profile_id / construct / PROFILE_RESOURCE_NAME
    if not resource.is_file():
        raise ProfileNotFoundError(
            f"{PROFILE_MISSING_CODE}: no packaged profile {profile_id!r} "
            f"(available: {', '.join(available_profiles(construct)) or 'none'})"
        )
    return resource.read_text(encoding="utf-8")


# -- schema helpers ------------------------------------------------------------


def _text(data: Mapping[str, object], key: str, where: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContractSchemaError(f"{where}: missing or empty string {key!r}")
    return value.strip()


def _string_tuple(
    data: Mapping[str, object],
    key: str,
    where: str,
    *,
    required: bool = True,
) -> tuple[str, ...]:
    value = data.get(key, [])
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ContractSchemaError(f"{where}: {key!r} must be an array of strings")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ContractSchemaError(f"{where}: {key!r} holds a non-string entry")
        items.append(item.strip())
    if required and not items:
        raise ContractSchemaError(f"{where}: {key!r} must not be empty")
    if len(set(items)) != len(items):
        raise ContractSchemaError(f"{where}: {key!r} holds duplicate entries")
    return tuple(items)


def _no_unknown_keys(
    data: Mapping[str, object], allowed: Sequence[str], where: str
) -> None:
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        raise ContractSchemaError(f"{where}: unknown key(s) {', '.join(unknown)}")


def _table(data: Mapping[str, object], key: str, where: str) -> Mapping[str, object]:
    value = data.get(key, {})
    if not isinstance(value, Mapping):
        raise ContractSchemaError(f"{where}: {key!r} must be a table")
    return value


def normalize_identity(value: str) -> str:
    """Normalize a model identity for matching (case and separator folding)."""
    return value.strip().casefold().replace("_", "-")


# -- profile parsing -----------------------------------------------------------

_PROFILE_KEYS = (
    "profile",
    "model_identity",
    "certification",
    "thresholds",
    "rules",
    "probes",
    "known_weaknesses",
    "evidence",
)
_PROFILE_META_KEYS = (
    "id",
    "version",
    "schema_version",
    "display_name",
    "requires_core_contract_version",
    "certification_status",
    "notes",
)
_MODEL_IDENTITY_KEYS = ("model_ids", "aliases", "services", "backend")
_CERTIFICATION_KEYS = ("required_methods", "required_rules")
_RULE_OVERRIDE_KEYS = (
    "strength",
    "additional_requirement",
    "additional_llm_instruction",
)
_PROBE_KEYS = ("id", "rules", "description", "evidence")


def parse_profile(data: Mapping[str, object]) -> ModelProfile:
    """Validate and build a :class:`ModelProfile` from parsed TOML data.

    Accepts a combined ``rules.toml`` that also carries contract keys; those
    are silently ignored here and consumed by ``parse_contract`` in
    ``contract.py``.
    """
    _no_unknown_keys(data, COMBINED_TOP_KEYS, "rules.toml")
    meta = _table(data, "profile", "profile")
    if not meta:
        raise ContractSchemaError("profile: missing [profile] table")
    _no_unknown_keys(meta, _PROFILE_META_KEYS, "[profile]")
    schema_version = meta.get("schema_version")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        raise ContractSchemaError("[profile]: missing or non-integer schema_version")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ContractSchemaError(
            f"[profile]: schema_version {schema_version} is not supported "
            f"(this build understands {SUPPORTED_SCHEMA_VERSION})"
        )
    certification_status = _text(meta, "certification_status", "[profile]")
    if certification_status not in CERTIFICATION_STATUSES:
        raise ContractSchemaError(
            f"[profile]: unknown certification_status {certification_status!r} "
            f"(allowed: {', '.join(CERTIFICATION_STATUSES)})"
        )

    identity = _table(data, "model_identity", "profile")
    if not identity:
        raise ContractSchemaError("profile: missing [model_identity] table")
    _no_unknown_keys(identity, _MODEL_IDENTITY_KEYS, "[model_identity]")
    model_ids = _string_tuple(identity, "model_ids", "[model_identity]")
    aliases = _string_tuple(identity, "aliases", "[model_identity]", required=False)

    certification = _table(data, "certification", "profile")
    _no_unknown_keys(certification, _CERTIFICATION_KEYS, "[certification]")
    required_methods = _string_tuple(
        certification, "required_methods", "[certification]", required=False
    )
    for method in required_methods:
        if method not in METHODS:
            raise ContractSchemaError(
                f"[certification]: unknown required method {method!r} "
                f"(allowed: {', '.join(METHODS)})"
            )
    required_rules = _string_tuple(
        certification, "required_rules", "[certification]", required=False
    )

    # In a combined rules.toml the thresholds section contains nested table
    # definitions (contract-level), not flat scalar overrides. Skip any entry
    # that is a Mapping (a nested table definition from the contract).
    thresholds_data = _table(data, "thresholds", "profile")
    threshold_overrides: dict[str, int | float | tuple[str, ...]] = {}
    for name in sorted(thresholds_data):
        raw = thresholds_data[name]
        if isinstance(raw, Mapping):
            continue
        if isinstance(raw, bool):
            raise ContractSchemaError(
                f"[thresholds]: override {name!r} must be a number or a string array"
            )
        if isinstance(raw, (int, float)):
            threshold_overrides[name] = raw
        elif isinstance(raw, Sequence) and not isinstance(raw, str):
            values: list[str] = []
            for item in raw:
                if not isinstance(item, str) or not item.strip():
                    raise ContractSchemaError(
                        f"[thresholds]: override {name!r} holds a non-string entry"
                    )
                values.append(item.strip())
            if not values:
                raise ContractSchemaError(
                    f"[thresholds]: override {name!r} must not be empty"
                )
            threshold_overrides[name] = tuple(values)
        else:
            raise ContractSchemaError(
                f"[thresholds]: override {name!r} must be a number or a string array"
            )

    # In a combined rules.toml the rules key is an array of tables
    # (contract-level [[rules]]), not a table of override sub-tables. Parse
    # overrides only when the key is actually a Mapping.
    rules_raw = data.get("rules", {})
    rule_overrides: dict[str, RuleOverride] = {}
    if isinstance(rules_raw, Mapping):
        for rule_id in sorted(rules_raw):
            entry = rules_raw[rule_id]
            where = f"[rules.{rule_id}]"
            if not isinstance(entry, Mapping):
                raise ContractSchemaError(f"{where}: must be a table")
            _no_unknown_keys(entry, _RULE_OVERRIDE_KEYS, where)
            if not entry:
                raise ContractSchemaError(
                    f"{where}: empty override carries no meaning"
                )
            strength = entry.get("strength")
            if strength is not None and not isinstance(strength, str):
                raise ContractSchemaError(f"{where}: strength must be a string")
            rule_overrides[rule_id] = RuleOverride(
                rule_id=rule_id,
                strength=strength.strip() if isinstance(strength, str) else None,
                additional_requirement=(
                    _text(entry, "additional_requirement", where)
                    if "additional_requirement" in entry
                    else None
                ),
                additional_llm_instruction=(
                    _text(entry, "additional_llm_instruction", where)
                    if "additional_llm_instruction" in entry
                    else None
                ),
            )

    probes = tuple(
        _parse_probe(entry, position=position, kind="probes")
        for position, entry in enumerate(_entry_list(data, "probes"))
    )
    weaknesses = tuple(
        _parse_weakness(entry, position=position)
        for position, entry in enumerate(_entry_list(data, "known_weaknesses"))
    )
    _reject_duplicate_ids([probe.id for probe in probes], "[[probes]]")
    _reject_duplicate_ids(
        [weakness.id for weakness in weaknesses], "[[known_weaknesses]]"
    )

    requires_core_raw = meta.get("requires_core_contract_version")
    requires_core_version = (
        requires_core_raw.strip()
        if isinstance(requires_core_raw, str) and requires_core_raw.strip()
        else ""
    )

    return ModelProfile(
        id=_text(meta, "id", "[profile]"),
        version=_text(meta, "version", "[profile]"),
        schema_version=schema_version,
        display_name=_text(meta, "display_name", "[profile]"),
        requires_core_contract_version=requires_core_version,
        certification_status=certification_status,
        model_ids=model_ids,
        aliases=aliases,
        services=_string_tuple(
            identity, "services", "[model_identity]", required=False
        ),
        backend=_text(identity, "backend", "[model_identity]"),
        required_methods=required_methods,
        required_rules=required_rules,
        threshold_overrides=MappingProxyType(threshold_overrides),
        rule_overrides=MappingProxyType(rule_overrides),
        probes=probes,
        known_weaknesses=weaknesses,
        evidence=_string_tuple(data, "evidence", "profile"),
        notes=_text(meta, "notes", "[profile]"),
        hash=canonical_hash(data),
    )


def _entry_list(
    data: Mapping[str, object], key: str
) -> tuple[Mapping[str, object], ...]:
    value = data.get(key, [])
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ContractSchemaError(f"profile: [[{key}]] must be an array of tables")
    entries: list[Mapping[str, object]] = []
    for position, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ContractSchemaError(f"[[{key}]] #{position + 1}: must be a table")
        entries.append(item)
    return tuple(entries)


def _parse_probe(
    data: Mapping[str, object], *, position: int, kind: str
) -> ProfileProbe:
    where = f"[[{kind}]] #{position + 1}"
    _no_unknown_keys(data, _PROBE_KEYS, where)
    return ProfileProbe(
        id=_text(data, "id", where),
        rules=_string_tuple(data, "rules", where),
        description=_text(data, "description", where),
        evidence=_string_tuple(data, "evidence", where),
    )


def _parse_weakness(data: Mapping[str, object], *, position: int) -> KnownWeakness:
    where = f"[[known_weaknesses]] #{position + 1}"
    _no_unknown_keys(data, _PROBE_KEYS, where)
    return KnownWeakness(
        id=_text(data, "id", where),
        rules=_string_tuple(data, "rules", where),
        description=_text(data, "description", where),
        evidence=_string_tuple(data, "evidence", where),
    )


def _reject_duplicate_ids(ids: Sequence[str], where: str) -> None:
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    if duplicates:
        raise ContractSchemaError(f"{where}: duplicate id(s) {', '.join(duplicates)}")


# -- loading and resolution ----------------------------------------------------


@lru_cache(maxsize=None)
def load_profile(profile_id: str, construct: str = CONSTRUCT_DIR) -> ModelProfile:
    """Load, validate and cache one packaged profile by id."""
    profile = parse_profile(tomllib.loads(profile_text(profile_id, construct)))
    if profile.id != profile_id:
        raise ContractSchemaError(
            f"profile {profile_id!r}: declares id {profile.id!r}; the directory "
            f"name and the declared id must agree so resolution is unambiguous"
        )
    return profile


def find_services_toml(start: Path | None = None) -> Path | None:
    """Locate the repository ``SERVICES.toml`` by walking up from ``start``.

    Returns ``None`` when it cannot be found, which is the normal case for an
    installed wheel. Service-based resolution then fails closed rather than
    guessing an identity.
    """
    origin = (start or Path(__file__)).resolve()
    for parent in origin.parents:
        candidate = parent / SERVICES_FILENAME
        if candidate.is_file():
            return candidate
    return None


def service_model_identity(
    service_name: str, *, services_path: Path | None = None
) -> str:
    """Return the model identity a service slot in ``SERVICES.toml`` serves."""
    path = services_path or find_services_toml()
    if path is None:
        raise ProfileNotFoundError(
            f"{PROFILE_MISSING_CODE}: cannot resolve service {service_name!r} "
            f"because no {SERVICES_FILENAME} was found; pass an explicit model "
            f"identity or profile id instead"
        )
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    services = data.get("services")
    if not isinstance(services, Mapping) or service_name not in services:
        raise ProfileNotFoundError(
            f"{PROFILE_MISSING_CODE}: {path.name} declares no service {service_name!r}"
        )
    entry = services[service_name]
    if not isinstance(entry, Mapping):
        raise ProfileNotFoundError(
            f"{PROFILE_MISSING_CODE}: service {service_name!r} is malformed"
        )
    model = entry.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ProfileNotFoundError(
            f"{PROFILE_MISSING_CODE}: service {service_name!r} declares no model"
        )
    return model.strip()


def resolve_profile(
    *,
    profile_id: str | None = None,
    model: str | None = None,
    service: str | None = None,
    services_path: Path | None = None,
    construct: str = CONSTRUCT_DIR,
) -> ModelProfile:
    """Resolve exactly one profile by id, by model identity, or by service.

    Exactly one selector must be given. An unmatched selector raises
    :class:`ProfileNotFoundError`; a selector matched by two profiles raises
    :class:`ProfileAmbiguousError`. There is no default and no fallback.
    """
    selectors = [value for value in (profile_id, model, service) if value]
    if len(selectors) != 1:
        raise ProfileError(
            "resolve_profile takes exactly one of profile_id, model or service"
        )
    if profile_id:
        return load_profile(profile_id, construct)
    identity = model or service_model_identity(
        service or "", services_path=services_path
    )
    wanted = normalize_identity(identity)
    matches: list[ModelProfile] = []
    for candidate_id in available_profiles(construct):
        candidate = load_profile(candidate_id, construct)
        known = {normalize_identity(value) for value in candidate.model_ids}
        known.update(normalize_identity(value) for value in candidate.aliases)
        if wanted in known:
            matches.append(candidate)
    if not matches:
        raise ProfileNotFoundError(
            f"{PROFILE_MISSING_CODE}: no profile claims model identity "
            f"{identity!r} (available: {', '.join(available_profiles(construct)) or 'none'})"
        )
    if len(matches) > 1:
        claimants = ", ".join(sorted(match.id for match in matches))
        raise ProfileAmbiguousError(
            f"model identity {identity!r} is claimed by more than one profile "
            f"({claimants}); resolution must be unambiguous"
        )
    return matches[0]


# -- combined loading ----------------------------------------------------------


@lru_cache(maxsize=None)
def load_combined(profile_id: str, construct: str = CONSTRUCT_DIR) -> ResolvedContract:
    """Load contract and profile from a single ``rules.toml`` and return the
    resolved contract. No overlay or merge step; values are baked in.
    """
    data = tomllib.loads(profile_text(profile_id, construct))
    contract = parse_contract(data)
    profile = parse_profile(data)
    if profile.id != profile_id:
        raise ContractSchemaError(
            f"profile {profile_id!r}: declares id {profile.id!r}; the directory "
            f"name and the declared id must agree so resolution is unambiguous"
        )
    return ResolvedContract(
        core=contract,
        profile=profile,
        rules=contract.rules,
        thresholds=contract.thresholds,
    )


def resolve_contract(
    *,
    profile_id: str | None = None,
    model: str | None = None,
    service: str | None = None,
    services_path: Path | None = None,
    core: TableContract | None = None,
    construct: str = CONSTRUCT_DIR,
) -> ResolvedContract:
    """Resolve the contract for a model profile.

    With no selector the default profile (``deepseek-v4``) is loaded. An
    unknown model fails closed via :class:`ProfileNotFoundError`.
    """
    if not any((profile_id, model, service)):
        return load_combined(DEFAULT_PROFILE_ID, construct)
    profile = resolve_profile(
        profile_id=profile_id,
        model=model,
        service=service,
        services_path=services_path,
        construct=construct,
    )
    return load_combined(profile.id, construct)


def resolved_core_only(construct: str = CONSTRUCT_DIR) -> ResolvedContract:
    """Return the default profile's full resolved contract.

    The name is historical: there is no core-only state after the merge of
    contract and profile into a single ``rules.toml``. The function loads
    the default profile (``deepseek-v4``) and returns the resolved contract
    with the profile attached.
    """
    return load_combined(DEFAULT_PROFILE_ID, construct=construct)
