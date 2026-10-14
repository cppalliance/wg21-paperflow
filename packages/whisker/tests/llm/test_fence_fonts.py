#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the source font evidence and prose_in_fence clamp (C9)."""

import asyncio
from pathlib import Path

import pytest
from whisker.det.pdf_geometry import PdfLine
from whisker.llm import fence_fonts
from whisker.llm.fence_fonts import (
    SOURCE_MONOSPACE_NOTE,
    FenceFontEvidence,
    clamp_source_monospace,
    fence_font_evidence,
)
from whisker.llm.models import CodeBoundaryFinding, CodeBoundaryJudgment

MONO = frozenset({"DejaVuSansMono"})
PROP = frozenset({"TimesNewRoman"})

_MD = (
    "# Title\n\nSome prose.\n\n"
    "```cpp\n"
    "[1e16, 1, 1, -1e16, 1, 1]\n"
    "Iterative Pairwise (IPR)     Recursive Bisection\n"
    "This sentence was really swallowed prose.\n"
    "\n"
    "}\n"
    "```\n\n"
    "More prose.\n\n"
    "```\n"
    "int main() {}\n"
    "```\n"
)


def _pdf(text: str, mono: bool) -> PdfLine:
    return PdfLine(
        page=1, x0=72.0, baseline=100.0, text=text,
        fonts=MONO if mono else PROP, sizes=frozenset({10.0}),
    )


def _patch_pdf(monkeypatch, lines: list[PdfLine]) -> None:
    monkeypatch.setattr(fence_fonts, "load_pdf_lines", lambda _p: lines)
    monkeypatch.setattr(
        fence_fonts, "is_monospace_line", lambda pl: pl.fonts == MONO,
    )


def _finding(kind: str, quote: str) -> CodeBoundaryFinding:
    return CodeBoundaryFinding(
        kind=kind, verdict="pass" if kind == "clean" else "review",
        candidate_quote=quote, rule_id="none" if kind == "clean" else "C9",
        reasoning="test",
    )


def _judgment(*findings: CodeBoundaryFinding) -> CodeBoundaryJudgment:
    non_clean = any(f.kind != "clean" for f in findings)
    return CodeBoundaryJudgment(
        reasoning="test", page="fence:1", findings=list(findings),
        verdict="review" if non_clean else "pass", confidence=0.9,
    )


# -- fence_font_evidence ----------------------------------------------------

def test_evidence_classifies_fence_lines_by_source_font(monkeypatch):
    _patch_pdf(monkeypatch, [
        _pdf("[1e16, 1, 1, -1e16, 1, 1]", mono=True),
        _pdf("Iterative Pairwise (IPR)  Recursive Bisection", mono=True),
        _pdf("This sentence was really swallowed prose.", mono=False),
        _pdf("int main() {}", mono=True),
    ])
    ev = fence_font_evidence(Path("x.pdf"), _MD)

    assert set(ev) == {"fence:1", "fence:2"}
    f1 = ev["fence:1"]
    assert f1.monospace == {
        "1e16 1 1 1e16 1 1",
        "iterative pairwise ipr recursive bisection",
    }
    assert f1.proportional == {"this sentence was really swallowed prose"}
    assert (f1.monospace_count, f1.proportional_count, f1.unmatched) == (2, 1, 1)
    assert f1.total == 4  # blank body line not counted; "}" too short -> unmatched
    assert f1.all_monospace is False
    assert f1.proportional_samples == (
        "This sentence was really swallowed prose.",
    )
    f2 = ev["fence:2"]
    assert f2.monospace == {"int main"}
    assert f2.all_monospace is True


def test_evidence_counts_repeated_lines_per_line(monkeypatch):
    md = "```\nop op op op\nop op op op\nop op op op\n```\n"
    _patch_pdf(monkeypatch, [_pdf("op op op op", mono=True)])
    ev = fence_font_evidence(Path("x.pdf"), md)["fence:1"]
    assert ev.monospace == {"op op op op"}
    assert ev.monospace_count == 3
    assert ev.total == 3


def test_evidence_treats_text_in_both_fonts_as_unmatched(monkeypatch):
    """`int main` set in prose AND in code proves nothing either way."""
    _patch_pdf(monkeypatch, [
        _pdf("int main() {}", mono=True),
        _pdf("int main() {}", mono=False),
        _pdf("[1e16, 1, 1, -1e16, 1, 1]", mono=True),
    ])
    ev = fence_font_evidence(Path("x.pdf"), _MD)["fence:2"]
    assert ev.monospace == frozenset()
    assert ev.proportional == frozenset()
    assert ev.unmatched == 1


