#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Offline tests for the whisker-readback harness (no network).

Covers the red-team fixes from Jul 2026:
- Anti-sycophancy: a bare YES without a groundable quote must not pass.
- Word-boundary table scoring: expected "8" must not pass on "18".
- Transport errors are ERROR (rerun), never comprehension FAIL.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
from whisker import constants as C
from whisker.facts import Fact
from whisker.llm import readback_cli
from whisker.llm.readback import (
    _CORRUPT_PREFIX,
    ReadbackCheck,
    ReadbackResult,
    _cell_value_in_answer,
    _corrupt_markdown,
    _evaluate_answer,
    _generate_locus_question,
    question_leaks_answer,
    readback_paper,
    render_markdown,
    render_terminal,
)

_BLIND_WIDGET_QUESTION = (
    "What two-word coined name does this document use for the sample gadget? "
    "Quote it."
)


def _fact(**kw) -> Fact:
    kw.setdefault("checked", True)
    if kw.get("type") in {
        "present", "absent", "math", "code", "xref", "order",
    }:
        kw.setdefault("question", _BLIND_WIDGET_QUESTION)
    return Fact(**kw)


def test_corrupt_markdown_scrambles_each_adversarial_surface():
    """Characterize the deterministic table, operator, and exponent corruption."""
    original = "| left | right |\nvalue >= limit and x^2\nplain prose"

    corrupted = _corrupt_markdown(original)

    assert corrupted == "| right | left |\nvalue <= limit and x^3\nplain prose"


def test_corrupt_markdown_touches_headings_prose_and_code():
    """The hardened corruption hits prose, headings, and fenced code blocks."""
    lines = []
    for i in range(9):
        lines.append(f"## Heading number {i} of the document")
    for i in range(9):
        lines.append(f"This is a paragraph with enough words to qualify for deletion {i}")
    lines.append("```")
    for i in range(9):
        lines.append(f"auto value_{i} = compute_result(x);")
    lines.append("```")
    original = "\n".join(lines)
    corrupted = _corrupt_markdown(original)

    assert corrupted != original

    orig_lines = original.split("\n")
    corr_lines = corrupted.split("\n")
    assert len(corr_lines) == len(orig_lines)

    heading_changes = sum(
        1 for o, c in zip(orig_lines[:9], corr_lines[:9]) if o != c
    )
    assert heading_changes >= 1, "at least one heading level shifted"

    prose_changes = sum(
        1 for o, c in zip(orig_lines[9:18], corr_lines[9:18]) if o != c
    )
    assert prose_changes >= 1, "at least one prose word deleted"

    code_changes = sum(
        1 for o, c in zip(orig_lines[19:28], corr_lines[19:28]) if o != c
    )
    assert code_changes >= 1, "at least one code identifier mangled"


# -- H2 Defect B: banner confound -------------------------------------------


def test_default_corrupt_path_omits_priming_banner():
    """The default --corrupt path must not inject the model-priming banner.

    Feeding the model a banner that says "distrust this document" measures
    the banner, not the corruption; the unconfounded control keeps it off
    unless explicitly opted in.
    """
    fact = Fact(
        id="p", type="present", text="widget frobnicator", checked=True,
        question=_BLIND_WIDGET_QUESTION,
    )
    seen_md: list[str] = []

    def _capture(client, base_url, api_key, model, paper_md, question, **_kwargs):
        seen_md.append(paper_md)
        return "NO", 5

    with patch("whisker.llm.readback._ask_pod", side_effect=_capture):
        result = readback_paper(
            "P0000R0", "widget frobnicator appears here.\n", [fact],
            base_url="http://localhost:1", api_key="x", model="m",
            corrupt=True,
        )

    assert not result.banner_applied
    assert len(seen_md) == 1
    assert _CORRUPT_PREFIX not in seen_md[0]
    assert "Priming banner: not applied (default)" in render_terminal(result)


