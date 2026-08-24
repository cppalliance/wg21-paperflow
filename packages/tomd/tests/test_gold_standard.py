# Copyright 2026 SG
# Distributed under the Boost Software License, Version 1.0.
# https://www.boost.org/LICENSE_1_0.txt

"""Gold-standard structural validation tests.

D4036 (general structure) and P2583R3 (wording sections) serve as
reference fixtures for what correct WG21 markdown looks like.
These tests validate structural properties, not conversion output.
"""

import re
from pathlib import Path

import pytest

from tomd.lib import parse_front_matter

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_D4036 = _FIXTURES / "d4036-gold-standard.md"
_P2583R3_PDF = _FIXTURES / "p2583r3-gold-standard.pdf"


@pytest.fixture
def d4036_md():
    return _D4036.read_text(encoding="utf-8")


@pytest.fixture
def d4036_fm(d4036_md):
    return parse_front_matter(d4036_md)


class TestD4036FrontMatter:
    def test_has_title(self, d4036_fm):
        assert "title" in d4036_fm
        assert d4036_fm["title"]

    def test_has_document(self, d4036_fm):
        assert "document" in d4036_fm
        assert re.match(r"[PD]\d+R\d+", d4036_fm["document"])

    def test_has_date(self, d4036_fm):
        assert "date" in d4036_fm
        assert re.match(r"\d{4}-\d{2}-\d{2}", d4036_fm["date"])

    def test_has_intent(self, d4036_fm):
        assert "intent" in d4036_fm
        assert d4036_fm["intent"] in ("info", "ask")

    def test_has_audience(self, d4036_fm):
        assert "audience" in d4036_fm

    def test_has_reply_to(self, d4036_fm):
        assert "reply-to" in d4036_fm
        assert isinstance(d4036_fm["reply-to"], list)
        assert len(d4036_fm["reply-to"]) >= 1


class TestD4036Structure:
    def test_no_h1_in_body(self, d4036_md):
        fm_end = d4036_md.find("---", 4)
        body = d4036_md[fm_end + 3:]
        h1_lines = [l for l in body.split("\n")
                     if l.strip().startswith("# ") and not l.strip().startswith("## ")]
        assert h1_lines == [], f"Body contains H1: {h1_lines}"

    def test_headings_start_at_h2(self, d4036_md):
        fm_end = d4036_md.find("---", 4)
        body = d4036_md[fm_end + 3:]
        headings = [l.strip() for l in body.split("\n") if l.strip().startswith("#")]
        assert headings, "No headings found"
        assert headings[0].startswith("## "), f"First heading is not H2: {headings[0]}"

    def test_has_code_blocks(self, d4036_md):
        assert "```" in d4036_md

    def test_has_tables(self, d4036_md):
        assert "| " in d4036_md and " |" in d4036_md

    def test_has_references(self, d4036_md):
        assert "## References" in d4036_md or "## Bibliography" in d4036_md

    def test_heading_hierarchy(self, d4036_md):
        """Verify heading levels never skip (e.g. H2 -> H4 without H3)."""
        fm_end = d4036_md.find("---", 4)
        body = d4036_md[fm_end + 3:]
        prev_level = 1
        for line in body.split("\n"):
            m = re.match(r"^(#{2,6})\s", line)
            if m:
                level = len(m.group(1))
                assert level <= prev_level + 1, (
                    f"Heading skip: H{prev_level} -> H{level} at '{line.strip()[:50]}'"
                )
                prev_level = level


@pytest.fixture
def p2583r3_md():
    from tomd.lib.pdf import run_pipeline
    if not _P2583R3_PDF.is_file():
        pytest.skip("P2583R3 PDF fixture not available")
    md = run_pipeline(_P2583R3_PDF).md
    return md


class TestP2583R3Wording:
    """Validate wording section handling on P2583R3 (proposed wording paper)."""

    def test_emits_no_wording_divs(self, p2583r3_md):
        # The Pandoc fenced div is retired: it said nothing the section's
        # own shape and inline tags do not, and it was noise in the output.
        assert ":::" not in p2583r3_md

    def test_has_ins_del_tags(self, p2583r3_md):
        assert "<ins>" in p2583r3_md or "<del>" in p2583r3_md, (
            "Wording paper should preserve insertion/deletion annotations"
        )

    def test_wording_tags_are_balanced(self, p2583r3_md):
        for tag in ("ins", "del"):
            opens = len(re.findall(rf"<{tag}>", p2583r3_md))
            closes = len(re.findall(rf"</{tag}>", p2583r3_md))
            assert opens == closes, (
                f"Mismatched <{tag}> tags: {opens} opens vs {closes} closes"
            )

    def test_has_front_matter(self, p2583r3_md):
        assert p2583r3_md.startswith("---")
        fm = parse_front_matter(p2583r3_md)
        assert "title" in fm
        assert "document" in fm

    def test_no_h1_in_body(self, p2583r3_md):
        fm_end = p2583r3_md.find("---", 4)
        body = p2583r3_md[fm_end + 3:]
        h1_lines = [l for l in body.split("\n")
                     if l.strip().startswith("# ") and not l.strip().startswith("## ")]
        assert h1_lines == [], f"Body contains H1: {h1_lines}"
