#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""VLM-PDF-Lane entry point: rasterize -> transcribe -> diff.

Ties the three VLM-lane modules (vision, transcribe, vlm_diff) into
a single async function that produces a tapetum-compatible sidecar.
Library-pure: returns data, never persists.

Dormant status: no production CLI or service configuration invokes this
prototype. It is retained as tested prior art and is not production coverage.
"""

from __future__ import annotations

import logging

from paperstore.backend import StorageBackend

from whisker.llm.vlm.transcribe import TranscriptionError, transcribe_pages
from whisker.llm.vlm.vision import RasterError, rasterize_pdf
from whisker.llm.vlm.vision_task import VisionAgent
from whisker.llm.vlm.vlm_diff import VlmDiffResult, diff_vlm_vs_tomd

logger = logging.getLogger(__name__)

__all__ = ["vlm_adjudicate_paper", "VlmLaneError"]


class VlmLaneError(Exception):
    """Raised when the VLM lane cannot complete for a paper."""


async def vlm_adjudicate_paper(
    pid: str,
    backend: StorageBackend,
    vision_agent: VisionAgent,
    *,
    debug: bool = False,
) -> VlmDiffResult:
    """Run the full VLM-PDF-Lane for one paper.

    1. Rasterize PDF pages to PNG images
    2. Transcribe each page via the VLM (serial, D11)
    3. Deterministic diff of VLM transcription vs tomd-Markdown

    Fidelity policy: any failure -> VlmLaneError (no partial results).

    Returns a VlmDiffResult whose ``.to_sidecar_dict()`` is
    tapetum-compatible for fusion.
    """
    source_path = backend.get_source_path(pid)
    if not str(source_path).lower().endswith(".pdf"):
        raise VlmLaneError(
            f"{pid}: VLM lane requires a PDF source, got {source_path.suffix}"
        )

    debug_log: list[str] | None = [] if debug else None

    try:
        page_images = rasterize_pdf(source_path)
    except RasterError as exc:
        raise VlmLaneError(f"{pid}: rasterization failed: {exc}") from exc

    logger.info(
        "%s: rasterized %d pages (%.1f KB avg)",
        pid, len(page_images),
        sum(len(p) for p in page_images) / max(len(page_images), 1) / 1024,
    )

    try:
        transcription = await transcribe_pages(
            pid, page_images, vision_agent, debug_log=debug_log,
        )
    except TranscriptionError as exc:
        raise VlmLaneError(f"{pid}: transcription failed: {exc}") from exc

    logger.info(
        "%s: transcribed %d pages (%d chars total)",
        pid, transcription.page_count, len(transcription.full_text),
    )

    tomd_md = backend.get_paper_md(pid)
    vlm_model = vision_agent.service_name or "vision"

    result = diff_vlm_vs_tomd(
        pid, transcription, tomd_md, vlm_model=vlm_model,
    )

    logger.info(
        "%s: VLM diff verdict=%s (nid=%.4f, recall=%.4f)",
        pid, result.verdict, result.text_nid, result.content_recall,
    )

    return result
