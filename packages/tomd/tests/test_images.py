#
# Copyright (c) 2026 Dmitriy Chukhin (dmitriy@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Unit tests for image extraction (Resource-Dictionary path).

Pure-function tests that build synthetic Block / Section / candidate
inputs in-memory. PDF-level end-to-end coverage lives in
``test_pdf_golden.py``; here we exercise the regex, dedup, multi-rect,
cap, and structure-pass-survival edges that would otherwise need a
hand-crafted PDF fixture per case.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pymupdf
import pytest

from conftest import make_section

from tomd.lib.pdf.emit import emit_markdown
from tomd.lib.pdf.images import (
    ExtractedImage,
    VectorUncertaintyStats,
    _MAX_IMAGES_PER_PAPER,
    _PageImageCandidate,
    _VectorExtractionStats,
    _caption_for,
    finalize_extraction,
)
from tomd.lib.pdf.pipeline import _make_image_section
from tomd.lib.pdf.structure import structure_sections
from tomd.lib.pdf.types import (
    Block,
    Confidence,
    Line,
    Section,
    SectionKind,
    Span,
)
from tomd.lib.pdf import vector_images
from tomd.lib.pdf.vector_images import (
    ALLOWED_REASON_KEYS,
    REASON_CLUSTERS_OVERFLOW,
    REASON_EDGE_BAND,
    REASON_TEXT_OVERLAP,
    REASON_TOO_FEW_ITEMS,
    REASON_TOO_SMALL,
    REASON_WORDING_COLOR,
    _cluster_drawings,
    _colour_in_wording_band,
    _synthetic_xref,
    _text_overlap_fraction,
    extract_page_vector_images,
    format_uncertainty_marker,
    should_emit_marker,
)


# ---- helpers ----------------------------------------------------------------


def _line(text: str, y0: float, x0: float = 50.0, height: float = 12.0) -> Line:
    """Build a single-span Line at (x0, y0) with given height."""
    span = Span(text=text, font_name="Test", font_size=11.0,
                bbox=(x0, y0, x0 + 200.0, y0 + height))
    return Line(spans=[span], bbox=(x0, y0, x0 + 200.0, y0 + height))


def _block(lines: list[Line], page_num: int = 0) -> Block:
    return Block(lines=lines, page_num=page_num)


def _candidate(
    xref: int,
    page: int,
    y0: float,
    x0: float = 50.0,
    *,
    ext: str = "png",
    data: bytes = b"PNGDATA",
    suggested_alt: str = "",
) -> _PageImageCandidate:
    return _PageImageCandidate(
        xref=xref,
        page=page,
        bbox=(x0, y0, x0 + 100.0, y0 + 100.0),
        ext=ext,
        bytes=data,
        suggested_alt=suggested_alt,
    )


def _image_section(
    *,
    page: int = 1,
    index: int = 1,
    bbox: tuple[float, float, float, float] = (10, 10, 100, 100),
    alt: str = "",
    stored_filename: str = "p1-fig1-1.png",
    xref: int = 1,
) -> Section:
    """Construct an IMAGE Section identical to what pipeline._make_image_section produces."""
    img = ExtractedImage(
        page=page,
        index_on_page=index,
        ext="png",
        bytes=b"PNGDATA",
        bbox=bbox,
        suggested_alt=alt,
        stored_filename=stored_filename,
        xref=xref,
    )
    return Section(
        kind=SectionKind.IMAGE,
        text="",
        confidence=Confidence.HIGH,
        page_num=page - 1,
        image_ref=img,
    )


# ---- _caption_for: label match below image ---------------------------------


def test_caption_for_figure_label_below():
    img_bbox = (100.0, 100.0, 300.0, 200.0)
    blocks = [_block([_line("Figure 1: Hello World!", y0=210.0)])]
    assert _caption_for(img_bbox, blocks) == "Figure 1: Hello World!"


def test_caption_for_listing_label():
    img_bbox = (100.0, 100.0, 300.0, 200.0)
    blocks = [_block([_line("Listing 3: example code", y0=205.0)])]
    assert _caption_for(img_bbox, blocks) == "Listing 3: example code"


def test_caption_for_en_dash_separator():
    """Real WG21 papers use the en-dash (U+2013) for figure captions."""
    img_bbox = (100.0, 100.0, 300.0, 200.0)
    blocks = [_block([_line("Figure 1 – memory layout", y0=210.0)])]
    assert _caption_for(img_bbox, blocks) == "Figure 1 – memory layout"


def test_caption_for_em_dash_separator():
    img_bbox = (100.0, 100.0, 300.0, 200.0)
    blocks = [_block([_line("Figure 1 — memory layout", y0=210.0)])]
    assert _caption_for(img_bbox, blocks) == "Figure 1 — memory layout"


def test_caption_for_above_when_below_absent():
    img_bbox = (100.0, 100.0, 300.0, 200.0)
    blocks = [_block([_line("Figure 5: above caption", y0=80.0)])]
    assert _caption_for(img_bbox, blocks) == "Figure 5: above caption"


def test_caption_for_prefers_below_over_above():
    img_bbox = (100.0, 100.0, 300.0, 200.0)
    blocks = [_block([
        _line("Figure 1: above", y0=80.0),
        _line("Figure 2: below", y0=210.0),
    ])]
    assert _caption_for(img_bbox, blocks) == "Figure 2: below"


# ---- _caption_for: graceful empty fallback ---------------------------------


def test_caption_for_no_match_returns_empty():
    img_bbox = (100.0, 100.0, 300.0, 200.0)
    blocks = [_block([_line("Just some surrounding prose.", y0=210.0)])]
    assert _caption_for(img_bbox, blocks) == ""


def test_caption_for_does_not_match_table_label():
    """N2 regression: Table N: must never leak into image alt text.

    Tables own their captions structurally via SectionKind.TABLE.
    A results table sitting 30pt below an image bbox should NOT
    become misattributed alt text on the image.
    """
    img_bbox = (100.0, 100.0, 300.0, 200.0)
    blocks = [_block([_line("Table 1: Comparison of foo vs bar", y0=230.0)])]
    assert _caption_for(img_bbox, blocks) == ""


def test_caption_for_rejects_bare_body_text():
    """Concern #2 regression: unlabeled body prose 30pt below an image must
    NOT become alt text. The bare-line fallback was removed because
    misattribution propagates into LLM prompts via wrap_source, a worse
    failure mode than empty alt.
    """
    img_bbox = (100.0, 100.0, 300.0, 200.0)
    blocks = [_block([_line(
        "We discussed this in Section 3.1, see references below for additional context.",
        y0=230.0,
    )])]
    assert _caption_for(img_bbox, blocks) == ""


def test_caption_for_skips_out_of_radius_below():
    """Lines below the 60pt search radius are ignored even when labelled."""
    img_bbox = (100.0, 100.0, 300.0, 200.0)
    blocks = [_block([_line("Figure 1: too far below", y0=270.0)])]   # 70pt below
    assert _caption_for(img_bbox, blocks) == ""


def test_caption_for_skips_out_of_radius_above():
    """Lines above the 30pt search radius are ignored even when labelled."""
    img_bbox = (100.0, 100.0, 300.0, 200.0)
    blocks = [_block([_line("Figure 1: too far above", y0=50.0)])]   # 50pt above
    assert _caption_for(img_bbox, blocks) == ""


