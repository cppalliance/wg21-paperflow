#
# Copyright (c) 2026 Dmitriy Chukhin (dmitriy@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Tests for ``preview.render``: paper image inlining + cache invalidation.

The full ``render_markdown`` path is integration-tested manually via
``paperflow preview <PID>`` (scrivener is heavy and out of scope here).
These tests exercise the pre-scrivener rewrite and the data-URL cache
key fix in isolation.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from paperstore import SqliteBackend
from preview.render import (
    _fix_split_ol_numbering,
    _image_data_url,
    _image_data_url_cached,
    _render_blockquote_tables,
    _rewrite_paper_image_refs,
    render_markdown,
)


# 1x1 transparent PNG.
_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBg"
    "AAAABQABh6FO1AAAAABJRU5ErkJggg=="
)


@pytest.fixture
def backend(tmp_path: Path) -> SqliteBackend:
    return SqliteBackend(tmp_path)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Each test starts with an empty data-url cache so mtime keying is
    actually exercised."""
    _image_data_url_cached.cache_clear()
    yield
    _image_data_url_cached.cache_clear()


# ---- _rewrite_paper_image_refs ----------------------------------------------


def test_rewrite_inlines_paper_image_as_html_img(backend: SqliteBackend):
    """The whole point of the rewrite: scrivener would strip the markdown
    img's src; raw HTML img passes through."""
    backend.write_paper_image("P3556R0", 3, 1, "png", _PNG_BYTES)
    md = (
        "Body before.\n\n"
        "![Figure 1: Hello World!](p3556r0-fig3-1.png)\n\n"
        "Body after.\n"
    )
    out = _rewrite_paper_image_refs(md, backend, "P3556R0")
    assert "![Figure 1: Hello World!]" not in out
    assert "<img src=\"data:image/png;base64," in out
    assert 'alt="Figure 1: Hello World!"' in out


def test_rewrite_empty_alt(backend: SqliteBackend):
    backend.write_paper_image("P1", 12, 1, "png", _PNG_BYTES)
    md = "![](p1-fig12-1.png)"
    out = _rewrite_paper_image_refs(md, backend, "P1")
    assert "<img src=\"data:image/png;base64," in out
    assert 'alt=""' in out


def test_rewrite_escapes_html_special_chars_in_alt(backend: SqliteBackend):
    """Quote, ampersand, and angle brackets must not break out of the
    attribute or inject HTML."""
    backend.write_paper_image("P1", 1, 1, "png", _PNG_BYTES)
    md = '![<b>"quoted" & x</b>](p1-fig1-1.png)'
    out = _rewrite_paper_image_refs(md, backend, "P1")
    # Quote, ampersand, and angle brackets must be escaped in the attr.
    assert "&lt;b&gt;" in out
    assert "&quot;quoted&quot;" in out
    assert "&amp; x" in out
    # The raw < should not appear inside the alt attr value.
    assert 'alt="<b>"' not in out


def test_rewrite_leaves_other_paper_refs_alone(backend: SqliteBackend):
    """Filenames whose pid does not match the current paper survive the
    rewrite (and get stripped by scrivener downstream, same as today -
    no regression on cross-paper refs)."""
    backend.write_paper_image("P1", 1, 1, "png", _PNG_BYTES)
    md = "![ours](p1-fig1-1.png)\n\n![not ours](p9999r0-fig5-1.png)"
    out = _rewrite_paper_image_refs(md, backend, "P1")
    # Our paper inlined as HTML
    assert "<img src=\"data:image/png" in out
    assert 'alt="ours"' in out
    # The other paper's ref is untouched markdown
    assert "![not ours](p9999r0-fig5-1.png)" in out


def test_rewrite_leaves_non_paper_refs_alone(backend: SqliteBackend):
    """A ref to ``foo.png`` (not the paperstore convention) is left as
    markdown so scrivener handles it (and strips it - same as today)."""
    md = "![logo](some-other-logo.png)"
    out = _rewrite_paper_image_refs(md, backend, "P1")
    assert out == md


def test_rewrite_when_image_file_missing(backend: SqliteBackend):
    """A ref to a paperstore-shaped filename that doesn't exist on disk
    leaves the markdown alone (no spurious empty data URL)."""
    md = "![ghost](p1-fig1-1.png)"
    out = _rewrite_paper_image_refs(md, backend, "P1")
    assert out == md


def test_rewrite_handles_multiple_refs(backend: SqliteBackend):
    backend.write_paper_image("P1", 0, 1, "png", _PNG_BYTES)
    backend.write_paper_image("P1", 0, 2, "jpeg", _PNG_BYTES)
    md = (
        "![one](p1-fig0-1.png)\n\nmid\n\n![two](p1-fig0-2.jpeg)\n"
    )
    out = _rewrite_paper_image_refs(md, backend, "P1")
    assert out.count("<img src=\"data:image/png;base64,") == 1
    assert out.count("<img src=\"data:image/jpeg;base64,") == 1
    assert 'alt="one"' in out
    assert 'alt="two"' in out


