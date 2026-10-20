"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
import re

from tomd.domain.elements import (
    BlockElement,
    Blockquote,
    CodeBlock,
    Heading,
    ImageElement,
    ListBlock,
    ListItem,
    Paragraph,
    ThematicBreak,
    UncertainElement,
    WordingBlock,
)
from tomd.domain.span import (
    EmphasisSpan,
    LinkSpan,
    Span,
    StrikethroughSpan,
    StrongSpan,
    SubscriptSpan,
    SuperscriptSpan,
    TextSpan,
    UnderlineSpan,
)
from tomd.domain.table import Table, TableRow, TextCell
from tomd.lib.pdf.cleanup import escape_leading_atx, normalize_whitespace
from tomd.lib.pdf.wording_emit import _escape_wording_text
from tomd.lib.wording_markup import wording_tag_open
from tomd.lib.wording_policy import UNIFORM_ROLE_THRESHOLD, implicit_role_for
from tomd.writers.markdown.spans import write_spans
from tomd.writers.markdown.tables import write_table


_BULLET_MARKER = "-"
_WHITESPACE_RE = re.compile(r"\s")
_RoleSpanType = type[UnderlineSpan | StrikethroughSpan]
_CONTAINER_SPAN_TYPES = (
    StrongSpan,
    EmphasisSpan,
    StrikethroughSpan,
    UnderlineSpan,
    SubscriptSpan,
    SuperscriptSpan,
    LinkSpan,
)


def _wrap_wording_tag(tag: str, inner: str) -> str:
    """Wrap ``inner`` in a wording tag while keeping outer whitespace outside."""
    leading_ws = inner[: len(inner) - len(inner.lstrip())]
    trailing_ws = inner[len(inner.rstrip()) :]
    stripped = inner.strip()
    if not stripped:
        return inner
    return f"{leading_ws}{wording_tag_open(tag, stripped)}{trailing_ws}"


def _is_whitespace_span(span: Span) -> bool:
    return isinstance(span, (TextSpan, UnderlineSpan, StrikethroughSpan)) and not span.text.strip()


def _group_domain_wording_spans(spans: Sequence[Span]) -> list[tuple[str | None, list[Span]]]:
    """Partition spans into ordered role / non-role segments, absorbing inner whitespace."""
    segments: list[tuple[str | None, list[Span]]] = []
    group: list[Span] = []
    group_role: str | None = None
    ws_buf: list[Span] = []

    def _flush() -> None:
        nonlocal group, group_role
        if group:
            segments.append((group_role, group))
            group = []
            group_role = None
        if ws_buf:
            segments.append((None, list(ws_buf)))
            ws_buf.clear()

    for span in spans:
        if _is_whitespace_span(span):
            ws_buf.append(TextSpan(span.text))
        elif isinstance(span, (UnderlineSpan, StrikethroughSpan)):
            role = "ins" if isinstance(span, UnderlineSpan) else "del"
            if role != group_role:
                _flush()
                group_role = role
            else:
                group.extend(ws_buf)
                ws_buf.clear()
            group.extend(span.children)
        else:
            _flush()
            segments.append((None, [span]))

    _flush()
    return segments


def _escape_wording_span(span: Span) -> Span:
    if isinstance(span, TextSpan):
        return TextSpan(_escape_wording_text(span.content))
    if isinstance(span, _CONTAINER_SPAN_TYPES):
        return replace(span, children=tuple(_escape_wording_span(c) for c in span.children))
    return span


def _write_wording_spans(spans: Sequence[Span]) -> str:
    parts: list[str] = []
    for role, seg_spans in _group_domain_wording_spans(spans):
        rendered = write_spans([_escape_wording_span(s) for s in seg_spans])
        if role in ("ins", "del"):
            parts.append(_wrap_wording_tag(role, rendered))
        else:
            parts.append(rendered)
    return "".join(parts)


def _format_wording_paragraph(element: Paragraph) -> str:
    """Format a wording prose paragraph with angle-bracket escaping and role grouping."""
    lines: list[list[Span]] = [[]]
    for span in element.spans:
        if isinstance(span, TextSpan) and span.content == "\n":
            lines.append([])
        else:
            lines[-1].append(span)

    rendered_lines = [
        normalize_whitespace(_write_wording_spans(line)).strip()
        for line in lines
    ]
    return escape_leading_atx(" ".join(ln for ln in rendered_lines if ln))