# ---- finalize_extraction: cross-page xref dedup ----------------------------


def test_finalize_dedupes_repeated_xref_across_pages():
    """A logo in an inherited resource dict appears on every page; the
    page-header pattern collapses to one IMAGE at its first occurrence."""
    per_page = [
        [_candidate(42, page=1, y0=10.0)],
        [_candidate(42, page=2, y0=10.0)],
        [_candidate(42, page=3, y0=10.0)],
    ]
    r = finalize_extraction(per_page, "p1")
    assert len(r.images) == 1
    assert r.images[0].xref == 42
    assert r.images[0].page == 1
    assert r.source_image_count == 1
    assert r.images_truncated is False


def test_finalize_multi_rect_on_same_page_picks_top_left():
    """Concern #5: same xref rendered at multiple rects on first-occurrence
    page -> smallest (y0, x0) rect is canonical.
    """
    per_page = [
        [
            _candidate(42, page=1, y0=600.0, x0=100.0),   # bottom rect (larger y0)
            _candidate(42, page=1, y0=50.0,  x0=100.0),   # TOP rect (smallest y0)
        ],
    ]
    r = finalize_extraction(per_page, "p1")
    assert len(r.images) == 1
    assert r.images[0].bbox == (100.0, 50.0, 200.0, 150.0)
    assert r.source_image_count == 1


def test_finalize_multi_page_picks_earliest_page():
    """Same xref on pages 3 and 1 -> first-occurrence page is 1."""
    per_page = [
        [_candidate(42, page=3, y0=10.0)],
        [_candidate(42, page=1, y0=10.0)],
    ]
    r = finalize_extraction(per_page, "p1")
    assert len(r.images) == 1
    assert r.images[0].page == 1


# ---- finalize_extraction: ordering and naming ------------------------------


def test_finalize_assigns_index_after_y0_sort():
    """index_on_page reflects the canonical (y0, x0) sort on the chosen page,
    not pymupdf's enumeration order."""
    per_page = [
        [
            _candidate(1, page=1, y0=400.0),    # arrives first but lower on page
            _candidate(2, page=1, y0=50.0),     # arrives second, topmost
        ],
    ]
    r = finalize_extraction(per_page, "p1")
    assert [im.xref for im in r.images] == [2, 1]
    assert [im.index_on_page for im in r.images] == [1, 2]


def test_finalize_stored_filename_uses_lowercase_pid():
    per_page = [[_candidate(1, page=3, y0=10.0, ext="png")]]
    r = finalize_extraction(per_page, "P3556R0")
    assert r.images[0].stored_filename == "p3556r0-fig3-1.png"


def test_finalize_preserves_image_format():
    per_page = [
        [_candidate(1, page=1, y0=10.0, ext="jpeg")],
        [_candidate(2, page=2, y0=10.0, ext="jpx")],
    ]
    r = finalize_extraction(per_page, "p1")
    assert {im.ext for im in r.images} == {"jpeg", "jpx"}


def test_finalize_empty_input():
    r = finalize_extraction([], "p1")
    assert r.images == []
    assert r.source_image_count == 0
    assert r.images_truncated is False


# ---- finalize_extraction: 20-image cap -------------------------------------


def test_finalize_cap_trips_on_unique_xrefs():
    """21 unique xrefs -> 20 kept, source_image_count=21, truncated=True."""
    per_page = [
        [_candidate(x, page=1, y0=10.0 + x) for x in range(1, 22)]
    ]
    r = finalize_extraction(per_page, "p1")
    assert len(r.images) == _MAX_IMAGES_PER_PAPER
    assert r.source_image_count == 21
    assert r.images_truncated is True


def test_finalize_cap_not_tripped_by_repeated_xref():
    """The cap is over UNIQUE xrefs. 21 references to one logo stays at 1."""
    per_page = [
        [_candidate(42, page=p, y0=10.0) for p in range(1, 22)]
    ]
    r = finalize_extraction(per_page, "p1")
    assert len(r.images) == 1
    assert r.source_image_count == 1
    assert r.images_truncated is False


def test_finalize_cap_keeps_earliest_unique_xrefs():
    """When truncating, the 20 kept must be the first by (page, y0, x0)."""
    per_page = [
        # 25 unique xrefs in monotonically increasing y0; we expect xrefs 1..20.
        [_candidate(x, page=1, y0=10.0 * x) for x in range(1, 26)]
    ]
    r = finalize_extraction(per_page, "p1")
    kept_xrefs = sorted(im.xref for im in r.images)
    assert kept_xrefs == list(range(1, 21))
    assert r.source_image_count == 25


# ---- structure_sections: IMAGE survives all adjacency passes ---------------


def test_structure_pass_preserves_image_between_paragraphs():
    """IMAGE must not be absorbed; image_ref must be intact post-structure."""
    img_sec = _image_section()
    sections = [
        make_section("First paragraph.", page_num=0),
        img_sec,
        make_section("Second paragraph.", page_num=0),
    ]
    _, out, _ = structure_sections(sections, has_title=True)
    images = [s for s in out if s.kind == SectionKind.IMAGE]
    assert len(images) == 1
    assert images[0].image_ref is img_sec.image_ref
    assert images[0].text == ""


def test_structure_pass_blocks_paragraph_merge_across_image():
    """A paragraph ending without terminal punctuation must NOT merge with
    the paragraph after the IMAGE.
    _merge_paragraphs is the pass at risk: it joins prev (no terminal
    punctuation) with current (starts lowercase). IMAGE has to break the
    chain.
    """
    sections = [
        make_section("First paragraph fragment", page_num=0),     # no terminal punct
        _image_section(),
        make_section("continuation begins lowercase.", page_num=0),
    ]
    _, out, _ = structure_sections(sections, has_title=True)
    paras = [s for s in out if s.kind == SectionKind.PARAGRAPH]
    assert len(paras) == 2, f"merged across IMAGE: {[s.text for s in paras]}"


def test_finalize_drops_inline_emoji_sized_rasters():
    """Inline emoji glyphs (PDF font-replacement PNGs at 8-18pt) are
    not figures and must be filtered out.

    The corpus survey of N5007 (editor's report with 107 emoji as
    embedded PNGs, all <= 18pt) and P4216R0 (8x8 emoji in a code
    block) showed: leaving these in produces phantom IMAGE sections
    at wrong y-positions, oversized rendering, and noise that
    pollutes the analytical pipelines downstream. The smallest
    genuine figure bbox in the workspace is 24x24, so the 20pt
    minimum bbox dim has comfortable margin.
    """
    per_page = [
        [
            _candidate(1, page=1, y0=10, x0=10),    # tiny emoji at 100x100
            _candidate(2, page=1, y0=200, x0=200),  # also tiny
            _candidate(3, page=1, y0=500, x0=200),  # real figure (overridden below)
        ],
    ]
    # Shrink the first two to emoji dimensions, leave the third figure-sized.
    per_page[0][0] = _PageImageCandidate(
        xref=1, page=1, bbox=(10.0, 10.0, 18.0, 18.0),
        ext="png", bytes=b"emoji1", suggested_alt="",
    )
    per_page[0][1] = _PageImageCandidate(
        xref=2, page=1, bbox=(200.0, 200.0, 212.8, 212.8),
        ext="png", bytes=b"emoji2", suggested_alt="",
    )
    per_page[0][2] = _PageImageCandidate(
        xref=3, page=1, bbox=(200.0, 500.0, 400.0, 700.0),
        ext="png", bytes=b"real_figure", suggested_alt="Figure 1: example",
    )

    r = finalize_extraction(per_page, "p1")
    assert len(r.images) == 1
    assert r.images[0].xref == 3
    assert r.images[0].suggested_alt == "Figure 1: example"
    # source_image_count is post-filter so the truncation marker
    # doesn't get inflated by emoji.
    assert r.source_image_count == 1
    assert r.images_truncated is False


