"""Snapshot regression: full PDF papers vs committed byte-exact Markdown."""

import difflib
import json
from pathlib import Path

import pytest
from tomd.lib.pdf import run_pipeline
from tomd.lib.pdf.types import SectionKind

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
    # Also the collateral-loss guard for the false-heading fix (#302). This
    # single-page extract promoted its standardese footnote "3 explicit
    # conversion to `basic_vec` allows ..." to an H2, which made
    # _strip_pre_heading_fragments treat the whole page above it as pre-heading
    # chrome and delete 7 of the 9 sections. The golden held that 85% content
    # loss; it now holds the full page (source-word coverage 0.15 -> 1.00).
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
    # Shattered-table guard (#380): P4096R0 is a Google-Docs export whose
    # tables arrive as one block per wrapped line. §5.1 and §5.4 are claimed
    # by the side-by-side pre-scanner (atomized header over a shattered
    # body), the two §5.2 tables stay with Pass 1 (row blocks with col-1+
    # wrapped tails merged backward, a trailing continuation absorbed
    # in-loop so the partial third row still joins). The golden pins all
    # four tables plus the prose and headings around them; the family pins
    # below guard the routing itself.
    "p4096r0",
)

# Issue-180 reported symptom: this sentence is P4024R0's final paragraph.
_P4024R0_CLOSING = "By embracing these practices"

# #380 family pins for P4096R0: (page_num, rows incl. header, cols,
# table_kind, table_source) for the four tables of §5.1, §5.2 (x2), §5.4.
_P4096R0_TABLE_PINS = {
    (9, 5, 4, "prose_table", "side_by_side_prepass"),
    (10, 4, 3, "prose_table", "horizontal_rows"),
    (10, 4, 3, "clean_matrix", "horizontal_rows"),
    (11, 5, 4, "clean_matrix", "side_by_side_prepass"),
}

# Family pins for P0957R8: the §5.4.2.1 Name/Value comparison (p.27
# printed, tomd page 26, side-by-side pre-scanner) and the 2-column
# monospace type-trait table on the next page (tomd page 27, Pass 1).
# The latter regressed to a cpp fence when a 2-column monospace guard
# in _try_orphan_lookahead rejected its wrapped cell tail; the pin keeps
# it a table with the tail merged back into its cell (2 rows).
_P0957R8_TABLE_PINS = {
    (26, 14, 2, "code_comparison", "side_by_side_prepass"),
    (27, 2, 2, "clean_matrix", "horizontal_rows"),
}

# Family pins for P4016R0 (#369): §7 Property comparison (tomd page 27,
# printed 28, Pass 1 with the wrapped `canonical_reduce` header tail
# merged), D.3 Sequential vs. Parallel (page 34, printed 35) and N.6
# Partition Strategy (page 51, printed 52). The last two are bordered
# grids whose uneven rows fail Pass 3's asymmetry gate; Pass 3 completes
# its run with the rows the find_tables() grid still holds
# (_grid_rows_left_behind). Pass 3 sections carry no table_source.
# N.14 Summary (page 54, printed 55) is a Property | Guarantee grid whose
# "Determinism" row arrives as a col-0 label block plus a separate
# multi-line cell block (Pass 1 branch 4d, _try_split_row) and whose
# "Practicality" cell wraps onto a line that starts slightly above the
# row bottom (_is_trailing_continuation tolerates the negative y gap).
_P4016R0_TABLE_PINS = {
    (27, 7, 5, "clean_matrix", "horizontal_rows"),
    (30, 3, 3, "clean_matrix", None),
    (34, 5, 3, "clean_matrix", None),
    (38, 5, 4, "prose_table", "horizontal_rows"),
    (44, 9, 5, "prose_table", None),
    (51, 5, 4, "clean_matrix", None),
    (54, 5, 2, "key_value", "horizontal_rows"),
}


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
def test_convert_pdf_matches_golden(stem: str):
    # Original 8 stems use sources/; newer stems live flat in the golden root.
    pdf_path = _GOLDEN / "sources" / f"{stem}.pdf"
    if not pdf_path.is_file():
        pdf_path = _GOLDEN / f"{stem}.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {stem}.pdf")

    result = run_pipeline(pdf_path)
    md, prompts = result.md, result.prompts
    # Originals use snapshots/<stem>.md; newer stems use <stem>.golden.md.
    snapshot_md = _GOLDEN / "snapshots" / f"{stem}.md"
    if not snapshot_md.is_file():
        snapshot_md = _GOLDEN / f"{stem}.golden.md"
    assert snapshot_md.is_file(), f"missing snapshot: {snapshot_md}"
    expected_md = snapshot_md.read_text(encoding="utf-8")
    got_md = _normalize_newlines(md)
    exp_md = _normalize_newlines(expected_md)
    if got_md != exp_md:
        pytest.fail(
            f"Markdown mismatch for {stem}\n{_diff_head(md, expected_md)}",
        )

    snapshot_prompts = _GOLDEN / "snapshots" / f"{stem}.prompts.json"
    if not snapshot_prompts.is_file():
        snapshot_prompts = _GOLDEN / f"{stem}.golden.prompts.json"
    if snapshot_prompts.is_file():
        assert prompts is not None, f"expected prompts for {stem}"
        expected = json.loads(snapshot_prompts.read_text(encoding="utf-8"))
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


