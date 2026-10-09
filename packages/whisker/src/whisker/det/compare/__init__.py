#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Block-aligned Markdown comparison for side-by-side review.

Splits two Markdown documents into typed blocks, aligns them preserving
reading order, and exposes a unified ``AlignedDocument`` consumed by both
the interactive HTML renderer and the PDF appendix generator.
"""

from whisker.det.compare.align import (
    AlignedDocument,
    AlignedPair,
    PairStatus,
    align_documents,
)
from whisker.det.compare.blocks import Block, BlockType, parse_blocks
from whisker.det.compare.exhibits import DETECTORS, Detector, Exhibit, find_exhibits
from whisker.det.compare.render_appendix import (
    ClaimEvidence,
    PaperEvidence,
    render_appendix_html,
)
from whisker.det.compare.render_html import render_html
from whisker.det.compare.render_pdf import render_pdf_html

__all__ = [
    "DETECTORS",
    "AlignedDocument",
    "AlignedPair",
    "Block",
    "BlockType",
    "ClaimEvidence",
    "Detector",
    "Exhibit",
    "PairStatus",
    "PaperEvidence",
    "align_documents",
    "find_exhibits",
    "parse_blocks",
    "render_appendix_html",
    "render_html",
    "render_pdf_html",
]