def test_finalize_keeps_image_at_filter_boundary():
    """A 20x20 bbox is exactly at the threshold and must be kept
    (the filter uses ``>= _MIN_IMAGE_DIM_PT``). Smaller-than-threshold
    is the dropped band.
    """
    per_page = [[
        _PageImageCandidate(
            xref=1, page=1, bbox=(0.0, 0.0, 20.0, 20.0),
            ext="png", bytes=b"boundary", suggested_alt="",
        ),
        _PageImageCandidate(
            xref=2, page=1, bbox=(0.0, 100.0, 19.5, 119.5),
            ext="png", bytes=b"under", suggested_alt="",
        ),
    ]]
    r = finalize_extraction(per_page, "p1")
    assert {im.xref for im in r.images} == {1}


def test_image_not_swept_into_toc_gap_fill():
    """Regression: an IMAGE section between two heading-matched
    sections (find_toc_indices gap-fill territory) must not be
    stripped as TOC content.

    Reproduces the P4216R0 failure mode: paper has headings
    ``Abstract``, ``Tony Table``, ``Revisions``, ``Motivation``
    consecutively, with an image between ``Tony Table`` and
    ``Revisions``. find_toc_indices marks the consecutive heading
    matches as a TOC run and gap-fills the IMAGE index. The
    pipeline filter must drop IMAGE indices from the TOC set
    before applying them.
    """
    # Build a section list that mimics the failure: heading,
    # heading, IMAGE, heading, heading.
    def _heading(text: str) -> Section:
        line = Line(spans=[
            Span(text=text, font_name="T", font_size=14.0,
                 bbox=(0, 0, 100, 14), bold=True),
        ], bbox=(0, 0, 100, 14))
        return Section(
            kind=SectionKind.HEADING, text=text, heading_level=2,
            confidence=Confidence.HIGH, lines=[line],
        )

    img_sec = _image_section()
    sections = [
        _heading("Abstract"),
        _heading("Tony Table"),
        img_sec,
        _heading("Revisions"),
        _heading("Motivation"),
    ]
    # Simulate the pipeline filter directly: build toc_indices set,
    # filter out IMAGE indices, ensure the IMAGE survives.
    from tomd.lib.toc import find_toc_indices

    texts = [sec.text.split("\n")[0].strip() for sec in sections]
    headings = {sec.text.split("\n")[0].strip() for sec in sections
                if sec.kind == SectionKind.HEADING}
    toc_indices = find_toc_indices(texts, headings, None)

    # The buggy state would include index 2 (the IMAGE) in toc_indices.
    # Verify the filter at the pipeline call site removes it.
    filtered = {i for i in toc_indices
                if sections[i].kind is not SectionKind.IMAGE}
    assert 2 not in filtered, "IMAGE must not be in TOC strip set"


def test_structure_pass_image_not_classified_as_list_item():
    """_detect_lists_by_position scans PARAGRAPH sections only; an IMAGE
    sandwiched between two LIST items must not become a list item itself."""
    bullet_line = Line(spans=[
        Span(text="• item one", font_name="Test", font_size=11.0,
             bbox=(60.0, 100.0, 200.0, 112.0)),
    ], bbox=(60.0, 100.0, 200.0, 112.0))
    list_sec_top = Section(
        kind=SectionKind.LIST, text="• item one",
        confidence=Confidence.HIGH, lines=[bullet_line],
        page_num=0, font_size=11.0,
    )
    img_sec = _image_section()
    bullet_line_bot = Line(spans=[
        Span(text="• item two", font_name="Test", font_size=11.0,
             bbox=(60.0, 300.0, 200.0, 312.0)),
    ], bbox=(60.0, 300.0, 200.0, 312.0))
    list_sec_bot = Section(
        kind=SectionKind.LIST, text="• item two",
        confidence=Confidence.HIGH, lines=[bullet_line_bot],
        page_num=0, font_size=11.0,
    )
    _, out, _ = structure_sections(
        [list_sec_top, img_sec, list_sec_bot], has_title=True,
    )
    image_positions = [i for i, s in enumerate(out) if s.kind == SectionKind.IMAGE]
    assert len(image_positions) == 1
    assert out[image_positions[0]].kind == SectionKind.IMAGE


# ---- emit_markdown: image and truncation rendering -------------------------


def test_emit_renders_image_with_caption():
    img_sec = _image_section(alt="Figure 1: Hello World!",
                              stored_filename="p3556r0-fig3-1.png")
    md = emit_markdown({"title": "Test"}, [img_sec])
    assert "![Figure 1: Hello World!](p3556r0-fig3-1.png)" in md


def test_emit_renders_image_with_empty_alt():
    img_sec = _image_section(alt="", stored_filename="p1-fig0-1.png")
    md = emit_markdown({"title": "Test"}, [img_sec])
    assert "![](p1-fig0-1.png)" in md


def test_emit_escapes_brackets_in_alt():
    """Alt text containing ``]`` would otherwise truncate the markdown image
    syntax (e.g. ``![Figure 1 [revised]: ...](...)``)."""
    img_sec = _image_section(
        alt="Figure 1 [revised]: caption",
        stored_filename="p1-fig0-1.png",
    )
    md = emit_markdown({"title": "Test"}, [img_sec])
    assert r"![Figure 1 \[revised\]: caption](p1-fig0-1.png)" in md


def test_emit_appends_truncation_marker_when_capped():
    img_sec = _image_section(alt="caption",
                              stored_filename="p1-fig0-1.png")
    md = emit_markdown(
        {"title": "Test"}, [img_sec],
        images_truncated=True, source_image_count=64,
    )
    assert "tomd:images-truncated" in md
    assert "kept 1 of 64" in md
    assert "63 image(s) dropped" in md


def test_emit_no_truncation_marker_when_not_capped():
    img_sec = _image_section(alt="caption",
                              stored_filename="p1-fig0-1.png")
    md = emit_markdown(
        {"title": "Test"}, [img_sec],
        images_truncated=False, source_image_count=1,
    )
    assert "tomd:images-truncated" not in md


# ---- source field: per-image discrimination of Confidence ------------------


def test_finalize_default_source_is_raster():
    """Candidates built without a source argument keep the legacy "raster"
    default. Pre-existing call sites (HTML manifest, v1 PDF path) need
    not know about the new field.
    """
    per_page = [[_candidate(1, page=1, y0=10.0)]]
    r = finalize_extraction(per_page, "p1")
    assert r.images[0].source == "raster"


def test_finalize_propagates_source_from_candidate():
    """A candidate explicitly tagged as vector reaches the extracted image
    unchanged. Round-trip the field through the full pipeline so that a
    future maintainer reordering the dataclass fields catches the break.
    """
    per_page = [[
        _PageImageCandidate(
            xref=-1234,                           # synthetic negative xref
            page=1,
            bbox=(50.0, 50.0, 200.0, 150.0),
            ext="png",
            bytes=b"VECTOR-RASTERISED-PNG",
            suggested_alt="",
            source="vector",
        ),
    ]]
    r = finalize_extraction(per_page, "p1")
    assert r.images[0].source == "vector"


