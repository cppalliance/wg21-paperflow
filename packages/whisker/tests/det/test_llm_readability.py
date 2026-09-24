#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Foundation tests for the whisker LLM-readability contract.

These tests guard the properties that make the contract worth having, not the
prose it happens to contain:

- the rule set is exactly R1-R14, uniquely identified and uniquely checked;
- a malformed contract loads nothing at all rather than under-checking;
- contract and profile hashes are stable across loads and move only when a
  normative value moves;
- the DeepSeek profile resolves by id, by model identity, by vendor alias and by
  the service slots `SERVICES.toml` actually declares, and an unknown model
  fails closed;
- the DeepSeek-specific values (R13 HARD, tightened thresholds) are baked into
  the single ``rules.toml`` and load correctly;
- nothing can be certified without a profile, without the methods that profile
  demands, or when there is no table at all.

Test data is built here, in the test package. The runtime package ships only the
contract and the profiles.
"""

from __future__ import annotations

import copy
import json
import tomllib
from importlib import resources
from pathlib import Path

import pytest
from whisker.det.llm_readability import (
    STATUS_FAIL,
    STATUS_NOT_APPLICABLE,
    STATUS_NOT_EVALUATED,
    STATUS_PASS,
    STATUS_REVIEW,
    STRENGTH_CONTEXTUAL,
    STRENGTH_HARD,
    VERDICT_FAIL,
    VERDICT_INCOMPLETE,
    VERDICT_NOT_APPLICABLE,
    CheckOutcome,
    ContractSchemaError,
    ProfileError,
    ProfileNotFoundError,
    TableUnit,
)
from whisker.det.llm_readability import cli as table_cli
from whisker.det.llm_readability.contract import (
    CONTRACT_PACKAGE,
    DEFAULT_PROFILE_ID,
    RULES_RESOURCE_NAME,
    canonical_hash,
    contract_to_dict,
    core_contract_text,
    load_core_contract,
    parse_contract,
    render_llm_rubric,
    render_rules_markdown,
)
from whisker.det.llm_readability.models import (
    CERTIFICATION_STATUS_PENDING,
    METHOD_CERTIFICATION,
    METHOD_DETERMINISTIC,
    METHOD_LLM,
    METHOD_SOURCE_COMPARE,
)
from whisker.det.llm_readability.profile import (
    available_profiles,
    load_combined,
    load_profile,
    normalize_identity,
    parse_profile,
    profile_text,
    resolve_contract,
    resolve_profile,
    resolved_core_only,
    service_model_identity,
)
from whisker.det.llm_readability.report import (
    render_markdown,
    report_to_dict,
    status_counts,
)
from whisker.det.llm_readability.validate import (
    APPLICABILITY_PREDICATES,
    DETERMINISTIC_CHECKS,
    default_registry,
    evaluate,
    table_units_from_markdown,
)

DEEPSEEK_PROFILE_ID = "deepseek-v4"
DEEPSEEK_MODEL_IDENTITY = "deepseek-v4-pro"
ALL_METHODS = (
    METHOD_DETERMINISTIC,
    METHOD_SOURCE_COMPARE,
    METHOD_LLM,
    METHOD_CERTIFICATION,
)


# -- fixtures and helpers ------------------------------------------------------


@pytest.fixture(scope="module")
def core():
    return load_core_contract()


@pytest.fixture
def core_data() -> dict:
    """A mutable copy of the parsed core contract data, for schema tests."""
    return copy.deepcopy(tomllib.loads(core_contract_text()))


@pytest.fixture
def profile_data() -> dict:
    """A mutable copy of the parsed DeepSeek profile data."""
    return copy.deepcopy(tomllib.loads(profile_text(DEEPSEEK_PROFILE_ID)))


def _rule_entry(data: dict, rule_id: str) -> dict:
    for entry in data["rules"]:
        if entry["id"] == rule_id:
            return entry
    raise AssertionError(f"no rule {rule_id} in the contract data")


def repo_services_toml() -> Path:
    """Locate the repository ``SERVICES.toml`` from this test file.

    Deliberately not `find_services_toml()`: that walks up from the installed
    package, so this test would silently start proving nothing under a
    non-editable install.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "SERVICES.toml"
        if candidate.is_file():
            return candidate
    raise AssertionError("could not find SERVICES.toml by walking up from the tests")


def repo_root() -> Path:
    return repo_services_toml().parent


def _assert_citation_resolves(citation: str, *, where: str) -> None:
    """Assert a repo-relative evidence citation still names a real file.

    Entries with no path separator are shorthand for a research source
    abbreviation (``gist:41-82``) and carry no path to check. A trailing
    ``:<line>`` or ``:<start>-<end>`` locator is stripped; a trailing ``:R7`` rule
    locator is too.
    """
    if "/" not in citation:
        return
    path_part = citation.split(":", 1)[0]
    assert (repo_root() / path_part).is_file(), (
        f"{where}: cited evidence {citation!r} no longer exists"
    )


def clean_units(*, columns: int = 3, rows: int = 4) -> tuple[TableUnit, ...]:
    """One fully-specified, contract-clean pipe table.

    Every field a deterministic check needs is supplied, which is what a
    span-aware supplier will hand in. A lane that leaves a field at ``None``
    gets ``not_evaluated``, which is tested separately.
    """
    header = tuple(f"col{index + 1}" for index in range(columns))
    body = tuple(
        tuple(f"r{row + 1}c{column + 1}" for column in range(columns))
        for row in range(rows - 1)
    )
    cells = (header,) + body
    raw_rows = tuple("| " + " | ".join(row) + " |" for row in cells)
    return (
        TableUnit(
            index=0,
            fmt="pipe",
            cells=cells,
            raw_rows=raw_rows,
            has_header=True,
            has_separator=True,
            spans_declared=False,
            caption_distance_lines=1,
        ),
    )


# -- packaging -----------------------------------------------------------------


class TestPackagedResources:
    def test_rules_toml_loads_as_a_package_resource(self):
        resource = (
            resources.files(CONTRACT_PACKAGE) / DEFAULT_PROFILE_ID / "tables" / RULES_RESOURCE_NAME
        )
        assert resource.is_file()
        text = resource.read_text(encoding="utf-8")
        assert "[contract]" in text
        assert "[profile]" in text

    def test_profile_directory_is_a_package_resource(self):
        root = resources.files(CONTRACT_PACKAGE)
        assert (root / DEEPSEEK_PROFILE_ID).is_dir()
        assert (root / DEEPSEEK_PROFILE_ID / "tables" / "rules.toml").is_file()

    def test_readmes_ship_next_to_the_contract(self):
        root = resources.files(CONTRACT_PACKAGE)
        assert (root / "README.md").is_file()
        assert (root / DEEPSEEK_PROFILE_ID / "README.md").is_file()

    def test_wheel_ships_the_package_that_carries_the_contract_data(self):
        """A wheel without rules.toml cannot load the contract at all.

        The data ships because the whole ``src/whisker`` tree is a wheel package.
        Force-including it a second time fails the wheel build outright, so this
        also guards against re-adding those entries.
        """
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        wheel = tomllib.loads(pyproject.read_text(encoding="utf-8"))["tool"]["hatch"][
            "build"
        ]["targets"]["wheel"]
        assert "src/whisker" in wheel["packages"]
        duplicated = [
            key for key in wheel.get("force-include", {}) if "llm_readability" in key
        ]
        assert not duplicated, f"force-include duplicates package data: {duplicated}"


# -- the rule set --------------------------------------------------------------


class TestRuleSet:
    def test_rules_are_exactly_r1_through_r14_in_order(self, core):
        assert core.rule_ids == tuple(f"R{number}" for number in range(1, 15))
        assert len(core.rules) == 14

    def test_rule_ids_are_unique(self, core):
        assert len(set(core.rule_ids)) == len(core.rule_ids)

    def test_check_ids_are_unique(self, core):
        check_ids = [rule.check_id for rule in core.rules]
        assert len(set(check_ids)) == len(check_ids)

    def test_every_rule_carries_prose_instruction_and_evidence(self, core):
        for rule in core.rules:
            assert rule.requirement.strip()
            assert rule.rationale.strip()
            assert rule.llm_instruction.strip()
            assert rule.evidence, f"{rule.id} cites no evidence"

    def test_hard_rules_fail_and_contextual_rules_review(self, core):
        for rule in core.rules:
            expected = STATUS_FAIL if rule.strength == STRENGTH_HARD else STATUS_REVIEW
            assert rule.failure_status == expected, rule.id

    def test_both_strengths_are_actually_used(self, core):
        strengths = {rule.strength for rule in core.rules}
        assert strengths == {STRENGTH_HARD, STRENGTH_CONTEXTUAL}

    def test_every_declared_applicability_has_a_predicate(self, core):
        """An unimplemented condition would make a rule permanently unfirable."""
        assert set(core.applicability) == set(APPLICABILITY_PREDICATES)

    def test_every_threshold_is_consumed_by_a_declared_rule(self, core):
        rules_by_id = {rule.id: rule for rule in core.rules}
        for name, threshold in core.thresholds.items():
            assert threshold.rules, f"threshold {name} is consumed by nothing"
            for rule_id in threshold.rules:
                assert rule_id in rules_by_id
                assert name in rules_by_id[rule_id].thresholds

    def test_rule_threshold_references_resolve(self, core):
        for rule in core.rules:
            for name in rule.thresholds:
                assert name in core.thresholds

    def test_r1_keeps_its_researched_semantics(self, core):
        """R1 is the epistemic premise, not merely a row-width check.

        The researched R1 says a reading model has no table AST, so a pipe table
        is a 1D token stream whose delimiters are the coordinates. Cell-count
        agreement is the enforceable consequence, not the rule. A rewrite that
        keeps only the consequence silently narrows the contract, which is
        exactly the drift this asserts against.
        """
        rule = core.rule("R1")
        premise = f"{rule.title} {rule.requirement}".casefold()
        assert "token stream" in premise
        assert "coordinate" in premise
        assert "table ast" in rule.requirement.casefold()
        assert "fewer cells" in rule.requirement.casefold(), (
            "R1 must still state the deterministic cell-count consequence"
        )

    def test_every_rule_points_at_its_researched_source(self, core):
        """No rule may be locally invented, and none may drift from its source."""
        for rule in core.rules:
            pointer = f"00-baseline.md:{rule.id}"
            assert any(pointer in item for item in rule.evidence), (
                f"{rule.id} cites no researched source ({pointer})"
            )

    def test_cited_evidence_files_exist(self, core):
        """A dead citation is not provenance."""
        for rule in core.rules:
            for item in rule.evidence:
                _assert_citation_resolves(item, where=rule.id)

    def test_registered_checks_belong_to_a_declared_rule(self, core):
        declared = {rule.check_id for rule in core.rules}
        orphans = sorted(set(DETERMINISTIC_CHECKS) - declared)
        assert not orphans, f"checks registered for no rule: {orphans}"

    def test_deterministic_checks_cover_the_candidate_side_rules(self, core):
        """Every check the contract expects from candidate markdown alone.

        R12 is deterministic but needs chunk boundaries a candidate file does not
        carry, so it is legitimately unregistered here and stays
        `not_evaluated` until a chunking lane registers it.
        """
        expected = {
            rule.check_id
            for rule in core.rules
            if rule.method == METHOD_DETERMINISTIC and rule.id != "R12"
        }
        assert expected <= set(DETERMINISTIC_CHECKS)


# -- fail-closed schema --------------------------------------------------------


