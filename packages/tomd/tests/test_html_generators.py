
"""Per-generator integration tests for the HTML converter."""
from pathlib import Path

from tomd.lib.html.extract import (
    parse_html, detect_generator, extract_metadata, strip_boilerplate,
)
from tomd.lib.html.render import render_body


FIXTURES = Path(__file__).parent / "fixtures" / "html"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ---- Bikeshed -----------------------------------------------------------

def test_bikeshed_detection():
    soup = parse_html(_load("bikeshed_sample.html"))
    assert detect_generator(soup) == "bikeshed"


def test_bikeshed_metadata_extraction():
    soup = parse_html(_load("bikeshed_sample.html"))
    meta = extract_metadata(soup, "bikeshed")
    assert meta.get("document") == "P9999R0"
    assert meta.get("title") == "Test Bikeshed Paper"
    assert meta.get("date") == "2026-03-15"
    assert meta.get("audience") == "SG1"
    reply_to = meta.get("reply-to", [])
    assert any("editor@example.com" in entry for entry in reply_to)


def test_bikeshed_boilerplate_stripped():
    soup = parse_html(_load("bikeshed_sample.html"))
    strip_boilerplate(soup, "bikeshed")
    # h1.p-name and data-fill-with divs removed.
    assert soup.find("h1", class_="p-name") is None


def test_bikeshed_body_renders():
    soup = parse_html(_load("bikeshed_sample.html"))
    strip_boilerplate(soup, "bikeshed")
    md = render_body(soup, "bikeshed")
    assert "## Introduction" in md
    assert "Body paragraph content." in md


# ---- HackMD -------------------------------------------------------------

def test_hackmd_detection():
    soup = parse_html(_load("hackmd_sample.html"))
    assert detect_generator(soup) == "hackmd"


def test_hackmd_metadata_via_generic_fallback():
    """HackMD has no specific extractor; metadata comes through the generic path."""
    soup = parse_html(_load("hackmd_sample.html"))
    meta = extract_metadata(soup, "hackmd")
    # detect_generator returned "hackmd" but extract_metadata dispatches by argument;
    # passing "hackmd" falls through to _extract_generic_metadata.
    assert meta.get("title") == "P9999R0: Test HackMD Paper"
    # The generic table scan should pick up document/audience from the <table>.
    assert meta.get("document") == "P9999R0"
    assert meta.get("audience") == "SG1"


def test_hackmd_body_renders():
    soup = parse_html(_load("hackmd_sample.html"))
    strip_boilerplate(soup, "hackmd")
    md = render_body(soup, "hackmd")
    assert "## Introduction" in md
    assert "Body paragraph." in md


# ---- Hand-written (address form) ----------------------------------------

def test_handwritten_address_detection():
    soup = parse_html(_load("handwritten_address_sample.html"))
    assert detect_generator(soup) == "hand-written"


def test_handwritten_address_metadata():
    soup = parse_html(_load("handwritten_address_sample.html"))
    meta = extract_metadata(soup, "hand-written")
    assert meta.get("document") == "P9999R0"
    assert meta.get("date") == "2026-03-15"
    assert meta.get("audience") == "SG1"
    reply_to = meta.get("reply-to", [])
    assert any("alice@example.com" in entry for entry in reply_to)


def test_handwritten_address_boilerplate_stripped():
    soup = parse_html(_load("handwritten_address_sample.html"))
    strip_boilerplate(soup, "hand-written")
    # <address> removed.
    assert soup.find("address") is None


def test_handwritten_address_body_renders():
    soup = parse_html(_load("handwritten_address_sample.html"))
    strip_boilerplate(soup, "hand-written")
    md = render_body(soup, "hand-written")
    assert "## Introduction" in md


# ---- Hand-written (table.header form) -----------------------------------

