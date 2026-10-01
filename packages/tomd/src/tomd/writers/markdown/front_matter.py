"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

from __future__ import annotations

import re
from typing import Any

from tomd.domain.metadata import FRONT_MATTER_ORDER, PaperMetadata

_YAML_SPECIAL_CHARS = set(':{}[]#&*?|>!%@`"\'\n\\')


def _yaml_escape(s: str) -> str:
    """Escape backslashes, quotes, and newlines for double-quoted YAML scalars."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _yaml_value(key: str, val: Any) -> str:
    """Format a single key-value entry according to YAML formatting rules."""
    if isinstance(val, (list, tuple)):
        items = [f'  - "{_yaml_escape(str(v))}"' for v in val if str(v).strip()]
        if not items:
            return ""
        return f"{key}:\n" + "\n".join(items)

    sval = str(val) if val is not None else ""
    if not sval.strip():
        return ""

    if key == "title" or any(c in sval for c in _YAML_SPECIAL_CHARS):
        return f'{key}: "{_yaml_escape(sval)}"'
    return f"{key}: {sval}"


def write_front_matter(metadata: PaperMetadata | dict[str, Any] | None) -> str:
    """Format metadata as YAML front matter adhering to strict canonical order."""
    if not metadata:
        return ""

    if isinstance(metadata, PaperMetadata):
        data = metadata.to_dict()
    elif isinstance(metadata, dict):
        data = dict(metadata)
    else:
        return ""

    if not data:
        return ""

    # Clean title whitespace and normalize ::
    if "title" in data and isinstance(data["title"], str):
        title = data["title"].replace("\n", " ")
        title = re.sub(r"\s*::\s*", "::", title)
        title = re.sub(r"  +", " ", title).strip()
        data["title"] = title

    # Intent auto-inference
    if "intent" not in data or not data["intent"]:
        title = str(data.get("title", "")).strip()
        if title.startswith("Info:"):
            data["intent"] = "info"
        elif title.startswith("Ask:"):
            data["intent"] = "ask"

    lines: list[str] = ["---"]
    pre_reply_to: list[str] = []
    reply_to_line: str | None = None

    for key in FRONT_MATTER_ORDER:
        if key not in data or data[key] in (None, "", []):
            continue
        rendered = _yaml_value(key, data[key])
        if not rendered:
            continue
        if key == "reply-to":
            reply_to_line = rendered
        else:
            pre_reply_to.append(rendered)

    lines.extend(pre_reply_to)

    # Extra non-standard keys appear after audience and before reply-to
    for key, val in data.items():
        if key in FRONT_MATTER_ORDER or val in (None, "", []):
            continue
        rendered = _yaml_value(key, val)
        if rendered:
            lines.append(rendered)

    if reply_to_line is not None:
        lines.append(reply_to_line)

    # If nothing was emitted between fences, metadata was effectively empty
    if len(lines) == 1:
        return ""

    lines.append("---")
    return "\n".join(lines)


__all__ = ["write_front_matter"]