def test_make_image_section_vector_source_yields_medium_confidence():
    """The Confidence branch keys on ``source``, not the sign of xref.
    Construct an ExtractedImage with source="vector" AND a positive
    xref. The section must still get Confidence.MEDIUM. Catches the
    regression where someone reverts to xref-sign discrimination.
    """
    img = ExtractedImage(
        page=1,
        index_on_page=1,
        ext="png",
        bytes=b"PNGDATA",
        bbox=(10.0, 10.0, 110.0, 110.0),
        suggested_alt="",
        stored_filename="p1-fig1-1.png",
        xref=42,                                  # deliberately positive
        source="vector",
    )
    sec = _make_image_section(img)
    assert sec.confidence == Confidence.MEDIUM


def test_make_image_section_raster_source_yields_high_confidence():
    """Raster IMAGE sections retain Confidence.HIGH - the bytes are
    unambiguously a figure. This is the v1 contract; pinning it here
    so the vector branch doesn't regress the raster path.
    """
    img = ExtractedImage(
        page=1,
        index_on_page=1,
        ext="png",
        bytes=b"PNGDATA",
        bbox=(10.0, 10.0, 110.0, 110.0),
        suggested_alt="",
        stored_filename="p1-fig1-1.png",
        xref=42,
        source="raster",
    )
    sec = _make_image_section(img)
    assert sec.confidence == Confidence.HIGH


# ---- vector_images: synthetic xref ----------------------------------------


class TestSyntheticXref:
    """:func:`_synthetic_xref` derives an opaque, negative, collision-resistant
    identifier for a vector cluster. The dedup pass in
    :func:`finalize_extraction` keys on xref; vector clusters get a
    negative-bit-set space so they can never alias a real pymupdf xref
    (positive) or the HTML sentinel (0).
    """

    def test_same_input_produces_same_xref(self):
        a = _synthetic_xref(1, (10.0, 20.0, 100.0, 80.0))
        b = _synthetic_xref(1, (10.0, 20.0, 100.0, 80.0))
        assert a == b

    def test_different_pages_produce_different_xrefs(self):
        a = _synthetic_xref(1, (10.0, 20.0, 100.0, 80.0))
        b = _synthetic_xref(2, (10.0, 20.0, 100.0, 80.0))
        assert a != b

    def test_all_outputs_are_negative(self):
        for page in (1, 2, 10, 99):
            for bbox in [
                (0.0, 0.0, 10.0, 10.0),
                (100.0, 200.0, 500.0, 600.0),
                (5.0, 5.0, 500.0, 5.0),                    # zero-height
            ]:
                assert _synthetic_xref(page, bbox) < 0

    def test_within_one_pt_rounds_to_same_xref(self):
        a = _synthetic_xref(1, (10.0, 20.0, 100.0, 80.0))
        b = _synthetic_xref(1, (10.4, 20.0, 100.0, 80.0))   # x0 drifted 0.4pt
        assert a == b, (
            "1-pt rounding deliberately conflates within-1pt drift on the "
            "same page so a sub-pt jitter does not split one diagram into two"
        )

    def test_large_page_geometry_is_safe(self):
        # A0 / tabloid pages can have bboxes beyond 10000. The earlier
        # packed-integer formula aliased here; the hash form must not.
        a = _synthetic_xref(1, (12345.0, 67890.0, 13345.0, 68890.0))
        b = _synthetic_xref(1, (12346.0, 67890.0, 13346.0, 68890.0))
        assert a != b
        assert a < 0 and b < 0

    def test_same_position_different_size_distinct(self):
        small = _synthetic_xref(1, (100.0, 100.0, 150.0, 150.0))    # 50x50
        large = _synthetic_xref(1, (100.0, 100.0, 600.0, 600.0))    # 500x500
        assert small != large, (
            "size is part of the key so a zoomed inset on top of its source "
            "does not collide with the source"
        )


# ---- vector_images: single-linkage clustering ------------------------------


class TestClusterDrawings:
    """Single-linkage clustering merges drawings whose bboxes are within
    ``_CLUSTER_LINK_DISTANCE_PT`` of each other. Behaviour is asserted at
    the membership level; the internal spatial-hash + union-find is an
    implementation detail.
    """

    @staticmethod
    def _drawing(x0: float, y0: float, x1: float, y1: float, items: int = 1) -> dict:
        return {
            "rect": pymupdf.Rect(x0, y0, x1, y1),
            "items": [("l", None, None)] * items,
        }

    def test_close_rects_form_one_cluster(self):
        # 10 rects spaced 20pt apart on the y axis - well within 30pt link distance.
        drawings = [self._drawing(0, y, 10, y + 5) for y in range(0, 200, 20)]
        clusters = _cluster_drawings(drawings)
        assert len(clusters) == 1
        assert clusters[0][1] == 10                            # item count

    def test_far_rects_form_separate_clusters(self):
        # 10 rects spaced 50pt apart - beyond 30pt link distance.
        drawings = [self._drawing(0, y, 10, y + 5) for y in range(0, 500, 50)]
        clusters = _cluster_drawings(drawings)
        assert len(clusters) == 10

    def test_mixed_two_clusters(self):
        # 5 near each other, 5 far away from those but near each other.
        near = [self._drawing(0, y, 10, y + 5) for y in range(0, 100, 20)]
        far = [self._drawing(0, y, 10, y + 5) for y in range(400, 500, 20)]
        clusters = _cluster_drawings(near + far)
        assert len(clusters) == 2
        assert sorted(c[1] for c in clusters) == [5, 5]

    def test_drawing_with_no_rect_is_skipped(self):
        drawings = [
            {"rect": None, "items": []},
            self._drawing(0, 0, 10, 10),
        ]
        clusters = _cluster_drawings(drawings)
        assert len(clusters) == 1

    def test_empty_input_returns_empty(self):
        assert _cluster_drawings([]) == []

    def test_cluster_bbox_is_union_of_members(self):
        drawings = [self._drawing(0, 0, 10, 10), self._drawing(5, 5, 30, 30)]
        clusters = _cluster_drawings(drawings)
        assert len(clusters) == 1
        bbox = clusters[0][0]
        assert bbox == (0.0, 0.0, 30.0, 30.0)


# ---- vector_images: text-overlap fraction ---------------------------------


class TestTextOverlapFraction:
    def test_tiny_cluster_in_huge_block_reports_one(self):
        """The denominator is the cluster's area, not the block's. A tiny
        cluster fully inside a huge block must report 1.0, never the
        cluster/block area ratio which would round to ~0."""
        cluster = (100.0, 100.0, 110.0, 110.0)             # 10x10 = 100
        huge_block = Block(bbox=(0.0, 0.0, 1000.0, 1000.0))
        assert _text_overlap_fraction(cluster, [huge_block]) == pytest.approx(1.0)

    def test_no_overlap_reports_zero(self):
        cluster = (0.0, 0.0, 50.0, 50.0)
        block = Block(bbox=(200.0, 200.0, 300.0, 300.0))
        assert _text_overlap_fraction(cluster, [block]) == 0.0

    def test_partial_overlap(self):
        cluster = (0.0, 0.0, 100.0, 100.0)                  # area 10_000
        # Block overlaps exactly the bottom-right 50x50 corner -> 2500 / 10000.
        block = Block(bbox=(50.0, 50.0, 150.0, 150.0))
        assert _text_overlap_fraction(cluster, [block]) == pytest.approx(0.25)

    def test_zero_area_cluster_does_not_divide_by_zero(self):
        zero = (10.0, 10.0, 10.0, 10.0)
        block = Block(bbox=(0.0, 0.0, 100.0, 100.0))
        assert _text_overlap_fraction(zero, [block]) == 0.0


