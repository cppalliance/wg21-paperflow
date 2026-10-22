"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from tomd.domain.document import PaperDocument
from tomd.domain.elements import UncertainElement

RECONCILE_INTRO = (
    "You are reconciling text extracted from a PDF using two independent "
    "methods that produced different results. Reconcile them into clean "
    "Markdown."
)

RECONCILE_CRITICAL = (
    "CRITICAL: Keep ALL data verbatim. Do not summarize, omit, or paraphrase "
    "any text. Every word from the source must appear in your output. You are "
    "only fixing structure (paragraphs, headings, lists, formatting) - never "
    "content."
)

PRECEDING_CONTEXT_HEADER = "Context (preceding confident section):"
FOLLOWING_CONTEXT_HEADER = "Context (following confident section):"
MUPDF_HEADER = "MuPDF extraction:"
SPATIAL_HEADER = "Spatial extraction:"


def _format_reconcile_prompt(elem: UncertainElement) -> str:
    """Format a single self-contained LLM reconcile prompt for ``elem``."""
    parts: list[str] = [
        RECONCILE_INTRO,
        "",
        RECONCILE_CRITICAL,
        "",
        f"This region is on page {elem.page}.",
        "",
    ]

    if elem.context_before:
        parts.extend((PRECEDING_CONTEXT_HEADER, f"> {elem.context_before}", ""))

    parts.extend(
        (
            MUPDF_HEADER,
            "```",
            elem.mupdf_text or elem.text,
            "```",
            "",
            SPATIAL_HEADER,
            "```",
            elem.spatial_text or elem.text,
            "```",
        )
    )

    if elem.context_after:
        parts.extend(("", FOLLOWING_CONTEXT_HEADER, f"> {elem.context_after}"))

    return "\n".join(parts)


def build_reconcile_prompts(document: PaperDocument) -> list[str] | None:
    """Generate self-contained LLM reconcile prompts for uncertain regions."""
    prompts = [
        _format_reconcile_prompt(elem)
        for elem in document.elements
        if isinstance(elem, UncertainElement)
    ]
    return prompts or None


__all__ = ["build_reconcile_prompts"]
