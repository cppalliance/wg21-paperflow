#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Independent reference Markdown via an existing converter (the oracle).

whisker's per-paper verdict has no ground truth, so it needs a second opinion
to score against. Rather than hand-label gold Markdown, we run a mature,
deterministic converter on the same staged source and treat its Markdown as
the reference. The agreement between tomd's output and the oracle's output
(scored by the bench metrics) is the quality signal.

The default oracle is markitdown (MIT, multi-format): PDF via pdfminer, HTML
via markdownify. Both are deterministic, CPU-only, no network, no LLM. The
engine is a parameter so a stronger (but non-deterministic / GPU) converter
could be added later without disturbing the default rule-compatible path.
"""

from __future__ import annotations

from functools import cache

from markitdown import MarkItDown
from paperstore.backend import StorageBackend

__all__ = ["REFERENCE_ENGINES", "reference_markdown"]

REFERENCE_ENGINES = ("markitdown",)


@cache
def _markitdown() -> MarkItDown:
    """Process-wide markitdown instance (cached: avoids re-loading per paper).

    ``enable_plugins=False`` keeps conversion to the built-in deterministic
    extractors only: no third-party plugins, no network, no LLM client.
    """
    return MarkItDown(enable_plugins=False)


def reference_markdown(
    pid: str,
    backend: StorageBackend,
    *,
    engine: str = "markitdown",
) -> str:
    """Convert the staged source for *pid* with the reference oracle.

    Returns the oracle's Markdown text.

    Raises:
        ValueError: for an unknown engine.
        paperstore.MissingSourceError: if ``<pid>.pdf|.html`` is not staged
            (propagated from ``backend.get_source_path``).
    """
    if engine not in REFERENCE_ENGINES:
        known = ", ".join(REFERENCE_ENGINES)
        raise ValueError(f"unknown reference engine {engine!r}; known: {known}")
    source_path = backend.get_source_path(pid)
    result = _markitdown().convert(str(source_path))
    return result.text_content
