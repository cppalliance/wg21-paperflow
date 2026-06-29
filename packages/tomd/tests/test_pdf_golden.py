"""Golden regression: full PDF papers vs committed expected Markdown."""

import difflib
import json
from pathlib import Path

import pytest
from tomd.lib.pdf import run_pipeline

_GOLDEN = Path(__file__).resolve().parent / "fixtures" / "golden"

_GOLDEN_STEMS = (
    "p0533r9",
    "p0957r8",
    "p1068r11",
    "p3556r0",
    "p1122r3",
    "p2040r0",
    "p3714r0",
    "p1112r4",
    # TOC-stripping regression guards: p4174r0 = total-loss bug paper
    # (body must survive), p4004r1 = partial-loss bug paper (sensitive mid-body
    # guard). The "TOC stays stripped" direction is covered by the synthetic
    # test_toc.py cases, not a golden: no corpus paper cleanly strips its
    # visible (space-separated dot-leader) TOC, so a golden would only enshrine
    # a pre-existing leak.
    # Both are also issue-180 affected: header/footer detection counts distinct
    # pages (not doubled dual-path occurrences), so p4174r0 keeps its recovered
    # "There isn't a standard library tool ... any_of" body line, and p4004r1
    # keeps its two bare "- N -" page-number lines. The page numbers are an
    # accepted chrome residual (another ticket should track the per-item
    # page-number strip that will remove them); they are never body.
    "p4174r0",
    "p4004r1",
    # Leaked heading-kind TOC guard: p4100r1 shipped a front block of
    # empty duplicate headings (its Table of Contents leaked as headings without
    # a dot-leader page number). The dedup post-pass removes them (35 -> 0). Pure
    # Population A: no doubled body, so "body intact and not doubled" is real.
    "p4100r1",
    # Population-B promotion-dedup guard: a confident page paired into a
    # promotion was emitted twice. p3968r0's sole defect was this double-emit
    # (sections 6 and 7 doubled at the tail); the golden pins that each section
    # appears exactly once. One uncertain region covers the front-page
    # metadata/TOC block (L12-L114); sections 2-8 are all confident and each
    # appears exactly once. Not a zero-uncertain-markers specimen.
    "p3968r0",
    # Mixed-kind leaked-TOC guard: p4094r0's Table of Contents leaked
    # as a *mix* of empty headings (## 3.7 Summary, ## 6.4 The Two Framings) and
    # title-like LIST/PARAGRAPH entries (4./5./7. ...) between the title block
    # and the Abstract; pt2 caught only the heading-kind ones and stranded the
    # rest. The unified detector removes the whole block: the golden front is
    # title -> metadata -> Abstract with no stray pre-Abstract sections and no
    # Table of Contents remnant. dup_body == 0 (no body duplication), so the
    # body below is untouched. p4100r1 above is the byte-identical guard that
    # the pass does not over-reach on an already-clean heading-kind TOC.
    "p4094r0",
    # Fragmented leaked-TOC guard (relaxed bridging): p4016r0's ~146-entry
    # Table of Contents leaks before the Abstract as a single block fragmented by
    # non-recurring stragglers (title-like appendix paragraphs whose body heading
    # carries a trailing "(Informative)" the leaked line lacks, plus once-only
    # empty headings like "1.2 Motivating example"). The relaxed-bridging pass
    # coalesces and removes the whole block: the golden front is title ->
    # metadata -> Abstract, and Appendices A-Q each appear exactly once, later,
    # with bodies. Pins that paragraph stragglers are removed only when they
    # forward-reference a later heading and that the real single-line Abstract
    # prose immediately after the TOC survives (the trailing rule).
    "p4016r0",
    # Issue-180 reported paper: P4024R0's closing paragraph ("By embracing
    # these practices ...") sits alone at the top of page 3, sharing y-buckets
    # with the page-1/2 headers. The old raw-occurrence count (doubled by the
    # dual extraction path) stripped it as a phantom header on this 3-page doc.
    # Distinct-page counting keeps it. The golden pins the full body; the
    # explicit closing-sentence assertion below is the focused guard.
    "p4024r0",
    # Code-block extraction regression guards (issue #128).
    "p4012r0-codeblock",
    "p4012r0-page-10",
    "p4012r0-page-6",
    "p0876r22-page-14",
    # Anti-narrative-trim guard: P3181R1's "Stronger semantics" / "Why this
    # matters" sections leaked whole prose paragraphs into ```cpp fences
    # (wholesale _rescue_unfenced_code promotion of mixed prose+code regions).
    # _trim_narrative_from_code splits those by symbol-density / alpha-ratio
    # (not font), so the prose renders as prose and only the Thread A/B/C
    # pseudo-code and the fetch_sub/atomic_thread_fence listings stay fenced.
    # The p4174r0 and p0533r9 goldens above were re-blessed for the same fix
    # (their fences likewise held prose).
    #
    # Residual-fence fix (trailing-label + tail-peel): P3181R1's "Detailed
    # example" had its leading listing label "Thread A:" wrapped onto the prose
    # tail (_absorb_trailing_label_into_code moves it into the fence head), and
    # its "Stronger semantics" tail sentence fragmented across the closing fence
    # (_peel_trailing_prose_from_code peels the trailing prose out). p0957r8 was
    # re-blessed for the same trailing-label move: a "public:" access specifier
    # that wrapped onto the prose tail now heads its class body in the fence,
    # consistent with the Circle/Point bodies below it.
    "p3181r1",
)