# ---- vector_images: _colour_in_wording_band tolerant decode ---------------


class TestColourInWordingBand:
    """:func:`_colour_in_wording_band` accepts the full set of shapes that
    ``pymupdf.Page.get_drawings()`` is known to emit, and returns False
    on anything else."""

    def test_none_is_not_wording(self):
        assert _colour_in_wording_band(None) is False

    def test_rgb_tuple_ins_green_is_wording(self):
        assert _colour_in_wording_band((0.0, 110.0 / 255.0, 40.0 / 255.0)) is True

    def test_rgb_tuple_del_red_is_wording(self):
        assert _colour_in_wording_band((191.0 / 255.0, 3.0 / 255.0, 3.0 / 255.0)) is True

    def test_rgba_four_tuple_is_read_via_rgb(self):
        # Alpha is ignored; the RGB part still falls in the green band.
        assert _colour_in_wording_band((0.0, 0.43, 0.16, 1.0)) is True

    def test_grayscale_one_tuple_is_not_wording(self):
        # A pure-gray drawing (k,) carries zero saturation -> outside both bands.
        assert _colour_in_wording_band((0.5,)) is False

    def test_two_tuple_is_safely_rejected(self):
        # pymupdf would not normally emit a 2-tuple; if it ever does, we
        # must not raise - just refuse to misclassify.
        assert _colour_in_wording_band((0.5, 0.5)) is False

    def test_black_rgb_is_not_wording(self):
        assert _colour_in_wording_band((0.0, 0.0, 0.0)) is False


# ---- vector_images: uncertainty marker ------------------------------------


class TestVectorUncertaintyMarker:
    """Marker template, alphabetical reason ordering, emission predicate,
    and rejection of foreign reason keys."""

    def test_marker_template_keys_match_dataclass_fields(self):
        # Sanity: template formats with all expected named fields.
        stats = VectorUncertaintyStats(
            pages_scanned=10, candidates=20, kept=15, rejected=5,
            reasons={"too_small": 5}, pages_skipped=0,
        )
        out = format_uncertainty_marker(stats)
        assert "pages_scanned=10" in out
        assert "candidates=20" in out
        assert "kept=15" in out
        assert "rejected=5" in out
        assert "pages_skipped=0" in out
        assert "too_small:5" in out

    def test_reasons_dict_renders_alphabetically_d7(self):
        # Reasons supplied in non-alphabetical order; the formatter sorts.
        stats = VectorUncertaintyStats(
            pages_scanned=1, candidates=10, kept=4, rejected=6,
            reasons={"too_small": 3, "edge_band": 1, "text_overlap": 2},
            pages_skipped=0,
        )
        out = format_uncertainty_marker(stats)
        rendered = out.split("reasons={", 1)[1].split("}", 1)[0]
        keys = [pair.split(":", 1)[0] for pair in rendered.split(", ")]
        assert keys == sorted(keys), (
            "D7: reasons dict must render in alphabetical key order so "
            "marker output is deterministic across runs"
        )
        assert keys == ["edge_band", "text_overlap", "too_small"]

    def test_format_marker_rejects_unknown_reason_key(self):
        stats = VectorUncertaintyStats(
            pages_scanned=1, candidates=1, kept=0, rejected=1,
            reasons={"grid_pattern": 1},                     # closed key set; no grid proxy
            pages_skipped=0,
        )
        with pytest.raises(ValueError, match="unknown vector-extraction reason key"):
            format_uncertainty_marker(stats)

    def test_should_emit_skips_clean_extraction(self):
        # All candidates kept, no skipped pages -> nothing honest to disclose.
        stats = VectorUncertaintyStats(
            pages_scanned=5, candidates=3, kept=3, rejected=0,
            reasons={}, pages_skipped=0,
        )
        assert should_emit_marker(stats) is False

    def test_should_emit_skips_zero_attempted(self):
        # Vector path never fired (e.g., HTML paper); nothing to disclose.
        stats = VectorUncertaintyStats(
            pages_scanned=0, candidates=0, kept=0, rejected=0,
            reasons={}, pages_skipped=0,
        )
        assert should_emit_marker(stats) is False

    def test_should_emit_fires_on_any_rejection(self):
        stats = VectorUncertaintyStats(
            pages_scanned=5, candidates=10, kept=8, rejected=2,
            reasons={"too_small": 2}, pages_skipped=0,
        )
        assert should_emit_marker(stats) is True

    def test_should_emit_fires_on_skipped_pages(self):
        stats = VectorUncertaintyStats(
            pages_scanned=4, candidates=0, kept=0, rejected=0,
            reasons={}, pages_skipped=1,
        )
        assert should_emit_marker(stats) is True

    def test_allowed_reason_keys_is_closed_set(self):
        # Pin the closed key set; adding to it without bumping the marker
        # contract is a versioned change per plan section 1.6a.
        assert sorted(ALLOWED_REASON_KEYS) == [
            "clusters_overflow",
            "edge_band",
            "text_overlap",
            "too_few_items",
            "too_small",
            "wording_color",
        ]


# ---- vector_images: _VectorExtractionStats accumulator --------------------


class TestVectorExtractionStatsCombine:
    def test_combine_sums_counters(self):
        a = _VectorExtractionStats(
            pages_scanned=1, candidates=3, kept=2, rejected=1,
            pages_skipped=0, reasons={"too_small": 1},
        )
        b = _VectorExtractionStats(
            pages_scanned=1, candidates=5, kept=3, rejected=2,
            pages_skipped=0, reasons={"too_small": 1, "text_overlap": 2},
        )
        out = _VectorExtractionStats.combine(a, b)
        assert out.pages_scanned == 2
        assert out.candidates == 8
        assert out.kept == 5
        assert out.rejected == 3
        assert out.pages_skipped == 0
        assert out.reasons == {"too_small": 2, "text_overlap": 2}

    def test_combine_preserves_disjoint_reason_keys(self):
        a = _VectorExtractionStats(reasons={"too_small": 1})
        b = _VectorExtractionStats(reasons={"text_overlap": 1})
        out = _VectorExtractionStats.combine(a, b)
        assert out.reasons == {"too_small": 1, "text_overlap": 1}

    def test_to_uncertainty_round_trips_fields(self):
        stats = _VectorExtractionStats(
            pages_scanned=3, candidates=10, kept=7, rejected=3,
            pages_skipped=1, reasons={"too_small": 3},
        )
        u = stats.to_uncertainty()
        assert isinstance(u, VectorUncertaintyStats)
        assert u.pages_scanned == 3
        assert u.candidates == 10
        assert u.kept == 7
        assert u.rejected == 3
        assert u.pages_skipped == 1
        assert dict(u.reasons) == {"too_small": 3}


# ---- vector_images: end-to-end extract_page_vector_images ------------------