def test_rewrite_pid_case_insensitive(backend: SqliteBackend):
    """Caller can pass the pid in any case; the filename match is on
    the lowercased form."""
    backend.write_paper_image("P3556R0", 3, 1, "png", _PNG_BYTES)
    md = "![cap](p3556r0-fig3-1.png)"
    out = _rewrite_paper_image_refs(md, backend, "P3556R0")
    assert "<img src=\"data:image/png;base64," in out


# ---- _render_blockquote_tables ----------------------------------------------


def test_bq_table_converted_to_html():
    """The whole point: a pipe table inside a blockquote becomes a raw
    HTML <table> (still ``> ``-prefixed) so scrivener passes it through
    instead of collapsing the rows into one literal paragraph."""
    md = (
        "> **POLL**: Forward to LWG.\n"
        ">\n"
        "> | SF | F | N | SA | SA |\n"
        "> | --- | --- | --- | --- | --- |\n"
        "> | 7 | 13 | 1 | 0 | 1 |\n"
    )
    out = _render_blockquote_tables(md)
    assert "> <table>" in out
    assert "> <tr><th>SF</th><th>F</th><th>N</th><th>SA</th><th>SA</th></tr>" in out
    assert "> <tr><td>7</td><td>13</td><td>1</td><td>0</td><td>1</td></tr>" in out
    assert "> </table>" in out
    assert "| SF |" not in out
    # Non-table blockquote lines survive untouched.
    assert "> **POLL**: Forward to LWG.\n" in out


def test_top_level_table_untouched():
    """Tables outside blockquotes render natively in scrivener and must
    not be rewritten."""
    md = (
        "| SF | F |\n"
        "| --- | --- |\n"
        "| 7 | 13 |\n"
    )
    assert _render_blockquote_tables(md) == md


def test_bq_pipe_lines_without_separator_untouched():
    """Pipe-ish lines that are not a GFM table (no separator row) stay
    literal - no phantom tables."""
    md = (
        "> | just some | text |\n"
        "> | more | text |\n"
    )
    assert _render_blockquote_tables(md) == md


def test_bq_separator_column_mismatch_untouched():
    """GFM requires separator and header column counts to match;
    a mismatch means the block is not a table."""
    md = (
        "> | a | b | c |\n"
        "> | --- | --- |\n"
        "> | 1 | 2 | 3 |\n"
    )
    assert _render_blockquote_tables(md) == md


def test_bq_table_cells_html_escaped():
    """Cell payloads like ``<=>`` must not inject markup."""
    md = (
        "> | op | result |\n"
        "> | --- | --- |\n"
        "> | <=> | a & b |\n"
    )
    out = _render_blockquote_tables(md)
    assert "<td>&lt;=&gt;</td>" in out
    assert "<td>a &amp; b</td>" in out


def test_bq_table_escaped_pipe_in_cell():
    r"""``\|`` inside a cell is a literal pipe, not a cell boundary."""
    md = (
        "> | expr | desc |\n"
        "> | --- | --- |\n"
        r"> | a \| b | or |" + "\n"
    )
    out = _render_blockquote_tables(md)
    assert "<td>a | b</td>" in out
    assert "<td>or</td>" in out


def test_bq_table_ragged_rows_normalized():
    """Data rows are padded/truncated to the header width (GFM behavior)."""
    md = (
        "> | a | b |\n"
        "> | --- | --- |\n"
        "> | 1 |\n"
        "> | 1 | 2 | 3 |\n"
    )
    out = _render_blockquote_tables(md)
    assert "<tr><td>1</td><td></td></tr>" in out
    assert "<tr><td>1</td><td>2</td></tr>" in out
    assert "<td>3</td>" not in out


def test_bq_header_only_table_no_tbody():
    """Header + separator with no data rows emits no empty <tbody>."""
    md = (
        "> | a | b |\n"
        "> | --- | --- |\n"
    )
    out = _render_blockquote_tables(md)
    assert "<thead>" in out
    assert "<tbody>" not in out


def test_fenced_code_block_untouched():
    """A markdown example inside a fenced code block (with or without
    blockquote prefix on the fence) is a code sample, not a table."""
    md = (
        "```md\n"
        "> | SF | F |\n"
        "> | --- | --- |\n"
        "> | 7 | 13 |\n"
        "```\n"
        "> ```\n"
        "> | a | b |\n"
        "> | --- | --- |\n"
        "> ```\n"
    )
    assert _render_blockquote_tables(md) == md


def test_bq_nested_quote_row_not_absorbed():
    """A pipe row at deeper quote nesting ends the run instead of being
    pulled into the outer table at the wrong nesting level."""
    md = (
        "> | a | b |\n"
        "> | --- | --- |\n"
        "> | 1 | 2 |\n"
        "> > | quoted | row |\n"
    )
    out = _render_blockquote_tables(md)
    assert "<tr><td>1</td><td>2</td></tr>" in out
    assert "> > | quoted | row |" in out
    assert "<td>quoted</td>" not in out


