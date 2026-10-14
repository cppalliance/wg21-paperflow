#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Foundation tests for the whisker codeblock LLM-readability contract.

Guards the properties that make C1-C10 trustworthy:

- the rule set is exactly C1-C10, uniquely identified and uniquely checked;
- the codeblock contract loads from its own construct directory without
  colliding with the tables contract;
- rubric names every C-rule;
- deterministic checks fire on fixture data;
- no ``llm`` import touches the ``llm_readability`` package;
- existing 13-rule table tests stay green (run the full suite to verify).
"""

from __future__ import annotations

import copy
import json
import sys
import tomllib
from importlib import resources
from pathlib import Path

import pytest
from whisker.det.llm_readability import (
    CONSTRUCT_CODEBLOCKS,
    CONSTRUCT_TABLES,
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
    CodeUnit,
    ContractSchemaError,
    ResolvedContract,
    TableReadabilityReport,
)
from whisker.det.llm_readability.code_validate import (
    CODE_APPLICABILITY_PREDICATES,
    DETERMINISTIC_CODE_CHECKS,
    code_units_from_markdown,
    code_units_with_spans,
    default_code_registry,
    evaluate_code,
)
from whisker.det.llm_readability.contract import (
    CONTRACT_PACKAGE,
    DEFAULT_PROFILE_ID,
    EXPECTED_CODE_RULE_COUNT,
    RULES_RESOURCE_NAME,
    canonical_hash,
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
    METHOD_SOURCE_COMPARE,
)
from whisker.det.llm_readability.profile import (
    load_combined,
    load_profile,
    resolve_contract,
    resolved_core_only,
)
from whisker.det.llm_readability.report import (
    render_markdown,
    report_to_dict,
    status_counts,
)

DEEPSEEK_PROFILE_ID = "deepseek-v4"
CODE_RULE_IDS = tuple(f"C{n}" for n in range(1, 11))


# -- fixtures and helpers ------------------------------------------------------


@pytest.fixture(scope="module")
def code_core():
    return load_core_contract(CONSTRUCT_CODEBLOCKS)


@pytest.fixture
def code_core_data() -> dict:
    """A mutable copy of the parsed codeblock contract data."""
    return copy.deepcopy(tomllib.loads(core_contract_text(CONSTRUCT_CODEBLOCKS)))


def _clean_fence_units() -> tuple[CodeUnit, ...]:
    """One well-formed fenced code block for a passing candidate."""
    return (
        CodeUnit(
            index=0,
            lang="cpp",
            body_lines=("int main() {", '  return 0;', "}"),
            fence_style="backtick",
        ),
    )


def _resolved_code() -> ResolvedContract:
    return resolved_core_only(CONSTRUCT_CODEBLOCKS)


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "SERVICES.toml").is_file():
            return parent
    raise AssertionError("could not find SERVICES.toml")


# -- construct isolation -------------------------------------------------------


class TestConstructIsolation:
    """Tables and codeblocks load from separate construct directories."""

    def test_codeblocks_rules_toml_loads_as_package_resource(self):
        resource = (
            resources.files(CONTRACT_PACKAGE)
            / DEFAULT_PROFILE_ID
            / "codeblocks"
            / RULES_RESOURCE_NAME
        )
        assert resource.is_file()
        text = resource.read_text(encoding="utf-8")
        assert "[contract]" in text
        assert "C1" in text

    def test_tables_resource_still_loads(self):
        resource = (
            resources.files(CONTRACT_PACKAGE)
            / DEFAULT_PROFILE_ID
            / "tables"
            / RULES_RESOURCE_NAME
        )
        assert resource.is_file()
        text = resource.read_text(encoding="utf-8")
        assert "R1" in text

    def test_code_contract_id_differs_from_table_contract_id(self):
        code = load_core_contract(CONSTRUCT_CODEBLOCKS)
        table = load_core_contract(CONSTRUCT_TABLES)
        assert code.id != table.id
        assert code.hash != table.hash

    def test_code_contract_has_10_rules_table_has_14(self):
        code = load_core_contract(CONSTRUCT_CODEBLOCKS)
        table = load_core_contract(CONSTRUCT_TABLES)
        assert len(code.rules) == EXPECTED_CODE_RULE_COUNT
        assert len(table.rules) == 14

    def test_construct_constants_are_distinct(self):
        assert CONSTRUCT_TABLES == "tables"
        assert CONSTRUCT_CODEBLOCKS == "codeblocks"
        assert CONSTRUCT_TABLES != CONSTRUCT_CODEBLOCKS


# -- the C-rule set ------------------------------------------------------------


class TestCodeRuleSet:
    def test_rules_are_exactly_c1_through_c10_in_order(self, code_core):
        assert code_core.rule_ids == CODE_RULE_IDS
        assert len(code_core.rules) == EXPECTED_CODE_RULE_COUNT

    def test_rule_ids_are_unique(self, code_core):
        assert len(set(code_core.rule_ids)) == len(code_core.rule_ids)

    def test_check_ids_are_unique(self, code_core):
        check_ids = [rule.check_id for rule in code_core.rules]
        assert len(set(check_ids)) == len(check_ids)

    def test_every_rule_carries_prose_instruction_and_evidence(self, code_core):
        for rule in code_core.rules:
            assert rule.requirement.strip()
            assert rule.rationale.strip()
            assert rule.llm_instruction.strip()
            assert rule.evidence, f"{rule.id} cites no evidence"

    def test_hard_rules_fail_and_contextual_rules_review(self, code_core):
        for rule in code_core.rules:
            expected = STATUS_FAIL if rule.strength == STRENGTH_HARD else STATUS_REVIEW
            assert rule.failure_status == expected, rule.id

    def test_both_strengths_are_actually_used(self, code_core):
        strengths = {rule.strength for rule in code_core.rules}
        assert strengths == {STRENGTH_HARD, STRENGTH_CONTEXTUAL}

    def test_every_declared_applicability_has_a_predicate(self, code_core):
        assert set(code_core.applicability) == set(CODE_APPLICABILITY_PREDICATES)

    def test_every_threshold_is_consumed_by_a_declared_rule(self, code_core):
        rules_by_id = {rule.id: rule for rule in code_core.rules}
        for name, threshold in code_core.thresholds.items():
            assert threshold.rules, f"threshold {name} is consumed by nothing"
            for rule_id in threshold.rules:
                assert rule_id in rules_by_id
                assert name in rules_by_id[rule_id].thresholds

    def test_rule_threshold_references_resolve(self, code_core):
        for rule in code_core.rules:
            for name in rule.thresholds:
                assert name in code_core.thresholds

    def test_every_rule_points_at_its_researched_source(self, code_core):
        for rule in code_core.rules:
            pointer = f"SYNTHESIS.md:{rule.id}"
            assert any(pointer in item for item in rule.evidence), (
                f"{rule.id} cites no researched source ({pointer})"
            )

    def test_cited_evidence_files_exist(self, code_core):
        root = _repo_root()
        for rule in code_core.rules:
            for item in rule.evidence:
                if "/" not in item:
                    continue
                path_part = item.split(":", 1)[0]
                assert (root / path_part).is_file(), (
                    f"{rule.id}: cited evidence {item!r} no longer exists"
                )

    def test_registered_checks_belong_to_a_declared_rule(self, code_core):
        declared = {rule.check_id for rule in code_core.rules}
        orphans = sorted(set(DETERMINISTIC_CODE_CHECKS) - declared)
        assert not orphans, f"checks registered for no rule: {orphans}"


# -- hashes and rendering (codeblocks) ----------------------------------------


class TestCodeHashesAndRendering:
    def test_hash_is_stable_across_parses(self, code_core, code_core_data):
        assert parse_contract(code_core_data).hash == code_core.hash

    def test_hash_is_a_full_sha256(self, code_core):
        assert len(code_core.hash) == 64
        assert code_core.hash == canonical_hash(
            tomllib.loads(core_contract_text(CONSTRUCT_CODEBLOCKS))
        )

    def test_rubric_is_byte_stable(self):
        first = render_llm_rubric(_resolved_code())
        second = render_llm_rubric(_resolved_code())
        assert first == second

    def test_rubric_names_every_c_rule(self, code_core):
        rubric = render_llm_rubric(_resolved_code())
        for rule in code_core.rules:
            assert f"## {rule.id} [{rule.strength}]" in rubric
        assert code_core.version in rubric
        assert code_core.hash in rubric

    def test_rubric_does_not_name_table_rules(self):
        rubric = render_llm_rubric(_resolved_code())
        for n in range(1, 15):
            assert f"## R{n} [" not in rubric

    def test_rules_markdown_lists_every_c_rule(self, code_core):
        listing = render_rules_markdown(_resolved_code())
        for rule in code_core.rules:
            assert f"| {rule.id} |" in listing


# -- profile resolution for codeblocks ----------------------------------------


class TestCodeProfileResolution:
    def test_resolve_code_contract_returns_10_rules(self):
        resolved = resolve_contract(construct=CONSTRUCT_CODEBLOCKS)
        assert len(resolved.rules) == EXPECTED_CODE_RULE_COUNT

    def test_resolve_table_contract_still_returns_14_rules(self):
        resolved = resolve_contract(construct=CONSTRUCT_TABLES)
        assert len(resolved.rules) == 14

    def test_code_load_combined(self):
        resolved = load_combined(DEEPSEEK_PROFILE_ID, construct=CONSTRUCT_CODEBLOCKS)
        assert resolved.core is not None
        assert resolved.profile is not None
        assert len(resolved.rules) == EXPECTED_CODE_RULE_COUNT

    def test_certification_status_is_pending(self):
        profile = load_profile(DEEPSEEK_PROFILE_ID, construct=CONSTRUCT_CODEBLOCKS)
        assert profile.certification_status == CERTIFICATION_STATUS_PENDING

    def test_profile_probes_and_weaknesses_name_real_rules(self):
        core = load_core_contract(CONSTRUCT_CODEBLOCKS)
        profile = load_profile(DEEPSEEK_PROFILE_ID, construct=CONSTRUCT_CODEBLOCKS)
        assert profile.probes and profile.known_weaknesses
        for entry in (*profile.probes, *profile.known_weaknesses):
            assert entry.evidence, f"{entry.id} cites no evidence"
            for rule_id in entry.rules:
                assert rule_id in core.rule_ids


# -- fence parser --------------------------------------------------------------


class TestCodeUnitsParser:
    def test_backtick_fence_parsed(self):
        md = "```cpp\nint x = 1;\n```\n"
        units = code_units_from_markdown(md)
        assert len(units) == 1
        assert units[0].lang == "cpp"
        assert units[0].fence_style == "backtick"
        assert units[0].body_lines == ("int x = 1;",)

    def test_tilde_fence_parsed(self):
        md = "~~~python\nprint('hi')\n~~~\n"
        units = code_units_from_markdown(md)
        assert len(units) == 1
        assert units[0].lang == "python"
        assert units[0].fence_style == "tilde"

    def test_unlabeled_fence(self):
        md = "```\nsome stuff\n```\n"
        units = code_units_from_markdown(md)
        assert len(units) == 1
        assert units[0].lang == ""

    def test_multiple_fences(self):
        md = "```cpp\nint x;\n```\n\n```python\nprint(1)\n```\n"
        units = code_units_from_markdown(md)
        assert len(units) == 2
        assert units[0].index == 0
        assert units[1].index == 1

    def test_empty_fence(self):
        md = "```cpp\n\n```\n"
        units = code_units_from_markdown(md)
        assert len(units) == 1
        assert units[0].is_empty is True

    def test_fence_with_content_is_not_empty(self):
        md = "```\ncode\n```\n"
        units = code_units_from_markdown(md)
        assert units[0].is_empty is False

    def test_no_fences_returns_empty(self):
        md = "Just prose, no fences.\n"
        units = code_units_from_markdown(md)
        assert units == ()

    def test_locus_with_lang(self):
        unit = CodeUnit(index=0, lang="cpp", body_lines=("x",), fence_style="backtick")
        assert unit.locus == "fence 1 (cpp)"

    def test_locus_without_lang(self):
        unit = CodeUnit(index=2, lang="", body_lines=("x",), fence_style="tilde")
        assert unit.locus == "fence 3"


# -- code_units_with_spans: line offsets ---------------------------------------


class TestCodeUnitsWithSpans:
    def test_single_fence_offsets(self):
        md = "line0\n```cpp\nint x;\n```\nline4"
        spans = code_units_with_spans(md)
        assert len(spans) == 1
        unit, start, end = spans[0]
        assert unit.lang == "cpp"
        assert start == 1
        assert end == 3

    def test_multiple_fences_sequential(self):
        md = "```cpp\na\n```\n\n```python\nb\n```\n"
        spans = code_units_with_spans(md)
        assert len(spans) == 2
        assert spans[0][1] == 0
        assert spans[0][2] == 2
        assert spans[1][1] == 4
        assert spans[1][2] == 6

    def test_no_fences(self):
        assert code_units_with_spans("no code here") == ()

    def test_units_match_code_units_from_markdown(self):
        md = "# Title\n```cpp\nint x;\n```\n```\nfoo\n```\n"
        units = code_units_from_markdown(md)
        spans = code_units_with_spans(md)
        assert tuple(u for u, _, _ in spans) == units


# -- evaluation: vacuous document ----------------------------------------------


class TestCodeVacuousDocument:
    def test_no_fence_is_not_applicable(self):
        report = evaluate_code(_resolved_code(), ())
        assert report.vacuous is True
        assert report.verdict == VERDICT_NOT_APPLICABLE
        assert report.document_deterministic_ok is False
        assert "vacuous" in report.blocking_reasons

    def test_fence_scoped_rules_are_not_applicable_when_no_fences(self):
        report = evaluate_code(_resolved_code(), ())
        statuses = report.statuses()
        for rule_id in ("C2", "C9"):
            assert statuses[rule_id] == STATUS_NOT_APPLICABLE, rule_id


# -- evaluation: deterministic checks fire -------------------------------------


class TestCodeDeterministicChecks:
    def test_clean_candidate_is_deterministically_ok(self):
        report = evaluate_code(_resolved_code(), _clean_fence_units())
        assert report.document_deterministic_ok is True
        assert report.model_certified is False

    def test_verdict_is_incomplete_while_source_rules_are_unproven(self):
        report = evaluate_code(_resolved_code(), _clean_fence_units())
        assert report.verdict == VERDICT_INCOMPLETE
        unproven = {
            rule_id
            for rule_id, status in report.statuses().items()
            if status == STATUS_NOT_EVALUATED
        }
        assert {"C3", "C4", "C5", "C10"} <= unproven

    def test_empty_fence_fails_c2(self):
        empty = (
            CodeUnit(index=0, lang="cpp", body_lines=("",), fence_style="backtick"),
        )
        report = evaluate_code(_resolved_code(), empty)
        assert report.result("C2").status == STATUS_FAIL
        assert report.result("C2").findings
        assert report.verdict == VERDICT_FAIL

    def test_non_empty_fence_passes_c2(self):
        report = evaluate_code(_resolved_code(), _clean_fence_units())
        assert report.result("C2").status == STATUS_PASS

    def test_wording_div_fails_c6(self):
        md = ":::wording\nsome text\n:::\n\n```cpp\nint x;\n```\n"
        units = code_units_from_markdown(md)
        report = evaluate_code(_resolved_code(), units, markdown_text=md)
        assert report.result("C6").status == STATUS_FAIL
        assert any("wording div" in f.message for f in report.result("C6").findings)

    def test_no_wording_div_passes_c6(self):
        md = "```cpp\nint x;\n```\n"
        units = code_units_from_markdown(md)
        report = evaluate_code(_resolved_code(), units, markdown_text=md)
        assert report.result("C6").status == STATUS_PASS

    def test_spec_element_in_fence_fails_c7(self):
        bad = (
            CodeUnit(
                index=0,
                lang="cpp",
                body_lines=("Effects: does something",),
                fence_style="backtick",
            ),
        )
        report = evaluate_code(_resolved_code(), bad)
        assert report.result("C7").status == STATUS_FAIL
        assert any("spec-element" in f.message for f in report.result("C7").findings)

    def test_code_in_fence_passes_c7(self):
        report = evaluate_code(_resolved_code(), _clean_fence_units())
        assert report.result("C7").status == STATUS_PASS

    def test_c8_always_passes(self):
        report = evaluate_code(_resolved_code(), _clean_fence_units())
        assert report.result("C8").status == STATUS_PASS

    def test_diagram_in_cpp_fence_reviews_c9(self):
        diagram = (
            CodeUnit(
                index=0,
                lang="cpp",
                body_lines=(
                    "┌──────┐",
                    "│ node │",
                    "└──────┘",
                ),
                fence_style="backtick",
            ),
        )
        report = evaluate_code(_resolved_code(), diagram)
        assert report.result("C9").status == STATUS_REVIEW
        assert any("box-drawing" in f.message for f in report.result("C9").findings)

    def test_real_cpp_in_cpp_fence_passes_c9(self):
        report = evaluate_code(_resolved_code(), _clean_fence_units())
        assert report.result("C9").status == STATUS_PASS

    def test_ascii_art_pipe_table_in_cpp_fence_reviews_c9(self):
        ascii_art = (
            CodeUnit(
                index=0,
                lang="cpp",
                body_lines=(
                    "+-------+-------+",
                    "| col1  | col2  |",
                    "+-------+-------+",
                ),
                fence_style="backtick",
            ),
        )
        report = evaluate_code(_resolved_code(), ascii_art)
        assert report.result("C9").status == STATUS_REVIEW


# -- certification cannot be faked ---------------------------------------------


class TestCodeCertification:
    def test_missing_required_method_blocks_certification(self):
        resolved = resolve_contract(construct=CONSTRUCT_CODEBLOCKS)
        report = evaluate_code(
            resolved,
            _clean_fence_units(),
            methods_executed=(METHOD_DETERMINISTIC,),
        )
        assert report.model_certified is False
        assert any(
            reason.startswith("required_method_not_executed:")
            for reason in report.blocking_reasons
        )

    def test_registered_lane_checks_close_their_rules(self):
        core = load_core_contract(CONSTRUCT_CODEBLOCKS)
        registry = default_code_registry()
        for rule in core.rules:
            registry.setdefault(
                rule.check_id, lambda ctx: CheckOutcome(status=STATUS_PASS)
            )
        report = evaluate_code(
            resolve_contract(construct=CONSTRUCT_CODEBLOCKS),
            _clean_fence_units(),
            methods_executed=(
                METHOD_DETERMINISTIC,
                METHOD_SOURCE_COMPARE,
                METHOD_CERTIFICATION,
            ),
            source_available=True,
            registry=registry,
        )
        assert report.blocking_reasons == ()
        assert report.model_certified is True
        assert report.document_deterministic_ok is True

    def test_a_check_may_not_invent_a_status_the_rule_forbids(self):
        registry = default_code_registry()
        registry["empty_fence"] = lambda ctx: CheckOutcome(status=STATUS_REVIEW)
        with pytest.raises(ContractSchemaError, match="does not allow"):
            evaluate_code(_resolved_code(), _clean_fence_units(), registry=registry)


# -- report rendering ----------------------------------------------------------


class TestCodeReportRendering:
    def test_report_dict_is_json_serializable(self):
        report = evaluate_code(_resolved_code(), _clean_fence_units())
        payload = json.loads(json.dumps(report_to_dict(report)))
        assert payload["model_certified"] is False
        assert len(payload["rules"]) == EXPECTED_CODE_RULE_COUNT

    def test_status_counts_cover_every_rule(self):
        report = evaluate_code(_resolved_code(), _clean_fence_units())
        assert sum(status_counts(report).values()) == EXPECTED_CODE_RULE_COUNT

    def test_markdown_report_states_the_verdict(self):
        report = evaluate_code(_resolved_code(), _clean_fence_units())
        rendered = render_markdown(report)
        assert f"- verdict: {report.verdict}" in rendered
        assert "model certified: no" in rendered


# -- CLI surface ---------------------------------------------------------------


class TestCodeCliSurface:
    def test_rules_codeblocks_lists_c_rules(self, capsys):
        from whisker.det.llm_readability import cli as table_cli

        assert table_cli.main(["rules", "--construct", "codeblocks"]) == table_cli.EXIT_OK
        out = capsys.readouterr().out
        assert "| C10 |" in out
        assert "| R1 |" not in out

    def test_check_codeblocks_on_clean_candidate(self, tmp_path, capsys):
        from whisker.det.llm_readability import cli as table_cli

        candidate = tmp_path / "candidate.md"
        candidate.write_text("```cpp\nint x = 1;\n```\n", encoding="utf-8")
        code = table_cli.main(["check", str(candidate), "--construct", "codeblocks"])
        assert code in (table_cli.EXIT_OK, table_cli.EXIT_REVIEW)

    def test_check_codeblocks_on_empty_fence_fails(self, tmp_path, capsys):
        from whisker.det.llm_readability import cli as table_cli

        candidate = tmp_path / "broken.md"
        candidate.write_text("```cpp\n\n```\n", encoding="utf-8")
        assert (
            table_cli.main(["check", str(candidate), "--construct", "codeblocks"])
            == table_cli.EXIT_FAIL
        )
        assert "- verdict: not-llm-readable" in capsys.readouterr().out


# -- calibration fixtures (PR 394 defect classes) -----------------------------
#
# Inline snippets cut from the PR 394 archived base/head markdown.
# No corpus dependency: these are self-contained regression fixtures.

# BASE p0533r9: heading swallowed into cpp fence (C7)
_BASE_P0533R9_HEADING_IN_FENCE = """\
```cpp
                        F.  Modifications to "Header<cmath> synopsis" [cmath.syn]
...
namespace std{
...
float acos(float x); // see [library.c]
```
"""

# HEAD p0533r9: listing-split fragments (C1): ellipsis-only, lone constexpr,
# micro-fence run
_HEAD_P0533R9_LISTING_SPLIT = """\
```cpp
...
```