def test_evidence_uses_body_lines_of_unclosed_fence(monkeypatch):
    md = "```\n[1e16, 1, 1, -1e16, 1, 1]\nint main() {}"
    _patch_pdf(monkeypatch, [
        _pdf("[1e16, 1, 1, -1e16, 1, 1]", mono=True),
        _pdf("int main() {}", mono=True),
    ])
    ev = fence_font_evidence(Path("x.pdf"), md)["fence:1"]
    assert ev.monospace_count == 2  # last body line of an unclosed fence kept


def test_evidence_line_names_counts_and_proportional_samples(monkeypatch):
    _patch_pdf(monkeypatch, [
        _pdf("[1e16, 1, 1, -1e16, 1, 1]", mono=True),
        _pdf("This sentence was really swallowed prose.", mono=False),
    ])
    line = fence_font_evidence(Path("x.pdf"), _MD)["fence:1"].line()

    assert line.startswith("SOURCE FONT EVIDENCE for fence:1: 1 of 4 fence lines")
    assert "1 match a proportional-font line" in line
    assert "2 have no confident match" in line
    assert "'This sentence was really swallowed prose.'" in line
    assert "Every line of this fence is monospace" not in line


def test_evidence_line_states_all_monospace(monkeypatch):
    _patch_pdf(monkeypatch, [_pdf("int main() {}", mono=True)])
    line = fence_font_evidence(Path("x.pdf"), _MD)["fence:2"].line()
    assert "Every line of this fence is monospace in the source." in line
    assert "Proportional-font lines" not in line


@pytest.mark.parametrize("suffix", [".html", ".HTM", ".md"])
def test_evidence_abstains_on_non_pdf_sources(monkeypatch, suffix):
    _patch_pdf(monkeypatch, [_pdf("int main() {}", mono=True)])
    assert fence_font_evidence(Path(f"x{suffix}"), _MD) == {}


def test_evidence_abstains_without_any_monospace_font(monkeypatch):
    _patch_pdf(monkeypatch, [_pdf("int main() {}", mono=False)])
    assert fence_font_evidence(Path("x.pdf"), _MD) == {}


def test_evidence_abstains_on_unreadable_pdf(monkeypatch):
    def _boom(_p):
        raise RuntimeError("cannot open")

    monkeypatch.setattr(fence_fonts, "load_pdf_lines", _boom)
    assert fence_font_evidence(Path("x.pdf"), _MD) == {}


# -- clamp_source_monospace --------------------------------------------------

def _ev(**overrides) -> FenceFontEvidence:
    base = dict(
        locus="fence:1",
        monospace=frozenset({
            "1e16 1 1 1e16 1 1",
            "iterative pairwise ipr recursive bisection",
            "else",
        }),
        proportional=frozenset({"this sentence was really swallowed prose"}),
        monospace_count=3, proportional_count=1, unmatched=1,
    )
    base.update(overrides)
    return FenceFontEvidence(**base)


_EV = _ev()


def test_clamp_rewrites_prose_in_fence_on_monospace_line():
    judgment = _judgment(_finding("prose_in_fence", "[1e16, 1, 1, -1e16, 1, 1]"))
    out, clamped = clamp_source_monospace(judgment, _EV)

    assert clamped == 1
    assert out.verdict == "pass"
    (f,) = out.findings
    assert f.kind == "clean"
    assert f.verdict == "pass"
    assert f.rule_id == "none"
    assert f.reasoning == SOURCE_MONOSPACE_NOTE
    assert f.candidate_quote == "[1e16, 1, 1, -1e16, 1, 1]"
    # input untouched
    assert judgment.findings[0].kind == "prose_in_fence"


@pytest.mark.parametrize("quote", [
    "```cpp\n[1e16, 1, 1, -1e16, 1, 1]",
    "cpp\n[1e16, 1, 1, -1e16, 1, 1]",
    "~~~\nIterative Pairwise (IPR)     Recursive Bisection",
])
def test_clamp_accepts_quote_spanning_fence_opener(quote):
    """The judge sometimes quotes '```cpp\\n[1e16 ...' as one string."""
    _, clamped = clamp_source_monospace(_judgment(_finding("prose_in_fence", quote)), _EV)
    assert clamped == 1


def test_clamp_accepts_fragment_of_a_monospace_line():
    judgment = _judgment(_finding("prose_in_fence", "Recursive Bisection"))
    _, clamped = clamp_source_monospace(judgment, _EV)
    assert clamped == 1


