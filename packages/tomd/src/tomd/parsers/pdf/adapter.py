"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
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
from tomd.lib.pdf.emit import (
    emit_table_prompts,
    is_code_comparison,
    render_section_block,
    set_lexicon,
)
from tomd.lib.pdf.pipeline import PipelineResult, run_pipeline
from tomd.lib.pdf.runctx import run_scope
from tomd.lib.pdf.types import Section, SectionKind
from tomd.parsers.legacy_bridge import render_pdf

_UNCERTAIN_CONTEXT_CHARS = 200

SectionAdapter = Callable[[Section], list[BlockElement]]

ADAPTERS: dict[SectionKind, SectionAdapter] = {}


def _raw_origin(sec: Section) -> str:
    """Return the ratchet origin label for a section adapted as a RawBlock."""
    if sec.kind == SectionKind.TABLE:
        if sec.columns and is_code_comparison(sec.columns):
            return "pdf:table:code_blocks"
        strategy = sec.table_strategy or "pipe_table"
        return f"pdf:table:{strategy}"
    return f"pdf:{sec.kind.value}"


def _adapt_raw_section(sec: Section) -> list[BlockElement]:
    """Adapt an unmigrated PDF section into a pre-rendered RawBlock."""
    rendered = render_section_block(sec)
    if not rendered:
        return []
    return [
        RawBlock(
            markdown=rendered,
            origin=_raw_origin(sec),
            provenance=Provenance(page=sec.page_num, confidence=sec.confidence),
        )
    ]


def _neighbor_context(sections: Sequence[Section], idx: int) -> str:
    if 0 <= idx < len(sections) and sections[idx].kind != SectionKind.UNCERTAIN:
        return sections[idx].text[:_UNCERTAIN_CONTEXT_CHARS].strip()
    return ""


def _adapt_uncertain_section(
    sections: Sequence[Section],
    idx: int,
) -> UncertainElement:
    sec = sections[idx]
    return UncertainElement(
        mupdf_text=sec.mupdf_text,
        spatial_text=sec.spatial_text,
        page=sec.page_num,
        text=sec.text,
        context_before=_neighbor_context(sections, idx - 1),
        context_after=_neighbor_context(sections, idx + 1),
        provenance=Provenance(page=sec.page_num, confidence=sec.confidence),
    )


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
                extra_prompts=result.extra_prompts or tuple(result.prompts or ()),
            ),
        )

    sections = result.sections
    elements: list[BlockElement] = []

    with run_scope() as ctx:
        ctx.hyphenates = result.hyphenates
        set_lexicon(sections)
        for idx, sec in enumerate(sections):
            if sec.kind == SectionKind.UNCERTAIN:
                elements.append(_adapt_uncertain_section(sections, idx))
            else:
                adapter = ADAPTERS.get(sec.kind, _adapt_raw_section)
                elements.extend(adapter(sec))
        table_prompts = emit_table_prompts(sections)
    diagnostics = Diagnostics(
        images_truncated=result.images_truncated,
        source_image_count=result.source_image_count,
        vector_uncertainty=result.vector_uncertainty,
        glyph_stats=result.glyph_stats,
        extra_prompts=(*table_prompts, *result.extra_prompts),
        summary=result.summary,
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
    result = run_pipeline(
        path,
        extract_vector=extract_vector,
        whiteout_text=whiteout_text,
    )
    return sections_to_document(result, paper_id=path.stem)


@dataclass(frozen=True)
class PdfParser:
    """PDF document parser implementing the DocumentParser protocol."""

    extract_vector: bool = False
    whiteout_text: bool = False

    def parse(self, path: Path) -> PaperDocument:
        return parse_pdf(
            path,
            extract_vector=self.extract_vector,
            whiteout_text=self.whiteout_text,
        )


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
