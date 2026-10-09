#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""C++ Alliance report theme: one branded HTML document shell for every report.

Any report that reaches a human goes through here, so the logo, palette and
typography are identical across the benchmark report, the side-by-side
comparisons, and whatever comes next. The stylesheet and logo were measured out
of ``assets/LAYOUT-REFERENCE.pdf``; that file is the design contract.

Assets are inlined rather than linked. These documents get emailed, attached to
gists, and printed to PDF from a temporary directory, and a relative asset path
survives none of those.
"""

from __future__ import annotations

import base64
import html
import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
CSS_PATH = ASSETS_DIR / "alliance.css"
LOGO_PATH = ASSETS_DIR / "cppalliance-logo.png"
REFERENCE_PDF = ASSETS_DIR / "LAYOUT-REFERENCE.pdf"

ORGANISATION = "The C++ Alliance"


@lru_cache(maxsize=1)
def stylesheet() -> str:
    """The Alliance report stylesheet."""
    return CSS_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def logo_data_uri() -> str:
    """The Alliance shield as a self-contained data URI."""
    encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@dataclass(frozen=True)
class ReportMeta:
    """Masthead and footer fields shared by every branded report."""

    title: str
    subtitle: str = ""
    fields: tuple[tuple[str, str], ...] = ()
    footer_left: str = ORGANISATION
    footer_right: str = ""

    def resolved_footer_right(self) -> str:
        return self.footer_right or date.today().isoformat()


def _masthead(meta: ReportMeta) -> str:
    subtitle = (
        f'<div class="report-subtitle">{html.escape(meta.subtitle)}</div>'
        if meta.subtitle
        else ""
    )
    return (
        '<header class="report-masthead">\n'
        f"<div><h1>{html.escape(meta.title)}</h1>{subtitle}</div>\n"
        f'<img class="report-logo" src="{logo_data_uri()}" '
        f'alt="{html.escape(ORGANISATION)}">\n'
        "</header>"
    )


# Report authors write metadata values like "commit `0d18a65b`", so the code
# spans have to survive into the masthead instead of showing their backticks.
_INLINE_CODE = re.compile(r"`([^`]+)`")


def _inline(value: str) -> str:
    escaped = html.escape(value)
    return _INLINE_CODE.sub(r"<code>\1</code>", escaped)


def _meta_block(meta: ReportMeta) -> str:
    if not meta.fields:
        return ""
    parts = [
        f"<strong>{html.escape(label)}:</strong> {_inline(value)}"
        for label, value in meta.fields
    ]
    return '<p class="report-meta">' + "<br>".join(parts) + "</p>"


def _footer(meta: ReportMeta) -> str:
    return (
        '<footer class="report-footer">'
        f"<span>{html.escape(meta.footer_left)}</span>"
        f"<span>{html.escape(meta.resolved_footer_right())}</span>"
        "</footer>"
    )


def wrap_document(
    body_html: str,
    meta: ReportMeta,
    extra_css: str = "",
    landscape: bool = False,
) -> str:
    """Wrap rendered body HTML in the branded, self-contained document shell."""
    orientation = "@page { size: A4 landscape; }" if landscape else ""
    css = stylesheet()
    if orientation:
        css += f"\n{orientation}\n"
    if extra_css:
        css += f"\n{extra_css}\n"

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(meta.title)}</title>\n"
        f"<style>{css}</style>\n"
        "</head>\n"
        "<body>\n"
        f"{_masthead(meta)}\n"
        f"{_meta_block(meta)}\n"
        f"{body_html}\n"
        f"{_footer(meta)}\n"
        "</body>\n"
        "</html>\n"
    )