def test_corrupt_banner_opt_in_is_applied_and_recorded():
    """Explicit opt-in still works, and the report records it happened."""
    fact = Fact(
        id="p", type="present", text="widget frobnicator", checked=True,
        question=_BLIND_WIDGET_QUESTION,
    )
    seen_md: list[str] = []

    def _capture(client, base_url, api_key, model, paper_md, question, **_kwargs):
        seen_md.append(paper_md)
        return "NO", 5

    with patch("whisker.llm.readback._ask_pod", side_effect=_capture):
        result = readback_paper(
            "P0000R0", "widget frobnicator appears here.\n", [fact],
            base_url="http://localhost:1", api_key="x", model="m",
            corrupt=True, inject_banner=True,
        )

    assert result.banner_applied
    assert seen_md[0].startswith(_CORRUPT_PREFIX)
    assert "Priming banner: applied" in render_terminal(result)
    assert "Priming banner**: applied" in render_markdown(result)


# -- Fix 2: anti-sycophancy (grounded quotes for YES/NO types) ----------------


def test_present_bare_yes_fails():
    fact = _fact(id="p", type="present", text="polymorphic allocator model")
    passed, weak = _evaluate_answer(fact, "YES", "YES.")
    assert not passed


def test_present_yes_with_quote_passes():
    fact = _fact(id="p", type="present", text="polymorphic allocator model")
    answer = 'YES. The document states: "the polymorphic allocator model is used here".'
    passed, weak = _evaluate_answer(fact, "YES", answer)
    assert passed
    assert not weak


def test_present_yes_with_unrelated_quote_fails():
    fact = _fact(id="p", type="present", text="polymorphic allocator model")
    answer = 'YES. The document says: "coroutines are stackless".'
    passed, _ = _evaluate_answer(fact, "YES", answer)
    assert not passed


def test_code_requires_raw_quote():
    fact = _fact(id="c", type="code", text="co_await sched.schedule()")
    assert not _evaluate_answer(fact, "YES", "YES, there is such code.")[0]
    answer = "YES:\n```cpp\nco_await sched.schedule();\n```"
    assert _evaluate_answer(fact, "YES", answer)[0]


def test_xref_requires_quote():
    fact = _fact(id="x", type="xref", text="P2300R10")
    assert not _evaluate_answer(fact, "YES", "YES it references that paper.")[0]
    assert _evaluate_answer(fact, "YES", "YES, it cites P2300R10 in section 2.")[0]


def test_image_ref_requires_image_syntax_quote():
    fact = _fact(id="i", type="image_ref", text="")
    assert not _evaluate_answer(fact, "YES", "YES, there are images.")[0]
    assert _evaluate_answer(
        fact, "YES", "YES: ![figure 1](p1234-fig1-1.png)"
    )[0]


def test_absent_no_is_weak_pass():
    fact = _fact(id="a", type="absent", text="quantum entanglement")
    passed, weak = _evaluate_answer(fact, "NO", "NO, that does not appear.")
    assert passed
    assert weak


def test_present_quote_without_yes_passes():
    fact = _fact(id="p", type="present", text="polymorphic allocator model")
    answer = 'The document states: "the polymorphic allocator model is used here".'
    passed, weak = _evaluate_answer(fact, fact.text, answer)
    assert passed
    assert not weak


def test_missing_authored_question_is_schema_error():
    fact = Fact(id="p", type="present", text="widget frobnicator", checked=True)
    with patch("whisker.llm.readback._ask_pod") as ask:
        result = readback_paper(
            "P0000R0", "widget frobnicator appears here.\n", [fact],
            base_url="http://localhost:1", api_key="x", model="m",
        )
    ask.assert_not_called()
    assert result.error_count == 1
    assert "authored question required" in result.checks[0].pod_answer


def test_leaky_authored_question_is_schema_error():
    fact = Fact(
        id="p", type="present", text="widget frobnicator", checked=True,
        question="Does the document contain widget frobnicator?",
    )
    with patch("whisker.llm.readback._ask_pod") as ask:
        result = readback_paper(
            "P0000R0", "widget frobnicator appears here.\n", [fact],
            base_url="http://localhost:1", api_key="x", model="m",
        )
    ask.assert_not_called()
    assert result.error_count == 1
    assert "leaks" in result.checks[0].pod_answer


def test_xref_and_image_ref_questions_request_quotes():
    """Grounding is only fair if the question asks for the quote."""
    q_xref = Fact(
        id="x", type="xref", text="P2300R10", checked=True,
        question="Which paper is cited? Quote the identifier.",
    ).question
    q_img = _generate_locus_question(_fact(id="i", type="image_ref", text=""))
    assert "quote" in q_xref.lower()
    assert "quote" in q_img.lower()


# -- Fix 3: word-boundary table scoring ---------------------------------------