class TestSchemaFailsClosed:
    def test_unknown_top_level_key_rejected(self, core_data):
        core_data["prompt"] = {"text": "a second normative copy"}
        with pytest.raises(ContractSchemaError):
            parse_contract(core_data)

    def test_unknown_rule_key_rejected(self, core_data):
        _rule_entry(core_data, "R1")["severity"] = "high"
        with pytest.raises(ContractSchemaError):
            parse_contract(core_data)

    def test_duplicate_rule_id_rejected(self, core_data):
        core_data["rules"].append(copy.deepcopy(_rule_entry(core_data, "R1")))
        with pytest.raises(ContractSchemaError, match="duplicate rule id"):
            parse_contract(core_data)

    def test_duplicate_check_id_rejected(self, core_data):
        _rule_entry(core_data, "R2")["check_id"] = _rule_entry(core_data, "R1")[
            "check_id"
        ]
        with pytest.raises(ContractSchemaError, match="duplicate check_id"):
            parse_contract(core_data)

    def test_hard_rule_that_only_reviews_rejected(self, core_data):
        _rule_entry(core_data, "R1")["failure_status"] = "review"
        with pytest.raises(ContractSchemaError, match="failure_status"):
            parse_contract(core_data)

    def test_contextual_rule_that_hard_fails_rejected(self, core_data):
        _rule_entry(core_data, "R7")["failure_status"] = "not-llm-readable"
        with pytest.raises(ContractSchemaError, match="failure_status"):
            parse_contract(core_data)

    def test_unknown_strength_rejected(self, core_data):
        _rule_entry(core_data, "R1")["strength"] = "MANDATORY"
        with pytest.raises(ContractSchemaError, match="strength"):
            parse_contract(core_data)

    def test_unknown_method_rejected(self, core_data):
        _rule_entry(core_data, "R1")["method"] = "vibes"
        with pytest.raises(ContractSchemaError, match="method"):
            parse_contract(core_data)

    def test_unknown_scope_rejected(self, core_data):
        _rule_entry(core_data, "R1")["scope"] = "everything"
        with pytest.raises(ContractSchemaError, match="scope"):
            parse_contract(core_data)

    def test_undeclared_applicability_rejected(self, core_data):
        _rule_entry(core_data, "R1")["applicability"] = "when_convenient"
        with pytest.raises(ContractSchemaError, match="applicability"):
            parse_contract(core_data)

    def test_undeclared_threshold_reference_rejected(self, core_data):
        _rule_entry(core_data, "R1")["thresholds"] = ["invented_budget"]
        with pytest.raises(ContractSchemaError, match="undeclared threshold"):
            parse_contract(core_data)

    def test_threshold_naming_unknown_rule_rejected(self, core_data):
        core_data["thresholds"]["wide_table_column_threshold"]["rules"] = ["R99"]
        with pytest.raises(ContractSchemaError, match="unknown rule"):
            parse_contract(core_data)

    def test_numeric_threshold_with_set_tightening_rejected(self, core_data):
        core_data["thresholds"]["wide_table_column_threshold"]["tighten"] = "shrink_set"
        with pytest.raises(ContractSchemaError, match="tighten"):
            parse_contract(core_data)

    def test_token_set_threshold_carrying_a_number_rejected(self, core_data):
        core_data["thresholds"]["empty_cell_sentinels"]["value"] = 3
        with pytest.raises(ContractSchemaError, match="must not set value"):
            parse_contract(core_data)

    def test_missing_llm_instruction_rejected(self, core_data):
        _rule_entry(core_data, "R1")["llm_instruction"] = "   "
        with pytest.raises(ContractSchemaError, match="llm_instruction"):
            parse_contract(core_data)

    def test_empty_evidence_rejected(self, core_data):
        _rule_entry(core_data, "R1")["evidence"] = []
        with pytest.raises(ContractSchemaError, match="evidence"):
            parse_contract(core_data)

    def test_future_schema_version_rejected(self, core_data):
        core_data["contract"]["schema_version"] = 2
        with pytest.raises(ContractSchemaError, match="schema_version"):
            parse_contract(core_data)

    def test_empty_rule_array_rejected(self, core_data):
        core_data["rules"] = []
        with pytest.raises(ContractSchemaError, match="must not be empty"):
            parse_contract(core_data)


# -- hashes and rendering ------------------------------------------------------


class TestHashesAndRendering:
    def test_hash_is_stable_across_parses(self, core, core_data):
        assert parse_contract(core_data).hash == core.hash

    def test_hash_ignores_comments_and_line_endings(self, core):
        text = core_contract_text()
        commented = "# a fresh comment\n" + text.replace("\n", "\r\n")
        assert parse_contract(tomllib.loads(commented)).hash == core.hash

    def test_hash_moves_when_a_normative_value_moves(self, core, core_data):
        core_data["thresholds"]["wide_table_column_threshold"]["value"] = 7
        assert parse_contract(core_data).hash != core.hash

    def test_hash_is_a_full_sha256(self, core):
        assert len(core.hash) == 64
        assert core.hash == canonical_hash(tomllib.loads(core_contract_text()))

    def test_rubric_is_byte_stable(self):
        first = render_llm_rubric(resolved_core_only())
        second = render_llm_rubric(resolved_core_only())
        assert first == second

    def test_rubric_names_every_rule_and_pins_the_contract(self, core):
        rubric = render_llm_rubric(resolved_core_only())
        for rule in core.rules:
            assert f"## {rule.id} [{rule.strength}]" in rubric
        assert core.version in rubric
        assert core.hash in rubric
        assert "unevaluated, never passed" in rubric

    def test_rubric_carries_profile_identity_when_resolved(self):
        resolved = resolve_contract(profile_id=DEEPSEEK_PROFILE_ID)
        rubric = render_llm_rubric(resolved)
        assert resolved.profile is not None
        assert resolved.profile.hash in rubric
        assert DEEPSEEK_MODEL_IDENTITY in rubric

    def test_rules_markdown_lists_every_rule(self, core):
        listing = render_rules_markdown(resolved_core_only())
        for rule in core.rules:
            assert f"| {rule.id} |" in listing

    def test_contract_dict_is_json_serializable_and_ordered(self, core):
        payload = contract_to_dict(resolved_core_only())
        assert json.loads(json.dumps(payload))["contract_hash"] == core.hash
        assert [entry["id"] for entry in payload["rules"]] == list(core.rule_ids)


class TestResolvedJsonCarriesItsCertificationGate:
    """The machine-readable contract must not omit what makes it certifiable."""

    def test_profile_json_exposes_the_status_and_what_it_demands(self, profile_data):
        payload = contract_to_dict(resolve_contract(profile_id=DEEPSEEK_PROFILE_ID))
        declared = profile_data["certification"]
        assert payload["profile_id"] == DEEPSEEK_PROFILE_ID
        assert payload["profile_certification_status"] == CERTIFICATION_STATUS_PENDING
        assert payload["required_methods"] == declared["required_methods"]
        assert payload["required_rules"] == declared["required_rules"]
        assert METHOD_CERTIFICATION in payload["required_methods"]

    def test_required_lists_keep_the_declared_order(self, profile_data):
        """Equality with the profile only proves order because it is not sorted."""
        declared = profile_data["certification"]
        assert declared["required_methods"] != sorted(declared["required_methods"])
        assert declared["required_rules"] != sorted(declared["required_rules"])
        payload = contract_to_dict(resolve_contract(profile_id=DEEPSEEK_PROFILE_ID))
        assert payload["required_methods"] == declared["required_methods"]
        assert payload["required_rules"] == declared["required_rules"]

    def test_default_json_carries_the_profile(self):
        payload = contract_to_dict(resolved_core_only())
        assert payload["profile_id"] == DEEPSEEK_PROFILE_ID
        assert payload["profile_version"] is not None
        assert payload["profile_hash"] is not None
        assert payload["model_identity"] == DEEPSEEK_MODEL_IDENTITY

    def test_profile_json_does_not_carry_service_configuration(self):
        profile = load_profile(DEEPSEEK_PROFILE_ID)
        blob = json.dumps(
            contract_to_dict(resolve_contract(profile_id=DEEPSEEK_PROFILE_ID))
        )
        assert profile.services and profile.backend
        for service in profile.services:
            assert service not in blob
        assert profile.backend not in blob


# -- profile resolution --------------------------------------------------------


class TestProfileResolution:
    def test_deepseek_profile_is_packaged(self):
        assert DEEPSEEK_PROFILE_ID in available_profiles()

    def test_resolves_by_profile_id(self):
        profile = resolve_profile(profile_id=DEEPSEEK_PROFILE_ID)
        assert profile.id == DEEPSEEK_PROFILE_ID
        assert profile.model_identity == DEEPSEEK_MODEL_IDENTITY

    def test_resolves_by_model_identity(self):
        assert resolve_profile(model=DEEPSEEK_MODEL_IDENTITY).id == DEEPSEEK_PROFILE_ID

    @pytest.mark.parametrize(
        "alias",
        ["deepseek-ai/DeepSeek-V4-Pro", "DeepSeek-V4-Pro", "DEEPSEEK-V4-PRO"],
    )
    def test_resolves_by_vendor_alias_case_insensitively(self, alias):
        assert resolve_profile(model=alias).id == DEEPSEEK_PROFILE_ID

    def test_profile_claims_the_model_the_repo_services_actually_serve(self):
        """Drift guard: the slots the profile names must still serve its model."""
        services = tomllib.loads(repo_services_toml().read_text(encoding="utf-8"))
        profile = load_profile(DEEPSEEK_PROFILE_ID)
        assert profile.services, "the profile records no service provenance"
        for slot in profile.services:
            assert slot in services["services"], slot
            assert services["services"][slot]["model"] in profile.model_ids

    def test_resolves_by_service_slot(self):
        path = repo_services_toml()
        profile = load_profile(DEEPSEEK_PROFILE_ID)
        for slot in profile.services:
            identity = service_model_identity(slot, services_path=path)
            assert identity in profile.model_ids
            assert resolve_profile(service=slot, services_path=path).id == profile.id

    def test_unknown_model_fails_closed(self):
        with pytest.raises(ProfileNotFoundError, match="profile_missing"):
            resolve_profile(model="gpt-9-turbo")

    def test_unknown_profile_id_fails_closed(self):
        with pytest.raises(ProfileNotFoundError, match="profile_missing"):
            resolve_profile(profile_id="no-such-profile")

    def test_service_serving_an_unprofiled_model_fails_closed(self):
        """The dangerous direction: never inherit whichever profile exists."""
        path = repo_services_toml()
        with pytest.raises(ProfileNotFoundError, match="profile_missing"):
            resolve_profile(service="h200-qwen3-32b", services_path=path)

    def test_unknown_service_fails_closed(self, tmp_path):
        services = tmp_path / "SERVICES.toml"
        services.write_text("[services]\n", encoding="utf-8")
        with pytest.raises(ProfileNotFoundError, match="profile_missing"):
            resolve_profile(service="ghost-pod", services_path=services)

    def test_service_without_a_model_fails_closed(self, tmp_path):
        services = tmp_path / "SERVICES.toml"
        services.write_text(
            '[services.mystery]\nbackend = "vllm_thinking"\n', encoding="utf-8"
        )
        with pytest.raises(ProfileNotFoundError, match="declares no model"):
            resolve_profile(service="mystery", services_path=services)

    def test_two_selectors_rejected(self):
        with pytest.raises(ProfileError, match="exactly one"):
            resolve_profile(profile_id=DEEPSEEK_PROFILE_ID, model="anything")

    def test_no_selector_resolves_default_profile(self):
        resolved = resolve_contract()
        assert resolved.profile is not None
        assert resolved.profile_id == DEEPSEEK_PROFILE_ID
        assert resolved.rule("R13").strength == STRENGTH_HARD
        assert resolved.thresholds["wide_table_column_threshold"].value == 6

    def test_every_packaged_profile_declares_its_own_directory_name(self):
        """Otherwise `--profile x` and the model binding could disagree."""
        for profile_id in available_profiles():
            assert load_profile(profile_id).id == profile_id

    def test_no_two_profiles_claim_the_same_model_identity(self):
        """Ambiguity must be impossible, not resolved by iteration order."""
        claims: dict[str, set[str]] = {}
        for profile_id in available_profiles():
            profile = load_profile(profile_id)
            claims[profile_id] = {
                normalize_identity(value)
                for value in (*profile.model_ids, *profile.aliases)
            }
        for first, first_claims in claims.items():
            for second, second_claims in claims.items():
                if first >= second:
                    continue
                overlap = sorted(first_claims & second_claims)
                assert not overlap, f"{first} and {second} both claim {overlap}"


# -- a profile may tighten, never weaken ---------------------------------------


class TestBakedProfileValues:
    """Verify the DeepSeek V4 values that are baked directly into rules.toml."""

    def test_r13_is_hard_with_fail_status(self):
        resolved = resolve_contract(profile_id=DEEPSEEK_PROFILE_ID)
        assert resolved.rule("R13").strength == STRENGTH_HARD
        assert resolved.rule("R13").failure_status == STATUS_FAIL

    def test_wide_table_threshold_is_tightened(self):
        resolved = resolve_contract(profile_id=DEEPSEEK_PROFILE_ID)
        assert resolved.thresholds["wide_table_column_threshold"].value == 6

    def test_caption_distance_is_tightened(self):
        resolved = resolve_contract(profile_id=DEEPSEEK_PROFILE_ID)
        assert resolved.thresholds["caption_max_distance_lines"].value == 5

    def test_untouched_thresholds_match_core(self):
        resolved = resolve_contract(profile_id=DEEPSEEK_PROFILE_ID)
        assert resolved.thresholds["long_table_row_threshold"].value == 30
        assert resolved.thresholds["header_repeat_row_interval"].value == 25
        assert resolved.thresholds["large_table_cell_budget"].value == 200
        assert resolved.thresholds["empty_cell_sentinels"].values == ("-", "N/A")

    def test_profile_hash_is_stable_and_full_length(self, profile_data):
        profile = parse_profile(profile_data)
        assert profile.hash == load_profile(DEEPSEEK_PROFILE_ID).hash
        assert len(profile.hash) == 64

    def test_profile_probes_and_weaknesses_name_real_rules(self):
        core = load_core_contract()
        profile = load_profile(DEEPSEEK_PROFILE_ID)
        assert profile.probes and profile.known_weaknesses
        for entry in (*profile.probes, *profile.known_weaknesses):
            assert entry.evidence, f"{entry.id} cites no evidence"
            for rule_id in entry.rules:
                assert rule_id in core.rule_ids

    def test_profile_certification_status_is_honest(self):
        """The profile must not claim certification it has not earned."""
        assert load_profile(DEEPSEEK_PROFILE_ID).certification_status == "pending"

    def test_load_combined_returns_contract_and_profile(self):
        resolved = load_combined(DEEPSEEK_PROFILE_ID)
        assert resolved.core is not None
        assert resolved.profile is not None
        assert resolved.profile_id == DEEPSEEK_PROFILE_ID
        assert resolved.core.id == "whisker-llm-readability-deepseek-v4"