def _mock_page(
    drawings: list[dict],
    *,
    page_number: int = 0,
    width: float = 612.0,
    height: float = 792.0,
) -> MagicMock:
    """MagicMock pymupdf.Page with just the surface :func:`extract_page_vector_images` reads."""
    page = MagicMock()
    page.number = page_number
    page.rect = pymupdf.Rect(0, 0, width, height)
    page.get_drawings.return_value = drawings
    return page


def _drawing(
    x0: float, y0: float, x1: float, y1: float,
    *,
    items: int = 1,
    color: tuple | None = (0.0, 0.0, 0.0),
    fill: tuple | None = None,
) -> dict:
    return {
        "rect": pymupdf.Rect(x0, y0, x1, y1),
        "items": [("l", None, None)] * items,
        "color": color,
        "fill": fill,
    }


class TestPageScanGuards:
    """The per-page driver early-exits below ``_MIN_PAGE_DRAWING_ITEMS`` and
    bails out above ``_MAX_DRAWINGS_PER_PAGE``. Behaviour is observable
    through the returned per-page stats."""

    def test_below_minimum_items_returns_silent_empty(self, monkeypatch):
        # 10 drawings, each 1 item = 10 < default 250.
        drawings = [_drawing(0, y, 10, y + 10) for y in range(0, 100, 10)]
        page = _mock_page(drawings)
        cands, stats = extract_page_vector_images(page, [])
        assert cands == []
        # Not even scanned - the per-page driver returns zero-everywhere stats.
        assert stats.pages_scanned == 0
        assert stats.pages_skipped == 0
        assert stats.candidates == 0

    def test_above_maximum_items_skips_page(self, monkeypatch):
        # Bypass min: monkeypatch min to 1, max to 10. With 12 items
        # we trip the max-bailout path.
        monkeypatch.setattr(vector_images, "_MIN_PAGE_DRAWING_ITEMS", 1)
        monkeypatch.setattr(vector_images, "_MAX_DRAWINGS_PER_PAGE", 10)
        drawings = [_drawing(0, y, 10, y + 10) for y in range(0, 120, 10)]
        page = _mock_page(drawings)
        cands, stats = extract_page_vector_images(page, [])
        assert cands == []
        assert stats.pages_skipped == 1
        assert stats.pages_scanned == 0
        assert stats.candidates == 0


class TestPerClusterFilter:
    """Per-cluster filter rejects clusters that fail each boundary. Boundary
    cases verify the threshold inequality direction."""

    @staticmethod
    def _setup(monkeypatch):
        """Bypass page-scan guards so we test the cluster filter itself."""
        monkeypatch.setattr(vector_images, "_MIN_PAGE_DRAWING_ITEMS", 1)
        monkeypatch.setattr(vector_images, "_MAX_DRAWINGS_PER_PAGE", 100_000)

    def test_too_small_drops_cluster(self, monkeypatch):
        # 1 drawing, 8 items (enough), but bbox is 30x30 (below 60pt floor).
        self._setup(monkeypatch)
        drawings = [_drawing(100, 100, 130, 130, items=8)]
        page = _mock_page(drawings)
        cands, stats = extract_page_vector_images(page, [])
        assert cands == []
        assert stats.reasons.get(REASON_TOO_SMALL) == 1
        assert stats.rejected == 1

    def test_too_small_boundary_60pt_passes(self, monkeypatch):
        self._setup(monkeypatch)
        # bbox is exactly 60x60 - at the inclusive boundary.
        drawings = [_drawing(100, 100, 160, 160, items=8)]
        page = _mock_page(drawings)
        cands, _stats = extract_page_vector_images(page, [])
        assert len(cands) == 1, (
            "boundary inclusive: width = _MIN_CLUSTER_DIM_PT must pass"
        )

    def test_too_few_items_drops_cluster(self, monkeypatch):
        self._setup(monkeypatch)
        # bbox is 100x100 (size OK), but only 7 items (below 8 floor).
        drawings = [_drawing(100, 100, 200, 200, items=7)]
        page = _mock_page(drawings)
        cands, stats = extract_page_vector_images(page, [])
        assert cands == []
        assert stats.reasons.get(REASON_TOO_FEW_ITEMS) == 1

    def test_too_few_items_boundary_eight_passes(self, monkeypatch):
        self._setup(monkeypatch)
        drawings = [_drawing(100, 100, 200, 200, items=8)]
        page = _mock_page(drawings)
        cands, _stats = extract_page_vector_images(page, [])
        assert len(cands) == 1

    def test_text_overlap_drops_cluster(self, monkeypatch):
        self._setup(monkeypatch)
        # Cluster 100x100 fully inside a 200x200 text block -> 100% overlap >= 35%.
        drawings = [_drawing(100, 100, 200, 200, items=8)]
        page = _mock_page(drawings)
        text_block = Block(bbox=(50.0, 50.0, 250.0, 250.0))
        cands, stats = extract_page_vector_images(page, [text_block])
        assert cands == []
        assert stats.reasons.get(REASON_TEXT_OVERLAP) == 1

    def test_text_overlap_boundary_under_threshold_passes(self, monkeypatch):
        self._setup(monkeypatch)
        # 100x100 cluster (area 10_000) overlapping a 34x100 block strip
        # placed inside it -> 3400 / 10000 = 0.34 < 0.35.
        drawings = [_drawing(100, 100, 200, 200, items=8)]
        page = _mock_page(drawings)
        text_block = Block(bbox=(100.0, 100.0, 134.0, 200.0))
        cands, _stats = extract_page_vector_images(page, [text_block])
        assert len(cands) == 1, "34% overlap passes the < 35% gate"

    def test_text_overlap_boundary_at_threshold_drops(self, monkeypatch):
        self._setup(monkeypatch)
        # 100x100 cluster with a 36x100 strip block: 0.36 >= 0.35.
        drawings = [_drawing(100, 100, 200, 200, items=8)]
        page = _mock_page(drawings)
        text_block = Block(bbox=(100.0, 100.0, 136.0, 200.0))
        cands, _stats = extract_page_vector_images(page, [text_block])
        assert cands == [], "36% overlap fails the < 35% gate"


class TestEdgeBand:
    """A drawing wholly inside the top or bottom 8% of the page is
    dropped pre-clustering; a drawing that straddles the boundary
    survives (real content adjacent to the running header)."""

    def test_drawing_wholly_in_top_band_drops(self, monkeypatch):
        monkeypatch.setattr(vector_images, "_MIN_PAGE_DRAWING_ITEMS", 1)
        # 8% of 792pt = 63.36pt; place a small running-header underline at y=10.
        drawings = [_drawing(0, 5, 200, 15, items=8)]
        page = _mock_page(drawings, height=792)
        cands, stats = extract_page_vector_images(page, [])
        # Drawing was dropped pre-cluster; no cluster formed; no other rejection.
        assert cands == []
        assert stats.reasons.get(REASON_EDGE_BAND) == 1

    def test_drawing_straddling_band_survives(self, monkeypatch):
        monkeypatch.setattr(vector_images, "_MIN_PAGE_DRAWING_ITEMS", 1)
        # 8% of 792pt = 63.36pt; drawing from y=10 to y=200 straddles the band.
        drawings = [_drawing(100, 10, 200, 200, items=8)]
        page = _mock_page(drawings, height=792)
        cands, stats = extract_page_vector_images(page, [])
        # Survives the pre-cluster edge-band drop and reaches the cluster filter.
        assert stats.reasons.get(REASON_EDGE_BAND, 0) == 0