# Issue-180 reported symptom: this sentence is P4024R0's final paragraph.
_P4024R0_CLOSING = "By embracing these practices"


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _diff_head(actual: str, golden: str, limit: int = 120) -> str:
    a_lines = _normalize_newlines(actual).splitlines(keepends=True)
    b_lines = _normalize_newlines(golden).splitlines(keepends=True)
    diff = difflib.unified_diff(
        b_lines,
        a_lines,
        fromfile="golden",
        tofile="actual",
        n=3,
    )
    return "".join(list(diff)[:limit])


@pytest.mark.parametrize("stem", _GOLDEN_STEMS)
def test_run_pipeline_matches_golden(stem: str):
    pdf_path = _GOLDEN / f"{stem}.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")

    result = run_pipeline(pdf_path)
    md, prompts = result.md, result.prompts
    golden_md = _GOLDEN / f"{stem}.golden.md"
    assert golden_md.is_file(), f"missing golden: {golden_md}"
    expected_md = golden_md.read_text(encoding="utf-8")
    got_md = _normalize_newlines(md)
    exp_md = _normalize_newlines(expected_md)
    if got_md != exp_md:
        pytest.fail(
            f"Markdown mismatch for {stem}\n{_diff_head(md, expected_md)}",
        )

    golden_prompts = _GOLDEN / f"{stem}.golden.prompts.json"
    if golden_prompts.is_file():
        assert prompts is not None, f"expected prompts for {stem}"
        expected = json.loads(golden_prompts.read_text(encoding="utf-8"))
        assert isinstance(expected, list)
        got = [_normalize_newlines(p) for p in prompts]
        exp = [_normalize_newlines(p) for p in expected]
        if got != exp:
            joined_got = "\n---\n".join(got)
            joined_exp = "\n---\n".join(exp)
            pytest.fail(
                f"Prompts mismatch for {stem}\n{_diff_head(joined_got, joined_exp)}",
            )
    else:
        assert prompts is None, f"unexpected prompts for {stem}: {prompts}"


def test_p4024r0_closing_paragraph_present():
    """Issue-180 focused guard: the reported closing paragraph survives.

    Pairs with the manual ``uv run preview P4024R0`` check. Independent of the
    full golden so a future golden regeneration can never silently drop the
    sentence the bug removed.
    """
    pdf_path = _GOLDEN / "p4024r0.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")
    md = run_pipeline(pdf_path).md
    assert _P4024R0_CLOSING in md
