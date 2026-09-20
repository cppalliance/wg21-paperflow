#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""vlm: dormant Vision Language Model lane for direct PDF-page QA.

This subpackage is quarantined, not deleted. It contains a tested prototype
for page-level rasterization, VLM transcription, and diff-against-tomd
scoring. The code is structurally sound but has no production entry point:
no CLI verb, no menu option, and no import from any whisker entry point
invokes it.

Activation path: when a self-hosted Vision Pod (olmocr or equivalent) is
deployed and the ``tapetum_llm`` CLI gains a ``--vlm`` flag, wire
``vlm_pipeline.vlm_adjudicate_paper`` into the advisory lane. Until then
the reachability guard in ``tests/test_vlm_lane.py`` enforces that these
modules stay unwired from production surfaces.
"""

from whisker.llm.vlm.transcribe import (
    PageTranscription,
    TranscriptionError,
    TranscriptionResult,
    transcribe_pages,
)
from whisker.llm.vlm.vision import RasterError, rasterize_pdf
from whisker.llm.vlm.vision_task import (
    VisionAgent,
    VisionTaskError,
    run_vision_task,
)
from whisker.llm.vlm.vlm_diff import VlmDiffResult, diff_vlm_vs_tomd
from whisker.llm.vlm.vlm_pipeline import vlm_adjudicate_paper

__all__ = [
    "PageTranscription",
    "RasterError",
    "TranscriptionError",
    "TranscriptionResult",
    "VisionAgent",
    "VisionTaskError",
    "VlmDiffResult",
    "diff_vlm_vs_tomd",
    "rasterize_pdf",
    "run_vision_task",
    "transcribe_pages",
    "vlm_adjudicate_paper",
]
