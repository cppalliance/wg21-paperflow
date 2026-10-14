#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""HTML to PDF via headless Chromium, shared by every report renderer.

Chromium is the only print engine assumed to be present on a developer machine,
and it is the one whose CSS support matches what the theme is written against.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

BROWSER_CANDIDATES: tuple[str, ...] = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/usr/bin/microsoft-edge",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)

PATH_CANDIDATES: tuple[str, ...] = (
    "msedge",
    "google-chrome",
    "chromium",
    "chromium-browser",
)

PDF_TIMEOUT_SECONDS = 180

# Chromium's legacy headless mode exits 0 without printing anything, so the new
# mode is tried first and the legacy one kept only as a fallback.
HEADLESS_MODES = ("--headless=new", "--headless")


def find_browser() -> str | None:
    """Locate a Chromium-family browser, or None."""
    for candidate in BROWSER_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    for name in PATH_CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    return None


def html_to_pdf(html_path: Path, pdf_path: Path) -> bool:
    """Print an HTML file to PDF. Returns True only if a PDF was actually written.

    Success is decided by inspecting the output file rather than the exit code,
    because Chromium reports 0 in several situations where it prints nothing. An
    earlier version trusted the exit code and reported PDFs that did not exist.
    """
    browser = find_browser()
    if browser is None:
        log.error("no Chromium-family browser found for PDF generation")
        return False

    html_uri = html_path.resolve().as_uri()
    pdf_path = pdf_path.resolve()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    for mode in HEADLESS_MODES:
        pdf_path.unlink(missing_ok=True)
        try:
            result = subprocess.run(
                [
                    browser,
                    mode,
                    "--disable-gpu",
                    "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path}",
                    html_uri,
                ],
                capture_output=True,
                timeout=PDF_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            log.warning("%s: timed out after %ss", mode, PDF_TIMEOUT_SECONDS)
            continue

        if pdf_path.is_file() and pdf_path.stat().st_size > 0:
            return True

        stderr = result.stderr.decode("utf-8", "replace").strip().splitlines()
        log.warning(
            "%s: exit %s, %s",
            mode,
            result.returncode,
            stderr[-1] if stderr else "no output written",
        )

    return False
