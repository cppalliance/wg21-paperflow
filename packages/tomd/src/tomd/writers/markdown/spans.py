"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from __future__ import annotations

import re
from typing import Sequence

from tomd.domain.span import (
    CodeSpan,
    EmphasisSpan,
    LineBreakSpan,
    LinkSpan,
    Span,
    StrikethroughSpan,
    StrongSpan,
    SubscriptSpan,
    SuperscriptSpan,
    TextSpan,
    UnderlineSpan,
)


def _wrap_delimiters(inner: str, delim: str) -> str:
    """Wrap content with Markdown delimiters while keeping leading/trailing whitespace outside."""
    leading_ws = inner[: len(inner) - len(inner.lstrip())]
    trailing_ws = inner[len(inner.rstrip()) :]
    stripped = inner.strip()
    if not stripped:
        return inner
    return f"{leading_ws}{delim}{stripped}{delim}{trailing_ws}"


def _format_code_span(code: str) -> str:
    """Format an inline code span handling embedded backticks."""
    if "`" not in code:
        return f"`{code}`"

    # Find longest run of backticks to choose fence length
    backtick_runs = re.findall(r"`+", code)
    max_run = max(len(r) for r in backtick_runs) if backtick_runs else 1
    fence = "`" * (max_run + 1)

    # Pad with space if code starts or ends with a backtick
    if code.startswith("`") or code.endswith("`"):
        return f"{fence} {code} {fence}"
    return f"{fence}{code}{fence}"


def write_span(span: Span, *, wording_tags: bool = True) -> str:
    """Recursively format a domain Span AST node into Markdown/HTML text."""
    if isinstance(span, TextSpan):
        return span.content

    if isinstance(span, CodeSpan):
        return _format_code_span(span.code)

    if isinstance(span, LineBreakSpan):
        return "<br>"

    if isinstance(span, StrongSpan):
        inner = write_spans(span.children, wording_tags=wording_tags)
        if not inner:
            return ""
        return _wrap_delimiters(inner, "**")

    if isinstance(span, EmphasisSpan):
        inner = write_spans(span.children, wording_tags=wording_tags)
        if not inner:
            return ""
        return _wrap_delimiters(inner, "*")

    if isinstance(span, StrikethroughSpan):
        inner = write_spans(span.children, wording_tags=wording_tags)
        if not inner:
            return ""
        if wording_tags:
            return f"<del>{inner}</del>"
        return _wrap_delimiters(inner, "~~")

    if isinstance(span, UnderlineSpan):
        inner = write_spans(span.children, wording_tags=wording_tags)
        if not inner:
            return ""
        if wording_tags:
            return f"<ins>{inner}</ins>"
        return f"<u>{inner}</u>"

    if isinstance(span, SubscriptSpan):
        inner = write_spans(span.children, wording_tags=wording_tags)
        if not inner:
            return ""
        return f"<sub>{inner}</sub>"

    if isinstance(span, SuperscriptSpan):
        inner = write_spans(span.children, wording_tags=wording_tags)
        if not inner:
            return ""
        return f"<sup>{inner}</sup>"

    if isinstance(span, LinkSpan):
        inner = write_spans(span.children, wording_tags=wording_tags)
        title_suffix = f' "{span.title}"' if span.title else ""
        return f"[{inner}]({span.url}{title_suffix})"

    return getattr(span, "text", "")


def write_spans(spans: Sequence[Span], *, wording_tags: bool = True) -> str:
    """Format a sequence of Spans into concatenated Markdown text."""
    return "".join(write_span(s, wording_tags=wording_tags) for s in spans)


__all__ = ["write_span", "write_spans"]
