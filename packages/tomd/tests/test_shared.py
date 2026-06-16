"""Tests for lib.shared utilities."""

from tomd.lib.shared import strip_leading_h1


class TestStripLeadingH1:
    def test_strips_h1_title_duplicate(self):
        out = strip_leading_h1("# My Paper\n\nBody.", "My Paper")
        assert not out.lstrip().startswith("#")
        assert "Body." in out

    def test_strips_h1_first_content_when_no_title(self):
        out = strip_leading_h1("# Anything\n\nBody.", "")
        assert not out.lstrip().startswith("#")

    def test_leaves_non_matching_h1(self):
        out = strip_leading_h1("# Other\n\nBody.", "My Paper")
        assert out.lstrip().startswith("# Other")

    def test_default_does_not_strip_h2(self):
        # PDF path keeps H1-only behavior: an H2 title-dup is left alone.
        out = strip_leading_h1("## My Paper\n\nBody.", "My Paper")
        assert out.lstrip().startswith("## My Paper")

    def test_max_level_2_strips_h2_title_duplicate(self):
        # HTML path: body headings start at H2, so the title-dup arrives as H2.
        out = strip_leading_h1("## My Paper\n\nBody.", "My Paper", max_level=2)
        assert not out.lstrip().startswith("#")
        assert "Body." in out

    def test_max_level_2_leaves_deeper_heading(self):
        out = strip_leading_h1("### My Paper\n\nBody.", "My Paper", max_level=2)
        assert out.lstrip().startswith("### My Paper")
