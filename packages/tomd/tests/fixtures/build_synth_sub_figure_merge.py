#
# Copyright (c) 2026 Dmitriy Chukhin (dmitriy@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Build the synth_sub_figure_merge.pdf golden fixture.

Run from the repo root:

    uv run --package tomd python \\
        packages/tomd/tests/fixtures/build_synth_sub_figure_merge.py

The output PDF is one page with:

  - Enough body text to satisfy ``is_readable``.
  - Two vertically-stacked vector clusters (110×80pt each) separated by
    a 65pt gap. Each cluster is one bounding rect + 4 diagonal/crossbar
    strokes + 4 short horizontal strokes (9 draw calls; actual pymupdf
    path-operator item count is printed by this script on stderr).
  - A sub-caption line "(a) Upper sub-figure" with baseline y=320,
    sitting in the gap between the two clusters. This line matches
    ``_SUB_FIGURE_SUB_CAPTION_RE`` and triggers ``_merge_sub_figure_clusters``
    to merge both clusters into one combined bbox (200,220,310,445).
  - A sub-caption line "(b) Lower sub-figure" with baseline y=457,
    below the lower cluster. Captured by ``_line_in_caption_region``
    and re-emitted as an italic paragraph after the image.
  - A "Figure 1: Multi-panel sub-figures" overall caption at baseline
    y=477. Attributed as alt-text via ``_caption_for``.

The gap of 65pt is chosen so that:
  - It exceeds ``_CLUSTER_LINK_DISTANCE_PT = 30pt`` → initial union-find
    clustering keeps the two clusters separate.
  - It is below ``_SUB_FIGURE_MAX_GAP_PT = 120pt`` → ``_merge_sub_figure_clusters``
    considers the pair for merging.
  - Each cluster has area 110×80 = 8,800 pt², below ``_MERGE_MIN_AREA_PT2 = 20,000``
    → ``_merge_close_clusters`` cannot merge them.

The merged cluster area (110×225 = 24,750 pt²) is below
``_DIAGRAM_MIN_AREA_PT2 = 30,000``, so ``is_diagram`` is False via the
dense/sparse paths; item count is far below 100 (compact-cov) and
``_drawing_coverage_sum`` ≈ 2.1 < 3.0 (tiny-cov). The cluster is admitted
via the low-overlap path, which the golden test patches to 1 via
``_LOW_OVERLAP_ADMIT_MIN_ITEMS``.

Reproducible: anyone can rerun this script to rebuild the PDF if a
pymupdf minor-version bump changes its rasterisation output.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf


_FIXTURES_DIR = Path(__file__).resolve().parent
_OUT_PATH = _FIXTURES_DIR / "synth_sub_figure_merge.pdf"


def _draw_cluster(page: pymupdf.Page, box: pymupdf.Rect) -> None:
    """Draw a cluster of vector strokes inside ``box``.

    One bounding rect + 2 diagonals + horizontal + vertical midline +
    4 short horizontal strokes = 9 draw calls. Verified item count: 9
    (each draw call produces 1 item in pymupdf's drawing dict on this
    pymupdf version; printed by ``build()`` on stderr for future checks).
    """
    page.draw_rect(box, color=(0, 0, 0), width=0.8)
    page.draw_line(pymupdf.Point(box.x0, box.y0),
                   pymupdf.Point(box.x1, box.y1),
                   color=(0, 0, 0), width=0.5)
    page.draw_line(pymupdf.Point(box.x1, box.y0),
                   pymupdf.Point(box.x0, box.y1),
                   color=(0, 0, 0), width=0.5)
    midx = (box.x0 + box.x1) / 2
    midy = (box.y0 + box.y1) / 2
    page.draw_line(pymupdf.Point(box.x0, midy),
                   pymupdf.Point(box.x1, midy),
                   color=(0, 0, 0), width=0.5)
    page.draw_line(pymupdf.Point(midx, box.y0),
                   pymupdf.Point(midx, box.y1),
                   color=(0, 0, 0), width=0.5)
    for i in range(4):
        y = box.y0 + 10 + i * 17
        page.draw_line(
            pymupdf.Point(box.x0 + 10, y),
            pymupdf.Point(box.x0 + 30, y),
            color=(0, 0, 0), width=0.4,
        )


def build() -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    # Body text: a short paragraph so the readability heuristic passes.
    # Lines stay under ~85 chars to fit in the 540pt usable width at 11pt helv.
    page.insert_text(
        pymupdf.Point(72, 80),
        "Synthetic Sub-Figure Merge Fixture",
        fontsize=16,
        fontname="helv",
    )
    body_lines = [
        "This fixture tests that two vertically-stacked vector clusters",
        "separated by a sub-caption line are merged into a single image",
        "by the _merge_sub_figure_clusters pass in vector_images.py.",
        "",
        "The pipeline must produce exactly one vector image spanning both",
        "panels, with (a) and (b) sub-captions as italic paragraphs below.",
    ]
    for i, line in enumerate(body_lines):
        if not line:
            continue
        page.insert_text(
            pymupdf.Point(72, 110 + i * 14),
            line,
            fontsize=11,
            fontname="helv",
        )

    # Upper cluster: (200, 220) to (310, 300) — 110×80pt.
    # Gap to lower cluster: 65pt (300 to 365).
    box_a = pymupdf.Rect(200, 220, 310, 300)
    _draw_cluster(page, box_a)

    # Sub-caption in gap: baseline y=320, text top y0≈313, 13pt inside
    # gap_top=300. Triggers _merge_sub_figure_clusters.
    page.insert_text(
        pymupdf.Point(200, 320),
        "(a) Upper sub-figure",
        fontsize=10,
        fontname="helv",
    )

    # Lower cluster: (200, 365) to (310, 445) — 110×80pt.
    box_b = pymupdf.Rect(200, 365, 310, 445)
    _draw_cluster(page, box_b)

    # Sub-caption below lower cluster: baseline y=457, text top y0≈450.
    # Falls inside _line_in_caption_region [220, 545] for the merged cluster.
    page.insert_text(
        pymupdf.Point(200, 457),
        "(b) Lower sub-figure",
        fontsize=10,
        fontname="helv",
    )

    # Overall figure caption: attributed as alt-text by _caption_for.
    page.insert_text(
        pymupdf.Point(200, 477),
        "Figure 1: Multi-panel sub-figures",
        fontsize=10,
        fontname="helv",
    )

    # Trailing body text.
    trailing_lines = [
        "The two panels above are rendered as a merged vector image.",
        "Sub-captions (a) and (b) appear as italic paragraphs below the image.",
    ]
    for i, line in enumerate(trailing_lines):
        page.insert_text(
            pymupdf.Point(72, 510 + i * 14),
            line,
            fontsize=11,
            fontname="helv",
        )

    doc.save(str(_OUT_PATH))
    doc.close()

    # Verify and print actual pymupdf path-operator item counts so the
    # builder comment can reflect the verified value (not an estimate).
    doc2 = pymupdf.open(str(_OUT_PATH))
    drawings = doc2[0].get_drawings()
    items_per = [len(d.get("items") or ()) for d in drawings]
    print(
        f"total drawing items: {sum(items_per)}, per-drawing: {items_per}",
        file=sys.stderr,
    )
    doc2.close()

    return _OUT_PATH


def main() -> int:
    out = build()
    print(f"wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
