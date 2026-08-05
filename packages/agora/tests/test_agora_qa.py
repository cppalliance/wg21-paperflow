#
# Copyright (c) 2026 Glenn Siegman (glenn@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the generation QA report (:mod:`agora.qa`).

The report is advisory — the emit step logs findings and records them
in the trace without failing the run — so these tests pin what each
rule flags, what it deliberately lets through, and that the report is
deterministic and skips ``[deleted]`` placeholders.
"""

from __future__ import annotations

from agora.models import (
    Reply,
    ResearchAgentReport,
    ResearchSummary,
    Thread,
)
from agora.qa import SUBMISSION_TARGET, qa_report

_DOCUMENT = "P4003R2"

_ROSTER_NAME = "monomorphic_dan"


def _reply(slot_id: str, content: str, **overrides) -> Reply:
    defaults = dict(
        slot_id=slot_id, parent_slot_id=None, depth=0,
        role="signal", brief="Do the thing.",
        character_username=_ROSTER_NAME, content=content,
    )
    defaults.update(overrides)
    return Reply(**defaults)


def _research() -> ResearchSummary:
    report = ResearchAgentReport(
        agent="public_reception", findings="None.", sources=[],
        heat_signal="warm", interest_signal="relevant",
    )
    return ResearchSummary(
        public_reception=report,
        committee_history=report.model_copy(
            update={"agent": "committee_history"}),
        author_ecosystem=report.model_copy(
            update={"agent": "author_ecosystem"}),
    )


def _thread(replies: list[Reply], submission_body: str = "The paper claims"
            " a 2x speedup on all workloads.") -> Thread:
    return Thread(
        document=_DOCUMENT, paper="P4003", revision=2,
        title="Foo", authors=["A. Author"], audience="EWG",
        date="2026-01-15", paper_type="proposal",
        research_summary=_research(),
        heat="warm", interest="relevant",
        target_comment_count=len(replies), encounter_count=0,
        signal_count=len(replies), noise_count=0,
        submission_title="[P4003R2] Foo",
        submission_body=submission_body,
        submission_link="https://wg21.link/p4003r2",
        replies=list(replies),
    )


# -- unknown-handle --------------------------------------------------------------


def test_unknown_handle_is_flagged():
    thread = _thread([
        _reply("s01", "I agree with u/some_invented_redditor here."),
    ])
    findings = qa_report(thread)
    assert len(findings) == 1
    assert findings[0].rule == "unknown-handle"
    assert findings[0].target == "s01"
    assert "some_invented_redditor" in findings[0].detail


def test_roster_handle_is_not_flagged():
    thread = _thread([
        _reply("s01", f"I agree with u/{_ROSTER_NAME} above."),
    ])
    assert qa_report(thread) == []


def test_submission_body_is_scanned():
    thread = _thread(
        [_reply("s01", "Fine.")],
        submission_body="Thread requested by u/not_on_the_roster.",
    )
    findings = qa_report(thread)
    assert len(findings) == 1
    assert findings[0].target == SUBMISSION_TARGET
    assert findings[0].rule == "unknown-handle"


# -- personal-attack -------------------------------------------------------------


def test_personal_attack_is_flagged():
    thread = _thread([
        _reply("s01", "Only a moron would propose this ABI break."),
    ])
    findings = qa_report(thread)
    assert [f.rule for f in findings] == ["personal-attack"]


def test_technical_criticism_is_not_flagged():
    thread = _thread([
        _reply("s01", "The benchmark section does not hold up; section 4"
               " compares against an unoptimized baseline."),
    ])
    assert qa_report(thread) == []


# -- typo-nitpick ----------------------------------------------------------------


def test_typo_nitpick_is_flagged():
    thread = _thread([
        _reply("s01", "There is a typo in section 3.2, should be"
               " 'coroutine' not 'corotuine'."),
    ])
    findings = qa_report(thread)
    assert [f.rule for f in findings] == ["typo-nitpick"]


def test_typo_in_code_reply_is_exempt():
    """the-mod.md section 10 sanctions a small typo someone corrects in
    a code reply; only prose-only editorial nitpicks are 1.3b noise."""
    thread = _thread([
        _reply("s01", "Small typo in your snippet:\n\n```cpp\n"
               "auto x = co_await task;\n```\n"),
    ])
    assert qa_report(thread) == []


# -- fourth-wall -----------------------------------------------------------------


def test_fourth_wall_leak_is_flagged():
    thread = _thread([
        _reply("s01", "As a language model I cannot evaluate ABI stability."),
    ])
    findings = qa_report(thread)
    assert [f.rule for f in findings] == ["fourth-wall"]


def test_brief_reference_is_flagged():
    thread = _thread([
        _reply("s01", "Per the brief I am supposed to challenge the"
               " benchmark."),
    ])
    findings = qa_report(thread)
    assert [f.rule for f in findings] == ["fourth-wall"]


# -- Report shape ----------------------------------------------------------------


def test_deleted_slots_are_skipped():
    thread = _thread([
        _reply("s01", "[deleted]", role="deleted", deleted=True),
    ])
    assert qa_report(thread) == []


def test_findings_come_out_in_thread_order():
    thread = _thread(
        [
            _reply("s01", "Fine."),
            _reply("s02", "Classic u/invented_one take."),
            _reply("s03", "Only an idiot ships this."),
        ],
        submission_body="Requested by u/invented_two.",
    )
    findings = qa_report(thread)
    assert [f.target for f in findings] == [SUBMISSION_TARGET, "s02", "s03"]


def test_multiple_rules_can_fire_on_one_body():
    thread = _thread([
        _reply("s01", "u/invented_guy is an imbecile, and there is a typo"
               " in section 2."),
    ])
    rules = {f.rule for f in qa_report(thread)}
    assert rules == {"unknown-handle", "personal-attack", "typo-nitpick"}


def test_finding_str_is_human_readable():
    thread = _thread([
        _reply("s01", "Ask u/invented_guy."),
    ])
    text = str(qa_report(thread)[0])
    assert text.startswith("s01 [unknown-handle]:")
