#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""llm: advisory LLM triage lane on top of whisker (opt-in).

Named for the tapetum lucidum, the reflective layer behind a cat's eye that
grants night vision: it sees what is hidden in the dark. This lane illuminates
the false-pass blind spot that whisker's deterministic gate cannot resolve on
its own: token-preserving semantic corruption (table swaps, math collapse,
code garbling) that passes because ``unigram_coverage`` is order-blind. It also
rescues the false-fail case: cosmetic ``heading_monotone``-only fails. It is
advisory: it never hard-fails and is never part of the ``whisker --gate`` CI
contract.

The decide step is severity-aware: an axis ``fail`` forces an overall ``fail``
only at severity ``major``; a non-major fail folds to ``review``. Papers larger
than ``MAX_PAPER_MD_CHARS`` are split on H2 boundaries, triaged serially, and
folded, so even multi-megabyte papers adjudicate without a ``413``. The
self-hosted pod runs 24/7, so the lane may run anytime.

Isolation invariant: whisker core never imports ``llm``. This lane
imports whisker core read-only (one-way dependency). Requires the optional
extra: ``pip install whisker[tapetum-llm]``.
"""

from whisker.llm.models import (
    Adjudication,
    AxisFinding,
    EvidenceSpan,
    FidelityAxis,
    TapetumResult,
    Verdict,
)
from whisker.llm.table_compare import (
    GRID_EQUAL,
    GRID_EXTRA_OR_MISSING_ROWS,
    GRID_ROW0_MISMATCH,
    GRID_UNRELIABLE,
    SourceGrid,
    TableCellDiff,
    TableCompareResult,
    TableGridMatch,
    classify_grid_pair,
    compare_pdf_tables,
    extract_pdf_table_grids,
    grid_pairing_note,
    grid_signal_for_unit,
    parse_markdown_tables,
)

__all__ = [
    "Adjudication",
    "AxisFinding",
    "EvidenceSpan",
    "FidelityAxis",
    "GRID_EQUAL",
    "GRID_EXTRA_OR_MISSING_ROWS",
    "GRID_ROW0_MISMATCH",
    "GRID_UNRELIABLE",
    "SourceGrid",
    "TableCellDiff",
    "TableCompareResult",
    "TableGridMatch",
    "TapetumResult",
    "Verdict",
    "classify_grid_pair",
    "compare_pdf_tables",
    "extract_pdf_table_grids",
    "grid_pairing_note",
    "grid_signal_for_unit",
    "parse_markdown_tables",
]

__version__ = "0.1.0"
