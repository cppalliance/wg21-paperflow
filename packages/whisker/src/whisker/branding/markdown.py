#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Markdown to branded report HTML.

Reports are authored as Markdown and read as PDFs, so this is the bridge. The
leading H1 and the metadata lines beneath it are lifted out of the body and into
the masthead, because the theme renders the title beside the logo rather than as
the first thing in the text flow.
"""

from __future__ import annotations

import re

import mistune

from whisker.branding.theme import ReportMeta, wrap_document

# "**Label:** value" lines directly under the title, as used by report authors.
_META_LINE = re.compile(r"^\*\*(?P<label>[^*]+?):\*\*\s*(?P<value>.+?)\s*$")
_H1_LINE = re.compile(r"^#\s+(?P<title>.+?)\s*$")

_TABLE_PLUGINS = ("table", "strikethrough", "footnotes", "url")


def split_front_block(md_text: str) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    """Split a report into its title, body, and masthead metadata fields.

    Returns (title, remaining_markdown, fields). The title and the run of
    ``**Label:** value`` lines that immediately follow it are consumed.
    """
    lines = md_text.splitlines()
    index = 0
    title = ""

    while index < len(lines) and not lines[index].strip():
        index += 1

    if index < len(lines):
        match = _H1_LINE.match(lines[index])
        if match:
            title = match.group("title").strip()
            index += 1

    fields: list[tuple[str, str]] = []
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            # Metadata runs may be blank-line separated from the title, but a
            # blank line after the run itself ends it.
            if fields:
                break
            continue
        match = _META_LINE.match(stripped)
        if not match:
            break
        fields.append((match.group("label").strip(), match.group("value").strip()))
        index += 1

    return title, "\n".join(lines[index:]), tuple(fields)


def markdown_to_body_html(md_text: str) -> str:
    """Render Markdown to HTML fragment with tables and footnotes enabled."""
    renderer = mistune.create_markdown(plugins=list(_TABLE_PLUGINS))
    return renderer(md_text)


def render_branded_html(
    md_text: str,
    title: str = "",
    subtitle: str = "",
    footer_right: str = "",
    landscape: bool = False,
) -> str:
    """Render a Markdown report as a complete branded HTML document."""
    parsed_title, body_md, fields = split_front_block(md_text)
    meta = ReportMeta(
        title=title or parsed_title or "Report",
        subtitle=subtitle,
        fields=fields,
        footer_right=footer_right,
    )
    return wrap_document(
        markdown_to_body_html(body_md), meta, landscape=landscape
    )
