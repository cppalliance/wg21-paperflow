#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

import pytest

from whisker.reference import REFERENCE_ENGINES, reference_markdown


class _Backend:
    """Minimal stand-in; get_source_path must never be reached on a bad engine."""

    def get_source_path(self, pid):
        raise AssertionError("engine must be validated before touching the backend")


def test_unknown_engine_raises_before_backend_access():
    with pytest.raises(ValueError, match="unknown reference engine"):
        reference_markdown("P1", _Backend(), engine="nope")


def test_default_engine_is_known():
    assert "markitdown" in REFERENCE_ENGINES


def test_reference_markdown_converts_a_real_source(tmp_path):
    # Convert a tiny HTML file through the real oracle to prove the wiring:
    # backend.get_source_path -> markitdown -> Markdown text.
    src = tmp_path / "p9999r0.html"
    src.write_text(
        "<html><body><h1>Title</h1><p>Hello world body text.</p></body></html>",
        encoding="utf-8",
    )

    class _FileBackend:
        def get_source_path(self, pid):
            return src

    md = reference_markdown("P9999R0", _FileBackend(), engine="markitdown")
    assert "Hello world body text." in md