def test_clamp_accepts_multi_line_quote_of_monospace_lines():
    quote = "[1e16, 1, 1, -1e16, 1, 1]\nIterative Pairwise (IPR)     Recursive Bisection"
    _, clamped = clamp_source_monospace(_judgment(_finding("prose_in_fence", quote)), _EV)
    assert clamped == 1


def test_clamp_keeps_prose_in_fence_on_proportional_line():
    judgment = _judgment(
        _finding("prose_in_fence", "This sentence was really swallowed prose."),
    )
    out, clamped = clamp_source_monospace(judgment, _EV)
    assert clamped == 0
    assert out is judgment
    assert out.verdict == "review"


def test_clamp_keeps_prose_in_fence_on_unmatched_line():
    judgment = _judgment(_finding("prose_in_fence", "Unknown line here"))
    _, clamped = clamp_source_monospace(judgment, _EV)
    assert clamped == 0


def test_clamp_does_not_match_short_monospace_line_inside_prose_quote():
    """`else` is monospace-set, but a prose sentence containing it is prose."""
    judgment = _judgment(
        _finding("prose_in_fence", "Otherwise we do something else entirely here."),
    )
    _, clamped = clamp_source_monospace(judgment, _EV)
    assert clamped == 0


def test_clamp_requires_every_quote_line_to_be_monospace():
    quote = "[1e16, 1, 1, -1e16, 1, 1]\nUnknown prose line here"
    _, clamped = clamp_source_monospace(_judgment(_finding("prose_in_fence", quote)), _EV)
    assert clamped == 0


def test_clamp_ignores_too_short_quotes():
    judgment = _judgment(_finding("prose_in_fence", "1e1"))
    _, clamped = clamp_source_monospace(judgment, _EV)
    assert clamped == 0


def test_clamp_leaves_other_kinds_alone():
    judgment = _judgment(_finding("heading_in_fence", "Recursive Bisection"))
    out, clamped = clamp_source_monospace(judgment, _EV)
    assert clamped == 0
    assert out.findings[0].kind == "heading_in_fence"


def test_clamp_keeps_verdict_when_another_defect_remains():
    judgment = _judgment(
        _finding("prose_in_fence", "Recursive Bisection"),
        _finding("heading_in_fence", "Iterative Pairwise"),
    )
    out, clamped = clamp_source_monospace(judgment, _EV)
    assert clamped == 1
    assert out.verdict == "review"
    assert [f.kind for f in out.findings] == ["clean", "heading_in_fence"]


@pytest.mark.parametrize("evidence", [
    None,
    _ev(monospace=frozenset(), monospace_count=0, unmatched=4),
])
def test_clamp_abstains_without_monospace_evidence(evidence):
    judgment = _judgment(_finding("prose_in_fence", "Recursive Bisection"))
    out, clamped = clamp_source_monospace(judgment, evidence)
    assert clamped == 0
    assert out is judgment


# -- wiring into the judge message ------------------------------------------

class _Agent:
    service_name = ""


def test_code_boundary_check_appends_evidence_line(monkeypatch):
    from whisker.llm import pdf_judge

    captured: dict[str, str] = {}

    async def _capture(agent, system, user_msg, out_type, **_k):
        captured["system"] = system
        captured["user"] = user_msg
        return _judgment(_finding("clean", "int main"))

    monkeypatch.setattr(pdf_judge, "run_judge_task", _capture)

    asyncio.run(pdf_judge._run_code_boundary_check(
        _Agent(), "P1R0", "fence:1", "```\nint main\n```", "fence 1 of 1",
        font_evidence=_EV,
    ))
    assert captured["user"].rstrip().endswith(_EV.line())
    assert "SOURCE FONT EVIDENCE" in captured["system"]
    assert "NO prose_in_fence" in captured["system"]


def test_code_boundary_check_without_evidence_is_unchanged(monkeypatch):
    from whisker.llm import pdf_judge

    captured: dict[str, str] = {}

    async def _capture(agent, system, user_msg, out_type, **_k):
        captured["user"] = user_msg
        return _judgment(_finding("clean", "int main"))

    monkeypatch.setattr(pdf_judge, "run_judge_task", _capture)

    asyncio.run(pdf_judge._run_code_boundary_check(
        _Agent(), "P1R0", "fence:1", "```\nint main\n```", "fence 1 of 1",
    ))
    assert "SOURCE FONT EVIDENCE" not in captured["user"]