def _format_code_diff_line(spans: Sequence[Span]) -> str:
    """Format one line of a fenced code diff with raw code text and role tags."""
    parts: list[str] = []
    for role, seg_spans in _group_domain_wording_spans(spans):
        text = "".join(s.text for s in seg_spans)
        if role in ("ins", "del"):
            parts.append(_wrap_wording_tag(role, text))
        else:
            parts.append(text)
    return "".join(parts).rstrip()


def _format_code_block(element: CodeBlock) -> str:
    """Format a fenced code block choosing appropriate fence length and info string."""
    if element.lines is not None:
        code_lines = [
            rendered
            for line in element.lines
            if (rendered := _format_code_diff_line(line)).strip()
        ]
        if not code_lines:
            return ""
        code_body = "\n".join(code_lines)
    else:
        if not element.code.strip():
            return ""
        code_body = element.code

    backtick_runs = re.findall(r"`+", code_body)
    max_run = max((len(r) for r in backtick_runs), default=2)
    fence = "`" * max(3, max_run + 1)

    lang = element.language or ""
    if element.title:
        info = f'{lang} title="{element.title}"' if lang else f'title="{element.title}"'
    else:
        info = lang

    return f"{fence}{info}\n{code_body}\n{fence}"


def _indent(text: str, width: int) -> str:
    """Indent every line of ``text`` by ``width`` spaces, blank lines included."""
    pad = " " * width
    return "\n".join(pad + line for line in text.split("\n"))


def _format_list_item(item: ListItem, marker: str) -> str:
    """Format one item as its label plus continuation blocks nested under the marker."""
    label = write_spans(item.spans)
    children = [
        (isinstance(child, ListBlock), rendered)
        for child in item.children
        if (rendered := write_element(child))
    ]
    if not label and not children:
        return ""

    width = len(marker) + 1
    first, _, rest = label.partition("\n")
    lines = [f"{marker} {first}" if label else marker]
    if rest:
        lines.append(_indent(rest, width))
    for position, (is_nested_list, rendered) in enumerate(children):
        if not is_nested_list and (label or position > 0):
            lines.append("")
        lines.append(_indent(rendered, width))
    return "\n".join(lines)


def _format_list_block(element: ListBlock) -> str:
    """Format an ordered or unordered list; empty items are skipped but still counted."""
    formatted_items: list[str] = []
    for index, item in enumerate(element.items):
        generated = f"{element.start + index}." if element.ordered else _BULLET_MARKER
        formatted = _format_list_item(item, item.marker or generated)
        if formatted:
            formatted_items.append(formatted)
    return "\n".join(formatted_items)


def _format_blockquote(element: Blockquote) -> str:
    """Format a blockquote by joining child blocks with a blank line and quoting every line."""
    inner = "\n\n".join(
        rendered
        for child in element.children
        if (rendered := write_element(child))
    )
    if not inner:
        return ""
    return "> " + inner.replace("\n", "\n> ")


def _non_ws_len(text: str) -> int:
    return len(_WHITESPACE_RE.sub("", text))


def _count_tagged_span_chars(spans: Sequence[Span], target_type: _RoleSpanType) -> int:
    total = 0
    for span in spans:
        if isinstance(span, target_type):
            total += _non_ws_len(span.text)
        elif isinstance(span, _CONTAINER_SPAN_TYPES):
            total += _count_tagged_span_chars(span.children, target_type)
    return total


def _count_tagged_block_chars(block: BlockElement, target_type: _RoleSpanType) -> int:
    if isinstance(block, (Paragraph, Heading)):
        return _count_tagged_span_chars(block.spans, target_type)
    if isinstance(block, ListBlock):
        return sum(
            _count_tagged_span_chars(item.spans, target_type)
            + sum(_count_tagged_block_chars(c, target_type) for c in item.children)
            for item in block.items
        )
    if isinstance(block, (Blockquote, WordingBlock)):
        return sum(_count_tagged_block_chars(c, target_type) for c in block.children)
    if isinstance(block, Table):
        cells = (*block.headers, *(c for row in block.rows for c in row.cells))
        return sum(
            _count_tagged_span_chars(c.spans, target_type)
            for c in cells
            if isinstance(c, TextCell)
        )
    # Code-shaped blocks (including code diffs) keep inline role tags literal.
    return 0


