#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Progress callback contract for paperflow pipelines.

Libraries fire ProgressEvent via an optional ProgressCallback. Rendering
(rich, logging, nothing) is the caller's responsibility.

Intentional duplicate of ``pipeline.progress``: the framework owns its own
copy so it need not import a paper package, while paper-only consumers use
this one. The two definitions are structurally identical and interoperate
at runtime by duck typing (no ``isinstance`` checks cross the boundary).
Keep them in sync - any field change here must be mirrored in
``pipeline.progress`` and vice versa.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

type ProgressCallback = Callable[[ProgressEvent], None]


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """A single progress notification from a pipeline step."""

    step: int
    """Current step index (0-based)."""

    total: int
    """Total number of steps."""

    name: str
    """Human-readable step name."""

    pct: float
    """Completion fraction (step / total), range [0.0, 1.0]."""
