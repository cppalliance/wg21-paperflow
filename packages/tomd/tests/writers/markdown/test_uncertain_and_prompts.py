"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from typing import Any

import pytest

from tomd.domain import (
    BlockElement,
    CodeBlock,
    Confidence,
    Heading,
    ImageElement,
    ListBlock,
    PaperDocument,
    Paragraph,
    Provenance,
    TextSpan,
    UncertainElement,
    WordingBlock,
)
from tomd.lib.pdf.emit import emit_markdown, emit_prompts
from tomd.lib.pdf.types import Line, Section, SectionKind, Span
from tomd.prompts import build_reconcile_prompts
from tomd.writers import MarkdownWriter

_FRONT_MATTER_META: dict[str, Any] = {
    "title": "constexpr for <cmath>",
    "document": "P0533R9",
    "date": "2021-11-12",
    "intent": "change",
    "audience": "LWG, CWG",
    "reply-to": [
        "Edward J. Rosten <erosten@snap.com>",
        "Oliver J. Rosten <oliver.rosten@gmail.com>",
    ],
}


def _make_section(
    text: str,
    *,
    kind: SectionKind = SectionKind.PARAGRAPH,
    heading_level: int = 0,
    page_num: int = 0,
    mupdf_text: str = "",
    spatial_text: str = "",
    confidence: Confidence = Confidence.HIGH,
    monospace: bool = False,
) -> Section:
    lines = [
        Line(
            spans=[
                Span(
                    text=ln,
                    font_size=10.0,
                    monospace=monospace,
                    bbox=(50.0, float(i * 14), 400.0, float(i * 14 + 12)),
                )
            ],
            bbox=(50.0, float(i * 14), 400.0, float(i * 14 + 12)),
            page_num=page_num,
        )
        for i, ln in enumerate(text.split("\n"))
    ]
    return Section(
        kind=kind,
        text=text,
        confidence=confidence,
        heading_level=heading_level,
        lines=lines,
        mupdf_text=mupdf_text,
        spatial_text=spatial_text,
        page_num=page_num,
    )


def _sections_to_document(sections: list[Section]) -> PaperDocument:
    elements: list[BlockElement] = []
    for idx, sec in enumerate(sections):
        prov = Provenance(page=sec.page_num, confidence=sec.confidence)
        if sec.kind == SectionKind.UNCERTAIN:
            ctx_before = ""
            ctx_after = ""
            if idx > 0 and sections[idx - 1].kind != SectionKind.UNCERTAIN:
                ctx_before = sections[idx - 1].text[:200].strip()
            if idx + 1 < len(sections) and sections[idx + 1].kind != SectionKind.UNCERTAIN:
                ctx_after = sections[idx + 1].text[:200].strip()
            elements.append(
                UncertainElement(
                    mupdf_text=sec.mupdf_text,
                    spatial_text=sec.spatial_text,
                    page=sec.page_num,
                    text=sec.text,
                    context_before=ctx_before,
                    context_after=ctx_after,
                    provenance=prov,
                )
            )
        elif sec.kind in (SectionKind.HEADING, SectionKind.TITLE):
            level = 1 if sec.kind == SectionKind.TITLE else sec.heading_level
            elements.append(Heading(level, [TextSpan(sec.text)], provenance=prov))
        elif sec.kind == SectionKind.CODE:
            elements.append(
                CodeBlock(code=sec.text, language=sec.fence_lang, provenance=prov)
            )
        elif sec.kind == SectionKind.IMAGE:
            elements.append(ImageElement(caption="", alt="", provenance=prov))
        elif sec.kind == SectionKind.LIST:
            elements.append(ListBlock(items=[], provenance=prov))
        elif sec.kind == SectionKind.WORDING:
            elements.append(WordingBlock(children=[], provenance=prov))
        else:
            elements.append(Paragraph([TextSpan(sec.text)], provenance=prov))

    return PaperDocument(paper_id="P0000R0", elements=elements)


