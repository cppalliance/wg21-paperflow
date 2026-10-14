#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Loader, validator and renderer for the table-readability contract.

Each model profile ships a single ``rules.toml`` that contains the full
contract (R1-R13, applicability predicates, named thresholds) and the model
profile (identity, certification, weaknesses, probes) with model-specific
values baked directly into the rule and threshold definitions. This module
loads it as a package resource with ``importlib.resources`` (so it works from a
source tree and from a built wheel), validates it fail-closed, and renders both
the human listing and the LLM rubric from the same data. Nothing here restates
a rule: a second copy of a rule can only drift from the first.

Validation is fail-closed by design. An unknown strength, scope, method,
applicability condition or threshold kind, a duplicate or missing rule id, a
missing LLM instruction, a rule whose failure status contradicts its strength,
or a threshold nobody declared, all raise instead of loading a contract that
would quietly under-check.

Hashes are computed over the canonically serialized parsed data, not over the
file bytes, so a line-ending or comment change does not move the hash while any
change to a normative value does.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from collections.abc import Mapping, Sequence
from functools import lru_cache
from importlib import resources
from types import MappingProxyType

from whisker.det.llm_readability.models import (
    METHODS,
    NUMERIC_TIGHTEN_DIRECTIONS,
    SCOPES,
    STATUS_FAIL,
    STATUS_REVIEW,
    STATUSES_VIOLATION,
    STRENGTH_HARD,
    STRENGTHS,
    THRESHOLD_KIND_NUMERIC,
    THRESHOLD_KINDS,
    TOKEN_SET_TIGHTEN_DIRECTIONS,
    ModelProfile,
    ResolvedContract,
    Rule,
    TableContract,
    Threshold,
)

__all__ = [
    "COMBINED_TOP_KEYS",
    "CONSTRUCT_CODEBLOCKS",
    "CONSTRUCT_DIR",
    "CONSTRUCT_TABLES",
    "CONTRACT_PACKAGE",
    "ContractError",
    "ContractSchemaError",
    "DEFAULT_PROFILE_ID",
    "EXPECTED_CODE_RULE_COUNT",
    "EXPECTED_RULE_COUNT",
    "RULES_RESOURCE_NAME",
    "SUPPORTED_SCHEMA_VERSION",
    "canonical_hash",
    "contract_to_dict",
    "core_contract_text",
    "load_core_contract",
    "parse_contract",
    "render_llm_rubric",
    "render_rules_markdown",
]

CONTRACT_PACKAGE = "whisker.det.llm_readability"
DEFAULT_PROFILE_ID = "deepseek-v4"
CONSTRUCT_TABLES = "tables"
CONSTRUCT_CODEBLOCKS = "codeblocks"
CONSTRUCT_DIR = CONSTRUCT_TABLES
RULES_RESOURCE_NAME = "rules.toml"

# Top-level TOML keys accepted in a combined rules.toml (contract + profile).
COMBINED_TOP_KEYS = (
    "contract",
    "applicability",
    "thresholds",
    "rules",
    "profile",
    "model_identity",
    "certification",
    "known_weaknesses",
    "probes",
    "evidence",
)

# Only one contract schema exists so far. A future schema bump must be an
# explicit code change, never a silently accepted unknown integer.
SUPPORTED_SCHEMA_VERSION = 1

# The number of rule ids each construct contract is expected to carry. Named so
# a dropped or duplicated rule is a test failure with a number in it, not a
# silent shrink.
EXPECTED_RULE_COUNT = 13
EXPECTED_CODE_RULE_COUNT = 10


class ContractError(Exception):
    """Base class for every table-readability contract failure."""


class ContractSchemaError(ContractError):
    """The contract or profile data violated the schema; nothing was loaded."""


