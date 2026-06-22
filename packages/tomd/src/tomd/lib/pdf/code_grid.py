#
# Copyright (c) 2026 Luan Fonseca (luan@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Character-grid reconstruction from PDF glyph x-positions.

PDF text extraction does not preserve the leading whitespace of code
lines reliably: indentation is carried by glyph x-coordinates, not by
space characters in the text layer. To render a fenced code block we
reconstruct the character column of each glyph from its x-position
relative to a grid origin, divided by the monospace character width.

``CodeGrid`` is that grid: an ``(origin_x, char_w)`` pair with two
operations. ``column`` maps a raw x to a character column; ``indent``
maps a whole line to its leading-space count, reconciling the
x-derived indent against the literal text indent (the x-position is the
source of truth; the literal count is trusted only when it agrees).

The two classmethods encode the two ways the grid origin and width are
chosen in practice:

* ``for_code_section`` - origin at the block's left margin (leftmost
  content glyph), width sampled from any multi-glyph span. Used for
  plain code blocks and code-shaped wording diffs.
* ``for_gutter`` - origin supplied by the caller (the leftmost gutter
  glyph), width sampled from monospace spans only so a multi-digit
  serif line number cannot be measured as the code character width.

The non-monospace vs monospace-only width split between the two
constructors is intentional and preserved; unifying it is a separate
semantic change that would move golden output.
"""

from __future__ import annotations

from dataclasses import dataclass

from .types import Line, Section

# Fallback monospace character width (points) when a section has no
# multi-glyph span to measure. WG21 code fonts run ~5-6pt/char.
_DEFAULT_CHAR_WIDTH = 6.0

# Minimum non-space glyph count for a span to estimate character width.
# A single glyph's bbox includes side bearing, so dividing its width by
# one over-estimates the per-character pitch; two or more glyphs average
# it out.
_MIN_SPAN_CHARS_FOR_WIDTH = 2


def _estimate_char_width(sec_lines: list[Line], mono_only: bool = False) -> float:
    """Estimate monospace character width from span bbox and text length.

    When ``mono_only`` is True, only monospace spans are sampled. A code
    block with a non-monospace line-number gutter would otherwise let a
    multi-digit serif number (``10``) be measured as the "character
    width", corrupting the indentation math for the monospace code.
    """
    for line in sec_lines:
        for span in line.spans:
            if mono_only and not span.monospace:
                continue
            n = len(span.text.replace(" ", ""))
            if n >= _MIN_SPAN_CHARS_FOR_WIDTH:
                w = span.bbox[2] - span.bbox[0]
                if w > 0:
                    return w / n
    return _DEFAULT_CHAR_WIDTH


@dataclass(frozen=True)
class CodeGrid:
    """A character grid for reconstructing code-line indentation.

    ``origin_x`` is the x-coordinate that maps to column 0; ``char_w``
    is the monospace character width in points.
    """

    origin_x: float
    char_w: float

    def column(self, x: float) -> int:
        """Character column for a glyph x, clamped at zero.

        Returns 0 when the character width is non-positive (a section
        with nothing measurable to scale by), matching the conservative
        no-indent fallback.
        """
        if self.char_w <= 0:
            return 0
        return max(round((x - self.origin_x) / self.char_w), 0)

    def indent(self, line: Line, *, max_indent: int | None = None) -> int:
        """Leading-space count for a code line.

        Reconciles the x-derived indent against the literal text indent:
        when both are positive and agree, the literal count is used;
        otherwise the x-derived column wins (it is the reliable signal),
        falling back to the literal count only when the x-derived column
        is zero. When ``max_indent`` is given and the result exceeds it,
        returns 0: an implausibly deep indent means the line's first
        glyph is a right-margin element extraction split onto its own
        line, not real nesting, so it is pinned to column zero.
        """
        if not line.spans:
            return 0
        first_text = line.spans[0].text
        text_indent = len(first_text) - len(first_text.lstrip())
        first_nonspace = line.first_content_span() or line.spans[0]
        x_indent = self.column(first_nonspace.bbox[0])
        if text_indent > 0 and x_indent > 0 and text_indent == x_indent:
            indent = text_indent
        else:
            indent = x_indent if x_indent > 0 else text_indent
        if max_indent is not None and indent > max_indent:
            return 0
        return indent

    @classmethod
    def for_code_section(cls, sec: Section) -> "CodeGrid":
        """Grid with origin at the block left margin, width from mono spans.

        The origin samples each line's first *content* span (the same
        accessor :meth:`indent` uses), not ``spans[0]``: a line whose
        leading span is whitespace-only would otherwise be dropped from
        the origin computation, and if every line started that way the
        origin fell back to ``0.0`` and inflated every reconstructed
        indent.

        Width estimation passes ``mono_only=True`` so a proportional
        (serif) leading comment cannot be the first qualifying span and
        skew the per-character pitch for the monospace code that
        follows. :meth:`for_gutter` already uses the same constraint.
        """
        char_w = _estimate_char_width(sec.lines, mono_only=True)
        content_x = [
            span.bbox[0] for ln in sec.lines
            if (span := ln.first_content_span()) is not None
        ]
        base_x = min(content_x) if content_x else 0.0
        return cls(origin_x=base_x, char_w=char_w)

    @classmethod
    def for_gutter(cls, sec: Section, origin_x: float) -> "CodeGrid":
        """Grid with a caller-supplied origin, width from mono spans only."""
        char_w = _estimate_char_width(sec.lines, mono_only=True)
        return cls(origin_x=origin_x, char_w=char_w)