class TestProfileProvenance:
    def test_every_cited_profile_evidence_file_exists(self):
        profile = load_profile(DEEPSEEK_PROFILE_ID)
        for item in profile.evidence:
            _assert_citation_resolves(item, where=f"profile {profile.id}")
        for entry in (*profile.known_weaknesses, *profile.probes):
            for item in entry.evidence:
                _assert_citation_resolves(item, where=entry.id)

    def test_column_association_cites_the_run_that_actually_failed(self):
        """The current certificate records this probe PASSING.

        Citing it as evidence of the F-vs-SF misread would present a passing run
        as a failure. The honest sources are the 2026-07-09 grounded readback and
        the TOC A/B experiment that attributed the delta to model variance.
        """
        weakness = next(
            entry
            for entry in load_profile(DEEPSEEK_PROFILE_ID).known_weaknesses
            if entry.id == "sub-threshold-column-association"
        )
        assert not any("READBACK-CERTIFICATE" in item for item in weakness.evidence), (
            "the current certificate records this probe passing, not failing"
        )
        assert any("fullread-32" in item for item in weakness.evidence)
        assert "PASSED" in weakness.description, (
            "the weakness must state that the current run passes this probe"
        )


# -- evaluation and verdicts ---------------------------------------------------


class TestVacuousDocument:
    def test_no_table_is_never_a_pass(self):
        report = evaluate(resolved_core_only(), ())
        assert report.vacuous is True
        assert report.verdict == VERDICT_NOT_APPLICABLE
        assert report.document_deterministic_ok is False
        assert report.model_certified is False
        assert report.certified is False
        assert "vacuous" in report.blocking_reasons

    def test_no_table_with_a_profile_is_still_never_certified(self):
        report = evaluate(
            resolve_contract(profile_id=DEEPSEEK_PROFILE_ID),
            (),
            methods_executed=ALL_METHODS,
        )
        assert report.vacuous is True
        assert report.model_certified is False
        assert "vacuous" in report.blocking_reasons

    def test_every_rule_is_not_applicable_when_there_is_no_table(self):
        report = evaluate(resolved_core_only(), ())
        assert set(report.statuses().values()) == {STATUS_NOT_APPLICABLE}


class TestDefaultProfileEvaluation:
    def test_clean_candidate_is_deterministically_ok_but_not_certified(self):
        report = evaluate(resolved_core_only(), clean_units())
        assert report.document_deterministic_ok is True
        assert report.model_certified is False
        assert report.certified is False
        assert any(
            reason.startswith("required_method_not_executed:")
            for reason in report.blocking_reasons
        )

    def test_verdict_is_incomplete_while_hard_source_rules_are_unproven(self):
        report = evaluate(resolved_core_only(), clean_units())
        assert report.verdict == VERDICT_INCOMPLETE
        unproven = {
            rule_id
            for rule_id, status in report.statuses().items()
            if status == STATUS_NOT_EVALUATED
        }
        assert {"R5", "R10", "R11"} <= unproven

    def test_deterministic_hard_rules_pass_on_a_clean_candidate(self):
        report = evaluate(resolved_core_only(), clean_units())
        for rule_id in ("R1", "R2", "R6"):
            assert report.result(rule_id).status == STATUS_PASS, rule_id

    def test_chunking_rule_is_not_applicable_until_chunking_is_in_scope(self):
        report = evaluate(resolved_core_only(), clean_units())
        assert report.result("R12").status == STATUS_NOT_APPLICABLE
        chunked = evaluate(resolved_core_only(), clean_units(), chunking_evaluated=True)
        assert chunked.result("R12").status == STATUS_NOT_EVALUATED
        assert chunked.document_deterministic_ok is False

    def test_unknown_method_name_is_rejected(self):
        with pytest.raises(ValueError, match="unknown evaluation method"):
            evaluate(resolved_core_only(), clean_units(), methods_executed=("vibes",))


class TestDeterministicChecksFire:
    def test_row_cell_deficit_fails_r1(self):
        clean = clean_units()[0]
        broken = TableUnit(
            index=0,
            fmt="pipe",
            cells=(clean.cells[0], ("only", "two"), *clean.cells[2:]),
            raw_rows=clean.raw_rows,
            has_header=True,
            has_separator=True,
        )
        report = evaluate(resolved_core_only(), (broken,))
        assert report.result("R1").status == STATUS_FAIL
        assert report.result("R1").findings
        assert report.verdict == VERDICT_FAIL
        assert report.document_deterministic_ok is False

    def test_missing_separator_fails_r2(self):
        clean = clean_units()[0]
        broken = TableUnit(
            index=0,
            fmt="pipe",
            cells=clean.cells,
            raw_rows=clean.raw_rows,
            has_header=True,
            has_separator=False,
        )
        report = evaluate(resolved_core_only(), (broken,))
        assert report.result("R2").status == STATUS_FAIL

    def test_unescaped_pipe_fails_r6(self):
        clean = clean_units()[0]
        rows = (
            clean.raw_rows[0],
            "| a | b | c | d |",
            *clean.raw_rows[2:],
        )
        broken = TableUnit(
            index=0,
            fmt="pipe",
            cells=clean.cells,
            raw_rows=rows,
            has_header=True,
            has_separator=True,
        )
        report = evaluate(resolved_core_only(), (broken,))
        assert report.result("R6").status == STATUS_FAIL

    def test_escaped_pipe_passes_r6(self):
        clean = clean_units()[0]
        rows = (clean.raw_rows[0], r"| a \| b | c | d |", *clean.raw_rows[2:])
        unit = TableUnit(
            index=0,
            fmt="pipe",
            cells=clean.cells,
            raw_rows=rows,
            has_header=True,
            has_separator=True,
        )
        assert (
            evaluate(resolved_core_only(), (unit,)).result("R6").status == STATUS_PASS
        )

    def test_blank_cell_reviews_r9_without_clearing_deterministic_ok(self):
        clean = clean_units()[0]
        cells = (clean.cells[0], ("value", "", "value"), *clean.cells[2:])
        unit = TableUnit(
            index=0,
            fmt="pipe",
            cells=cells,
            raw_rows=clean.raw_rows,
            has_header=True,
            has_separator=True,
        )
        report = evaluate(resolved_core_only(), (unit,))
        assert report.result("R9").status == STATUS_REVIEW
        assert report.document_deterministic_ok is True

    def test_baked_wide_threshold_triggers_review_at_seven_columns(self):
        """Seven columns exceed the baked threshold of 6."""
        units = clean_units(columns=7)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R7").status == STATUS_REVIEW

    def test_five_columns_is_below_baked_threshold(self):
        """Five columns stay below the baked threshold of 6."""
        units = clean_units(columns=5)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R7").status == STATUS_NOT_APPLICABLE

    def test_long_table_without_repeated_header_reviews_r8(self):
        units = clean_units(rows=40)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R8").status == STATUS_REVIEW


class TestCertificationCannotBeFaked:
    def test_missing_required_method_blocks_certification(self):
        resolved = resolve_contract(profile_id=DEEPSEEK_PROFILE_ID)
        report = evaluate(
            resolved,
            clean_units(),
            methods_executed=(METHOD_DETERMINISTIC,),
        )
        assert report.model_certified is False
        for method in (METHOD_SOURCE_COMPARE, METHOD_LLM, METHOD_CERTIFICATION):
            assert f"required_method_not_executed:{method}" in report.blocking_reasons

    def test_claiming_every_method_without_checks_still_blocks(self):
        """Declaring a lane ran does not conjure a result for its rules."""
        report = evaluate(
            resolve_contract(profile_id=DEEPSEEK_PROFILE_ID),
            clean_units(),
            methods_executed=ALL_METHODS,
            source_available=True,
        )
        assert report.model_certified is False
        assert any(
            reason.startswith("hard_rule_not_evaluated")
            for reason in report.blocking_reasons
        )
        assert "required_rule_not_evaluated:R13" in report.blocking_reasons

    def test_registered_lane_checks_close_their_rules(self):
        """The registry contract Grok's lanes plug into."""
        core = load_core_contract()
        registry = default_registry()
        for rule in core.rules:
            registry.setdefault(
                rule.check_id, lambda ctx: CheckOutcome(status=STATUS_PASS)
            )
        report = evaluate(
            resolve_contract(profile_id=DEEPSEEK_PROFILE_ID),
            clean_units(),
            methods_executed=ALL_METHODS,
            source_available=True,
            chunking_evaluated=True,
            registry=registry,
        )
        assert report.blocking_reasons == ()
        assert report.model_certified is True
        assert report.certified is True
        assert report.document_deterministic_ok is True

    def test_a_check_may_not_invent_a_status_the_rule_forbids(self):
        registry = default_registry()
        registry["pipe_row_cell_deficit"] = lambda ctx: CheckOutcome(
            status=STATUS_REVIEW
        )
        with pytest.raises(ContractSchemaError, match="does not allow"):
            evaluate(resolved_core_only(), clean_units(), registry=registry)

    def test_review_blocks_certified(self):
        """Sol: ANY per-rule review finding blocks model_certified."""
        registry = default_registry()
        for rule in load_core_contract().rules:
            registry.setdefault(
                rule.check_id, lambda ctx: CheckOutcome(status=STATUS_PASS)
            )
        registry["representation_choice_matrix"] = lambda ctx: CheckOutcome(
            status=STATUS_REVIEW
        )
        report = evaluate(
            resolve_contract(profile_id=DEEPSEEK_PROFILE_ID),
            clean_units(),
            methods_executed=ALL_METHODS,
            source_available=True,
            chunking_evaluated=True,
            registry=registry,
        )
        assert report.model_certified is False
        assert report.certified is False
        assert any(
            reason.startswith("rule_review:") for reason in report.blocking_reasons
        )


class TestMarkdownAdapterIsHonest:
    MARKDOWN = "# Paper\n\n| Option | Votes |\n|---|---|\n| SF | 4 |\n| WF | 2 |\n"
    MALFORMED = "| a | b |\n| c | d |\n"
    PROSE = "Use a | b as bitwise or.\nMore | text with a bar.\n"

    def test_units_are_parsed_from_markdown(self):
        units = table_units_from_markdown(self.MARKDOWN)
        assert len(units) == 1
        assert units[0].fmt == "pipe"
        assert units[0].cells[0] == ("Option", "Votes")
        assert units[0].has_header is True
        assert units[0].has_separator is True
        assert units[0].raw_rows is not None
        assert not any("---" in row for row in units[0].raw_rows)

    def test_escape_and_separator_rules_on_the_markdown_adapter(self):
        """Valid markdown sets separator flags so R2 can pass; R6 still uses raw_rows."""
        report = evaluate(
            resolved_core_only(), table_units_from_markdown(self.MARKDOWN)
        )
        assert report.result("R2").status == STATUS_PASS
        assert report.result("R6").status == STATUS_PASS
        assert report.document_deterministic_ok is True

    def test_malformed_outer_pipe_block_fails_r2(self):
        from whisker.tables import parse_pipe_tables

        assert parse_pipe_tables(self.MALFORMED) == []
        units = table_units_from_markdown(self.MALFORMED)
        assert len(units) == 1
        assert units[0].has_header is True
        assert units[0].has_separator is False
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_FAIL

    def test_prose_pipe_creates_no_table_unit(self):
        units = table_units_from_markdown(self.PROSE)
        assert units == ()
        report = evaluate(resolved_core_only(), units)
        assert report.vacuous is True

    def test_no_table_markdown_is_vacuous(self):
        report = evaluate(resolved_core_only(), table_units_from_markdown("# Paper\n"))
        assert report.vacuous is True


