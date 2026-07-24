#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Exception hierarchy for PromptForge, rooted at :class:`PromptForgeError`.

The failure taxonomy mirrors the three-layer detection in the design:

- ``PreconditionError`` - a section's Lua preconditions failed, so it never
  launched. Not retryable.
- ``IncompleteError`` - the model stopped without calling ``done()`` (hit the
  budget, stalled, or got confused). Retryable.
- ``PostconditionError`` - ``done()`` was called but the Lua ``check()`` found
  the work incomplete or wrong. Retryable.

Plus structural errors that are never retried (``DepthLimitError``,
``TaskLimitError``).
"""

from __future__ import annotations


class PromptForgeError(Exception):
    """Base class for all PromptForge errors."""


class PreconditionError(PromptForgeError):
    """A section's Lua preconditions failed before the model launched."""


class IncompleteError(PromptForgeError):
    """The model stopped without calling done()."""


class PostconditionError(PromptForgeError):
    """The Lua check() postcondition failed after done()."""


class DepthLimitError(PromptForgeError):
    """Subagent nesting exceeded the configured maximum depth."""


class TaskLimitError(PromptForgeError):
    """A run exceeded the configured maximum total task count."""
