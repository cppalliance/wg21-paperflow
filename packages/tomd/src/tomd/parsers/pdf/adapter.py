"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from collections.abc import Callable
from pathlib import Path

from tomd.domain.diagnostics import Diagnostics
from tomd.domain.document import PaperDocument
from tomd.domain.elements import (
    BlockElement,
    Provenance,
    RawBlock,
    UncertainElement,
)
from tomd.domain.metadata import PaperMetadata
from tomd.lib.pdf.emit import _render_section_md
from tomd.lib.pdf.pipeline import PipelineResult, run_pipeline
from tomd.lib.pdf.types import Section, SectionKind
from tomd.parsers.legacy_bridge import render_pdf

_UNCERTAIN_CONTEXT_CHARS = 200

SectionAdapter = Callable[[Section], list[BlockElement]]

ADAPTERS: dict[SectionKind, SectionAdapter] = {}


def _raw_origin(sec: Section) -> str:
    """Return the ratchet origin label for a section adapted as a RawBlock."""
    if sec.kind == SectionKind.TABLE and sec.table_strategy:
        return f"pdf:table:{sec.table_strategy}"
    return f"pdf:{sec.kind.value}"


def _adapt_raw_section(sec: Section) -> list[BlockElement]:
    """Adapt an unmigrated PDF section into a pre-rendered RawBlock."""
    rendered = _render_section_md(sec)
    if not rendered.strip():
        return []
    if sec.kind in (SectionKind.TITLE, SectionKind.HEADING):
        if not rendered.lstrip("#").strip():
            return []
    return [
        RawBlock(
            markdown=rendered,
            origin=_raw_origin(sec),
            provenance=Provenance(page=sec.page_num, confidence=sec.confidence),
        )
    ]


def sections_to_document(
    result: PipelineResult,
    *,
    paper_id: str = "",
) -> PaperDocument:
    """Translate a PDF PipelineResult into a PaperDocument AST."""
    if result.skipped:
        return PaperDocument(
            paper_id=paper_id,
            is_skipped=True,
            skip_reason=result.skip_reason,
            diagnostics=Diagnostics(
                extra_prompts=tuple(result.prompts or ()),
            ),
        )

    sections = result.sections
    elements: list[BlockElement] = []
    uncertain_count = 0

    for idx, sec in enumerate(sections):
        if sec.kind == SectionKind.UNCERTAIN:
            uncertain_count += 1
            ctx_before = ""
            ctx_after = ""
            if idx > 0 and sections[idx - 1].kind != SectionKind.UNCERTAIN:
                ctx_before = sections[idx - 1].text[:_UNCERTAIN_CONTEXT_CHARS].strip()
            if (
                idx + 1 < len(sections)
                and sections[idx + 1].kind != SectionKind.UNCERTAIN
            ):
                ctx_after = sections[idx + 1].text[:_UNCERTAIN_CONTEXT_CHARS].strip()
            elements.append(
                UncertainElement(
                    mupdf_text=sec.mupdf_text,
                    spatial_text=sec.spatial_text,
                    page=sec.page_num,
                    text=sec.text,
                    context_before=ctx_before,
                    context_after=ctx_after,
                    provenance=Provenance(
                        page=sec.page_num,
                        confidence=sec.confidence,
                    ),
                )
            )
            continue

        adapter = ADAPTERS.get(sec.kind, _adapt_raw_section)
        elements.extend(adapter(sec))

    extra_prompts = tuple((result.prompts or ())[uncertain_count:])
    diagnostics = Diagnostics(
        images_truncated=result.images_truncated,
        source_image_count=result.source_image_count,
        vector_uncertainty=result.vector_uncertainty,
        glyph_stats=result.glyph_stats,
        extra_prompts=extra_prompts,
    )

    return PaperDocument(
        paper_id=paper_id,
        metadata=PaperMetadata.from_dict(result.metadata),
        elements=elements,
        images=list(result.images),
        diagnostics=diagnostics,
    )


def parse_pdf(
    path: Path,
    *,
    extract_vector: bool = False,
    whiteout_text: bool = False,
) -> PaperDocument:
    """Run the PDF pipeline on ``path`` and adapt its output into a PaperDocument."""
    path = Path(path)
    result = run_pipeline(
        path,
        extract_vector=extract_vector,
        whiteout_text=whiteout_text,
    )
    return sections_to_document(result, paper_id=path.stem)


def convert_pdf_dark(
    path: Path,
    *,
    extract_vector: bool = False,
    whiteout_text: bool = False,
) -> str:
    """Convert a PDF file to Markdown through the dark AST + legacy bridge path."""
    doc = parse_pdf(
        path,
        extract_vector=extract_vector,
        whiteout_text=whiteout_text,
    )
    return render_pdf(doc)