class TestContinuationHeaderDetection:
    """R2 must fail when a page-break produces a data row as a GFM header."""

    ADJACENT_CONTINUATION = (
        "| Name | Body |\n|---|---|\n| Alice | ANSI |\n| Bob | BSI |\n\n"
        "| Alice | ANSI |\n|---|---|\n| Carol | DIN |\n"
    )

    HEADING_SEPARATES = (
        "| Name | Body |\n|---|---|\n| Alice | ANSI |\n\n"
        "## Section B\n\n"
        "| Alice | ANSI |\n|---|---|\n| Bob | BSI |\n"
    )

    SAME_HEADER_NO_CONTINUATION = (
        "| Name | Body |\n|---|---|\n| Alice | ANSI |\n\n"
        "| Name | Body |\n|---|---|\n| Bob | BSI |\n"
    )

    DIFFERENT_COLUMN_COUNT = (
        "| Name | Body | Extra |\n|---|---|---|\n| Alice | ANSI | X |\n\n"
        "| Foo | Bar |\n|---|---|\n| Baz | Qux |\n"
    )

    N5040_ATTENDANCE = (
        "## 10. Attendance\n\n"
        "| | Name | National Body |\n| --- | --- | --- |\n"
        "| Adams, Michael |  | SCC |\n"
        "| Davidson, Guy |  | BSI |\n\n"
        "| de Wever, Mark | ANSI |\n| --- | --- |\n"
        "| Delfino, Gianluca | UNI |\n\n"
        "| Mara Bos | NEN |\n| --- | --- |\n"
        "| Sutter, Herb | ANSI |\n"
    )

    # P2583R0 #374 BASE: page-break promoted the Boost.Capy row to a header.
    # Lock (#411): header B values match A's body column 1 verbatim, and
    # ``Returns `p_->continuation()``` is prose + code, not a label.
    P2583_BOOST_CAPY = (
        "| [folly::coro](http://example/folly) | `coroutine_handle<>` |\n"
        "| --- | --- |\n"
        "| [Boost.Cobalt](http://example/cobalt) | `coroutine_handle<>` |\n"
        "| [libcoro](http://example/libcoro) | `coroutine_handle<>` |\n"
        "\n"
        "Returns `awaited_from` or `noop_coroutine()`\n"
        "\n"
        "Library\n"
        "\n"
        "Mechanism\n"
        "\n"
        "| [Boost.Capy](http://example/capy) | `coroutine_handle<>` | Returns `p_->continuation()` |\n"
        "| --- | --- | --- |\n"
        "| [asyncpp](http://example/asyncpp) | `void` | Event-based notification |\n"
    )

    # #411 logic-check M3: a promoted data row made only of code spans is
    # label-like cell by cell but is not a label header. A's body does not
    # repeat B's header, so only the eff-count branch can catch it.
    CODE_SPAN_HEADER_AFTER_CODE_TABLE = (
        "| Library | Handle type |\n"
        "| --- | --- |\n"
        "| `folly` | `Task<T>` |\n"
        "| `libcoro` | `task<T>` |\n"
        "\n"
        "| `cobalt` | `coroutine_handle<>` |\n"
        "| --- | --- |\n"
        "| `asyncpp` | `void` |\n"
    )

    def test_adjacent_continuation_fails_r2(self):
        units = table_units_from_markdown(self.ADJACENT_CONTINUATION)
        assert len(units) == 2
        assert units[1].continuation_of == 0
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_FAIL
        assert any(
            "continuation" in f.message for f in report.result("R2").findings
        )

    def test_heading_between_tables_prevents_continuation(self):
        units = table_units_from_markdown(self.HEADING_SEPARATES)
        assert len(units) == 2
        assert units[0].continuation_of is None
        assert units[1].continuation_of is None
        report = evaluate(resolved_core_only(), units)
        r2_findings = [
            f for f in report.result("R2").findings if "continuation" in f.message
        ]
        assert r2_findings == []

    def test_same_header_is_not_continuation(self):
        units = table_units_from_markdown(self.SAME_HEADER_NO_CONTINUATION)
        assert len(units) == 2
        assert units[0].continuation_of is None
        assert units[1].continuation_of is None

    def test_different_column_count_no_body_match_is_not_continuation(self):
        units = table_units_from_markdown(self.DIFFERENT_COLUMN_COUNT)
        assert len(units) == 2
        assert units[1].continuation_of is None

    def test_n5040_attendance_fixture(self):
        """The plan's N5040 fixture: three fragments, last two flagged."""
        units = table_units_from_markdown(self.N5040_ATTENDANCE)
        assert len(units) == 3
        assert units[0].continuation_of is None
        assert units[1].continuation_of == 0
        assert units[2].continuation_of == 1

        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_FAIL
        assert report.document_deterministic_ok is False
        cont_findings = [
            f for f in report.result("R2").findings if "continuation" in f.message
        ]
        assert len(cont_findings) == 2

    def test_p2583_boost_capy_still_continuation(self):
        """#374 lock: the promoted Boost.Capy row still reads as continuation."""
        units = table_units_from_markdown(self.P2583_BOOST_CAPY)
        pipes = [u for u in units if u.fmt == "pipe" and not u.flattened_prose]
        assert len(pipes) == 2
        assert pipes[1].continuation_of == pipes[0].index

    def test_code_span_only_header_is_continuation(self):
        """M3: code-span-only header B is a data row, not a label header."""
        units = table_units_from_markdown(self.CODE_SPAN_HEADER_AFTER_CODE_TABLE)
        pipes = [u for u in units if u.fmt == "pipe" and not u.flattened_prose]
        assert len(pipes) == 2
        assert pipes[1].continuation_of == pipes[0].index

    def test_no_continuations_on_fixed_n5040(self):
        """After PR #365 fix, N5040 has no continuation fragments."""
        from pathlib import Path

        p = Path("data/paperstore/n5040.md")
        if not p.exists():
            pytest.skip("corpus file not available")
        md = p.read_text(encoding="utf-8")
        units = table_units_from_markdown(md)
        conts = [u for u in units if u.continuation_of is not None]
        assert len(conts) == 0


class TestLabelShiftDetection:
    """R1 must fail when a phantom column shifts values away from headers."""

    PHANTOM_SHIFT = (
        "| | Name | National Body |\n| --- | --- | --- |\n"
        "| Adams, Michael |  | SCC |\n"
        "| Alday, Juan |  | ANSI |\n"
        "| Baker, Billy |  | ANSI |\n"
    )

    LEGITIMATE_ROW_STUB = (
        "| | Revenue | Expenses |\n| --- | --- | --- |\n"
        "| Q1 | 100 | 80 |\n"
        "| Q2 | 120 | 90 |\n"
        "| Q3 | 110 | 85 |\n"
    )

    def test_phantom_shift_fails_r1(self):
        """Empty header col with filled body + named neighbour with empty body."""
        units = table_units_from_markdown(self.PHANTOM_SHIFT)
        assert len(units) == 1
        report = evaluate(resolved_core_only(), units)
        assert report.result("R1").status == STATUS_FAIL
        assert any("label shift" in f.message for f in report.result("R1").findings)

    def test_legitimate_row_stub_passes_r1(self):
        """Empty corner header is fine when both data columns are filled."""
        units = table_units_from_markdown(self.LEGITIMATE_ROW_STUB)
        assert len(units) == 1
        report = evaluate(resolved_core_only(), units)
        r1_shift = [
            f for f in report.result("R1").findings if "label shift" in f.message
        ]
        assert r1_shift == []

    def test_n5040_attendance_excerpt_fails_r1(self):
        """The N5040 Attendance first fragment has the phantom column."""
        units = table_units_from_markdown(
            TestContinuationHeaderDetection.N5040_ATTENDANCE
        )
        report = evaluate(resolved_core_only(), units)
        assert report.result("R1").status == STATUS_FAIL
        assert any("label shift" in f.message for f in report.result("R1").findings)

    def test_real_n5040_passes_r1_after_fix(self):
        """After PR #365, N5040 attendance has no phantom column."""
        from pathlib import Path

        p = Path("data/paperstore/n5040.md")
        if not p.exists():
            pytest.skip("corpus file not available")
        md = p.read_text(encoding="utf-8")
        units = table_units_from_markdown(md)
        report = evaluate(resolved_core_only(), units)
        r1_shift = [
            f for f in report.result("R1").findings if "label shift" in f.message
        ]
        assert len(r1_shift) == 0

    def test_corpus_p4182r0_no_false_positive(self):
        """P4182R0 must not false-positive on R1 label shift."""
        from pathlib import Path

        p = Path("data/paperstore/p4182r0.md")
        if not p.exists():
            pytest.skip("corpus file not available")
        md = p.read_text(encoding="utf-8")
        units = table_units_from_markdown(md)
        report = evaluate(resolved_core_only(), units)
        r1_shift = [
            f for f in report.result("R1").findings if "label shift" in f.message
        ]
        assert r1_shift == []

    def test_corpus_p0876r23_no_false_positive(self):
        """P0876R23 must not false-positive on R1 label shift."""
        from pathlib import Path

        p = Path("data/paperstore/p0876r23.md")
        if not p.exists():
            pytest.skip("corpus file not available")
        md = p.read_text(encoding="utf-8")
        units = table_units_from_markdown(md)
        report = evaluate(resolved_core_only(), units)
        r1_shift = [
            f for f in report.result("R1").findings if "label shift" in f.message
        ]
        assert r1_shift == []


class TestDataAsHeaderDetection:
    """R2 must fail when all header cells are numeric and body is blank."""

    POLL_BROKEN = (
        "| 8 | 3 | 1 | 0 | 0 |\n| --- | --- | --- | --- | --- |\n"
        "|  |  |  |  |  |\n"
    )

    POLL_GOOD = (
        "| SF | F | N | A | SA |\n| --- | --- | --- | --- | --- |\n"
        "| 8 | 3 | 1 | 0 | 0 |\n"
    )

    def test_numeric_header_blank_body_flags_data_as_header(self):
        units = table_units_from_markdown(self.POLL_BROKEN)
        assert len(units) == 1
        assert units[0].data_as_header is True

    def test_good_poll_not_flagged(self):
        units = table_units_from_markdown(self.POLL_GOOD)
        assert len(units) == 1
        assert units[0].data_as_header is False

    def test_data_as_header_fails_r2(self):
        units = table_units_from_markdown(self.POLL_BROKEN)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_FAIL
        assert any(
            "data row used as header" in f.message
            for f in report.result("R2").findings
        )

    def test_mixed_header_not_flagged(self):
        md = (
            "| Name | 42 | Score |\n| --- | --- | --- |\n"
            "| alpha | 1 | 10 |\n"
        )
        units = table_units_from_markdown(md)
        assert units[0].data_as_header is False


class TestWrapBleedDetection:
    """R2 must fail when a sentence fragment bleeds from header into body."""

    WRAP_BLEED = (
        "| `predicate_false` | The predicate of the contract assertion "
        "evaluated to `false` or would have |  |  |\n"
        "| --- | --- | --- | --- |\n"
        "| `evaluation_exception` | evaluated to `false`. An uncaught "
        "exception occurred |  |  |\n"
    )

    CLEAN_TABLE = (
        "| Name | Meaning |\n| --- | --- |\n"
        "| `unspecified` | Not yet determined |\n"
        "| `predicate_false` | The predicate evaluated to false |\n"
    )

    def test_sentence_fragment_flags_wrap_bleed(self):
        units = table_units_from_markdown(self.WRAP_BLEED)
        assert len(units) == 1
        assert units[0].wrap_bleed is True

    def test_clean_table_not_flagged(self):
        units = table_units_from_markdown(self.CLEAN_TABLE)
        assert len(units) == 1
        assert units[0].wrap_bleed is False

    def test_wrap_bleed_fails_r2(self):
        units = table_units_from_markdown(self.WRAP_BLEED)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_FAIL
        assert any(
            "sentence fragment bleeds" in f.message
            for f in report.result("R2").findings
        )

    def test_short_header_not_flagged(self):
        md = (
            "| notes | see below |\n| --- | --- |\n"
            "| a | b |\n"
        )
        units = table_units_from_markdown(md)
        assert units[0].wrap_bleed is False

    def test_p0876r23_no_false_positive(self):
        from pathlib import Path

        p = Path("data/paperstore/p0876r23.md")
        if not p.exists():
            pytest.skip("corpus file not available")
        md = p.read_text(encoding="utf-8")
        units = table_units_from_markdown(md)
        flagged = [u for u in units if u.data_as_header or u.wrap_bleed]
        assert flagged == [], f"false positive on {[u.index for u in flagged]}"


