#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Branded report rendering: one theme for every PDF the project produces.

Named ``branding`` rather than ``report`` because ``whisker.det.report`` is the QA
verdict renderer and predates this.
"""

from whisker.branding.markdown import (
    markdown_to_body_html,
    render_branded_html,
    split_front_block,
)
from whisker.branding.pdf import find_browser, html_to_pdf
from whisker.branding.theme import (
    ASSETS_DIR,
    CSS_PATH,
    LOGO_PATH,
    REFERENCE_PDF,
    ReportMeta,
    logo_data_uri,
    stylesheet,
    wrap_document,
)

__all__ = [
    "ASSETS_DIR",
    "CSS_PATH",
    "LOGO_PATH",
    "REFERENCE_PDF",
    "ReportMeta",
    "find_browser",
    "html_to_pdf",
    "logo_data_uri",
    "markdown_to_body_html",
    "render_branded_html",
    "split_front_block",
    "stylesheet",
    "wrap_document",
]