def canonical_hash(payload: object) -> str:
    """Return the SHA-256 of a canonical JSON serialization of ``payload``.

    Hashed over the parsed data, never over the file bytes, and with newlines in
    every string normalized. A contract checked out with CRLF endings, or with a
    comment added, must produce the same hash as one checked out with LF, or a
    profile pin and a report fingerprint would mean something different per
    platform. Any change to a normative value still moves the hash.
    """
    blob = json.dumps(
        _canonical(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=_json_default,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _canonical(value: object) -> object:
    """Convert parsed TOML data into newline-normalized JSON-able containers."""
    if isinstance(value, str):
        return value.replace("\r\n", "\n").replace("\r", "\n")
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, bytes):
        return [_canonical(item) for item in value]
    return value


def _json_default(value: object) -> object:
    raise ContractSchemaError(
        f"contract data carries a non-serializable value of type "
        f"{type(value).__name__!r}; contract data must be plain TOML scalars, "
        f"arrays and tables"
    )


# -- schema helpers ------------------------------------------------------------


def _table(data: Mapping[str, object], key: str, where: str) -> Mapping[str, object]:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise ContractSchemaError(f"{where}: missing or non-table {key!r}")
    return value


def _text(data: Mapping[str, object], key: str, where: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContractSchemaError(f"{where}: missing or empty string {key!r}")
    return value.strip()


def _integer(data: Mapping[str, object], key: str, where: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ContractSchemaError(f"{where}: missing or non-integer {key!r}")
    return value


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


def _enum(value: str, allowed: Sequence[str], key: str, where: str) -> str:
    if value not in allowed:
        raise ContractSchemaError(
            f"{where}: unknown {key} {value!r} (allowed: {', '.join(allowed)})"
        )
    return value


def _no_unknown_keys(
    data: Mapping[str, object], allowed: Sequence[str], where: str
) -> None:
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        raise ContractSchemaError(f"{where}: unknown key(s) {', '.join(unknown)}")


# -- threshold parsing ---------------------------------------------------------

_THRESHOLD_KEYS = (
    "kind",
    "value",
    "values",
    "unit",
    "tighten",
    "rationale",
    "rules",
)


def _parse_threshold(name: str, data: Mapping[str, object]) -> Threshold:
    where = f"threshold {name!r}"
    _no_unknown_keys(data, _THRESHOLD_KEYS, where)
    kind = _enum(_text(data, "kind", where), THRESHOLD_KINDS, "kind", where)
    tighten = _text(data, "tighten", where)
    value: int | float | None = None
    values: tuple[str, ...] | None = None
    if kind == THRESHOLD_KIND_NUMERIC:
        _enum(tighten, NUMERIC_TIGHTEN_DIRECTIONS, "tighten", where)
        raw = data.get("value")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ContractSchemaError(f"{where}: numeric threshold needs a number")
        if "values" in data:
            raise ContractSchemaError(f"{where}: numeric threshold must not set values")
        value = raw
    else:
        _enum(tighten, TOKEN_SET_TIGHTEN_DIRECTIONS, "tighten", where)
        if "value" in data:
            raise ContractSchemaError(
                f"{where}: token_set threshold must not set value"
            )
        values = _string_tuple(data, "values", where)
    return Threshold(
        name=name,
        kind=kind,
        tighten=tighten,
        unit=_text(data, "unit", where),
        rationale=_text(data, "rationale", where),
        rules=_string_tuple(data, "rules", where),
        value=value,
        values=values,
    )


# -- rule parsing --------------------------------------------------------------

_RULE_KEYS = (
    "id",
    "title",
    "strength",
    "scope",
    "method",
    "applicability",
    "check_id",
    "failure_status",
    "thresholds",
    "requirement",
    "rationale",
    "llm_instruction",
    "evidence",
)


def _parse_rule(
    data: Mapping[str, object],
    *,
    position: int,
    applicability_keys: Sequence[str],
    threshold_names: Sequence[str],
) -> Rule:
    where = f"rule #{position + 1}"
    _no_unknown_keys(data, _RULE_KEYS, where)
    rule_id = _text(data, "id", where)
    where = f"rule {rule_id!r}"
    strength = _enum(_text(data, "strength", where), STRENGTHS, "strength", where)
    failure_status = _enum(
        _text(data, "failure_status", where),
        STATUSES_VIOLATION,
        "failure_status",
        where,
    )
    # A HARD rule that only reviews on violation is not hard, and a CONTEXTUAL
    # rule that hard-fails is not contextual. Either shape is a contradictory
    # verdict and is rejected rather than reconciled.
    expected_status = STATUS_FAIL if strength == STRENGTH_HARD else STATUS_REVIEW
    if failure_status != expected_status:
        raise ContractSchemaError(
            f"{where}: strength {strength} requires failure_status "
            f"{expected_status!r}, found {failure_status!r}"
        )
    applicability = _text(data, "applicability", where)
    if applicability not in applicability_keys:
        raise ContractSchemaError(
            f"{where}: applicability {applicability!r} is not declared in "
            f"[applicability]"
        )
    thresholds = _string_tuple(data, "thresholds", where, required=False)
    for threshold_name in thresholds:
        if threshold_name not in threshold_names:
            raise ContractSchemaError(
                f"{where}: references undeclared threshold {threshold_name!r}"
            )
    return Rule(
        id=rule_id,
        title=_text(data, "title", where),
        strength=strength,
        scope=_enum(_text(data, "scope", where), SCOPES, "scope", where),
        method=_enum(_text(data, "method", where), METHODS, "method", where),
        applicability=applicability,
        check_id=_text(data, "check_id", where),
        failure_status=failure_status,
        requirement=_text(data, "requirement", where),
        rationale=_text(data, "rationale", where),
        llm_instruction=_text(data, "llm_instruction", where),
        evidence=_string_tuple(data, "evidence", where),
        thresholds=thresholds,
    )


# -- contract parsing ----------------------------------------------------------

_CONTRACT_META_KEYS = ("id", "version", "schema_version", "title", "authority")


def parse_contract(data: Mapping[str, object]) -> TableContract:
    """Validate and build a :class:`TableContract` from parsed TOML data.

    Accepts a combined ``rules.toml`` that also carries profile keys; those
    are silently ignored here and consumed by ``parse_profile`` in
    ``profile.py``.

    Raises :class:`ContractSchemaError` on any schema violation. Nothing
    partially loaded is ever returned.
    """
    _no_unknown_keys(data, COMBINED_TOP_KEYS, "rules.toml")
    meta = _table(data, "contract", "core")
    _no_unknown_keys(meta, _CONTRACT_META_KEYS, "[contract]")
    schema_version = _integer(meta, "schema_version", "[contract]")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ContractSchemaError(
            f"[contract]: schema_version {schema_version} is not supported "
            f"(this build understands {SUPPORTED_SCHEMA_VERSION})"
        )

    applicability_data = _table(data, "applicability", "core")
    applicability: dict[str, str] = {}
    for key in sorted(applicability_data):
        entry = applicability_data[key]
        if not isinstance(entry, Mapping):
            raise ContractSchemaError(f"[applicability.{key}]: must be a table")
        _no_unknown_keys(entry, ("description",), f"[applicability.{key}]")
        applicability[key] = _text(entry, "description", f"[applicability.{key}]")
    if not applicability:
        raise ContractSchemaError("core: [applicability] must declare at least one key")

    thresholds_data = _table(data, "thresholds", "core")
    thresholds: dict[str, Threshold] = {}
    for name in sorted(thresholds_data):
        entry = thresholds_data[name]
        if not isinstance(entry, Mapping):
            raise ContractSchemaError(f"[thresholds.{name}]: must be a table")
        thresholds[name] = _parse_threshold(name, entry)

    rules_data = data.get("rules")
    if not isinstance(rules_data, Sequence) or isinstance(rules_data, str):
        raise ContractSchemaError("core: [[rules]] must be an array of tables")
    rules: list[Rule] = []
    for position, entry in enumerate(rules_data):
        if not isinstance(entry, Mapping):
            raise ContractSchemaError(f"rule #{position + 1}: must be a table")
        rules.append(
            _parse_rule(
                entry,
                position=position,
                applicability_keys=tuple(applicability),
                threshold_names=tuple(thresholds),
            )
        )
    if not rules:
        raise ContractSchemaError("core: [[rules]] must not be empty")

    rule_ids = [rule.id for rule in rules]
    duplicates = sorted({rid for rid in rule_ids if rule_ids.count(rid) > 1})
    if duplicates:
        raise ContractSchemaError(f"core: duplicate rule id(s) {', '.join(duplicates)}")
    check_ids = [rule.check_id for rule in rules]
    duplicate_checks = sorted({cid for cid in check_ids if check_ids.count(cid) > 1})
    if duplicate_checks:
        raise ContractSchemaError(
            f"core: duplicate check_id(s) {', '.join(duplicate_checks)}"
        )
    for name, threshold in thresholds.items():
        unknown_rules = sorted(set(threshold.rules) - set(rule_ids))
        if unknown_rules:
            raise ContractSchemaError(
                f"threshold {name!r}: names unknown rule(s) {', '.join(unknown_rules)}"
            )

    return TableContract(
        id=_text(meta, "id", "[contract]"),
        version=_text(meta, "version", "[contract]"),
        schema_version=schema_version,
        title=_text(meta, "title", "[contract]"),
        authority=_text(meta, "authority", "[contract]"),
        rules=tuple(rules),
        thresholds=MappingProxyType(thresholds),
        applicability=MappingProxyType(applicability),
        hash=canonical_hash(data),
    )


def core_contract_text(construct: str = CONSTRUCT_DIR) -> str:
    """Return the raw ``rules.toml`` of the default profile as text."""
    resource = (
        resources.files(CONTRACT_PACKAGE)
        / DEFAULT_PROFILE_ID
        / construct
        / RULES_RESOURCE_NAME
    )
    return resource.read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def load_core_contract(construct: str = CONSTRUCT_DIR) -> TableContract:
    """Load, validate and cache the contract from the default profile."""
    return parse_contract(tomllib.loads(core_contract_text(construct)))


# -- rendering -----------------------------------------------------------------
#
# Both renderers below are pure functions of the resolved contract: same input,
# same bytes, no clock, no environment, no dict-iteration order. That is what
# lets a prompt hash be a meaningful fingerprint.


def _threshold_lines(rule: Rule, resolved: ResolvedContract) -> list[str]:
    lines: list[str] = []
    for name in rule.thresholds:
        threshold = resolved.thresholds[name]
        lines.append(
            f"- threshold {name} = {threshold.rendered_value()} ({threshold.unit})"
        )
    return lines


def render_llm_rubric(resolved: ResolvedContract) -> str:
    """Render the contract as a compact rubric for an LLM judge.

    This is trusted system material. It carries no paper content and must be
    placed outside the untrusted-source delimiters by the calling lane.
    """
    core = resolved.core
    out: list[str] = []
    out.append(f"# {core.title}")
    out.append("")
    out.append(f"contract: {core.id} v{core.version} sha256:{core.hash}")
    if resolved.profile is not None:
        profile = resolved.profile
        out.append(
            f"model profile: {profile.id} v{profile.version} "
            f"sha256:{profile.hash} (model {profile.model_identity})"
        )
    else:
        out.append("model profile: none (universal rules only)")
    out.append("")
    out.append(
        "Judge the converted table representation against every rule below. "
        "Name the R-ids you relied on. A rule you could not evaluate is "
        "unevaluated, never passed."
    )
    for rule in resolved.rules:
        out.append("")
        out.append(f"## {rule.id} [{rule.strength}] {rule.title}")
        out.append(f"- scope: {rule.scope}")
        out.append(f"- proven by: {rule.method}")
        out.append(f"- applies when: {core.applicability[rule.applicability]}")
        out.append(f"- on violation: {rule.failure_status}")
        out.extend(_threshold_lines(rule, resolved))
        out.append(f"- requirement: {_flatten(rule.requirement)}")
        out.append(f"- instruction: {_flatten(rule.llm_instruction)}")
        for extra in rule.profile_requirements:
            out.append(f"- profile requirement: {_flatten(extra)}")
        for extra in rule.profile_instructions:
            out.append(f"- profile instruction: {_flatten(extra)}")
    if resolved.profile is not None:
        out.extend(_profile_rubric_tail(resolved.profile))
    out.append("")
    return "\n".join(out)


def _profile_rubric_tail(profile: ModelProfile) -> list[str]:
    out: list[str] = ["", f"## Model profile: {profile.display_name}"]
    out.append(f"- certification status: {profile.certification_status}")
    for weakness in profile.known_weaknesses:
        out.append(
            f"- known weakness {weakness.id} "
            f"({', '.join(weakness.rules)}): {_flatten(weakness.description)}"
        )
    for probe in profile.probes:
        out.append(
            f"- required probe {probe.id} "
            f"({', '.join(probe.rules)}): {_flatten(probe.description)}"
        )
    return out


def render_rules_markdown(resolved: ResolvedContract) -> str:
    """Render the contract as a human listing for the CLI."""
    core = resolved.core
    out: list[str] = [f"# {core.title}", ""]
    out.append(f"- contract: {core.id} v{core.version}")
    out.append(f"- contract hash: sha256:{core.hash}")
    if resolved.profile is not None:
        profile = resolved.profile
        out.append(f"- model profile: {profile.id} v{profile.version}")
        out.append(f"- profile hash: sha256:{profile.hash}")
        out.append(f"- model identity: {profile.model_identity}")
        out.append(f"- certification status: {profile.certification_status}")
    else:
        out.append("- model profile: none (universal rules only)")
    out.append("")
    out.append("| Rule | Strength | Scope | Proven by | On violation | Title |")
    out.append("|---|---|---|---|---|---|")
    for rule in resolved.rules:
        out.append(
            f"| {rule.id} | {rule.strength} | {rule.scope} | {rule.method} "
            f"| {rule.failure_status} | {rule.title} |"
        )
    out.append("")
    out.append("## Thresholds")
    out.append("")
    out.append("| Threshold | Value | Unit | Stricter when | Rules |")
    out.append("|---|---|---|---|---|")
    for name in sorted(resolved.thresholds):
        threshold = resolved.thresholds[name]
        out.append(
            f"| {name} | {threshold.rendered_value()} | {threshold.unit} "
            f"| {threshold.tighten} | {', '.join(threshold.rules)} |"
        )
    out.append("")
    return "\n".join(out)


def contract_to_dict(resolved: ResolvedContract) -> dict[str, object]:
    """Return a JSON-able, stably ordered view of the resolved contract.

    The profile's certification gate travels with the rules it gates. A consumer
    reading only the merged rules would otherwise see tightened thresholds and a
    promoted strength while the demands that make certification reachable, the
    lanes that must run and the rules that must carry a real status, stayed
    invisible.

    Every profile key is always present. On a core-only contract they are ``None``
    and the required lists are empty, and ``profile_id`` being ``None`` is the
    authoritative signal that nothing here can be model certified. Service slots,
    backends and anything else from ``SERVICES.toml`` are deliberately not
    serialized: this is the contract, not the infrastructure.

    ``required_methods`` and ``required_rules`` keep the order the profile
    declares them in, never a sorted order, so a diff of two runs reflects an
    authoring change rather than a serializer's opinion.
    """
    core = resolved.core
    profile = resolved.profile
    payload: dict[str, object] = {
        "contract_id": core.id,
        "contract_version": core.version,
        "contract_hash": core.hash,
        "schema_version": core.schema_version,
        "title": core.title,
        "profile_id": resolved.profile_id,
        "profile_version": resolved.profile_version,
        "profile_hash": resolved.profile_hash,
        "profile_certification_status": (
            profile.certification_status if profile is not None else None
        ),
        "model_identity": resolved.model_identity,
        "required_methods": (
            list(profile.required_methods) if profile is not None else []
        ),
        "required_rules": list(profile.required_rules) if profile is not None else [],
        "applicability": {
            key: core.applicability[key] for key in sorted(core.applicability)
        },
        "thresholds": [
            {
                "name": name,
                "kind": resolved.thresholds[name].kind,
                "value": resolved.thresholds[name].value,
                "values": list(resolved.thresholds[name].values or ()),
                "unit": resolved.thresholds[name].unit,
                "tighten": resolved.thresholds[name].tighten,
                "rules": list(resolved.thresholds[name].rules),
            }
            for name in sorted(resolved.thresholds)
        ],
        "rules": [
            {
                "id": rule.id,
                "title": rule.title,
                "strength": rule.strength,
                "scope": rule.scope,
                "method": rule.method,
                "applicability": rule.applicability,
                "check_id": rule.check_id,
                "failure_status": rule.failure_status,
                "thresholds": list(rule.thresholds),
                "requirement": _flatten(rule.requirement),
                "rationale": _flatten(rule.rationale),
                "llm_instruction": _flatten(rule.llm_instruction),
                "evidence": list(rule.evidence),
                "profile_requirements": list(rule.profile_requirements),
                "profile_instructions": list(rule.profile_instructions),
            }
            for rule in resolved.rules
        ],
    }
    return payload


def _flatten(text: str) -> str:
    """Collapse a TOML multi-line string into one whitespace-normalized line."""
    return " ".join(text.split())