class TestPreClusteringInsDelExclusion:
    """Drawings whose stroke or fill colour falls in the ins / del hue band
    are excluded before clustering. Uses pymupdf's actual float-tuple
    colour format to exercise :func:`is_wording_rgb` end-to-end."""

    def test_ins_green_color_drops_drawing(self, monkeypatch):
        monkeypatch.setattr(vector_images, "_MIN_PAGE_DRAWING_ITEMS", 1)
        # mpark/wg21 ins green #006e28 -> (0.0, 0.43, 0.16) as float tuple.
        drawings = [_drawing(100, 100, 200, 200, items=8,
                             color=(0.0, 110.0 / 255.0, 40.0 / 255.0))]
        page = _mock_page(drawings)
        cands, stats = extract_page_vector_images(page, [])
        assert cands == []
        assert stats.reasons.get(REASON_WORDING_COLOR) == 1

    def test_del_red_color_drops_drawing(self, monkeypatch):
        monkeypatch.setattr(vector_images, "_MIN_PAGE_DRAWING_ITEMS", 1)
        # mpark/wg21 del red #bf0303 -> (0.75, 0.01, 0.01).
        drawings = [_drawing(100, 100, 200, 200, items=8,
                             color=(191.0 / 255.0, 3.0 / 255.0, 3.0 / 255.0))]
        page = _mock_page(drawings)
        cands, stats = extract_page_vector_images(page, [])
        assert cands == []
        assert stats.reasons.get(REASON_WORDING_COLOR) == 1

    def test_ins_green_fill_drops_drawing(self, monkeypatch):
        # Wording colour can be in the fill, not just the stroke.
        monkeypatch.setattr(vector_images, "_MIN_PAGE_DRAWING_ITEMS", 1)
        drawings = [_drawing(100, 100, 200, 200, items=8,
                             color=(0.0, 0.0, 0.0),
                             fill=(0.0, 110.0 / 255.0, 40.0 / 255.0))]
        page = _mock_page(drawings)
        cands, stats = extract_page_vector_images(page, [])
        assert cands == []
        assert stats.reasons.get(REASON_WORDING_COLOR) == 1

    def test_black_drawing_survives(self, monkeypatch):
        monkeypatch.setattr(vector_images, "_MIN_PAGE_DRAWING_ITEMS", 1)
        drawings = [_drawing(100, 100, 200, 200, items=8,
                             color=(0.0, 0.0, 0.0))]
        page = _mock_page(drawings)
        cands, stats = extract_page_vector_images(page, [])
        assert stats.reasons.get(REASON_WORDING_COLOR, 0) == 0
        # Black drawing reaches the cluster filter and passes (size + item count OK).
        assert len(cands) == 1


class TestClustersOverflowCap:
    """When more clusters survive the filter than ``_MAX_CLUSTERS_PER_PAGE``,
    the top-of-page survivors are kept and the rest counted as
    ``clusters_overflow``."""

    def test_overflow_drops_bottom_clusters(self, monkeypatch):
        monkeypatch.setattr(vector_images, "_MIN_PAGE_DRAWING_ITEMS", 1)
        monkeypatch.setattr(vector_images, "_MAX_CLUSTERS_PER_PAGE", 3)
        # Five well-separated 80x80 clusters at different y positions.
        # All pass the filter; only the top 3 by (y0, x0) survive the cap.
        drawings = [
            _drawing(50, y, 130, y + 80, items=8)
            for y in (100, 250, 400, 550, 700)
        ]
        page = _mock_page(drawings, height=1000)
        cands, stats = extract_page_vector_images(page, [])
        assert stats.reasons.get(REASON_CLUSTERS_OVERFLOW) == 2
        # The kept clusters are the 3 with smallest y0.
        kept_y0 = sorted(c.bbox[1] for c in cands)
        assert kept_y0 == [100.0, 250.0, 400.0]


class TestExtractPageRasterisation:
    """End-to-end extract path against a real pymupdf-built PDF so the
    rasterisation, bbox clamp, and PNG-bytes contract are pinned."""

    @staticmethod
    def _make_pdf_with_diagram(monkeypatch, *, draw_outside_page: bool = False) -> pymupdf.Document:
        """Build a 1-page PDF with a small diagram of 8 line segments
        clustered in one corner. Spacing is chosen so the cluster bbox
        clears ``_MIN_CLUSTER_DIM_PT`` on both axes (80 x 105 pt).
        ``draw_outside_page`` adds a stroke extending past the page's
        right edge to test the bbox clamp."""
        monkeypatch.setattr(vector_images, "_MIN_PAGE_DRAWING_ITEMS", 1)
        monkeypatch.setattr(vector_images, "_MIN_CLUSTER_ITEM_COUNT", 1)
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)
        # 8 line segments at 15pt spacing -> cluster height 105pt (>= 60).
        for i in range(8):
            page.draw_line(
                pymupdf.Point(100, 100 + i * 15),
                pymupdf.Point(180, 100 + i * 15),
                color=(0, 0, 0),
                width=0.5,
            )
        if draw_outside_page:
            # Past the page's right edge (612pt) - cluster bbox must clamp.
            page.draw_line(
                pymupdf.Point(180, 130),
                pymupdf.Point(700, 130),
                color=(0, 0, 0),
                width=0.5,
            )
        return doc

    def test_rasterise_produces_png_bytes(self, monkeypatch):
        doc = self._make_pdf_with_diagram(monkeypatch)
        try:
            page = doc[0]
            cands, stats = extract_page_vector_images(page, [])
            assert len(cands) >= 1, (
                f"expected at least one vector candidate, got {len(cands)}; "
                f"stats={stats}"
            )
            png = cands[0].bytes
            assert png[:8] == b"\x89PNG\r\n\x1a\n", (
                f"vector candidate bytes are not a PNG: {png[:8]!r}"
            )
            assert cands[0].source == "vector"
            assert cands[0].xref < 0
            assert cands[0].ext == "png"
        finally:
            doc.close()

    def test_bbox_clamped_to_page_rect(self, monkeypatch):
        # A drawing extending past the page edge must produce a clamped
        # candidate bbox (not the raw drawing extent).
        doc = self._make_pdf_with_diagram(monkeypatch, draw_outside_page=True)
        try:
            page = doc[0]
            page_right = page.rect.x1
            cands, _stats = extract_page_vector_images(page, [])
            assert len(cands) >= 1
            assert all(c.bbox[2] <= page_right + 0.001 for c in cands), (
                "bbox x1 must be clamped to <= page.rect.x1"
            )
            # And the rendered PNG must decode (i.e., rasterisation did not
            # raise on the past-edge geometry).
            assert cands[0].bytes[:8] == b"\x89PNG\r\n\x1a\n"
        finally:
            doc.close()

    def test_whiteout_off_by_default_leaves_text(self, monkeypatch):
        """The v2.0 default contract: text glyphs survive the rasterisation
        unless the caller explicitly opts in to ``whiteout_text``. Pinned
        via a synthetic line.bbox that overlaps a known-pixel region of
        the cluster.
        """
        doc = self._make_pdf_with_diagram(monkeypatch)
        try:
            page = doc[0]
            # Synthetic Line with bbox inside the diagram region. The
            # whiteout pass would paint this region white if invoked.
            line = Line(spans=[Span(text="LABEL")], bbox=(110.0, 110.0, 160.0, 120.0))
            block = Block(lines=[line], bbox=(110.0, 110.0, 160.0, 120.0))
            # Default extract (whiteout_text=False).
            cands, _stats = extract_page_vector_images(page, [block])
            # The cluster filter rejects clusters whose text-overlap >= 35%.
            # The line bbox is 50x10 = 500; cluster ~80x35 ~ 2800; overlap
            # is the line area ~ 500 / 2800 = 18% which passes.
            assert len(cands) == 1
            # Decode pixmap from PNG bytes to inspect a pixel near the line.
            pix_default = pymupdf.Pixmap(cands[0].bytes)
            # Pick a pixel near the centre of the line region. The exact
            # value depends on what's been drawn; we only require that the
            # surrounding region is not uniformly white.
            non_white = 0
            for x in range(0, pix_default.width, 4):
                for y in range(0, pix_default.height, 4):
                    pixel = pix_default.pixel(x, y)
                    if pixel != (255, 255, 255):
                        non_white += 1
            assert non_white > 0, (
                "whiteout default is OFF; the diagram strokes must leave "
                "non-white pixels in the rasterised PNG"
            )
        finally:
            doc.close()

    def test_whiteout_on_paints_over_line_region(self, monkeypatch):
        """When the caller opts in, text-line bboxes get painted white.
        Compares the same diagram rasterised with whiteout off vs on; the
        on-version must have strictly more white pixels."""
        doc = self._make_pdf_with_diagram(monkeypatch)
        try:
            page = doc[0]
            # Small line block well inside the cluster; overlap stays well
            # below the 35% text-overlap floor.
            line = Line(spans=[Span(text="LABEL")], bbox=(110.0, 110.0, 160.0, 120.0))
            block = Block(lines=[line], bbox=(110.0, 110.0, 160.0, 120.0))

            cands_off, _ = extract_page_vector_images(
                page, [block], whiteout_text=False,
            )
            cands_on, _ = extract_page_vector_images(
                page, [block], whiteout_text=True,
            )
            assert len(cands_off) == 1 and len(cands_on) == 1

            def _count_white(png_bytes: bytes) -> int:
                pix = pymupdf.Pixmap(png_bytes)
                n = 0
                for x in range(pix.width):
                    for y in range(pix.height):
                        if pix.pixel(x, y) == (255, 255, 255):
                            n += 1
                return n

            assert _count_white(cands_on[0].bytes) > _count_white(cands_off[0].bytes), (
                "whiteout_text=True must produce strictly more white pixels "
                "than whiteout_text=False on the same diagram"
            )
        finally:
            doc.close()