def _unwrap_spans(spans: Sequence[Span], target_type: _RoleSpanType) -> list[Span]:
    unwrapped: list[Span] = []
    for span in spans:
        if isinstance(span, target_type):
            unwrapped.extend(_unwrap_spans(span.children, target_type))
        elif isinstance(span, _CONTAINER_SPAN_TYPES):
            children = tuple(_unwrap_spans(span.children, target_type))
            unwrapped.append(replace(span, children=children))
        else:
            unwrapped.append(span)
    return unwrapped


def _unwrap_block(block: BlockElement, target_type: _RoleSpanType) -> BlockElement:
    if isinstance(block, (Paragraph, Heading)):
        return replace(block, spans=_unwrap_spans(block.spans, target_type))
    if isinstance(block, ListBlock):
        items = [
            replace(
                item,
                spans=_unwrap_spans(item.spans, target_type),
                children=[_unwrap_block(c, target_type) for c in item.children],
            )
            for item in block.items
        ]
        return replace(block, items=items)
    if isinstance(block, (Blockquote, WordingBlock)):
        return replace(
            block,
            children=[_unwrap_block(c, target_type) for c in block.children],
        )
    if isinstance(block, Table):
        headers = [
            replace(c, spans=_unwrap_spans(c.spans, target_type))
            if isinstance(c, TextCell)
            else c
            for c in block.headers
        ]
        rows = [
            TableRow(
                cells=[
                    replace(c, spans=_unwrap_spans(c.spans, target_type))
                    if isinstance(c, TextCell)
                    else c
                    for c in row.cells
                ]
            )
            for row in block.rows
        ]
        return replace(block, headers=headers, rows=rows)
    return block


def strip_redundant_roles(block: WordingBlock) -> WordingBlock:
    """Unwrap redundant inline role spans when ``block`` is uniformly one role."""
    implicit = implicit_role_for(block.role)
    if implicit is None:
        return block

    total_chars = _non_ws_len(block.text)
    if total_chars == 0:
        return block

    target_type = UnderlineSpan if implicit == "ins" else StrikethroughSpan
    if _count_tagged_block_chars(block, target_type) / total_chars < UNIFORM_ROLE_THRESHOLD:
        return block

    return replace(
        block,
        children=[_unwrap_block(child, target_type) for child in block.children],
    )


def _format_wording_child(child: BlockElement) -> str:
    if isinstance(child, Paragraph):
        return _format_wording_paragraph(child)
    return write_element(child)


def _format_wording_block(element: WordingBlock) -> str:
    """Format a wording block without a fenced div wrapper."""
    cleaned = strip_redundant_roles(element)
    return "\n\n".join(
        rendered
        for child in cleaned.children
        if (rendered := _format_wording_child(child))
    )


def write_element(element: BlockElement) -> str:
    """Format a single BlockElement into Markdown text."""
    if isinstance(element, Heading):
        level = max(1, min(6, element.level))
        prefix = "#" * level
        return f"{prefix} {write_spans(element.spans)}"

    if isinstance(element, Paragraph):
        return write_spans(element.spans)

    if isinstance(element, CodeBlock):
        return _format_code_block(element)

    if isinstance(element, ListBlock):
        return _format_list_block(element)

    if isinstance(element, Table):
        return write_table(element)

    if isinstance(element, Blockquote):
        return _format_blockquote(element)

    if isinstance(element, ThematicBreak):
        return "---"

    if isinstance(element, WordingBlock):
        return _format_wording_block(element)

    # Markdown never carries image syntax (#408); the node stays in the AST for other writers.
    if isinstance(element, ImageElement):
        return ""

    if isinstance(element, UncertainElement):
        prompt_str = element.prompt.replace('"', '\\"')
        return f'<!-- tomd:uncertain prompt="{prompt_str}" -->\n{element.raw_content}'

    return getattr(element, "text", "")


__all__ = ["strip_redundant_roles", "write_element"]