class TestHeaderIsDataDetection:
    """R2 must fail when header cells look like data values (P4016R0 T5/T7)."""

    PROPERTY_HEADER = (
        "| `inclusive_scan` | `std::execution::par_unseq` | GENERALIZED_SUM |\n"
        "| --- | --- | --- |\n"
        "| Operand order | Policy | Grouping |\n"
    )

    D3_GROUPING_HEADER = (
        "| GENERALIZED_SUM | GENERALIZED_NONCOMMUTATIVE_SUM |\n"
        "| --- | --- |\n"
        "| Grouping | Associativity |\n"
    )

    CLEAN_LABEL_HEADER = (
        "| Feature | Status | Notes |\n| --- | --- | --- |\n"
        "| Coroutines | Partial | See paper |\n"
    )

    NUMERIC_HEADER_NOT_HEADER_IS_DATA = (
        "| 8 | 3 | 1 | 0 | 0 |\n| --- | --- | --- | --- | --- |\n"
        "|  |  |  |  |  |\n"
    )

    def test_code_and_phrase_header_flags_header_is_data(self):
        units = table_units_from_markdown(self.PROPERTY_HEADER)
        assert len(units) == 1
        assert units[0].header_is_data is True

    def test_allcaps_identifier_header_flags_header_is_data(self):
        units = table_units_from_markdown(self.D3_GROUPING_HEADER)
        assert len(units) == 1
        assert units[0].header_is_data is True

    def test_clean_label_header_not_flagged(self):
        units = table_units_from_markdown(self.CLEAN_LABEL_HEADER)
        assert len(units) == 1
        assert units[0].header_is_data is False

    def test_numeric_header_stays_data_as_header(self):
        units = table_units_from_markdown(self.NUMERIC_HEADER_NOT_HEADER_IS_DATA)
        assert len(units) == 1
        assert units[0].data_as_header is True
        assert units[0].header_is_data is False

    def test_header_is_data_fails_r2(self):
        units = table_units_from_markdown(self.PROPERTY_HEADER)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_FAIL
        assert any(
            "header contains data values" in f.message
            for f in report.result("R2").findings
        )

    def test_comparison_header_aspect_not_flagged(self):
        md = (
            "| Aspect | std::accumulate | This Proposal (`op(I, R)`) |\n"
            "| --- | --- | --- |\n"
            "| Init handling | Folded at every step | Combined once at end |\n"
        )
        units = table_units_from_markdown(md)
        assert units[0].header_is_data is False

    def test_colon_value_header_flags(self):
        md = (
            "| Grouping | Mandated: Left-to-right | Generalized Sum (Unspecified) |\n"
            "| --- | --- | --- |\n"
            "| Complexity | O(N) operations | O(N) operations |\n"
        )
        units = table_units_from_markdown(md)
        assert units[0].header_is_data is True

    def test_truncated_header_flags(self):
        md = (
            "| HPC frameworks (Kokkos, | Yes Same-config deterministic |\n"
            "| --- | --- |\n"
            "| etc.) | backends |\n"
        )
        units = table_units_from_markdown(md)
        assert units[0].header_is_data is True


class TestTruncatedLeakDetection:
    """R2 must fail when a 1-body-row table leaks rows into prose (P4016R0 F.1)."""

    LEAKED_TABLE = (
        "| Feature | Support | Status |\n| --- | --- | --- |\n"
        "| Topology | Full | Complete |\n\n"
        "Parameterization Fixed constant byte span\n"
        "Init placement Post-reduction op\n"
    )

    CLEAN_TABLE_WITH_PROSE = (
        "| Feature | Status |\n| --- | --- |\n"
        "| Parameterization | Complete |\n\n"
        "The following section discusses implementation details.\n"
    )

    HEADING_STOPS_LEAK = (
        "| Feature | Support | Status |\n| --- | --- | --- |\n"
        "| Parameterization | Full | Complete |\n\n"
        "## Next Section\n"
        "Init feature support partial status pending\n"
    )

    def test_leaked_prose_flags_truncated_leak(self):
        units = table_units_from_markdown(self.LEAKED_TABLE)
        assert len(units) == 1
        assert units[0].truncated_leak is True

    def test_normal_prose_not_flagged(self):
        units = table_units_from_markdown(self.CLEAN_TABLE_WITH_PROSE)
        assert len(units) == 1
        assert units[0].truncated_leak is False

    def test_heading_prevents_leak_detection(self):
        units = table_units_from_markdown(self.HEADING_STOPS_LEAK)
        assert len(units) == 1
        assert units[0].truncated_leak is False

    def test_truncated_leak_fails_r2(self):
        units = table_units_from_markdown(self.LEAKED_TABLE)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_FAIL
        assert any(
            "truncated" in f.message
            for f in report.result("R2").findings
        )


class TestRowMergeDetection:
    """R2 must fail when a cell merges distinct row records (P4016R0 3.6.1)."""

    MERGED_VENDORS = (
        "| Algorithm | Vendor Support |\n| --- | --- |\n"
        "| reduce | Intel oneMKL NVIDIA CUB AMD rocPRIM |\n"
    )

    SINGLE_ENTRY = (
        "| Algorithm | Vendor Support |\n| --- | --- |\n"
        "| reduce | Intel oneMKL |\n"
    )

    COMMA_SEPARATED = (
        "| Algorithm | Vendor Support |\n| --- | --- |\n"
        "| reduce | Intel oneMKL, NVIDIA CUB, AMD rocPRIM |\n"
    )

    def test_concatenated_vendors_flags_row_merge(self):
        units = table_units_from_markdown(self.MERGED_VENDORS)
        assert len(units) == 1
        assert units[0].row_merge is True

    def test_single_entry_not_flagged(self):
        units = table_units_from_markdown(self.SINGLE_ENTRY)
        assert len(units) == 1
        assert units[0].row_merge is False

    def test_comma_separated_not_flagged(self):
        units = table_units_from_markdown(self.COMMA_SEPARATED)
        assert len(units) == 1
        assert units[0].row_merge is False

    def test_row_merge_fails_r2(self):
        units = table_units_from_markdown(self.MERGED_VENDORS)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_FAIL
        assert any(
            "merged without separator" in f.message
            for f in report.result("R2").findings
        )


class TestWrapOrphanDetection:
    def test_appendix_wrap_flags(self):
        md = (
            "| Reader | Read |\n| --- | --- |\n"
            "| **Implementer** | Polls, §4, Appendix B, N |\n"
        )
        units = table_units_from_markdown(md)
        assert units[0].wrap_orphan is True

    def test_plain_cell_not_flagged(self):
        md = (
            "| Reader | Read |\n| --- | --- |\n"
            "| **Implementer** | Polls, §4, Appendix B |\n"
        )
        units = table_units_from_markdown(md)
        assert units[0].wrap_orphan is False


class TestHyphenGlueDetection:
    def test_glued_independent_flags(self):
        md = (
            "| Demonstrator | Notes |\n| --- | --- |\n"
            "| GB-SEQ | Debuggerfriendly golden, singlethreaded only |\n"
        )
        units = table_units_from_markdown(md)
        assert units[0].hyphen_glue is True

    def test_hyphenated_not_flagged(self):
        md = (
            "| Demonstrator | Notes |\n| --- | --- |\n"
            "| GB-SEQ | Debugger-friendly golden, single-threaded only |\n"
        )
        units = table_units_from_markdown(md)
        assert units[0].hyphen_glue is False


class TestHtmlHeaderIsDataR2:
    """R2 must report header_is_data findings on HTML units (P4016R0 §7)."""

    KOKKOS_HTML = (
        '<table border="1" rules="all" cellpadding="6" cellspacing="0" '
        'style="border-collapse: collapse; width: 100%;">\n'
        "<tr>\n"
        '<th style="border: 1px solid #999; padding: 6px 10px; '
        'vertical-align: top; width: 50%;">HPC frameworks (Kokkos,</th>\n'
        '<th style="border: 1px solid #999; padding: 6px 10px; '
        "vertical-align: top; width: 50%;\">Yes\n"
        "Same-config deterministic; not across thread counts or</th>\n"
        "</tr>\n"
        "<tr>\n"
        '<td style="border: 1px solid #999; padding: 6px 10px; '
        'vertical-align: top; width: 50%;"><pre style="margin: 0;">'
        "<code>etc.)</code></pre></td>\n"
        '<td style="border: 1px solid #999; padding: 6px 10px; '
        'vertical-align: top; width: 50%;"><pre style="margin: 0;">'
        "<code>backends</code></pre></td>\n"
        "</tr>\n"
        "</table>\n"
    )

    def test_html_kokkos_unit_exists(self):
        units = table_units_from_markdown(self.KOKKOS_HTML)
        html = [u for u in units if u.fmt == "html"]
        assert len(html) == 1

    def test_html_kokkos_header_is_data(self):
        units = table_units_from_markdown(self.KOKKOS_HTML)
        html = [u for u in units if u.fmt == "html"]
        assert html[0].header_is_data is True

    def test_html_kokkos_fails_r2(self):
        units = table_units_from_markdown(self.KOKKOS_HTML)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_FAIL
        findings = report.result("R2").findings
        assert any("header contains data" in f.message for f in findings)
        assert any("html" in f.locus for f in findings)


class TestFlattenedProseDetection:
    """R2 must detect tables flattened to heading + prose (P4016R0 B.1)."""

    B1_FLATTENED = (
        "#### B.1 Two Degrees of Parallelism\n"
        "\n"
        "Real implementations exploit two orthogonal forms of parallelism:\n"
        "\n"
        "##### Parallelism Mechanism Typical Scale\n"
        "\n"
        "SIMD Vector registers, GPU warps 4–64 lanes\n"
        "\n"
        "Threads CPU cores, GPU blocks 4–thousands\n"
        "\n"
        "This leads to two levels of reduction:\n"
    )

    NORMAL_HEADING = (
        "##### 7.1 The Cost of Determinism\n"
        "\n"
        "Deterministic reduction requires a fixed evaluation order.\n"
        "This constraint limits parallelism exploitation.\n"
    )

    NORMAL_HEADING_NO_NUMBER = (
        "##### General Principle\n"
        "\n"
        "The following describes the general approach.\n"
        "Each step is carefully documented.\n"
    )

    def test_b1_detected_as_flattened(self):
        units = table_units_from_markdown(self.B1_FLATTENED)
        flat = [u for u in units if u.flattened_prose]
        assert len(flat) == 1

    def test_b1_has_correct_header(self):
        units = table_units_from_markdown(self.B1_FLATTENED)
        flat = [u for u in units if u.flattened_prose][0]
        assert flat.cells[0] == ("Parallelism", "Mechanism", "Typical", "Scale")

    def test_b1_has_data_rows(self):
        units = table_units_from_markdown(self.B1_FLATTENED)
        flat = [u for u in units if u.flattened_prose][0]
        assert len(flat.cells) == 3
        assert flat.cells[1][0] == "SIMD"
        assert flat.cells[2][0] == "Threads"

    def test_b1_fails_r2(self):
        units = table_units_from_markdown(self.B1_FLATTENED)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_FAIL
        findings = report.result("R2").findings
        assert any("flattened" in f.message for f in findings)

    def test_numbered_heading_not_flagged(self):
        units = table_units_from_markdown(self.NORMAL_HEADING)
        flat = [u for u in units if u.flattened_prose]
        assert flat == []

    def test_normal_heading_plus_sentences_not_flagged(self):
        units = table_units_from_markdown(self.NORMAL_HEADING_NO_NUMBER)
        flat = [u for u in units if u.flattened_prose]
        assert flat == []

    def test_single_data_row_not_flagged(self):
        md = (
            "##### Status Category Level\n"
            "\n"
            "Active High Critical\n"
            "\n"
            "The rest is normal prose.\n"
        )
        units = table_units_from_markdown(md)
        flat = [u for u in units if u.flattened_prose]
        assert flat == []


class TestP4047StackedFlattened:
    """P4047R0 Safety/Customization: stacked labels + S1/C1 row ids."""

    SAFETY = (
        "Safety and Correctness\n"
        "\n"
        "#\n"
        "Prediction\n"
        "Source\n"
        "Date\n"
        "Outcome\n"
        "\n"
        "S1\n"
        "Stack overflow from reentrant completion\n"
        "\n"
        "S2\n"
        "P2300 design insufficiently paranoid\n"
    )

    def test_stacked_detected(self):
        units = table_units_from_markdown(self.SAFETY)
        flat = [u for u in units if u.flattened_prose]
        assert len(flat) == 1
        assert "S1" in {cell[0] for cell in flat[0].cells[1:]}
        assert "S2" in {cell[0] for cell in flat[0].cells[1:]}

    def test_stacked_fails_r2(self):
        units = table_units_from_markdown(self.SAFETY)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_FAIL
        assert any("flattened" in f.message for f in report.result("R2").findings)

    def test_normal_prose_list_not_flagged(self):
        md = (
            "The following identifiers appear in the paper:\n"
            "\n"
            "S1\n"
            "S2\n"
        )
        units = table_units_from_markdown(md)
        assert [u for u in units if u.flattened_prose] == []