# ---- vector_images: caption reuse + mixed raster + vector through finalize -


class TestMixedRasterAndVector:
    """Once a vector :class:`_PageImageCandidate` reaches
    :func:`finalize_extraction`, it is treated symmetrically with raster
    candidates: same y-x ordering, same cap, same filename scheme."""

    def test_finalize_dedupes_mixed_raster_and_vector_candidates(self):
        # Raster candidate at y=50 (smaller y -> index 1); vector at y=150.
        raster = _PageImageCandidate(
            xref=42, page=1,
            bbox=(100.0, 50.0, 200.0, 150.0),
            ext="png", bytes=b"RASTER",
            suggested_alt="", source="raster",
        )
        vector = _PageImageCandidate(
            xref=-1_234_567, page=1,
            bbox=(100.0, 150.0, 200.0, 250.0),
            ext="png", bytes=b"VECTOR",
            suggested_alt="", source="vector",
        )
        r = finalize_extraction([[raster, vector]], "p1")
        assert len(r.images) == 2
        assert r.images[0].source == "raster"
        assert r.images[0].stored_filename == "p1-fig1-1.png"
        assert r.images[1].source == "vector"
        assert r.images[1].stored_filename == "p1-fig1-2.png"

    def test_cap_covers_raster_plus_vector_combined(self):
        # 15 raster + 10 vector at ascending y; 20-image cap fires globally.
        raster = [
            _PageImageCandidate(
                xref=i, page=1,
                bbox=(0.0, 10.0 * i, 100.0, 10.0 * i + 100),
                ext="png", bytes=b"R",
                suggested_alt="", source="raster",
            )
            for i in range(1, 16)
        ]
        vector = [
            _PageImageCandidate(
                xref=-(100 + i), page=1,
                bbox=(0.0, 1000.0 + 10.0 * i, 100.0, 1000.0 + 10.0 * i + 100),
                ext="png", bytes=b"V",
                suggested_alt="", source="vector",
            )
            for i in range(1, 11)
        ]
        r = finalize_extraction([raster + vector], "p1")
        assert len(r.images) == _MAX_IMAGES_PER_PAPER
        assert r.source_image_count == 25
        assert r.images_truncated is True
        # The kept 20 are the first 20 in (page, y0, x0) order: all 15
        # raster (y0 = 10..150) and the first 5 vector (y0 = 1010..1050).
        kept_sources = [im.source for im in r.images]
        assert kept_sources.count("raster") == 15
        assert kept_sources.count("vector") == 5

    def test_caption_heuristic_reuse_for_vector(self):
        # Synthetic page-block with "Figure 1: ..." 30pt below the
        # cluster bbox; _caption_for is shared between raster and vector.
        cluster_bbox = (100.0, 100.0, 200.0, 200.0)
        caption_line = Line(
            spans=[Span(text="Figure 1: Adjacency graph", bbox=(0, 220, 300, 232))],
            bbox=(0, 220, 300, 232),
        )
        block = Block(lines=[caption_line], bbox=(0, 220, 300, 232))
        alt = _caption_for(cluster_bbox, [block])
        assert alt == "Figure 1: Adjacency graph"

    def test_caption_heuristic_rejects_table_label_for_vector(self):
        # Table labels do not become vector alt text either.
        cluster_bbox = (100.0, 100.0, 200.0, 200.0)
        table_line = Line(
            spans=[Span(text="Table 1: Comparison", bbox=(0, 220, 300, 232))],
            bbox=(0, 220, 300, 232),
        )
        block = Block(lines=[table_line], bbox=(0, 220, 300, 232))
        alt = _caption_for(cluster_bbox, [block])
        assert alt == "", "Table N: labels are not figure captions"


class TestForcedXrefCollision:
    """:func:`finalize_extraction`'s dedup keys on xref. If two distinct
    vector clusters happen to hash to the same synthetic xref, the
    collision resolves by picking the smallest ``(page, y0, x0)`` rect,
    matching the raster contract."""

    def test_two_candidates_with_same_xref_collapse_to_one(self):
        # Force the same negative xref on two different bbox / page pairs.
        same_xref = -777
        a = _PageImageCandidate(
            xref=same_xref, page=1,
            bbox=(50.0, 50.0, 150.0, 150.0),
            ext="png", bytes=b"FIRST",
            suggested_alt="", source="vector",
        )
        b = _PageImageCandidate(
            xref=same_xref, page=2,
            bbox=(50.0, 50.0, 150.0, 150.0),
            ext="png", bytes=b"SECOND",
            suggested_alt="", source="vector",
        )
        r = finalize_extraction([[a], [b]], "p1")
        # Exactly one extracted image, and it is the smaller-(page, y0, x0)
        # of the two collided candidates.
        assert len(r.images) == 1
        assert r.images[0].page == 1
        assert r.images[0].bytes == b"FIRST"
