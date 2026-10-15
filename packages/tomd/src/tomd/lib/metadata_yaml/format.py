# Copyright 2026 The C++ Alliance, Inc.
# SPDX-License-Identifier: BSL-1.0
"""YAML front matter formatting and parsing for WG21 paper metadata.

Serializes metadata in the canonical order (``FRONT_MATTER_ORDER``, owned by
``tomd.domain.front_matter``) and parses it back. The value rules applied while
formatting (blank values, title normalization, intent from title) live in the
domain; this module only applies them.

``parse_front_matter`` recognizes only the shapes ``format_front_matter``
emits: scalar ``key: value`` (optionally double-quoted) and ``key:``
followed by indented ``- "item"`` lines.
"""

import re

from tomd.domain.front_matter import FRONT_MATTER_ORDER, is_blank_value
from tomd.domain.metadata import intent_from_title, normalize_title

FrontMatterDict = dict[str, str | list[str]]

FRONT_MATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n?", re.DOTALL)

_LIST_ITEM_RE = re.compile(r"^\s+-\s+(.*)$")


def _unquote_yaml_scalar(s: str) -> str:
    """Strip surrounding double-quotes and resolve YAML backslash escapes."""
    if len(s) < 2 or s[0] != '"' or s[-1] != '"':
        return s
    inner = s[1:-1]
    out: list[str] = []
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and i + 1 < len(inner):
            nxt = inner[i + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt in ('"', "\\"):
                out.append(nxt)
            else:
                out.append(nxt)
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _parse_front_matter_body(body: str) -> FrontMatterDict:
    """Parse a YAML front-matter body into a dict."""
    parsed: FrontMatterDict = {}
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if line.startswith((" ", "\t", "-")):
            i += 1
            continue
        head, sep, tail = line.partition(":")
        if not sep:
            i += 1
            continue
        key = head.strip()
        value = tail.strip()
        if value:
            parsed[key] = _unquote_yaml_scalar(value)
            i += 1
            continue
        items: list[str] = []
        j = i + 1
        while j < len(lines):
            item_line = lines[j]
            if not item_line.strip():
                j += 1
                continue
            m = _LIST_ITEM_RE.match(item_line)
            if not m:
                break
            items.append(_unquote_yaml_scalar(m.group(1).strip()))
            j += 1
        if items:
            parsed[key] = items
            i = j
        else:
            i += 1
    return parsed


def parse_front_matter(md: str) -> FrontMatterDict:
    """Parse YAML front matter from markdown into a metadata dict.

    Scalar keys map to ``str``; list-valued keys (e.g. ``reply-to``) map to
    ``list[str]``. Returns an empty dict when no front matter block is present.
    """
    match = FRONT_MATTER_RE.match(md)
    if not match:
        return {}
    return _parse_front_matter_body(match.group("body"))


def strip_front_matter(md: str) -> str:
    """Return markdown with the leading YAML front matter block removed."""
    match = FRONT_MATTER_RE.match(md)
    if not match:
        return md
    return md[match.end():]


def _yaml_escape(s: str) -> str:
    """Escape a string for safe inclusion in double-quoted YAML."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _yaml_value(key: str, val) -> str:
    """Format a single YAML value, quoting where needed."""
    if isinstance(val, list):
        items = [f'  - "{_yaml_escape(str(v))}"' for v in val]
        return f"{key}:\n" + "\n".join(items)
    val = str(val) if not isinstance(val, str) else val
    if key == "title" or any(c in val for c in ':{}[]#&*?|>!%@`"\'\n\\'):
        return f'{key}: "{_yaml_escape(val)}"'
    return f"{key}: {val}"


def _without_blanks(metadata: dict) -> dict:
    """Return ``metadata`` without blank values; list values lose their blank items."""
    kept: dict = {}
    for key, value in metadata.items():
        if is_blank_value(value):
            continue
        if isinstance(value, (list, tuple)):
            value = [item for item in value if not is_blank_value(item)]
        kept[key] = value
    return kept


def format_front_matter(metadata: dict) -> str:
    """Format metadata dict as YAML front matter in strict canonical order.

    Strict-order contract: keys are emitted exactly in the order
    ``title, document, date, intent, audience, reply-to``. Missing and
    blank keys are skipped (no placeholders, no blank lines); a list value
    drops its blank items. Unknown keys appear
    after ``audience`` so ``reply-to`` is always last. Callers and
    downstream tools may rely on this ordering for diffs and parsing.

    Title and values containing YAML-special characters are double-quoted
    with backslash-escaping for embedded quotes, backslashes, and newlines.
    Reply-to is a YAML list of double-quoted strings. Returns the empty
    string when no non-blank value remains.
    """
    if not metadata:
        return ""
    metadata = dict(metadata)
    if isinstance(metadata.get("title"), str):
        metadata["title"] = normalize_title(metadata["title"])

    metadata = _without_blanks(metadata)
    if not metadata:
        return ""

    if "intent" not in metadata and isinstance(metadata.get("title"), str):
        intent = intent_from_title(metadata["title"])
        if intent:
            metadata["intent"] = intent

    lines = ["---"]
    pre_reply_to: list[str] = []
    reply_to_line: str | None = None
    for key in FRONT_MATTER_ORDER:
        if key not in metadata:
            continue
        rendered = _yaml_value(key, metadata[key])
        if key == "reply-to":
            reply_to_line = rendered
        else:
            pre_reply_to.append(rendered)
    lines.extend(pre_reply_to)
    for key, val in metadata.items():
        if key not in FRONT_MATTER_ORDER:
            lines.append(_yaml_value(key, val))
    if reply_to_line is not None:
        lines.append(reply_to_line)
    lines.append("---")
    return "\n".join(lines)