def test_p4096r0_table_family_pins():
    """#380 focused guard: each of the four shattered tables is routed to
    the intended family with the intended shape. Independent of the full
    golden so a re-bless can never silently move a table to another pass.
    """
    pdf_path = _GOLDEN / "p4096r0.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")
    sections = run_pipeline(pdf_path).sections
    got = {
        (s.page_num, len(s.columns), len(s.columns[0]),
         s.table_kind, s.table_source)
        for s in sections
        if s.kind == SectionKind.TABLE and s.page_num in (9, 10, 11)
    }
    assert got == _P4096R0_TABLE_PINS


def test_p0957r8_table_family_pins():
    """Focused guard for the two P0957R8 tables on tomd pages 26 and 27.
    Independent of the full golden so a re-bless can never silently drop
    the type-trait table back into a code fence.
    """
    pdf_path = _GOLDEN / "sources" / "p0957r8.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")
    sections = run_pipeline(pdf_path).sections
    got = {
        (s.page_num, len(s.columns), len(s.columns[0]),
         s.table_kind, s.table_source)
        for s in sections
        if s.kind == SectionKind.TABLE and s.page_num in (26, 27)
    }
    assert got == _P0957R8_TABLE_PINS


def test_p4016r0_table_family_pins():
    """Focused guard for the P4016R0 tables on tomd pages 27, 30, 34, 38,
    44, 51 and 54. Independent of the full golden so a re-bless can never
    silently hand D.3 or N.6 back to Pass 3 with their header or last row
    missing, let N.14 explode into headings again, lose B.1 (drawn grid
    under a find_tables() phantom, 39pt tall), leave K.1 at Pass 1's two
    rows with the other seven leaking as prose, or let F.1 fall to Pass 2
    as a two-row column-aligned table (its shape only is pinned here;
    the Rationale cell contents are the golden's job).
    """
    pdf_path = _GOLDEN / "p4016r0.pdf"
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")
    sections = run_pipeline(pdf_path).sections
    got = {
        (s.page_num, len(s.columns), len(s.columns[0]),
         s.table_kind, s.table_source)
        for s in sections
        if s.kind == SectionKind.TABLE
        and s.page_num in (27, 30, 34, 38, 44, 51, 54)
    }
    assert got == _P4016R0_TABLE_PINS


@pytest.mark.parametrize(
    ("rel", "absent", "present"),
    [
        ("p4016r0.pdf", ("<ins>", "<del>"), ()),
        ("sources/p1068r11.pdf", (), ("<ins>__gen</ins>",)),
        ("sources/p3556r0.pdf", (), ("<del>input</del><ins>source</ins>",)),
    ],
)
def test_highlighter_palette_keeps_genuine_wording(rel, absent, present):
    """#413 focused guard for the highlighter-palette skip in wording.py.

    P4016R0's Pygments listings (two greens: keyword and number) must
    carry no ins/del at all, while the one-green-one-red diff markup of
    P1068R11 (inside monospace code) and P3556R0 (prose) must survive.
    Independent of the full goldens so a re-bless can never silently
    trade one for the other.
    """
    pdf_path = _GOLDEN / rel
    if not pdf_path.is_file():
        pytest.skip(f"missing PDF fixture: {pdf_path}")
    md = run_pipeline(pdf_path).md
    for needle in absent:
        assert needle not in md, f"{rel}: unexpected {needle!r}"
    for needle in present:
        assert needle in md, f"{rel}: missing {needle!r}"
