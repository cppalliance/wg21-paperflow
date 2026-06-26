#
# Copyright (c) 2026 Luan Fonseca (luan@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Wording-section rendering for the PDF emitter.

A wording section (``:::wording-add`` / ``:::wording-remove`` / neutral
``:::wording``) renders in one of three shapes, fidelity first: a
wholesale fenced code block, a code-shaped ``<br>`` diff, or prose. All
three live here so :mod:`emit` keeps to general block dispatch. The
uniform-role boundary shared with the post-render cleanup pass lives in
:mod:`lib.wording_policy`; the code-promotion knobs below are emit-only
because they need span-level structure the assembled Markdown has
already collapsed.
"""

from __future__ import annotations

from .. import DEFAULT_FENCE_LANG
from ..wording_markup import WORDING_FENCE_CLOSE, wording_fence_open
from ..wording_policy import UNIFORM_ROLE_THRESHOLD, implicit_role_for
from .cleanup import normalize_whitespace
from .code_format import normalize_code_line
from .code_grid import CodeGrid
from .types import Line, Span, Section, SectionKind

# Monospace fraction at or above which a wording section reads as code.
_MONO_DOMINANT_THRESHOLD = 0.80

# A single bullet item like "* common_type_t<From, To> is To," can
# cross the monospace threshold by character count yet still read as a
# list item, not a code block. Multi-line is the structural signal
# that distinguishes a declaration from inline code in prose.
_CODE_PROMOTION_MIN_LINES = 2

# Largest plausible leading indent (in spaces) for a code line. WG21
# wording code nests shallowly; a larger glyph-derived indent always
# means the line's first glyph is a right-margin element (a section
# anchor like [simd.expos], a trailing `// exposition only` comment)
# that extraction split onto its own line, not real nesting. Such
# lines are pinned to column zero instead of indented across the page.
_MAX_CODE_DIFF_INDENT = 24


def _escape_wording_text(text: str) -> str:
    """HTML-escape literal (non-tag, non-backtick) text in a wording line.

    Wording lines render inside a Pandoc fenced div where ``<ins>`` /
    ``<del>`` are real HTML tags, so the surrounding content sits in an
    HTML context. A literal ``<`` / ``>`` in the code (the ``<float>`` in
    ``vec<float>``) is otherwise parsed as a stray HTML tag and silently
    dropped by the renderer. Escaping makes those angle brackets render
    literally. Backtick code spans are left untouched: the Markdown
    renderer already escapes their contents, and escaping them here would
    surface the raw entities. The ``<ins>`` / ``<del>`` tags themselves
    are emitted around the escaped text, never through this helper.
    """
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))


def _group_wording_spans(line: Line) -> list[tuple[str | None, list[Span]]]:
    """Partition a line's spans into ordered role / non-role segments.

    Each segment is ``(role, spans)``. A ``role`` of ``"ins"`` or
    ``"del"`` is a run of same-role spans, with whitespace between two
    spans of that role absorbed into the run; a ``None`` role is a
    buffer of whitespace or non-role spans sitting between role runs.
    The prose and code-diff line renderers share this partition and
    differ only in how they emit each segment.
    """
    segments: list[tuple[str | None, list[Span]]] = []
    group: list[Span] = []
    group_role: str | None = None
    ws_buf: list[Span] = []

    for span in line.spans:
        role = span.wording_role if span.text.strip() else None
        if role is None:
            ws_buf.append(span)
        elif role == group_role:
            group.extend(ws_buf)
            ws_buf.clear()
            group.append(span)
        else:
            if group:
                segments.append((group_role, group))
                group = []
            if ws_buf:
                segments.append((None, list(ws_buf)))
                ws_buf.clear()
            group_role, group = role, [span]

    if group:
        segments.append((group_role, group))
    if ws_buf:
        segments.append((None, list(ws_buf)))
    return segments


def _role_tag(
    role: str, spans: list[Span], *, normalize: bool = False,
) -> str:
    """Wrap a same-role run in its ``<ins>`` / ``<del>`` tag.

    Leading and trailing whitespace stay outside the tag so adjacent
    segments join cleanly; the inner text is HTML-escaped. When
    ``normalize`` is true (the code-diff path), the inner text is also
    run through :func:`normalize_code_line` so edited tokens get the
    same PDF kerning cleanup the surrounding role-less context already
    receives. The prose path keeps ``normalize=False`` because its
    inner text is natural-language, not C++.
    """
    text = "".join(s.text for s in spans)
    inner = text.strip()
    lead = text[:len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    if normalize:
        inner = normalize_code_line(inner)
    return f"{lead}<{role}>{_escape_wording_text(inner)}</{role}>{trail}"


def _render_wording_line(line: Line) -> str:
    """Render a wording line, merging consecutive same-role spans.

    Whitespace-only spans between two same-role spans are absorbed into
    the group. ``ins`` / ``del`` runs become HTML tags; any other named
    role (e.g. ``context``) and bare whitespace render as prose, with
    monospace spans backticked. Stripping redundant tags (when the whole
    div is uniformly one role) is delegated to the post-render pass in
    ``lib.wording_cleanup``, which sees the assembled Markdown and is
    shared between PDF and HTML emitters.
    """
    parts: list[str] = []
    for role, spans in _group_wording_spans(line):
        if role in ("ins", "del"):
            parts.append(_role_tag(role, spans))
        elif role is None:
            parts.extend(_escape_wording_text(s.text) for s in spans)
        else:
            parts.append("".join(
                f"`{s.text.strip()}`" if s.monospace and s.text.strip()
                else _escape_wording_text(s.text)
                for s in spans
            ))
    return "".join(parts)


def _wording_glyph_stats(lines: list[Line]) -> tuple[int, int, dict[str, int]]:
    """Tally non-whitespace glyph chars in a wording section.

    Returns ``(total, monospace, role_counts)`` where ``role_counts``
    maps each non-``None`` ``wording_role`` to the number of glyph
    characters carrying it. Whitespace is excluded throughout: it
    drifts between spans during extraction and would skew both ratios.
    """
    total = 0
    mono = 0
    roles: dict[str, int] = {}
    for line in lines:
        for span in line.spans:
            stripped = span.text.strip()
            if not stripped:
                continue
            n = len(stripped)
            total += n
            if span.monospace:
                mono += n
            if span.wording_role:
                roles[span.wording_role] = roles.get(span.wording_role, 0) + n
    return total, mono, roles


def _render_wording_code_block(sec: Section, lang: str) -> str:
    """Render a uniform-role monospace wording section as fenced code.

    Preserves the per-line structure (unlike the prose path which
    collapses lines) and runs every emitted line through
    ``normalize_code_line``. Extend with :func:`is_diagram_block` if
    wording-colored diagrams ever appear in the corpus. Leading
    indentation is reconstructed from
    glyph x-positions via ``CodeGrid``, the same machinery the
    code-diff sibling (:func:`_render_wording_code_diff`) uses, with an
    implausibly deep indent (a right-margin element split onto its own
    line) pinned to column zero via ``_MAX_CODE_DIFF_INDENT``. The cap
    stays appropriate here because wording C++ nests shallowly.
    """
    grid = CodeGrid.for_code_section(sec)
    code_lines: list[str] = []
    has_content = False
    for line in sec.lines:
        text = "".join(span.text for span in line.spans).rstrip()
        if not text:
            # Preserve blank lines so a fenced wording listing keeps
            # the same paragraph rhythm the source PDF had: the plain
            # code path also keeps them (a fenced ``cpp`` block with a
            # blank middle line renders as two visual paragraphs of
            # code), and dropping them silently rewraps unrelated
            # declarations together.
            code_lines.append("")
            continue
        has_content = True
        indent = grid.indent(line, max_indent=_MAX_CODE_DIFF_INDENT)
        code_lines.append(" " * indent + normalize_code_line(text.lstrip()))
    if not has_content:
        return ""
    return f"```{lang}\n" + "\n".join(code_lines) + "\n```"


def _render_wording_code_diff_line(line: Line) -> str:
    """Render one wording line as code: raw text + inline role tags.

    Unlike :func:`_render_wording_line`, non-role monospace runs are
    emitted verbatim (no surrounding backticks) and passed through
    :func:`normalize_code_line` to clean PDF kerning artifacts. Role
    runs (``ins`` / ``del``) keep their HTML tags so the intra-block
    diff survives. This is the per-line primitive for the code-diff
    shape, which a fenced code block cannot represent.
    """
    def _emit(role: str | None, spans: list[Span]) -> str:
        if role in ("ins", "del"):
            return _role_tag(role, spans, normalize=True)
        text = "".join(s.text for s in spans)
        return _escape_wording_text(normalize_code_line(text))

    parts = [_emit(role, spans) for role, spans in _group_wording_spans(line)]
    return "".join(parts).rstrip()


def _render_wording_code_diff(sec: Section) -> str:
    """Render a code-shaped wording section preserving line structure.

    Used when the section is monospace-dominant and multi-line but is
    NOT a uniform single-role block: it carries an intra-block edit
    (mixed ins/del, or one struck/inserted token amid unchanged
    context), or its role coloring is too sparse to safely promote to
    a fence. A fenced code block cannot carry ``<ins>`` / ``<del>``
    (they would render literally), so each source line is emitted on
    its own line, joined with ``<br>``, inline tags intact. Leading
    indentation is reconstructed from glyph x-positions, with an
    implausibly deep indent (a right-margin element split onto its own
    line) pinned to column zero via ``_MAX_CODE_DIFF_INDENT``.
    """
    grid = CodeGrid.for_code_section(sec)

    out_lines: list[str] = []
    for line in sec.lines:
        rendered = _render_wording_code_diff_line(line)
        if not rendered.strip():
            continue
        indent = grid.indent(line, max_indent=_MAX_CODE_DIFF_INDENT)
        out_lines.append(" " * indent + rendered.lstrip())
    return "<br>\n".join(out_lines)


def _render_wording_section(sec: Section) -> str:
    """Render a wording section with Pandoc fenced div markers.

    Three rendering shapes, fidelity first (never collapse code line
    structure, never drop a diff):

    1. **Wholesale code (fence).** Monospace-dominant, multi-line, and
       uniformly the div's role: emit a fenced ``cpp`` block inside the
       directional div, dropping the now-redundant inline tags.
    2. **Code-shaped diff (``<br>``).** Monospace-dominant and
       multi-line but not uniform: a *partial* change. Emit a neutral
       ``:::wording`` div (never the directional ``wording-add`` /
       ``wording-remove``, which would paint the unchanged context as
       inserted/removed) and carry the diff entirely through inline
       ``<ins>`` / ``<del>`` tags, one source line per output line
       joined with ``<br>``.
    3. **Prose (default).** Render each span faithfully in the
       directional div; the post-render pass in ``lib.wording_cleanup``
       decides whether the inline tags are redundant with the div role.
    """
    div_class = sec.kind.value
    implicit_role = implicit_role_for(div_class)

    total, mono, roles = _wording_glyph_stats(sec.lines)
    # A fence cannot carry inline ``<ins>`` / ``<del>`` tags (they would
    # render literally), so the fence path collapses every span into the
    # div's implicit role. Promotion is therefore gated on two clauses:
    # the dominant role must clear ``UNIFORM_ROLE_THRESHOLD`` (the share
    # contract with ``lib.wording_cleanup``), AND no contrarian-role
    # chars may exist. The strict zero check prevents a small ``<del>``
    # inside an otherwise-uniform ``<ins>`` block from being silently
    # flattened into the implicit role; when one is present the section
    # falls through to ``_render_wording_code_diff`` (the ``<br>`` diff
    # path), which preserves the contrarian tag verbatim.
    contrarian_chars = sum(
        n for role, n in roles.items() if role != implicit_role
    )
    uniform_role = (
        implicit_role is not None
        and total > 0
        and contrarian_chars == 0
        and roles.get(implicit_role, 0) / total >= UNIFORM_ROLE_THRESHOLD
    )
    monospace_dominant = total > 0 and mono / total >= _MONO_DOMINANT_THRESHOLD

    nonblank_lines = sum(
        1 for ln in sec.lines if any(s.text.strip() for s in ln.spans)
    )
    code_shaped = monospace_dominant and nonblank_lines >= _CODE_PROMOTION_MIN_LINES

    if code_shaped and uniform_role:
        lang = sec.fence_lang or DEFAULT_FENCE_LANG
        code = _render_wording_code_block(sec, lang)
        if code:
            return f"{wording_fence_open(div_class)}\n\n{code}\n\n{WORDING_FENCE_CLOSE}"

    if code_shaped:
        diff = _render_wording_code_diff(sec)
        if diff:
            neutral = SectionKind.WORDING.value
            return f"{wording_fence_open(neutral)}\n\n{diff}\n\n{WORDING_FENCE_CLOSE}"

    rendered_lines = [_render_wording_line(line) for line in sec.lines]
    text = normalize_whitespace("\n".join(rendered_lines))
    inner = " ".join(ln.strip() for ln in text.split("\n") if ln.strip())
    return f"{wording_fence_open(div_class)}\n\n{inner}\n\n{WORDING_FENCE_CLOSE}"
