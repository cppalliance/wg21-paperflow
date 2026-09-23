"""Snapshot regression: full PDF papers vs committed byte-exact Markdown.

The stem list is ``fixtures/golden/stems/<stem>.txt``, one file per paper.
The file body is the comment that used to sit in the tuple here. A new
golden adds that file and does not edit this module. Family-pin tests
live in ``pdf_pins/``, one module per paper.
"""

import difflib
import json
from pathlib import Path

import pytest
from tomd.lib.pdf import run_pipeline

_GOLDEN = Path(__file__).resolve().parent / "fixtures" / "golden"
_STEMS_DIR = _GOLDEN / "stems"
# Sorted so parametrize order does not depend on directory order.
_GOLDEN_STEMS = tuple(sorted(p.stem for p in _STEMS_DIR.glob("*.txt")))

# Issue-180 reported symptom: this sentence is P4024R0's final paragraph.
_P4024R0_CLOSING = "By embracing these practices"


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"


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