def test_image_ref_in_bq_table_cell_inlined(backend: SqliteBackend):
    """Pass ordering: the table pass html-escapes cell text, so it must
    run before the image pass. An image ref inside a cell survives the
    escape (no markup chars) and is then inlined as a raw <img> by the
    image pass instead of becoming a visible base64 blob."""
    backend.write_paper_image("P1", 1, 1, "png", _PNG_BYTES)
    md = (
        "> | desc | fig |\n"
        "> | --- | --- |\n"
        "> | one | ![fig](p1-fig1-1.png) |\n"
    )
    out = render_markdown(md, backend=backend, pid="P1")
    assert '<td><img src="data:image/png;base64,' in out
    assert "&lt;img" not in out


# ---- _fix_split_ol_numbering -------------------------------------------------


def test_split_ol_gets_start_attribute():
    """Scrivener splits an <ol> around a table without start= on the
    continuation; the post-pass adds it so numbering continues."""
    html_text = (
        "<ol><li>a</li><li>b</li></ol>"
        "<table><tr><td>x</td></tr></table>"
        "<ol><li>c</li></ol>"
    )
    out = _fix_split_ol_numbering(html_text)
    assert '<ol start="3"><li>c</li></ol>' in out


def test_split_ol_respects_existing_start():
    """A preceding <ol start=N> shifts the continuation's base."""
    html_text = (
        '<ol start="5"><li>a</li></ol>'
        "<table><tr><td>x</td></tr></table>"
        "<ol><li>b</li></ol>"
    )
    out = _fix_split_ol_numbering(html_text)
    assert '<ol start="6"><li>b</li></ol>' in out


def test_split_ol_chained_splits_accumulate():
    """Two tables splitting the same list: the second continuation must
    build on the start= added to the first, not restart from the
    original fragment (iterative replacement, not one re.sub pass)."""
    html_text = (
        "<ol><li>a</li><li>b</li></ol>"
        "<table><tr><td>x</td></tr></table>"
        "<ol><li>c</li></ol>"
        "<table><tr><td>y</td></tr></table>"
        "<ol><li>d</li></ol>"
    )
    out = _fix_split_ol_numbering(html_text)
    assert '<ol start="3"><li>c</li></ol>' in out
    assert '<ol start="4"><li>d</li></ol>' in out


def test_table_between_unrelated_lists_untouched():
    """No preceding <ol> before the match means nothing to continue;
    the fragment stays unchanged."""
    html_text = (
        "</ol><table><tr><td>x</td></tr></table><ol><li>a</li></ol>"
    )
    out = _fix_split_ol_numbering(html_text)
    assert out == html_text


def test_html_without_split_ol_unchanged():
    html_text = "<ol><li>a</li></ol><p>text</p><table></table>"
    assert _fix_split_ol_numbering(html_text) == html_text


# ---- cache invalidation -----------------------------------------------------


def test_image_data_url_invalidates_when_mtime_changes(
    backend: SqliteBackend, tmp_path: Path,
):
    """A re-convert that overwrites the image file with new bytes must
    cause the next preview render to return the new base64, not the
    cached old one.
    """
    backend.write_paper_image("P1", 1, 1, "png", _PNG_BYTES)
    path = backend.get_paper_image_path("P1", 1, 1, "png")
    first = _image_data_url(path)
    assert first is not None
    assert base64.b64encode(_PNG_BYTES).decode() in first

    # Overwrite with different bytes, bumping mtime past the cache key.
    new_bytes = _PNG_BYTES + b"\x00" * 16
    path.write_bytes(new_bytes)
    import os
    new_mtime = path.stat().st_mtime + 1.0
    os.utime(path, (new_mtime, new_mtime))

    second = _image_data_url(path)
    assert second is not None
    assert second != first
    assert base64.b64encode(new_bytes).decode() in second


def test_image_data_url_returns_none_for_missing_file(tmp_path: Path):
    missing = tmp_path / "no-such-file.png"
    assert _image_data_url(missing) is None


# ---- caption-duplication gate (plan section 6) ------------------------------


def test_rewrite_produces_bare_img_not_figure(backend: SqliteBackend):
    """Caption-duplication gate. The rewrite emits a bare ``<img>``
    tag, NOT a ``<figure><figcaption>`` wrap.

    The "keep both" decision in plan section 1.2 (caption appears as
    image alt text AND as a body paragraph) relies on ``<img alt>``
    being invisible to the browser - the user sees the caption
    exactly once via the body paragraph. A ``<figure><figcaption>``
    wrap would render the alt text visibly below the image,
    duplicating the body paragraph in the rendered output and
    forcing dedupe-at-emit instead.

    Verified once visually for P3556R0 ("Figure 1: Hello World!"
    rendered once in the preview iframe). This test pins the
    invariant against accidental regressions.
    """
    backend.write_paper_image("P1", 3, 1, "png", _PNG_BYTES)
    md = "![Figure 1: Hello World!](p1-fig3-1.png)"
    out = _rewrite_paper_image_refs(md, backend, "P1")
    assert "<figure" not in out
    assert "<figcaption" not in out
    assert out.startswith('<img src="data:image/png;base64,')
    assert 'alt="Figure 1: Hello World!"' in out
