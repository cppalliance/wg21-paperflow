"""Integration tests for lib.html.convert_html."""

from pathlib import Path

from tomd.lib.html import convert_html


def _write(tmp: Path, name: str, html: str) -> Path:
    p = tmp / name
    p.write_text(html, encoding="utf-8")
    return p


MPARK_WITH_BODY = """<!DOCTYPE html>
<html><head><meta charset="utf-8"/></head><body>
<header id="title-block-header">
<h1 class="title">Paper Title</h1>
<table>
<tr><td>Document #:</td><td>P9999R0</td></tr>
<tr><td>Date:</td><td>2026-04-01</td></tr>
</table>
</header>
<p>Body paragraph one.</p>
</body></html>
"""


def test_convert_html_happy_path(tmp_path):
    path = _write(tmp_path, "x.html", MPARK_WITH_BODY)
    md, prompts = convert_html(path)
    assert prompts is None
    assert md.startswith("---")
    assert "P9999R0" in md
    assert "Body paragraph one." in md
    assert md.endswith("\n")
    assert "\n\nBody paragraph one." in md


def test_convert_html_unknown_generator_prompts(tmp_path):
    html = "<html><body><p>Only content</p></body></html>"
    path = _write(tmp_path, "u.html", html)
    md, prompts = convert_html(path)
    assert isinstance(prompts, list) and prompts
    joined = "\n".join(prompts)
    assert "HTML-to-Markdown conversion" in joined
    assert "Unrecognized" in joined
    assert "Only content" in md


def test_convert_html_unicode_preserved(tmp_path):
    html = """<!DOCTYPE html><html><body>
<header id="title-block-header">
<h1 class="title">T\u00fctle</h1>
<table><tr><td>Document #:</td><td>P1R0</td></tr></table>
</header>
<p>Body \u00fc</p>
</body></html>"""
    path = _write(tmp_path, "enc.html", html)
    md, prompts = convert_html(path)
    assert prompts is None
    assert "\xfc" in md


def test_convert_html_metadata_only_empty_body(tmp_path):
    html = """<html><body>
<header id="title-block-header">
<h1 class="title">Solo</h1>
<table><tr><td>Document #:</td><td>P2R0</td></tr></table>
</header>
</body></html>"""
    path = _write(tmp_path, "meta.html", html)
    md, prompts = convert_html(path)
    assert prompts is None
    assert md.startswith("---")
    assert "Solo" in md or "solo" in md.lower()


def test_convert_html_title_with_embedded_dashes(tmp_path):
    html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"/></head><body>
<header id="title-block-header">
<h1 class="title">Before --- After</h1>
<table>
<tr><td>Document #:</td><td>P8888R0</td></tr>
<tr><td>Date:</td><td>2026-04-01</td></tr>
</table>
</header>
<p>Paragraph after title.</p>
</body></html>"""
    path = _write(tmp_path, "dashes.html", html)
    md, prompts = convert_html(path)
    assert prompts is None
    assert "Before --- After" in md
    assert "Paragraph after title." in md
    body_start = md.find("---", 4)
    assert body_start >= 0
    body = md[body_start:]
    closing = body.find("\n---", 1)
    assert closing >= 0
    body_text = body[closing + 4 :]
    assert "# Before --- After" not in body_text


def test_convert_html_front_matter_then_body_separator(tmp_path):
    path = _write(tmp_path, "sep.html", MPARK_WITH_BODY)
    md, _ = convert_html(path)
    idx = md.find("Body paragraph one.")
    assert idx > 0
    before = md[:idx]
    assert before.rstrip().endswith("---")
    assert "\n\n" in md[: idx + 1]


def test_unknown_no_warning_when_table_metadata_found(tmp_path):
    """unknown generator: warning suppressed when metadata was extracted."""
    html = """<!DOCTYPE html><html><body>
<h1>Some Paper</h1>
<table>
  <tr><th>Document number:</th><td>P9001R0</td></tr>
  <tr><th>Date:</th><td>2026-04-01</td></tr>
</table>
<p>Body text here.</p>
</body></html>"""
    path = _write(tmp_path, "unknown_meta.html", html)
    md, prompts = convert_html(path)
    assert prompts is None, "warning should be suppressed when metadata was found"
    assert "P9001R0" in md


def test_unknown_warning_preserved_when_no_metadata(tmp_path):
    """unknown generator, no recognizable metadata: warning IS emitted.

    This is the failure-detection test - extraction failed, and tomd correctly
    signals it via the prompts file so the user knows.
    """
    html = """<!DOCTYPE html><html><body>
<p>This has no document number, date, or any WG21 metadata at all.</p>
<p>Just pure prose with nothing recognizable.</p>
</body></html>"""
    path = _write(tmp_path, "unknown_no_meta.html", html)
    md, prompts = convert_html(path)
    assert isinstance(prompts, list) and prompts, (
        "warning should be present when extraction failed"
    )
    assert any("Unrecognized" in p for p in prompts)