```cpp
...
```

```cpp
float acos(float x);
double acos(double x);
```

```cpp
...
constexpr
```

```cpp
float frexp(float value, int* exp);
```
"""

# BASE p2040r0: <ins>// comment</ins> inside fence (C6)
_BASE_P2040R0_FALSE_WORDING = """\
```cpp
void f(meta::info expression) requires meta::is_expression;
<ins>//constrains on the type of the expression</ins>
void f(meta::info expression) requires meta::is_expression_of<int>;
f(reflexpr("not an int")); <ins>// ko</ins>
f(reflexpr(42)); <ins>// ok</ins>
```
"""

# HEAD p2040r0: clean code with // comments (C6 should NOT fire)
_HEAD_P2040R0_CLEAN = """\
```cpp
void f(meta::info expression) requires meta::is_expression;
//constrains on the type of the expression
void f(meta::info expression) requires meta::is_expression_of<int>;
f(reflexpr("not an int")); // ko
f(reflexpr(42)); // ok
```
"""

# Clean cpp fence: no C1/C6/C7 should fire
_CLEAN_CPP_FENCE = """\
```cpp
int main() {
    return 0;
}
```
"""


class TestHeadingInFence:
    """C7 heading-in-fence branch fires on BASE p0533r9 evidence."""

    def test_lettered_heading_in_fence_fires_c7(self):
        units = code_units_from_markdown(_BASE_P0533R9_HEADING_IN_FENCE)
        report = evaluate_code(_resolved_code(), units)
        assert report.result("C7").status == STATUS_FAIL
        assert any(
            "lettered heading" in f.message
            for f in report.result("C7").findings
        )

    def test_stable_name_bracket_in_fence_fires_c7(self):
        md = '```cpp\nModifications to cmath [cmath.syn]\nint x;\n```\n'
        units = code_units_from_markdown(md)
        report = evaluate_code(_resolved_code(), units)
        assert report.result("C7").status == STATUS_FAIL
        assert any(
            "stable-name bracket" in f.message
            for f in report.result("C7").findings
        )

    def test_normal_cpp_passes_c7(self):
        units = code_units_from_markdown(_CLEAN_CPP_FENCE)
        report = evaluate_code(_resolved_code(), units)
        assert report.result("C7").status == STATUS_PASS

    def test_head_p0533r9_does_not_fire_heading_in_fence(self):
        units = code_units_from_markdown(_HEAD_P0533R9_LISTING_SPLIT)
        report = evaluate_code(_resolved_code(), units)
        findings = report.result("C7").findings or ()
        heading_findings = [
            f for f in findings
            if "heading" in f.message or "bracket" in f.message
        ]
        assert heading_findings == []


class TestListingSplit:
    """C1 listing-split fires on HEAD p0533r9 evidence."""

    def test_ellipsis_only_fence_fires_c1(self):
        md = '```cpp\n...\n```\n'
        units = code_units_from_markdown(md)
        report = evaluate_code(_resolved_code(), units)
        assert report.result("C1").status == STATUS_FAIL
        assert any("..." in f.message for f in report.result("C1").findings)

    def test_lone_survival_keyword_fires_c1(self):
        md = '```cpp\nconstexpr\n```\n'
        units = code_units_from_markdown(md)
        report = evaluate_code(_resolved_code(), units)
        assert report.result("C1").status == STATUS_FAIL
        assert any(
            "survival keyword" in f.message
            for f in report.result("C1").findings
        )

    def test_micro_fence_run_fires_c1(self):
        units = code_units_from_markdown(_HEAD_P0533R9_LISTING_SPLIT)
        report = evaluate_code(_resolved_code(), units)
        assert report.result("C1").status == STATUS_FAIL
        assert any(
            "micro-fences" in f.message
            for f in report.result("C1").findings
        )

    def test_single_healthy_fence_passes_c1(self):
        units = code_units_from_markdown(_CLEAN_CPP_FENCE)
        report = evaluate_code(_resolved_code(), units)
        assert report.result("C1").status == STATUS_PASS


class TestFalseWordingOnComment:
    """C6 false-wording-on-comment branch fires on BASE p2040r0 evidence."""

    def test_ins_del_around_comment_fires_c6(self):
        units = code_units_from_markdown(_BASE_P2040R0_FALSE_WORDING)
        report = evaluate_code(
            _resolved_code(), units,
            markdown_text=_BASE_P2040R0_FALSE_WORDING,
        )
        assert report.result("C6").status == STATUS_FAIL
        assert any(
            "// comment" in f.message
            for f in report.result("C6").findings
        )

    def test_clean_comments_pass_c6(self):
        units = code_units_from_markdown(_HEAD_P2040R0_CLEAN)
        report = evaluate_code(
            _resolved_code(), units,
            markdown_text=_HEAD_P2040R0_CLEAN,
        )
        assert report.result("C6").status == STATUS_PASS

    def test_head_p2040r0_absl_flag_present(self):
        """HEAD p2040r0 has ### ABSL_FLAG section, not a C6 concern."""
        head_md = (
            "### `ABSL_FLAG`\n\n"
            "```cpp\n"
            "ABSL_FLAG(bool, big_menu, true,\n"
            '    "Include \'advanced\' options");\n'
            "```\n"
        )
        units = code_units_from_markdown(head_md)
        report = evaluate_code(
            _resolved_code(), units, markdown_text=head_md,
        )
        assert report.result("C6").status == STATUS_PASS


