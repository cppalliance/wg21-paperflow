#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Progress callback contract for the pipeline framework.

Libraries fire ProgressEvent via an optional ProgressCallback. Rendering
(rich, logging, nothing) is the caller's responsibility. This is the
framework-owned contract; it carries no paper-domain concepts.

Intentional duplicate of ``paperstore.progress``: the framework must not
import a paper package, and paper-only consumers should not depend on the
framework. The two definitions are structurally identical and interoperate
at runtime by duck typing (no ``isinstance`` checks cross the boundary).
Keep them in sync - any field change here must be mirrored in
``paperstore.progress`` and vice versa.
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