def _assert_twin_parity(
    sections: list[Section],
    meta: dict[str, Any] | None = None,
) -> tuple[str, list[str] | None]:
    metadata = meta or {}
    doc = _sections_to_document(sections)
    actual_md = MarkdownWriter().write(doc, meta=metadata)
    actual_prompts = build_reconcile_prompts(doc)
    assert actual_md == emit_markdown(metadata, sections)
    assert actual_prompts == emit_prompts(sections)
    return actual_md, actual_prompts


@pytest.mark.parametrize(
    ("sections", "meta", "expected_marker"),
    [
        pytest.param(
            [
                _make_section(
                    "uncertain lead line 1\nuncertain lead line 2",
                    kind=SectionKind.UNCERTAIN,
                    confidence=Confidence.UNCERTAIN,
                    page_num=0,
                    mupdf_text="mupdf lead",
                    spatial_text="spatial lead",
                ),
                _make_section("Following confident paragraph.", page_num=0),
            ],
            None,
            "<!-- tomd:uncertain:L3-L4 -->",
            id="uncertain-at-start-no-front-matter",
        ),
        pytest.param(
            [
                _make_section("Introductory paragraph.", page_num=1),
                _make_section(
                    "middle uncertain text",
                    kind=SectionKind.UNCERTAIN,
                    confidence=Confidence.UNCERTAIN,
                    page_num=2,
                    mupdf_text="mupdf middle",
                    spatial_text="spatial middle",
                ),
                _make_section("Concluding paragraph.", page_num=2),
            ],
            None,
            "<!-- tomd:uncertain:L5-L5 -->",
            id="uncertain-in-middle-no-front-matter",
        ),
        pytest.param(
            [
                _make_section(
                    "Section Intro",
                    kind=SectionKind.HEADING,
                    heading_level=2,
                    page_num=3,
                ),
                _make_section("Body text before uncertain region.", page_num=3),
                _make_section(
                    "trailing uncertain block\nwith two lines",
                    kind=SectionKind.UNCERTAIN,
                    confidence=Confidence.UNCERTAIN,
                    page_num=4,
                    mupdf_text="mupdf tail",
                    spatial_text="spatial tail",
                ),
            ],
            None,
            "<!-- tomd:uncertain:L7-L8 -->",
            id="uncertain-at-end-no-front-matter",
        ),
        pytest.param(
            [
                _make_section(
                    "int a = 1;\nint b = 2;\nreturn a + b;",
                    kind=SectionKind.CODE,
                    page_num=1,
                    monospace=True,
                ),
                _make_section(
                    "uncertain after multiline code block\nsecond line",
                    kind=SectionKind.UNCERTAIN,
                    confidence=Confidence.UNCERTAIN,
                    page_num=1,
                    mupdf_text="mupdf after code",
                    spatial_text="spatial after code",
                ),
            ],
            None,
            "<!-- tomd:uncertain:L9-L10 -->",
            id="uncertain-after-multiline-code-block",
        ),
        pytest.param(
            [
                _make_section("Preceding confident text.", page_num=1),
                _make_section(
                    "first uncertain region",
                    kind=SectionKind.UNCERTAIN,
                    confidence=Confidence.UNCERTAIN,
                    page_num=1,
                    mupdf_text="mupdf 1",
                    spatial_text="spatial 1",
                ),
                _make_section(
                    "second uncertain region\nspanning two lines",
                    kind=SectionKind.UNCERTAIN,
                    confidence=Confidence.UNCERTAIN,
                    page_num=2,
                    mupdf_text="mupdf 2",
                    spatial_text="spatial 2",
                ),
                _make_section("Following confident text.", page_num=2),
            ],
            None,
            "<!-- tomd:uncertain:L9-L10 -->",
            id="adjacent-uncertain-regions",
        ),
        pytest.param(
            [
                _make_section("First real paragraph.", page_num=0),
                _make_section("   ", kind=SectionKind.PARAGRAPH, page_num=0),
                _make_section("   ", kind=SectionKind.HEADING, heading_level=2, page_num=0),
                Section(kind=SectionKind.IMAGE, text="", confidence=Confidence.HIGH, page_num=0),
                _make_section(
                    "uncertain after skipped sections\nsecond line\nthird line",
                    kind=SectionKind.UNCERTAIN,
                    confidence=Confidence.UNCERTAIN,
                    page_num=1,
                    mupdf_text="mupdf after empty",
                    spatial_text="spatial after empty",
                ),
                _make_section("", kind=SectionKind.LIST, page_num=1),
                _make_section("", kind=SectionKind.WORDING, page_num=1),
                _make_section(
                    "second uncertain after empty list and wording",
                    kind=SectionKind.UNCERTAIN,
                    confidence=Confidence.UNCERTAIN,
                    page_num=2,
                    mupdf_text="mupdf 2",
                    spatial_text="spatial 2",
                ),
            ],
            None,
            "<!-- tomd:uncertain:L5-L7 -->",
            id="uncertain-after-empty-rendering-sections",
        ),
        pytest.param(
            [
                _make_section(
                    "uncertain at start after front matter",
                    kind=SectionKind.UNCERTAIN,
                    confidence=Confidence.UNCERTAIN,
                    page_num=0,
                    mupdf_text="mupdf start",
                    spatial_text="spatial start",
                ),
                _make_section(
                    (
                        "We propose simple criteria for selecting functions in <cmath> "
                        "which should be declared constexpr. " * 4
                    ).strip(),
                    page_num=0,
                ),
                _make_section(
                    "uncertain body line 1\nuncertain body line 2\n\n  ",
                    kind=SectionKind.UNCERTAIN,
                    confidence=Confidence.UNCERTAIN,
                    page_num=5,
                    mupdf_text="",
                    spatial_text="",
                ),
                _make_section("int abs(int j);", kind=SectionKind.CODE, page_num=6, monospace=True),
            ],
            _FRONT_MATTER_META,
            "<!-- tomd:uncertain:L14-L14 -->",
            id="uncertain-with-front-matter-and-long-neighbors",
        ),
        pytest.param(
            [
                _make_section("   ", kind=SectionKind.PARAGRAPH, page_num=1),
                _make_section(
                    "fallback text used when mupdf is empty",
                    kind=SectionKind.UNCERTAIN,
                    confidence=Confidence.UNCERTAIN,
                    page_num=2,
                    mupdf_text="",
                    spatial_text="explicit spatial",
                ),
                _make_section("Middle bridge.", page_num=2),
                _make_section(
                    "fallback text used when spatial is empty",
                    kind=SectionKind.UNCERTAIN,
                    confidence=Confidence.UNCERTAIN,
                    page_num=3,
                    mupdf_text="explicit mupdf",
                    spatial_text="",
                ),
                _make_section(
                    ("Following confident section exceeding two hundred characters. " * 5).strip(),
                    page_num=3,
                ),
            ],
            None,
            "<!-- tomd:uncertain:L3-L3 -->",
            id="asymmetric-extraction-fallbacks-and-long-context-after",
        ),
    ],
)
def test_twin_uncertain_and_prompts_parity(
    sections: list[Section],
    meta: dict[str, Any] | None,
    expected_marker: str,
):
    actual_md, actual_prompts = _assert_twin_parity(sections, meta=meta)
    assert expected_marker in actual_md
    assert actual_prompts is not None


def test_twin_prompts_none_when_no_uncertain():
    sections = [
        _make_section("Introduction", kind=SectionKind.HEADING, heading_level=2, page_num=0),
        _make_section("All sections are confident.", page_num=0),
    ]
    _, actual_prompts = _assert_twin_parity(sections)
    assert actual_prompts is None