class TestP4047HtmlSmash:
    """P4047R0 Universality/Networking smashed HTML headers."""

    UNIV = (
        "<table>\n"
        "<tr>\n"
        "<th>should be coroutines\"</th>\n"
        "<th>\"Structured Concurrency\" [16]</th>\n"
        "<th>2020-11 Shifted - by 2024: returning a</th>\n"
        "<th>sender is a great choice [17]</th>\n"
        "</tr>\n"
        "<tr>\n"
        "<td>U2 senders are like iterators</td>\n"
        "<td>Kuhl</td>\n"
        "<td>2021-25</td>\n"
        "<td>Unconfirmed</td>\n"
        "</tr>\n"
        "</table>\n"
    )

    NET = (
        "<table>\n"
        "<tr>\n"
        "<th>and long overdue.\" N2 \"We don't have a composable approach</th>\n"
        "<th></th>\n"
        "<th>[4] Voutilainen</th>\n"
        "<th>2021-10 Confirmed - still true</th>\n"
        "</tr>\n"
        "<tr><td>N3</td><td>x</td><td>y</td><td>z</td></tr>\n"
        "</table>\n"
    )

    CLEAN = (
        "<table>\n"
        "<tr><th>#</th><th>Prediction</th><th>Source</th><th>Date</th><th>Outcome</th></tr>\n"
        "<tr><td>T1</td><td>Ship in C++26</td><td>P2300</td><td>2021-10</td><td>Confirmed</td></tr>\n"
        "</table>\n"
    )

    def test_universality_header_is_data(self):
        units = table_units_from_markdown(self.UNIV)
        html = [u for u in units if u.fmt == "html"]
        assert html and html[0].header_is_data is True

    def test_networking_header_is_data(self):
        units = table_units_from_markdown(self.NET)
        html = [u for u in units if u.fmt == "html"]
        assert html and html[0].header_is_data is True

    def test_clean_html_not_flagged(self):
        units = table_units_from_markdown(self.CLEAN)
        html = [u for u in units if u.fmt == "html"]
        assert html and html[0].header_is_data is False


class TestP4047ScorecardAndConclusion:
    """P4047R0 §4 count-row header and §5 last-row leak."""

    SCORECARD = (
        "### Category Predictions Confirmed Unconfirmed Shifted /\n"
        "\n"
        "### Pending\n"
        "\n"
        "### Partial\n"
        "\n"
        "| Timeline | 5 | 4 | 1 | 0 | 0 |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| Safety / Correctness | 5 | 4 | 0 | 1 | 0 |\n"
        "| Customization Mechanism | 3 | 0 | 2 | 0 | 1 |\n"
        "| **Total** | **27** | **18** | **5** | **2** | **2** |\n"
    )

    CONCLUSION = (
        "| Predictive | Not Predictive |\n"
        "| --- | --- |\n"
        "| Safety and correctness concerns | Universality claims |\n"
        "| Domain viability (where deployed) | Customization mechanism design |\n"
        "| Networking gap | Timeline estimates (all sides) |\n"
        "\n"
        "Implementation maturity concerns\n"
        "\n"
        "## References\n"
    )

    FEATURE_YEARS = (
        "| Feature | C++11 | C++14 | C++17 |\n"
        "| --- | --- | --- | --- |\n"
        "| Concepts | No | No | No |\n"
        "| Auto | Yes | Yes | Yes |\n"
    )

    def test_scorecard_header_is_data(self):
        units = table_units_from_markdown(self.SCORECARD)
        pipes = [u for u in units if u.fmt == "pipe" and not u.flattened_prose]
        assert pipes and pipes[0].header_is_data is True

    def test_scorecard_fails_r2(self):
        units = table_units_from_markdown(self.SCORECARD)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_FAIL
        assert any("header contains data" in f.message for f in report.result("R2").findings)

    def test_feature_year_headers_not_flagged(self):
        units = table_units_from_markdown(self.FEATURE_YEARS)
        assert units[0].header_is_data is False

    def test_conclusion_truncated_leak(self):
        units = table_units_from_markdown(self.CONCLUSION)
        pipes = [u for u in units if u.fmt == "pipe"]
        assert pipes and pipes[0].truncated_leak is True

    def test_conclusion_fails_r2(self):
        units = table_units_from_markdown(self.CONCLUSION)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_FAIL
        assert any("truncated" in f.message for f in report.result("R2").findings)


class TestP4094PaperCiteAndFlatten:
    """P4094R0 T1 paper-cite header and both screenshot flattens."""

    CITE_HEADER = (
        "| [P0285R0](http://example/p0285r0.html)[14] (2016) | (none found in the published record) No survey |\n"
        "| --- | --- |\n"
        "| [P0761R2](http://example/p0761r2.pdf)[13] (2018) | One hypothetical snippet |\n"
    )

    PAPER_LABEL = (
        "| Paper | Year | Continuation status |\n"
        "| --- | --- | --- |\n"
        "| [P0113R0](http://example/p0113r0.html) | 2015 | First-class |\n"
    )

    ASSERTION_FLAT = (
        "### Assertion Source Evidence\n"
        "\n"
        '"we want to be able to have a single thread pool object"\n'
        "\n"
        "| [P0285R0](http://example/p0285r0.html)[14] (2016) | (none found) |\n"
        "| --- | --- |\n"
        "| [P0761R2](http://example/p0761r2.pdf)[13] (2018) | snippet |\n"
    )

    SUMMARY_LEAD = (
        "5.7 Summary\n"
        "\n"
        "6. The Framing Change\n"
        "\n"
        "No survey; reactor and work queue are\n"
        "architecturally different (7.3)\n"
        "\n"
        "| Question Shared thread pool needed? N x M explosion? | 2014 Assertion \"single thread pool\" | 2026 Outcome 21 years |\n"
        "| --- | --- | --- |\n"
        "| Unified model deployed? | (not discussed in 2014) | P0443 never deployed |\n"
    )

    def test_paper_cite_header_is_data(self):
        units = table_units_from_markdown(self.CITE_HEADER)
        pipes = [u for u in units if u.fmt == "pipe" and not u.flattened_prose]
        assert pipes and pipes[0].header_is_data is True

    def test_paper_cite_fails_r2(self):
        units = table_units_from_markdown(self.CITE_HEADER)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_FAIL
        assert any("header contains data" in f.message for f in report.result("R2").findings)

    def test_paper_column_label_not_flagged(self):
        units = table_units_from_markdown(self.PAPER_LABEL)
        pipes = [u for u in units if u.fmt == "pipe" and not u.flattened_prose]
        assert pipes and pipes[0].header_is_data is False

    def test_assertion_heading_flattened(self):
        units = table_units_from_markdown(self.ASSERTION_FLAT)
        flat = [u for u in units if u.flattened_prose]
        assert flat
        assert "Assertion" in flat[0].cells[0]

    def test_summary_leading_flatten(self):
        units = table_units_from_markdown(self.SUMMARY_LEAD)
        smash = [u for u in units if u.header_is_data]
        lead = [u for u in units if u.flattened_prose]
        assert smash
        assert lead

    def test_numbered_real_heading_not_label_flatten(self):
        md = (
            "##### 7.1 The Cost of Determinism\n"
            "\n"
            "Deterministic reduction requires a fixed evaluation order.\n"
            "This constraint limits parallelism exploitation.\n"
        )
        units = table_units_from_markdown(md)
        assert [u for u in units if u.flattened_prose] == []


class TestP4096TrailFlattenAndCiteGloss:
    """P4096R0 §5.1 / §5.4 trailing flatten; real P2300R10 column title stays quiet."""

    EMPIRICAL = (
        "| Criterion | [P2464R0](http://example/p2464r0.html)[1] Predicted claim outcome |\n"
        "| --- | --- |\n"
        "| Error channel | **(2021)** P2300R10[8 `execute(F&` `&)` has no |\n"
        "\n"
        "] provides error `set_error` channel\n"
        "\n"
        "P2300R10[8\n"
        "\n"
        "Lifecycle `execute(F&`\n"
        "\n"
        "Generic composition No generic\n"
        "\n"
        "### 5.2 The Symmetry Test\n"
    )

    SUMMARY = (
        "| Criterion | [P2464R0](http://example/p2464r0.html)[1] |\n"
        "| --- | --- |\n"
        "| **[P2300R10](http://example/p2300r10.html)****[8]** **(2026)** | **Coroutine executor** |\n"
        "\n"
        "**(2021)**\n"
        "\n"
        "Error channel `execute(F&&)` `set_error` exists; does not handle\n"
        "\n"
        "Lifecycle `execute(F&&)`\n"
        "\n"
        "| Generic composition `execute(F&&)` has none dispatch | machines |\n"
        "| --- | --- |\n"
        "| Deployed networking \"I don't None published | New. |\n"
    )

    EVIDENCE_HEADING = (
        "## 2026 evidence\n"
        "\n"
        "[P2430R0](http://example/p2430r0.pdf)[11] (Kohlhoff, 2021): compound I/O.\n"
        "\n"
        "## Ecosystem-scale validation:\n"
    )

    PROPERTY_GLOSS = (
        "| Property | Coroutine executor | [P2300R10](http://example/p2300r10.html)[8] for networking |\n"
        "| --- | --- | --- |\n"
        "| Age | P4003R0 (2026). New. | P2464R0 redirected the committee |\n"
    )

    def test_empirical_trail_flatten(self):
        units = table_units_from_markdown(self.EMPIRICAL)
        smash = [u for u in units if u.header_is_data and not u.flattened_prose]
        trail = [u for u in units if u.flattened_prose]
        assert smash
        assert trail

    def test_summary_trail_flatten(self):
        units = table_units_from_markdown(self.SUMMARY)
        trail = [u for u in units if u.flattened_prose]
        cont = [u for u in units if u.continuation_of is not None]
        assert trail
        assert cont

    def test_year_evidence_heading_flatten(self):
        units = table_units_from_markdown(self.EVIDENCE_HEADING)
        flat = [u for u in units if u.flattened_prose]
        assert flat
        assert "2026" in flat[0].cells[0]

    def test_paper_cite_column_gloss_not_flagged(self):
        units = table_units_from_markdown(self.PROPERTY_GLOSS)
        pipes = [u for u in units if u.fmt == "pipe" and not u.flattened_prose]
        assert pipes and pipes[0].header_is_data is False

    # -- #411: fixed tables must read clean, BASE smashes must still fire ----

    # HEAD 5.2: Age table and noexcept table back-to-back, both 3 columns,
    # distinct label headers. Not a continuation.
    HEAD_BACK_TO_BACK = (
        "| Property | Coroutine executor | [P2300R10](http://example/p2300r10.html)[8] for networking |\n"
        "| --- | --- | --- |\n"
        "| Age | [P4003R0](http://example/p4003r0.pdf)[4] (2026). New. | [P2464R0](http://example/p2464r0.html)[1] redirected the committee toward [P2300R10](http://example/p2300r10.html)[8] in 2021. Five years. |\n"
        "| Deployments | [Capy](http://example/capy)[6], [Corosio](http://example/corosio)[7]. | [P2470R0](http://example/p2470r0.pdf)[15]: Facebook, NVIDIA, Bloomberg - GPU dispatch, thread pools, infrastructure. |\n"
        "| Networking deployments | New. | None published. Boost.Asio and Boost.Beast - the deployed networking that the committee set aside - used the continuation model. |\n"
        "\n"
        "**The** `noexcept` **context.** Both models can reach `std::terminate` in a `noexcept` coroutine. The difference is in the trigger condition:\n"
        "\n"
        "| Property | Coroutine executor | `execution::task` ([P3552R3](http://example/p3552r3.html)[14]) |\n"
        "| --- | --- | --- |\n"
        "| What throws | `post(coroutine_handle<>)` throws `std::system_error` on scheduling failure. | `AS-EXCEPT-PTR` converts routine `error_code` to `exception_ptr`. |\n"
        "| Trigger condition | Scheduling failure on an I/O reactor. | `ECONNRESET`, `ETIMEDOUT`, `EWOULDBLOCK` - routine I/O outcomes. |\n"
        "| In a `noexcept` context | `std::terminate` on catastrophic system condition. | `std::terminate` on routine I/O. |\n"
    )

    # HEAD 5.4: comparison matrix, cite+year column labels, label column 0.
    HEAD_SUMMARY_MATRIX = (
        "| Criterion | [P2464R0](http://example/p2464r0.html)[1] (2021) | [P2300R10](http://example/p2300r10.html)[8] (2026) | Coroutine executor |\n"
        "| --- | --- | --- | --- |\n"
        "| Error channel | `execute(F&&)` has none | `set_error` exists; does not handle compound I/O results without information loss ([P2430R0](http://example/p2430r0.pdf)[11]) | Not needed; result delivered to continuation on resume |\n"
        "| Lifecycle | `execute(F&&)` has none | Structured lifecycle exists; `task` converts routine errors to exceptions ([P3552R3](http://example/p3552r3.html)[14]) | Ownership contract: resume or destroy |\n"
        "| Generic composition | `execute(F&&)` has none | Sender algorithms exist; deployed for GPU dispatch, thread pools, infrastructure | `co_await` replaces state machines |\n"
        "| Deployed networking | \"I don't know\" | None published | New. |\n"
    )

    # BASE 5.2 (#380): header and first two rows smashed into one header
    # cell. Same column count as the Age table, but not label-like.
    BASE_NOEXCEPT_SMASH = (
        "| Property | Coroutine executor | [P2300R10](http://example/p2300r10.html)[8] for networking |\n"
        "| --- | --- | --- |\n"
        "| Age | [P4003R0](http://example/p4003r0.pdf)[4] (2026). New. | [P2464R0](http://example/p2464r0.html)[1] redirected the committee toward [P2300R10](http://example/p2300r10.html)[8] |\n"
        "| Deployments | [Capy](http://example/capy)[6], [Corosio](http://example/corosio)[7]. | [P2470R0](http://example/p2470r0.pdf)[15]: Facebook, NVIDIA, Bloomberg - GPU |\n"
        "| Networking deployments | New. | None published. Boost.Asio and Boost.Beast - the |\n"
        "\n"
        "**The** `noexcept` **context.** Both models can reach `std::terminate` in a `noexcept` coroutine. The difference is in the trigger condition:\n"
        "\n"
        "| Property What throws Trigger condition | Coroutine executor `post(coroutine_handle<>)` throws `std::system_error` on scheduling failure. Scheduling failure on an I/O reactor. | `execution::task` ([P3552R3](http://example/p3552r3.html)[14]) `ECONNRESET`, `ETIMEDOUT`, `EWOULDBLOCK` - |\n"
        "| --- | --- | --- |\n"
        "| In a `noexcept` context | `std::terminate` on catastrophic system condition. |  |\n"
    )

    # BASE 5.4 (#380): cite-only header cell with a bold-cite body column 0.
    # Not a comparison matrix, so the cite still counts as data.
    BASE_SUMMARY_CITE_HEADER = (
        "| Criterion | [P2464R0](http://example/p2464r0.html)[1] |\n"
        "| --- | --- |\n"
        "| **[P2300R10](http://example/p2300r10.html)****[8]** **(2026)** | **Coroutine executor** |\n"
    )

    # #411 logic-check M2: a ``Topic | Paper`` table whose first row was
    # promoted to the header. Column 0 is label-like (a matrix by shape),
    # the header cite is cite-only, but the body column under it is cite-only
    # too, so the cite is a leftover data row and must still fire.
    TOPIC_PAPER_PROMOTED_ROW = (
        "| Error handling | [P2464R0](http://example/p2464r0.html)[1] (2021) |\n"
        "| --- | --- |\n"
        "| Lifecycle | [P2300R10](http://example/p2300r10.html)[8] (2026) |\n"
        "| Networking | [P3552R3](http://example/p3552r3.html)[14] (2025) |\n"
    )

    def test_head_back_to_back_label_headers_not_continuation(self):
        units = table_units_from_markdown(self.HEAD_BACK_TO_BACK)
        pipes = [u for u in units if u.fmt == "pipe" and not u.flattened_prose]
        assert len(pipes) == 2
        assert all(u.continuation_of is None for u in pipes)
        assert all(u.header_is_data is False for u in pipes)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_PASS

    def test_head_comparison_matrix_cite_columns_not_header_is_data(self):
        units = table_units_from_markdown(self.HEAD_SUMMARY_MATRIX)
        pipes = [u for u in units if u.fmt == "pipe" and not u.flattened_prose]
        assert pipes and pipes[0].header_is_data is False
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_PASS

    def test_base_noexcept_smash_still_continuation(self):
        units = table_units_from_markdown(self.BASE_NOEXCEPT_SMASH)
        pipes = [u for u in units if u.fmt == "pipe" and not u.flattened_prose]
        assert len(pipes) == 2
        assert pipes[1].continuation_of == pipes[0].index
        assert pipes[1].header_is_data is True

    def test_base_summary_cite_header_still_data(self):
        units = table_units_from_markdown(self.BASE_SUMMARY_CITE_HEADER)
        pipes = [u for u in units if u.fmt == "pipe" and not u.flattened_prose]
        assert pipes and pipes[0].header_is_data is True

    def test_topic_paper_promoted_row_still_header_is_data(self):
        """M2: cite-only header over a cite-only body column is data."""
        units = table_units_from_markdown(self.TOPIC_PAPER_PROMOTED_ROW)
        pipes = [u for u in units if u.fmt == "pipe" and not u.flattened_prose]
        assert pipes and pipes[0].header_is_data is True

    def test_head_p4096r0_r2_clean(self):
        """After PR #412 the converted P4096R0 has zero R2 findings."""
        p = Path("data/paperstore/p4096r0.md")
        if not p.exists():
            pytest.skip("corpus file not available")
        md = p.read_text(encoding="utf-8")
        units = table_units_from_markdown(md)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_PASS, [
            f.message for f in report.result("R2").findings
        ]