class TestNewCodeFlagsControlPapers:
    """New code flags must not false-positive on control papers.

    Only the new branches are guarded here: C1 listing-split, C6
    false-wording-on-comment (not the pre-existing :::wording-div check),
    and C7 heading-in-fence (not the pre-existing spec-element branch).
    """

    @staticmethod
    def _new_branch_findings(
        report: TableReadabilityReport,
    ) -> list[str]:
        """Collect findings from the newly added branches only."""
        msgs: list[str] = []
        c1 = report.result("C1")
        if c1.findings:
            msgs.extend(f"C1: {f.message}" for f in c1.findings)
        c6 = report.result("C6")
        if c6.findings:
            for f in c6.findings:
                if "// comment" in f.message:
                    msgs.append(f"C6: {f.message}")
        c7 = report.result("C7")
        if c7.findings:
            for f in c7.findings:
                if "heading" in f.message or "bracket" in f.message:
                    msgs.append(f"C7: {f.message}")
        return msgs

    def test_p0876r23_no_new_code_flags(self):
        p = Path("data/paperstore/p0876r23.md")
        if not p.exists():
            pytest.skip("corpus file not available")
        md = p.read_text(encoding="utf-8")
        units = code_units_from_markdown(md)
        report = evaluate_code(_resolved_code(), units, markdown_text=md)
        hits = self._new_branch_findings(report)
        assert hits == [], f"false positive on p0876r23: {hits}"

    def test_p3596r0_no_new_code_flags(self):
        p = Path("data/paperstore/p3596r0.md")
        if not p.exists():
            pytest.skip("corpus file not available")
        md = p.read_text(encoding="utf-8")
        units = code_units_from_markdown(md)
        report = evaluate_code(_resolved_code(), units, markdown_text=md)
        hits = self._new_branch_findings(report)
        assert hits == [], f"false positive on p3596r0: {hits}"


# -- import isolation ----------------------------------------------------------


class TestImportIsolation:
    """llm_readability must not import the advisory LLM lane."""

    def test_no_llm_import_in_llm_readability(self):
        mods = [
            name
            for name in sys.modules
            if name.startswith("whisker.det.llm_readability")
        ]
        for mod_name in mods:
            mod = sys.modules[mod_name]
            source = getattr(mod, "__file__", "") or ""
            if "/whisker/llm/" in source.replace("\\", "/"):
                pytest.fail(
                    f"{mod_name} is loaded from whisker.llm: {source}"
                )
        llm_mods = [
            name
            for name in sys.modules
            if name == "whisker.llm" or name.startswith("whisker.llm.")
        ]
        for mod_name in llm_mods:
            source_file = getattr(sys.modules[mod_name], "__file__", "")
            if source_file and "llm_readability" in source_file:
                pytest.fail(
                    f"whisker.llm module {mod_name} lives in llm_readability: {source_file}"
                )
