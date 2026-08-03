
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


def test_handwritten_title_h1_stripped():
    """The title <h1> is removed so it does not inflate the heading-level
    baseline used by _normalize_heading_levels (issue #300)."""
    soup = parse_html(_load("handwritten_address_sample.html"))
    strip_boilerplate(soup, "hand-written")
    assert soup.find("h1") is None


def test_handwritten_heading_levels_not_offset_by_title_h1():
    """Body headings keep their source level. With the title <h1> stripped it
    stays out of the minimum-heading calculation, so a body <h2> renders as
    `## ` and is not offset to `### ` (issue #300, the p4020r0 defect).
    Asserted on whole lines, not substrings: `### Introduction` also contains
    the string `## Introduction`."""
    soup = parse_html(_load("handwritten_address_sample.html"))
    strip_boilerplate(soup, "hand-written")
    md = render_body(soup, "hand-written")
    lines = md.splitlines()
    assert "## Introduction" in lines
    assert "### Introduction" not in lines
    # The title text is not duplicated into the body as a heading.
    assert not any("Test Handwritten Paper" in ln for ln in lines)


def test_handwritten_title_h1_in_header_table_preserves_body_h1():
    """The title <h1> nested inside the removed table.header must not cause the
    first *body* <h1> to be deleted (reviewer sabriguenes on #300).

    strip_boilerplate previously called ``soup.find("h1")`` *after* decomposing
    ``table.header``. When the title <h1> lived inside that table, the fresh
    lookup matched and deleted the first body <h1> ("Introduction") instead."""
    html = (
        "<html><body>"
        "<table class='header'>"
        "<tr><td><h1>Real Paper Title</h1></td></tr>"
        "<tr><th>Document Number:</th><td>P9999R0</td></tr>"
        "</table>"
        "<h1>Introduction</h1>"
        "<p>Body paragraph.</p>"
        "</body></html>"
    )
    soup = parse_html(html)
    meta = extract_metadata(soup, "hand-written")
    assert meta.get("title") == "Real Paper Title"
    strip_boilerplate(soup, "hand-written")
    md = render_body(soup, "hand-written")
    lines = md.splitlines()
    # The body heading survives (shifted to H2 by _normalize_heading_levels).
    assert "## Introduction" in lines
    assert "Body paragraph." in md
    # The title h1 is not left in the body.
    assert not any("Real Paper Title" in ln for ln in lines)


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


def test_hatemplate_title_h1_in_nav_preserves_body_h1():
    """The title <h1> nested inside the removed <nav> must not cause the first
    *body* <h1> to be deleted (reviewer sabriguenes on #300).

    Same latent bug as the hand-written branch: strip_boilerplate called
    ``soup.find("h1")`` *after* decomposing <nav>, so a title <h1> inside <nav>
    left the lookup matching and deleting the first body <h1> ("Overview")."""
    html = (
        "<html><head>"
        "<meta name='generator' content='hatemplate/v2'>"
        "</head><body>"
        "<nav><div class='paper-info'>"
        "<span class='key'>Number:</span><span>P9999R0</span>"
        "</div>"
        "<h1>Real Hatemplate Title</h1>"
        "</nav>"
        "<article>"
        "<h1>Overview</h1>"
        "<p>Body paragraph.</p>"
        "</article>"
        "</body></html>"
    )
    soup = parse_html(html)
    meta = extract_metadata(soup, "hatemplate")
    assert meta.get("title") == "Real Hatemplate Title"
    strip_boilerplate(soup, "hatemplate")
    md = render_body(soup, "hatemplate")
    lines = md.splitlines()
    # The body heading survives (shifted to H2 by _normalize_heading_levels).
    assert "## Overview" in lines
    assert "Body paragraph." in md
    assert not any("Real Hatemplate Title" in ln for ln in lines)
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