def test_handwritten_table_metadata():
    soup = parse_html(_load("handwritten_table_sample.html"))
    meta = extract_metadata(soup, "hand-written")
    assert meta.get("document") == "P9998R0"
    assert meta.get("date") == "2026-02-01"
    assert meta.get("audience") == "EWG"
    reply_to = meta.get("reply-to", [])
    assert any("bob@example.com" in entry for entry in reply_to)


def test_handwritten_table_boilerplate_stripped():
    soup = parse_html(_load("handwritten_table_sample.html"))
    strip_boilerplate(soup, "hand-written")
    assert soup.find("table", class_="header") is None


# ---- Hatemplate (eelis/draft) -------------------------------------------

def test_hatemplate_detection():
    soup = parse_html(_load("hatemplate_sample.html"))
    assert detect_generator(soup) == "hatemplate"


def test_hatemplate_metadata_deobfuscates_author_email():
    soup = parse_html(_load("hatemplate_sample.html"))
    meta = extract_metadata(soup, "hatemplate")
    assert meta.get("document") == "P9999R0"
    assert meta.get("date") == "2026-03-15"
    # Audience is the subgroup mailing-list label, not an author.
    assert meta.get("audience") == "Library Evolution"
    reply_to = meta.get("reply-to", [])
    assert reply_to == ["Test Author <author@example.com>"]
    # The obfuscated mailto decoy must never reach the front matter.
    assert not any("YOU-NEED-JAVASCRIPT" in entry for entry in reply_to)


def test_hatemplate_boilerplate_strips_chrome():
    soup = parse_html(_load("hatemplate_sample.html"))
    strip_boilerplate(soup, "hatemplate")
    assert soup.find("nav") is None
    assert soup.find("div", id="hide") is None
    assert soup.find("div", class_="marginalizedparent") is None
    assert soup.find("div", class_="sourceLinkParent") is None
    # The title <h1> is stripped so it does not inflate the heading-level
    # baseline used by _normalize_heading_levels.
    assert soup.find("h1") is None


def test_hatemplate_heading_levels_not_offset_by_title_h1():
    """Body headings keep their source level: stripping the title <h1> keeps
    it out of the minimum-heading calculation, so body headings are not
    offset by +1 (### staying ###, not becoming ####)."""
    soup = parse_html(_load("hatemplate_sample.html"))
    strip_boilerplate(soup, "hatemplate")
    md = render_body(soup, "hatemplate")
    assert "### 1.1 Header synopsis [test.syn]" in md
    assert "##### " not in md


def test_hatemplate_wording_flows_as_prose():
    soup = parse_html(_load("hatemplate_sample.html"))
    strip_boilerplate(soup, "hatemplate")
    md = render_body(soup, "hatemplate")
    # Sentences flow into one paragraph, not one fragment per line.
    assert "A widget is a kind of container. Storage is managed in *element blocks*." in md
    # No bare paragraph-anchor "#", no margin glyphs, no nav glyph.
    assert not any(line.strip() == "#" for line in md.splitlines())
    assert "🔗" not in md
    assert "◀" not in md
    # Itemized sub-paragraphs flow with a separating space (no "limit.When").
    assert "the maximum limit. When limits are not specified" in md


def test_hatemplate_code_is_fenced():
    soup = parse_html(_load("hatemplate_sample.html"))
    strip_boilerplate(soup, "hatemplate")
    md = render_body(soup, "hatemplate")
    # Synopsis span.codeblock and the itemdecl code.itemdeclcode both fence.
    assert "```cpp\nnamespace std {\n  constexpr void f() noexcept;\n}\n```" in md
    assert "```cpp\nconstexpr void f() noexcept;\n```" in md


def test_hatemplate_no_obfuscated_email_in_body():
    soup = parse_html(_load("hatemplate_sample.html"))
    strip_boilerplate(soup, "hatemplate")
    md = render_body(soup, "hatemplate")
    assert "YOU-NEED-JAVASCRIPT" not in md
    assert "Number:" not in md