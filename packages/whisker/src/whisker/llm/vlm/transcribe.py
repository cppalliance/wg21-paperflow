#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Per-page VLM transcription for the VLM-PDF-Lane.

Sends rasterized page images to an olmOCR-class VLM and collects
per-page Markdown transcriptions. Runs serially (D11). Library-pure:
returns data, never persists.

Prompt adapted from olmOCR's no-anchor path
(``prompts.build_no_anchoring_v4_yaml_prompt``), stripped of the
rotation/language/diagram metadata we don't need and narrowed to our
WG21 corpus conventions (fenced code, Markdown tables, LaTeX math).

NOT ported from olmOCR (anti-pattern list from opus-C research):
- Temperature ladder on retries
- Parallel page races
- pdftotext fallback
- max_page_error_rate tolerance (partial results)

Dormant status: this transcriber is used only by the unwired VLM prototype.
It is retained as tested prior art and is not production coverage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from whisker.llm.unit_judge import (
    inject_code_rubric,
    inject_table_rubric,
    resolve_runtime_code_contract,
    resolve_runtime_table_contract,
)
from whisker.llm.vlm.vision_task import VisionAgent, run_vision_task

logger = logging.getLogger(__name__)

__all__ = [
    "PageTranscription",
    "TranscriptionResult",
    "TranscriptionError",
    "TRANSCRIPTION_SYSTEM_PROMPT",
    "transcribe_pages",
]

OUTPUT_RETRIES = 3
"""D10: finite retry budget for schema validation failures."""


TRANSCRIPTION_SYSTEM_PROMPT = (
    "You are a document OCR system. You receive one page of a PDF "
    "document as an image. Return a faithful plain-text transcription "
    "of the page content as Markdown.\n\n"
    "Rules:\n"
    "- Reproduce all text exactly as it appears. Do not paraphrase.\n"
    "- Convert equations and math symbols to LaTeX: use \\( \\) for "
    "inline math and \\[ \\] for display math.\n"
    "- Convert tables using the dual strategy: a Markdown pipe table for a "
    "clean 1x1 rectangular matrix; HTML <table> when cells merge, contain "
    "code, or contain newlines. Do not flatten spans into a pipe table.\n"
    "- Preserve code blocks with ``` fences.\n"
    "- Preserve heading levels with # syntax.\n"
    "- Preserve list structure.\n"
    "- Remove page headers and footers (running titles, page numbers).\n"
    "- If a sentence continues from a previous page or onto the next, "
    "preserve it exactly as shown.\n"
    "- If the page is blank or has no readable text, set text to null.\n"
    "- Do not hallucinate content that is not visible in the image.\n"
)


class PageTranscription(BaseModel):
    """Structured output for one page's VLM transcription (D6)."""

    text: str | None = Field(
        description="Markdown transcription of the page, or null if blank."
    )


@dataclass
class TranscriptionResult:
    """All pages transcribed for one paper."""

    pid: str
    page_transcriptions: list[str] = field(default_factory=list)
    page_count: int = 0
    status: str = "ok"
    error: str = ""

    @property
    def full_text(self) -> str:
        """Concatenate all page transcriptions with page separators."""
        return "\n\n".join(self.page_transcriptions)


class TranscriptionError(Exception):
    """Raised when transcription fails for any page (fidelity rule)."""


async def transcribe_pages(
    pid: str,
    page_images: list[bytes],
    agent: VisionAgent,
    *,
    debug_log: list[str] | None = None,
) -> TranscriptionResult:
    """Transcribe each page image serially via the VLM.

    Fidelity policy: if ANY page fails (schema error after retry budget,
    API error), the entire paper fails. No partial results.

    Returns a TranscriptionResult with status="ok" on success or raises
    TranscriptionError on failure.
    """
    result = TranscriptionResult(pid=pid, page_count=len(page_images))

    for page_num, img_bytes in enumerate(page_images):
        label = f"transcribe-page-{page_num}"
        user_msg = f"Page {page_num + 1} of {len(page_images)} of document {pid}."

        try:
            system = inject_code_rubric(
                inject_table_rubric(
                    TRANSCRIPTION_SYSTEM_PROMPT,
                    resolve_runtime_table_contract(),
                ),
                resolve_runtime_code_contract(),
            )
            page_result: PageTranscription = await run_vision_task(
                agent,
                system,
                user_msg,
                PageTranscription,
                label=label,
                debug_log=debug_log,
                user_media=[img_bytes],
            )
        except Exception as exc:
            raise TranscriptionError(
                f"Page {page_num} transcription failed for {pid}: {exc}"
            ) from exc

        text = page_result.text or ""
        result.page_transcriptions.append(text.strip())
        logger.debug(
            "Transcribed page %d/%d for %s: %d chars",
            page_num + 1, len(page_images), pid, len(text),
        )

    return result