class TestLabelLikeCell:
    """#411 predicate: narrows two R2 branches, never fires a flag itself."""

    @pytest.mark.parametrize(
        ("cell", "expected"),
        [
            ("Property", True),
            ("Coroutine executor", True),
            ("`execution::task` ([P3552R3](http://example/p3552r3.html)[14])", True),
            ("Criterion", True),
            ("Error channel", True),
            ("Generic composition", True),
            # locks: data cells that must stay data
            ("de Wever, Mark", False),
            ("NEN", False),
            ("Property What throws Trigger condition", False),
            ("[Boost.Capy](http://example/capy)", False),
            ("Returns `p_->continuation()`", False),
            ("`submdspan(md, range_slice{0, 10, stride})`", False),
            ("**[P2300R10](http://example/p2300r10.html)****[8]** **(2026)**", False),
            ("[P0285R0](http://example/p0285r0.html)[14] (2016)", False),
            ("P2300R10 for networking", False),
            ("New.", False),
            ("", False),
        ],
    )
    def test_label_like(self, cell, expected):
        from whisker.det.llm_readability.validate import _is_label_like_cell

        assert _is_label_like_cell(cell) is expected

    @pytest.mark.parametrize(
        ("cell", "expected"),
        [
            ("[P2464R0](http://example/p2464r0.html)[1] (2021)", True),
            ("[P0285R0](http://example/p0285r0.html)[14] (2016)", True),
            ("P2300R10[8] for networking", False),
            ("[P2464R0](http://example/p2464r0.html)[1] Predicted claim outcome", False),
            ("Criterion", False),
        ],
    )
    def test_cite_only(self, cell, expected):
        from whisker.det.llm_readability.validate import _paper_cite_only_cell

        assert _paper_cite_only_cell(cell) is expected

    @pytest.mark.parametrize(
        ("cell", "expected"),
        [
            ("Criterion", None),
            ("[P2464R0](http://example/p2464r0.html)[1] (2021)", []),
            ("P2300R10[8] for networking", ["for", "networking"]),
            ("P2464R0 Predicted claim outcome", ["Predicted", "claim", "outcome"]),
        ],
    )
    def test_cite_leftover_words(self, cell, expected):
        from whisker.det.llm_readability.validate import _paper_cite_leftover_words

        assert _paper_cite_leftover_words(cell) == expected

    @pytest.mark.parametrize(
        ("cells", "expected"),
        [
            (("Property", "Coroutine executor", "`execution::task`"), True),
            (("Criterion", "[P2464R0](http://x)[1] (2021)"), False),
            (("`cobalt`", "`coroutine_handle<>`"), False),
            (("", "Name", "National Body"), True),
            (("de Wever, Mark", "ANSI"), False),
            (("", ""), False),
            ((), False),
        ],
    )
    def test_label_header(self, cells, expected):
        from whisker.det.llm_readability.validate import _is_label_header

        assert _is_label_header(cells) is expected


class TestWordingClauseDetection:
    """R2 must detect numbered wording paragraphs rendered as a pipe table."""

    FACET = (
        "| 1 | A type `T` models `allowed_semantics_label` if it is an "
        "allowed-semantics control | type([basic.contract.control]). |\n"
        "| --- | --- | --- |\n"
        "| 2 | [*Note*: Combined assertion-control objects intersect the "
        "allowed semantics sets of their | constituents. *— end* *note*] |\n"
    )

    STRAW_POLL = (
        "| SF | F | N | A | SA |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| 8 | 3 | 1 | 0 | 0 |\n"
    )

    KEY_VALUE = (
        "| Document | P3400R3 |\n"
        "| --- | --- |\n"
        "| Date | 2024-01-15 |\n"
    )

    SINGLE_ROW = (
        "| 1 | A type `T` models `allowed_semantics_label` if it is an "
        "allowed-semantics control type([basic.contract.control]). |\n"
        "| --- | --- |\n"
    )

    def test_facet_flags_wording_clause(self):
        units = table_units_from_markdown(self.FACET)
        assert units
        assert units[0].wording_clause is True

    def test_facet_fails_r2(self):
        units = table_units_from_markdown(self.FACET)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_FAIL
        findings = report.result("R2").findings
        assert any(
            "numbered wording paragraphs rendered as pipe table" in f.message
            for f in findings
        )

    def test_straw_poll_not_flagged(self):
        units = table_units_from_markdown(self.STRAW_POLL)
        assert units
        assert units[0].wording_clause is False

    def test_key_value_not_flagged(self):
        units = table_units_from_markdown(self.KEY_VALUE)
        assert units
        assert units[0].wording_clause is False

    def test_single_row_not_flagged(self):
        units = table_units_from_markdown(self.SINGLE_ROW)
        assert units
        assert units[0].wording_clause is False


class TestTrailingRowLeakDetection:
    """R2 must flag when a multi-column pipe table leaks trailing rows into prose."""

    # N.6 in P4016R0: 4-column, 3 body rows, 4th row leaked
    LEAKED_MULTI_COL = (
        "| Thread | Chunks | Blocks | Output |\n"
        "| --- | --- | --- | --- |\n"
        "| 0 | 0-1 | [0, 256) | Two buckets at level 7, merged locally |\n"
        "| 1 | 2-3 | [256, 512) | Two buckets at level 7, merged locally |\n"
        "| 2 | 4-5 | [512, 768) | Two buckets at level 7, merged locally |\n"
        "\n"
        "3 6-7 [768, 1000) Bucket at level 7 + remainder (104 blocks)\n"
    )

    CLEAN_MULTI_COL = (
        "| Thread | Chunks | Blocks | Output |\n"
        "| --- | --- | --- | --- |\n"
        "| 0 | 0-1 | [0, 256) | Two buckets |\n"
        "| 1 | 2-3 | [256, 512) | Two buckets |\n"
        "| 2 | 4-5 | [512, 768) | Two buckets |\n"
        "\n"
        "The algorithm proceeds by iterating over each element.\n"
    )

    TWO_COL_TABLE = (
        "| Name | Value |\n"
        "| --- | --- |\n"
        "| Alpha | 1 |\n"
        "| Beta | 2 |\n"
        "\n"
        "3 Some extra text here after the table\n"
    )

    def test_leaked_row_flags_trailing_row_leak(self):
        units = table_units_from_markdown(self.LEAKED_MULTI_COL)
        assert len(units) >= 1
        assert units[0].trailing_row_leak is True

    def test_clean_prose_not_flagged(self):
        units = table_units_from_markdown(self.CLEAN_MULTI_COL)
        assert len(units) >= 1
        assert units[0].trailing_row_leak is False

    def test_two_col_excluded(self):
        """trailing_row_leak requires >= 3 columns (two-col uses truncated_leak)."""
        units = table_units_from_markdown(self.TWO_COL_TABLE)
        for u in units:
            assert u.trailing_row_leak is False

    def test_trailing_row_leak_fails_r2(self):
        units = table_units_from_markdown(self.LEAKED_MULTI_COL)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_FAIL
        assert any(
            "leaked into prose" in f.message
            for f in report.result("R2").findings
        )


class TestD3PartialTableCoveredByExistingHelpers:
    """D.3 (P4016R0) is already covered: no new interleaved_prose_row helper.

    The smashed header becomes ``header_is_data`` and the trailing prose
    row fires ``truncated_leak`` (one-body-row path). Adding a fourth
    helper would duplicate those locks.
    """

    D3 = (
        "##### Property Sequential (accumulate/fold_left) Parallel (reduce)\n"
        "\n"
        "Standard Section [accumulate] / [alg.fold] [reduce]\n"
        "\n"
        "| Grouping | Mandated: Left-to-right | Generalized Sum (Unspecified) |\n"
        "| --- | --- | --- |\n"
        "| Complexity | O(N) operations | O(N) operations |\n"
        "\n"
        "Evaluation Order Fully specified Not specified\n"
    )

    def test_d3_fires_existing_flags(self):
        units = table_units_from_markdown(self.D3)
        flagged = [
            u for u in units
            if u.header_is_data or u.truncated_leak or u.flattened_prose
        ]
        assert flagged, "D.3 partial table produced no existing R2 flag"