def test_cell_value_8_does_not_match_18():
    assert not _cell_value_in_answer("8", "The value is 18.")
    assert _cell_value_in_answer("8", "The value is 8.")


def test_cell_value_boundary_with_punctuation():
    assert _cell_value_in_answer("8", "SF: (8), F: 3")
    assert _cell_value_in_answer("42", "cells: 42, 99")
    assert not _cell_value_in_answer("42", "cell 4242 only")


def test_table_answer_substring_exploit_fails():
    fact = _fact(
        id="t", type="table", cell="SF",
        neighbors=(("right", "8"),), table_heading="SF",
    )
    passed, _ = _evaluate_answer(fact, "cell=SF, right: 8", "The cell right of SF is 18.")
    assert not passed
    passed, _ = _evaluate_answer(fact, "cell=SF, right: 8", "The cell right of SF is 8.")
    assert passed


# -- Fix 6: transport errors are ERROR, not FAIL -------------------------------


def test_transport_error_marked_error_not_fail():
    fact = _fact(id="p", type="present", text="anything")

    def _boom(*args, **kwargs):
        raise httpx.ReadTimeout("pod timed out")

    with patch("whisker.llm.readback._ask_pod", side_effect=_boom):
        result = readback_paper(
            "P0000R0", "# doc", [fact],
            base_url="http://localhost:1", api_key="x", model="m",
        )

    assert len(result.checks) == 1
    check = result.checks[0]
    assert check.error
    assert not check.passed
    assert result.error_count == 1
    assert result.fail_count == 0
    assert result.pass_count == 0


def test_render_shows_error_and_weak_states():
    result = ReadbackResult(pid="P0000R0", model="m")
    result.checks.append(ReadbackCheck(
        fact_id="e", fact_type="present", question="q", expected="YES",
        pod_answer="(transport error: ReadTimeout: x)", passed=False, error=True,
    ))
    result.checks.append(ReadbackCheck(
        fact_id="a", fact_type="absent", question="q", expected="NO",
        pod_answer="NO", passed=True, weak=True,
    ))
    term = render_terminal(result)
    assert "ERROR" in term
    assert "weak" in term
    assert "Error: 1" in term
    md = render_markdown(result)
    assert "ERROR" in md
    assert "weak" in md


# -- H2 Defect A: typed exit codes (readback_cli) -----------------------------


def _write_verified_present_fact(corpus_dir, pid="p0000r0"):
    facts_path = corpus_dir / f"{pid}.facts.jsonl"
    record = {
        "id": "p1", "type": "present", "text": "widget frobnicator",
        "checked": "verified",
        "question": _BLIND_WIDGET_QUESTION,
    }
    facts_path.write_text(json.dumps(record) + "\n", encoding="utf-8")


def _run_readback_cli(tmp_path, extra_args, pod_answer):
    """Run readback_cli.main() with the pod boundary mocked (no network)."""
    _write_verified_present_fact(tmp_path)
    argv = ["--corpus", str(tmp_path), "--workspace", str(tmp_path), *extra_args]
    with (
        patch("whisker.llm.readback_cli.SqliteBackend") as backend_cls,
        patch(
            "whisker.llm.readback_cli._resolve_service",
            return_value=("http://localhost:1", "key", "model"),
        ),
        patch(
            "whisker.llm.readback._ask_pod",
            return_value=(pod_answer, 5),
        ),
    ):
        backend_cls.return_value.get_paper_md.return_value = (
            "widget frobnicator appears in this document.\n"
        )
        return readback_cli.main(argv)


_ANSWER_COMPREHENSION_PASSES = 'YES. The document states "widget frobnicator".'
_ANSWER_COMPREHENSION_FAILS = "NO, that concept does not appear."


def test_clean_mode_all_passing_exits_ok(tmp_path):
    exit_code = _run_readback_cli(tmp_path, [], _ANSWER_COMPREHENSION_PASSES)
    assert exit_code == C.EXIT_OK


def test_clean_mode_with_failures_exits_nonzero(tmp_path):
    exit_code = _run_readback_cli(tmp_path, [], _ANSWER_COMPREHENSION_FAILS)
    assert exit_code == C.EXIT_FAIL
    assert exit_code != C.EXIT_OK


def test_corrupt_mode_everything_passing_is_inverted_canary_exits_nonzero(tmp_path):
    """G6 guard: --corrupt with zero failures means the control has no teeth."""
    exit_code = _run_readback_cli(
        tmp_path, ["--corrupt"], _ANSWER_COMPREHENSION_PASSES,
    )
    assert exit_code == C.EXIT_FAIL
    assert exit_code != C.EXIT_OK


def test_corrupt_mode_detected_exits_ok(tmp_path):
    """Corruption caught (comprehension actually failed) is the success case."""
    exit_code = _run_readback_cli(
        tmp_path, ["--corrupt"], _ANSWER_COMPREHENSION_FAILS,
    )
    assert exit_code == C.EXIT_OK


def test_operational_error_no_corpus_exits_error(tmp_path):
    missing = tmp_path / "does-not-exist"
    exit_code = readback_cli.main(["--corpus", str(missing)])
    assert exit_code == C.EXIT_ERROR


def test_default_cli_corrupt_run_omits_priming_banner(tmp_path):
    """CLI-level check: --corrupt alone (no --corrupt-banner) sends no banner."""
    _write_verified_present_fact(tmp_path)
    argv = ["--corpus", str(tmp_path), "--workspace", str(tmp_path), "--corrupt"]
    seen_md: list[str] = []

    def _capture(client, base_url, api_key, model, paper_md, question, **_kwargs):
        seen_md.append(paper_md)
        return _ANSWER_COMPREHENSION_FAILS, 5

    with (
        patch("whisker.llm.readback_cli.SqliteBackend") as backend_cls,
        patch(
            "whisker.llm.readback_cli._resolve_service",
            return_value=("http://localhost:1", "key", "model"),
        ),
        patch("whisker.llm.readback._ask_pod", side_effect=_capture),
    ):
        backend_cls.return_value.get_paper_md.return_value = (
            "widget frobnicator appears in this document.\n"
        )
        readback_cli.main(argv)

    assert len(seen_md) == 1
    assert _CORRUPT_PREFIX not in seen_md[0]


# -- Protocol v2: authored questions on the five-paper corpus -----------------

_CORPUS = Path(__file__).resolve().parents[2] / "corpus"
_FIVE_PAPERS = frozenset({
    "N5040", "P0876R23", "P4182R0", "P4185R0", "P4234R0",
})
_AUTHORED_TYPES = frozenset({
    "present", "absent", "math", "code", "xref", "order",
})


def test_five_paper_corpus_questions_are_blind():
    """Every verified fact on the modal corpus has a non-leaky question."""
    from whisker.facts import parse_facts_jsonl
    from whisker.llm.readback import _question_for

    verified = []
    for path in sorted(_CORPUS.glob("*.facts.jsonl")):
        pid = path.name[: -len(".facts.jsonl")].upper()
        if pid not in _FIVE_PAPERS:
            continue
        facts = parse_facts_jsonl(path.read_text(encoding="utf-8-sig"), pid)
        for fact in facts:
            if fact.checked:
                verified.append((pid, fact))

    assert len(verified) == 37, f"expected 37 verified facts, got {len(verified)}"
    leaks = []
    missing = []
    for pid, fact in verified:
        question = _question_for(fact)
        if question is None:
            missing.append(f"{pid}:{fact.id}")
            continue
        leaked = question_leaks_answer(fact, question)
        if leaked:
            leaks.append(f"{pid}:{fact.id} -> {leaked!r}")
        if fact.type in _AUTHORED_TYPES:
            assert fact.question.strip(), f"{pid}:{fact.id} missing authored question"
    assert not missing, "missing questions:\n" + "\n".join(missing)
    assert not leaks, "leaky questions:\n" + "\n".join(leaks)


def test_code_fact_asks_pod_with_code_rubric_flag():
    fact = Fact(
        id="c",
        type="code",
        text="widget_factory",
        checked=True,
        question="Which factory function does the first listing declare? Quote the identifier.",
    )
    seen: dict = {}

    def _capture(*_args, **kwargs):
        seen.update(kwargs)
        return "widget_factory", 5

    with patch("whisker.llm.readback._ask_pod", side_effect=_capture):
        readback_paper(
            "P0000R0",
            "```cpp\nint widget_factory();\n```\n",
            [fact],
            base_url="http://localhost:1",
            api_key="x",
            model="m",
        )
    assert seen.get("code_fact") is True
    assert seen.get("table_fact") is False