class TestHeadingShatteredDetection:
    """R2 must flag when column headers become consecutive ATX headings."""

    # N.14 in P4016R0: headers shattered into ##### lines
    SHATTERED_HEADINGS = (
        "##### Property Guarantee\n"
        "\n"
        "##### Determinism\n"
        "\n"
        "Expression-identical to the single-threaded canonical expression.\n"
        "\n"
        "| Correctness | Equivalent to the canonical pairwise tree |\n"
        "| --- | --- |\n"
        "| **Efficiency** | O(N) work |\n"
    )

    NORMAL_HEADINGS = (
        "##### 7.1 Introduction\n"
        "\n"
        "##### 7.2 Background\n"
        "\n"
        "This section describes the approach.\n"
    )

    SINGLE_HEADING = (
        "##### Property Guarantee\n"
        "\n"
        "The algorithm is correct.\n"
    )

    def test_shattered_detected_as_flattened(self):
        units = table_units_from_markdown(self.SHATTERED_HEADINGS)
        flat = [u for u in units if u.flattened_prose]
        assert len(flat) >= 1, "heading-shattered table not detected"

    def test_chapter_numbered_headings_ignored(self):
        units = table_units_from_markdown(self.NORMAL_HEADINGS)
        flat = [u for u in units if u.flattened_prose]
        assert flat == [], f"false positive on chapter headings: {flat}"

    def test_single_heading_not_flagged(self):
        units = table_units_from_markdown(self.SINGLE_HEADING)
        flat = [u for u in units if u.flattened_prose]
        assert flat == [], "single heading should not trigger shatter"


class TestAbsorbedProseDetection:
    """R2 must flag when a body row has extreme token count vs siblings."""

    # K.1 in P4016R0: multiple demonstrators merged into one mega-row
    MEGA_ROW = (
        "| Demonstrator | Platform | Purpose | Arbitrary | Notes |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| GB-SEQ single-thread reference | Portable | ref | no | base |\n"
        "| GB-x86-AVX2 single-file x86 GB-x86-MT multi-threaded x86 "
        "GB-x86-MT-PERF multi-threaded perf GB-x86-MT-EXT extended "
        "correctness GB-NEON single-file NEON GB-NEON-PERF NEON performance "
        "GB-CUDA optional CUDA CUB comparison | x86-64 standard accumulate "
        "and reduce Deterministic multi threaded 870 hostile bitwise "
        "comparisons five generators twenty nine awkward sizes three thread "
        "counts Canonical reduction on AArch64 No std plus double only "
        "Illustrates canonical topology evaluation on GPU | lots of words "
        "here about purpose describing multiple demonstrators merged into "
        "one single cell row that has lots and lots of tokens | No and yes "
        "| many notes |\n"
    )

    EVEN_ROWS = (
        "| A | B | C |\n"
        "| --- | --- | --- |\n"
        "| word word word word word word | word word word | word word |\n"
        "| word word word word word | word word word word | word word word |\n"
    )

    SINGLE_BODY_ROW = (
        "| A | B | C |\n"
        "| --- | --- | --- |\n"
        "| very many words in this cell to see what happens when there is "
        "only one body row but it is very long indeed with lots of tokens |\n"
    )

    def test_mega_row_flags_absorbed(self):
        units = table_units_from_markdown(self.MEGA_ROW)
        assert len(units) >= 1
        assert units[0].absorbed_prose_row is True

    def test_even_rows_not_flagged(self):
        units = table_units_from_markdown(self.EVEN_ROWS)
        for u in units:
            assert u.absorbed_prose_row is False

    def test_single_body_row_not_flagged(self):
        """Need >= 2 body rows to compute sibling comparison."""
        units = table_units_from_markdown(self.SINGLE_BODY_ROW)
        for u in units:
            assert u.absorbed_prose_row is False

    # K.1 shape: collapsed mega-row promoted to the GFM header
    MEGA_HEADER = (
        "| GB-x86-AVX2 single-file x86 GB-x86-MT multi-threaded x86 "
        "GB-x86-MT-PERF multi-threaded perf GB-x86-MT-EXT extended "
        "correctness GB-NEON single-file NEON GB-NEON-PERF NEON performance "
        "GB-CUDA optional CUDA CUB comparison | x86-64 standard accumulate "
        "and reduce Deterministic multi threaded 870 hostile bitwise "
        "comparisons five generators twenty nine awkward sizes three thread "
        "counts Canonical reduction on AArch64 No std plus double only "
        "Illustrates canonical topology evaluation on GPU |\n"
        "| --- | --- |\n"
        "| short | note |\n"
        "| also | brief |\n"
    )

    def test_mega_header_flags_absorbed(self):
        units = table_units_from_markdown(self.MEGA_HEADER)
        assert any(u.absorbed_prose_row for u in units)

    def test_absorbed_prose_fails_r2(self):
        units = table_units_from_markdown(self.MEGA_ROW)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_FAIL
        assert any(
            "absorbed prose" in f.message
            for f in report.result("R2").findings
        )


class TestNewFlagsControlPapers:
    """New flags must not false-positive on control papers."""

    def test_p0876r23_no_new_flags(self):
        from pathlib import Path

        p = Path("data/paperstore/p0876r23.md")
        if not p.exists():
            pytest.skip("corpus file not available")
        md = p.read_text(encoding="utf-8")
        units = table_units_from_markdown(md)
        flagged = [
            u for u in units
            if (
                u.header_is_data or u.truncated_leak or u.row_merge
                or u.wrap_orphan or u.hyphen_glue or u.flattened_prose
                or u.wording_clause or u.trailing_row_leak
                or u.absorbed_prose_row
            )
        ]
        assert flagged == [], (
            f"false positive on T{[u.index for u in flagged]}"
        )

    def test_p3596r0_no_new_flags(self):
        from pathlib import Path

        p = Path("data/paperstore/p3596r0.md")
        if not p.exists():
            pytest.skip("corpus file not available")
        md = p.read_text(encoding="utf-8")
        units = table_units_from_markdown(md)
        flagged = [
            u for u in units
            if (
                u.header_is_data or u.truncated_leak or u.row_merge
                or u.wrap_orphan or u.hyphen_glue or u.flattened_prose
                or u.wording_clause or u.trailing_row_leak
                or u.absorbed_prose_row
            )
        ]
        assert flagged == [], (
            f"false positive on T{[u.index for u in flagged]}"
        )

    def test_fixed_n5040_no_new_flags(self):
        from pathlib import Path

        p = Path("data/paperstore/n5040.md")
        if not p.exists():
            pytest.skip("corpus file not available")
        md = p.read_text(encoding="utf-8")
        units = table_units_from_markdown(md)
        flagged = [
            u for u in units
            if (
                u.header_is_data or u.truncated_leak or u.row_merge
                or u.wrap_orphan or u.hyphen_glue or u.flattened_prose
                or u.wording_clause or u.trailing_row_leak
                or u.absorbed_prose_row
            )
        ]
        assert flagged == [], (
            f"false positive on T{[u.index for u in flagged]}"
        )


class TestTableReadabilityFlagsDoNotGate:
    """New flags must be report-only: verdicts unchanged when flags fire."""

    def test_trailing_row_leak_does_not_change_verdict_category(self):
        """R2 already fails from the header defect; adding trailing_row_leak
        does not make it worse-than-FAIL or promote REVIEW to FAIL."""
        md = (
            "| Thread | Chunks | Blocks | Output |\n"
            "| --- | --- | --- | --- |\n"
            "| 0 | 0-1 | [0, 256) | Two buckets |\n"
            "| 1 | 2-3 | [256, 512) | Two buckets |\n"
            "| 2 | 4-5 | [512, 768) | Two buckets |\n"
            "\n"
            "3 6-7 [768, 1000) Bucket at level 7 + remainder\n"
        )
        units = table_units_from_markdown(md)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status in (STATUS_FAIL, STATUS_REVIEW)

    def test_absorbed_prose_does_not_change_verdict_category(self):
        md = (
            "| Demonstrator | Platform | Purpose | Arbitrary | Notes |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| GB-SEQ ref | Portable | ref | no | base |\n"
            "| GB-x86 GB-MT GB-PERF GB-EXT GB-NEON GB-NEON-PERF GB-CUDA "
            "optional CUDA CUB comparison | x86-64 standard accumulate "
            "Deterministic multi 870 hostile bitwise comparisons generators "
            "twenty nine awkward sizes thread counts AArch64 No std plus "
            "double only topology GPU CUB reduction | lots of words purpose "
            "multiple demonstrators merged one cell row lots tokens | No | n |\n"
        )
        units = table_units_from_markdown(md)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status in (STATUS_FAIL, STATUS_REVIEW)

    def test_clean_table_still_passes(self):
        """A clean pipe table must still be R2-pass with the new code."""
        md = (
            "| Name | Value | Description |\n"
            "| --- | --- | --- |\n"
            "| Alpha | 1 | First item |\n"
            "| Beta | 2 | Second item |\n"
        )
        units = table_units_from_markdown(md)
        report = evaluate(resolved_core_only(), units)
        assert report.result("R2").status == STATUS_PASS


class TestReportRendering:
    def test_report_dict_is_json_serializable(self):
        report = evaluate(resolved_core_only(), clean_units())
        payload = json.loads(json.dumps(report_to_dict(report)))
        assert payload["contract_version"] == load_core_contract().version
        assert payload["model_certified"] is False
        assert payload["certified"] is False
        assert len(payload["rules"]) == 14

    def test_status_counts_cover_every_rule(self):
        report = evaluate(resolved_core_only(), clean_units())
        assert sum(status_counts(report).values()) == 14

    def test_markdown_report_states_the_contract_and_the_verdict(self):
        report = evaluate(resolved_core_only(), clean_units())
        rendered = render_markdown(report)
        assert f"- verdict: {report.verdict}" in rendered
        assert "model certified: no" in rendered
        assert load_core_contract().hash in rendered

    def test_markdown_report_is_byte_stable(self):
        first = render_markdown(evaluate(resolved_core_only(), clean_units()))
        second = render_markdown(evaluate(resolved_core_only(), clean_units()))
        assert first == second


class TestCliSurface:
    def test_rules_lists_the_contract(self, capsys):
        assert table_cli.main(["rules"]) == table_cli.EXIT_OK
        out = capsys.readouterr().out
        assert "| R13 |" in out
        assert load_core_contract().hash in out

    def test_rules_rubric_carries_the_profile(self, capsys):
        code = table_cli.main(["rules", "--profile", DEEPSEEK_PROFILE_ID, "--rubric"])
        assert code == table_cli.EXIT_OK
        assert load_profile(DEEPSEEK_PROFILE_ID).hash in capsys.readouterr().out

    def test_rules_json_is_parseable(self, capsys):
        assert table_cli.main(["rules", "--json"]) == table_cli.EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert len(payload["rules"]) == 14

    def test_profiles_lists_deepseek(self, capsys):
        assert table_cli.main(["profiles"]) == table_cli.EXIT_OK
        assert DEEPSEEK_PROFILE_ID in capsys.readouterr().out

    def test_profiles_prints_the_profile_hash(self, capsys):
        """A report's profile fingerprint has to be traceable to a directory."""
        assert table_cli.main(["profiles"]) == table_cli.EXIT_OK
        out = capsys.readouterr().out
        profile = load_profile(DEEPSEEK_PROFILE_ID)
        assert f"sha256:{profile.hash}" in out
        assert f"v{profile.version}" in out
        assert profile.certification_status in out

    def test_unknown_profile_exits_with_an_error(self, capsys):
        assert table_cli.main(["rules", "--profile", "ghost"]) == table_cli.EXIT_ERROR
        assert "profile_missing" in capsys.readouterr().err

    def test_check_on_a_clean_candidate_reports_review(self, tmp_path, capsys):
        candidate = tmp_path / "candidate.md"
        candidate.write_text(TestMarkdownAdapterIsHonest.MARKDOWN, encoding="utf-8")
        code = table_cli.main(["check", str(candidate)])
        assert code == table_cli.EXIT_REVIEW
        assert "model certified: no" in capsys.readouterr().out

    def test_check_on_a_broken_table_fails(self, tmp_path, capsys):
        candidate = tmp_path / "broken.md"
        candidate.write_text(
            "| Option | Votes | Notes |\n|---|---|---|\n| SF | 4 |\n",
            encoding="utf-8",
        )
        assert table_cli.main(["check", str(candidate)]) == table_cli.EXIT_FAIL
        assert "- verdict: not-llm-readable" in capsys.readouterr().out

    def test_check_on_a_table_free_candidate_is_ok(self, tmp_path, capsys):
        candidate = tmp_path / "prose.md"
        candidate.write_text("# Paper\n\nNo tables here.\n", encoding="utf-8")
        assert table_cli.main(["check", str(candidate)]) == table_cli.EXIT_OK
        assert "vacuous" in capsys.readouterr().out

    def test_check_json_reports_the_blocking_reasons(self, tmp_path, capsys):
        candidate = tmp_path / "candidate.md"
        candidate.write_text(TestMarkdownAdapterIsHonest.MARKDOWN, encoding="utf-8")
        assert table_cli.main(["check", str(candidate), "--json"]) in (
            table_cli.EXIT_REVIEW,
            table_cli.EXIT_FAIL,
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload["model_certified"] is False
        assert payload["blocking_reasons"]

    def test_missing_file_is_an_operational_error(self, tmp_path, capsys):
        missing = tmp_path / "nope.md"
        assert table_cli.main(["check", str(missing)]) == table_cli.EXIT_ERROR
        assert "error:" in capsys.readouterr().err
