"""Tests for lib.pdf.emit."""

from conftest import make_section, make_line, make_span
from tomd.lib.pdf.types import SectionKind, Confidence, Span, Line
from tomd.lib.pdf.emit import emit_markdown, emit_prompts, _render_wording_line


def test_emit_heading():
    sec = make_section("Introduction", kind=SectionKind.HEADING,
                       heading_level=2)
    md = emit_markdown({}, [sec])
    assert "## Introduction" in md


def test_emit_heading_joins_all_lines():
    """A heading split across lines (number / title / clause tag laid out
    with wide x-gaps on one visual line) renders as a single heading, not
    just the first line (the bare section number)."""
    sec = make_section(
        "1\nScope\n[scope]", kind=SectionKind.HEADING, heading_level=2,
        lines=[make_line(["1"]), make_line(["Scope"]), make_line(["[scope]"])],
    )
    md = emit_markdown({}, [sec])
    assert "## 1 Scope [scope]" in md


def test_emit_heading_dedupes_overprinted_lines():
    """A heading the PDF overprints several times at the same position (faux
    bold) renders once, not repeated."""
    sec = make_section(
        "Abstract\nAbstract\nAbstract", kind=SectionKind.HEADING,
        heading_level=2,
        lines=[make_line(["Abstract"]), make_line(["Abstract"]),
               make_line(["Abstract"])],
    )
    md = emit_markdown({}, [sec])
    assert "## Abstract\n" in md or md.strip().endswith("## Abstract")
    assert "Abstract Abstract" not in md


def test_emit_paragraph_unwrapped():
    sec = make_section("Hello world")
    md = emit_markdown({}, [sec])
    assert "Hello world" in md


def test_emit_code_fenced():
    sec = make_section("int main() {}", kind=SectionKind.CODE,
                       fence_lang="cpp")
    sec.lines[0].spans[0].monospace = True
    md = emit_markdown({}, [sec])
    assert "```cpp" in md
    assert "int main()" in md


def test_emit_uncertain_has_comment():
    sec = make_section("uncertain text", kind=SectionKind.UNCERTAIN,
                       confidence=Confidence.UNCERTAIN)
    sec.mupdf_text = "uncertain text"
    sec.spatial_text = "different text"
    md = emit_markdown({}, [sec])
    assert "<!-- tomd:uncertain:" in md


def test_emit_prompts_none_when_no_uncertain():
    sec = make_section("hello")
    assert emit_prompts([sec]) is None


def test_emit_prompts_returns_one_self_contained_prompt_per_region():
    sec_a = make_section(
        "uncertain a", kind=SectionKind.UNCERTAIN, confidence=Confidence.UNCERTAIN
    )
    sec_a.mupdf_text = "mupdf a"
    sec_a.spatial_text = "spatial a"
    sec_a.page_num = 3
    sec_b = make_section(
        "uncertain b", kind=SectionKind.UNCERTAIN, confidence=Confidence.UNCERTAIN
    )
    sec_b.mupdf_text = "mupdf b"
    sec_b.spatial_text = "spatial b"
    sec_b.page_num = 7

    result = emit_prompts([sec_a, sec_b])
    assert isinstance(result, list)
    assert len(result) == 2

    for r in result:
        assert "MuPDF extraction" in r
        assert "Spatial extraction" in r
        assert "CRITICAL" in r
        assert "verbatim" in r

    assert "page 3" in result[0]
    assert "mupdf a" in result[0]
    assert "page 7" in result[1]
    assert "mupdf b" in result[1]


def test_front_matter_title_quoted():
    md = emit_markdown({"title": "My Paper: A Study"}, [])
    assert 'title: "My Paper: A Study"' in md


def test_front_matter_reply_to_list():
    meta = {"reply-to": ["Alice <a@b.com>", "Bob <c@d.com>"]}
    md = emit_markdown(meta, [])
    assert "reply-to:" in md
    assert '"Alice <a@b.com>"' in md
    assert '"Bob <c@d.com>"' in md


def test_front_matter_special_chars_quoted():
    from tomd.lib import format_front_matter
    result = format_front_matter({"document": "P1234R0", "audience": "SG1: Concurrency"})
    assert '"SG1: Concurrency"' in result


def test_front_matter_canonical_order():
    """All six known keys come out in strict canonical order regardless of input order."""
    from tomd.lib import format_front_matter
    meta = {
        "reply-to": ["Alice <a@x>"],
        "audience": "LEWG",
        "intent": "info",
        "date": "2026-04-28",
        "document": "P9999R0",
        "title": "Canonical Test",
    }
    result = format_front_matter(meta)
    lines = result.splitlines()
    keys = [l.split(":")[0] for l in lines if l and not l.startswith((" ", "\t", "-")) and l != "---"]
    assert keys[0] == "title"
    assert "reply-to" in keys
    assert keys[-1] == "reply-to", "reply-to must always be last"
    assert keys.index("title") < keys.index("document") < keys.index("date")
    assert keys.index("date") < keys.index("intent") < keys.index("audience")
    assert 'title: "Canonical Test"' in result
    assert "document: P9999R0" in result
    assert "revision" not in result


def test_front_matter_intent_position():
    """`intent` lands between `date` and `audience`."""
    from tomd.lib import format_front_matter
    result = format_front_matter({
        "title": "T",
        "date": "2026-04-28",
        "intent": "ask",
        "audience": "LWG",
    })
    title_pos = result.index("title:")
    date_pos = result.index("date:")
    intent_pos = result.index("intent:")
    audience_pos = result.index("audience:")
    assert title_pos < date_pos < intent_pos < audience_pos


def test_front_matter_skips_missing_keys():
    """Missing keys produce no placeholders and no blank lines."""
    from tomd.lib import format_front_matter
    result = format_front_matter({"title": "T", "document": "P1R0"})
    assert 'title: "T"' in result
    assert "document: P1R0" in result
    assert "intent" not in result


def test_front_matter_unknown_keys_keep_reply_to_last():
    """Unknown keys land after canonical scalars; reply-to stays last."""
    from tomd.lib import format_front_matter
    result = format_front_matter({
        "title": "T",
        "audience": "LWG",
        "reply-to": ["X <x@y>"],
        "paper-type": "proposal",
    })
    audience_pos = result.index("audience:")
    paper_type_pos = result.index("paper-type:")
    reply_to_pos = result.index("reply-to:")
    assert audience_pos < paper_type_pos < reply_to_pos


def test_emit_list():
    span = make_span("- item one")
    line = make_line(["- item one"])
    sec = make_section("- item one", kind=SectionKind.LIST)
    md = emit_markdown({}, [sec])
    assert "- item one" in md


def test_emit_list_top_level_bullet_uses_star():
    sec = make_section("● item", kind=SectionKind.LIST)
    md = emit_markdown({}, [sec])
    assert "* item" in md
    assert "●" not in md


def test_emit_list_nested_bullet_indented_dash():
    sec = make_section("○ nested", kind=SectionKind.LIST, indent_level=1)
    md = emit_markdown({}, [sec])
    assert "  - nested" in md


def test_emit_list_circle_glyph_not_emitted_literally():
    """U+25CB is a recognized bullet, never left as a literal glyph (issue #150)."""
    sec = make_section("○ child", kind=SectionKind.LIST, indent_level=1)
    md = emit_markdown({}, [sec])
    assert "○" not in md


def test_emit_list_deeper_nesting_indents_more():
    sec = make_section("○ deep", kind=SectionKind.LIST, indent_level=2)
    md = emit_markdown({}, [sec])
    assert "    - deep" in md


def test_emit_list_unwraps_wrapped_item():
    """A single bullet item split across PDF lines renders as one line."""
    line1 = make_line(["○ Perform a check of the value"])
    line2 = make_line(["expected."])
    sec = make_section(
        "○ Perform a check of the value\nexpected.",
        kind=SectionKind.LIST, lines=[line1, line2], indent_level=1,
    )
    md = emit_markdown({}, [sec])
    assert "  - Perform a check of the value expected." in md


def test_emit_list_multiple_clean_items_one_per_line():
    line1 = make_line(["● first"])
    line2 = make_line(["● second"])
    sec = make_section("● first\n● second",
                       kind=SectionKind.LIST, lines=[line1, line2])
    md = emit_markdown({}, [sec])
    assert "* first" in md
    assert "* second" in md


def test_emit_list_numbered_item_keeps_own_marker():
    """An item that already carries an ordinal marker keeps it, not a bullet.

    Exercises the _format_list_item branch for self-marked items directly
    rather than only through the golden files.
    """
    sec = make_section("2. The override keyword shall be added",
                       kind=SectionKind.LIST)
    md = emit_markdown({}, [sec])
    assert "2. The override keyword shall be added" in md


def test_emit_list_consecutive_numbered_items_split():
    """Successive numbered lines stay separate items (current item numbered)."""
    line1 = make_line(["1. first"])
    line2 = make_line(["2. second"])
    sec = make_section("1. first\n2. second",
                       kind=SectionKind.LIST, lines=[line1, line2])
    md = emit_markdown({}, [sec])
    assert "1. first" in md
    assert "2. second" in md


def test_emit_list_year_continuation_stays_joined():
    """A wrapped bullet continuation starting with a year does not split.

    The continuation "2017. The meeting..." matches the numbered-list
    pattern, but the open item is a bullet (not numbered), so it stays
    joined instead of opening a phantom numbered item (issue #175 review).
    """
    line1 = make_line(["● Approved at the meeting in"])
    line2 = make_line(["2017. The decision still stands."])
    sec = make_section("● Approved at the meeting in\n2017. The decision still stands.",
                       kind=SectionKind.LIST, lines=[line1, line2])
    md = emit_markdown({}, [sec])
    assert "* Approved at the meeting in 2017. The decision still stands." in md


def test_emit_list_ordinal_after_finished_bullet_stays_separate():
    """A genuine ordinal label after a completed bullet is its own item.

    Regression guard (issue #175, p1068r11): the bullet ends in terminal
    punctuation, so "d) ..." must not be absorbed as a continuation the way
    a mid-sentence wrap would be.
    """
    line1 = make_line(["● It may be considered a controversial feature."])
    line2 = make_line(["d) Constraining iterators and ranges"])
    sec = make_section(
        "● It may be considered a controversial feature.\n"
        "d) Constraining iterators and ranges",
        kind=SectionKind.LIST, lines=[line1, line2],
    )
    md = emit_markdown({}, [sec])
    assert "* It may be considered a controversial feature." in md
    assert "d) Constraining iterators and ranges" in md
    assert "feature. d)" not in md


def test_emit_table():
    from tomd.lib.pdf.types import Section
    sec = Section(
        kind=SectionKind.TABLE,
        text="",
        columns=[
            [[make_span("Header A")], [make_span("Header B")]],
            [[make_span("Cell 1")], [make_span("Cell 2")]],
        ],
    )
    md = emit_markdown({}, [sec])
    assert "Header A" in md
    assert "Header B" in md
    assert "---" in md
    assert "Cell 1" in md


def test_emit_code_comparison_html_table():
    """A CODE_COMPARISON table renders via the shared comparison markup:
    the mixed-table marker, <th> headers, and <pre><code> code cells. This is
    byte-identical to what the HTML converter emits (see lib/tables.py)."""
    from tomd.lib.pdf.types import Section
    sec = Section(
        kind=SectionKind.TABLE,
        text="",
        table_strategy="html_table",
        table_kind="code_comparison",
        columns=[
            [[make_span("Before")], [make_span("After")]],
            [[make_span("int verbose();")], [make_span("int proposed();")]],
        ],
    )
    md = emit_markdown({}, [sec])
    assert "<!-- tomd:mixed-table -->" in md
    assert ">Before</th>" in md
    assert ">After</th>" in md
    assert '<pre style="margin: 0;"><code>int verbose();</code></pre>' in md
    assert '<pre style="margin: 0;"><code>int proposed();</code></pre>' in md


def test_emit_spec_table_html_no_mixed_marker():
    """Other html_table kinds (here SPEC_TABLE) render as an HTML table with
    the shared <pre><code> cells but carry no mixed-table marker: only code
    comparisons are marked, matching the HTML side."""
    from tomd.lib.pdf.types import Section
    sec = Section(
        kind=SectionKind.TABLE,
        text="",
        table_strategy="html_table",
        table_kind="spec_table",
        columns=[
            [[make_span("Expression")], [make_span("Return type")]],
            [[make_span("a.foo()")], [make_span("int")]],
        ],
    )
    md = emit_markdown({}, [sec])
    assert "<!-- tomd:mixed-table -->" not in md
    assert "<table" in md
    assert '<pre style="margin: 0;"><code>' in md


def test_emit_wording_section():
    from tomd.lib.pdf.types import Section
    span = make_span("added text")
    span.wording_role = "ins"
    line = make_line(["added text"])
    line.spans[0].wording_role = "ins"
    sec = Section(
        kind=SectionKind.WORDING_ADD,
        text="added text",
        lines=[line],
    )
    md = emit_markdown({}, [sec])
    assert ":::wording-add" in md
    assert ":::" in md


def test_emit_wording_remove_section():
    from tomd.lib.pdf.types import Section
    line = make_line(["removed text"])
    line.spans[0].wording_role = "del"
    sec = Section(
        kind=SectionKind.WORDING_REMOVE,
        text="removed text",
        lines=[line],
    )
    md = emit_markdown({}, [sec])
    assert ":::wording-remove" in md


def _ins(text: str) -> Span:
    s = Span(text=text)
    s.wording_role = "ins"
    return s


def _del(text: str) -> Span:
    s = Span(text=text)
    s.wording_role = "del"
    return s


def _plain(text: str) -> Span:
    return Span(text=text)


class TestRenderWordingLine:
    def _line(self, *spans: Span) -> Line:
        return Line(spans=list(spans))

    def test_single_ins(self):
        result = _render_wording_line(self._line(_ins("added")))
        assert result == "<ins>added</ins>"

    def test_single_del(self):
        result = _render_wording_line(self._line(_del("removed")))
        assert result == "<del>removed</del>"

    def test_adjacent_ins_merged(self):
        result = _render_wording_line(self._line(_ins("A"), _ins("B")))
        assert result == "<ins>AB</ins>"

    def test_adjacent_del_merged(self):
        result = _render_wording_line(self._line(_del("X"), _del("Y")))
        assert result == "<del>XY</del>"

    def test_whitespace_between_same_role_absorbed(self):
        result = _render_wording_line(self._line(_ins("A"), _plain(" "), _ins("B")))
        assert result == "<ins>A B</ins>"

    def test_whitespace_between_different_roles_emitted(self):
        result = _render_wording_line(self._line(_ins("A"), _plain(" "), _del("B")))
        assert result == "<ins>A</ins> <del>B</del>"

    def test_ins_then_del_not_merged(self):
        result = _render_wording_line(self._line(_ins("add"), _del("remove")))
        assert result == "<ins>add</ins><del>remove</del>"

    def test_context_between_ins_not_merged(self):
        ctx = Span(text=" context ")
        ctx.wording_role = "context"
        result = _render_wording_line(self._line(_ins("A"), ctx, _ins("B")))
        assert result == "<ins>A</ins> context <ins>B</ins>"

    def test_many_fragmented_ins_merged(self):
        """Reproduces the p3596r0 fragment: 8 separate ins → one block."""
        spans = [
            _ins("1"), _plain(" "), _ins("Specified in:"),
            _ins(" [lifetime.outside.pointer.delete]"), _plain(" "),
            _ins("For a pointer"), _plain(" "), _ins("pointing to an object."),
        ]
        result = _render_wording_line(self._line(*spans))
        assert result.count("<ins>") == 1
        assert "1 Specified in:" in result
        assert "pointing to an object." in result

    def test_leading_whitespace_preserved(self):
        result = _render_wording_line(self._line(_plain("  "), _ins("code")))
        assert result == "  <ins>code</ins>"

    def test_empty_line(self):
        assert _render_wording_line(Line(spans=[])) == ""


from tomd.lib import sanitize_metadata as _sanitize_metadata


class TestSanitizeMetadata:
    """Tests for sanitize_metadata post-processing."""

    def test_title_with_metadata_labels(self):
        md = _sanitize_metadata({
            "title": "Paper Number: P1068R11 Title: Vector API Authors: Bob"
        })
        assert md["title"] == "Vector API"

    def test_title_with_newlines(self):
        md = _sanitize_metadata({
            "title": "Unicode in the Library, Part\n1: UTF Transcoding"
        })
        assert "\n" not in md["title"]
        assert md["title"] == "Unicode in the Library, Part 1: UTF Transcoding"

    def test_title_without_labels_unchanged(self):
        md = _sanitize_metadata({"title": "A Normal Title"})
        assert md["title"] == "A Normal Title"

    def test_reply_to_double_angle_bracket(self):
        md = _sanitize_metadata({
            "reply-to": ["Mingxin Wang < <mingxwa@microsoft.com>"]
        })
        assert md["reply-to"] == ["Mingxin Wang <mingxwa@microsoft.com>"]

    def test_reply_to_non_author_filtered(self):
        md = _sanitize_metadata({
            "reply-to": [
                "Bob <bob@email.com>",
                "Target: C++26",
                "Proposed Wording for Concurrent Data",
                "Structures: Read-Copy-Update RCU",
            ]
        })
        assert md["reply-to"] == ["Bob <bob@email.com>"]

    def test_reply_to_all_filtered_removes_key(self):
        md = _sanitize_metadata({
            "reply-to": ["Target: C++26"]
        })
        assert "reply-to" not in md

    def test_no_mutation_of_input(self):
        original = {"title": "Good Title", "reply-to": ["Author <a@b.com>"]}
        result = _sanitize_metadata(original)
        assert result is not original


# -- _render_paragraph_spans: sec.text fallback when lines is empty --
# Used by the sub-caption insertion path in pipeline.py: inserted
# PARAGRAPH sections carry pre-built ``text`` (``*<escaped>*``) and
# ``lines=[]``; the fallback below renders the text verbatim,
# bypassing _render_line_spans so the *...* wrapper survives.


from tomd.lib.pdf.emit import _render_paragraph_spans, _escape_italic_text
from tomd.lib.pdf.types import Section


def test_render_paragraph_spans_falls_back_to_text_when_lines_empty():
    sec = Section(
        kind=SectionKind.PARAGRAPH,
        text="*(a) The italic caption.*",
        confidence=Confidence.MEDIUM,
        page_num=5,
        lines=[],
    )
    assert _render_paragraph_spans(sec) == "*(a) The italic caption.*"


def test_render_paragraph_spans_uses_lines_when_present():
    """Sanity guard: the fallback only fires when lines is empty.
    Existing PARAGRAPH sections with non-empty lines still go through
    the span-rendering path."""
    sec = make_section("Hello world")
    # make_section builds one line containing the text.
    out = _render_paragraph_spans(sec)
    assert "Hello world" in out


def test_emit_markdown_renders_inserted_sub_caption_paragraph():
    """End-to-end: an IMAGE section followed by a synthesised
    sub-caption PARAGRAPH (lines=[], text=*...*) renders as the
    image reference + a blank line + the italic paragraph."""
    from tomd.lib.pdf.images import ExtractedImage
    img = ExtractedImage(
        page=6, index_on_page=1, ext="png", bytes=b"",
        bbox=(86, 0, 506, 284),
        suggested_alt="Figure 1: ...",
        stored_filename="p3127r1-fig6-1.png",
        xref=0, source="vector",
        sub_captions=(("a", "(a) An undirected graph."),),
    )
    image_section = Section(
        kind=SectionKind.IMAGE, text="",
        confidence=Confidence.MEDIUM, page_num=5,
        image_ref=img,
    )
    sub_section = Section(
        kind=SectionKind.PARAGRAPH,
        text="*(a) An undirected graph.*",
        confidence=Confidence.MEDIUM,
        page_num=5,
        lines=[],
    )
    md = emit_markdown({}, [image_section, sub_section])
    assert "![Figure 1: ...](p3127r1-fig6-1.png)" in md
    assert "*(a) An undirected graph.*" in md
    # The italic caption should appear AFTER the image reference.
    assert md.index("](p3127r1-fig6-1.png)") < md.index("*(a)")


# -- _escape_italic_text: markdown-escape correctness ---------------


def test_escape_italic_text_escapes_asterisk():
    assert _escape_italic_text("a * b") == r"a \* b"


def test_escape_italic_text_escapes_underscore():
    assert _escape_italic_text("foo_bar") == r"foo\_bar"


def test_escape_italic_text_escapes_backtick():
    assert _escape_italic_text("code `x` here") == r"code \`x\` here"


def test_escape_italic_text_escapes_backslash():
    assert _escape_italic_text("path\\to\\file") == r"path\\to\\file"


def test_escape_italic_text_escapes_leading_list_marker():
    assert _escape_italic_text("- a list looking line") == r"\- a list looking line"
    # Asterisks are escaped first; the leading-block branch only adds
    # a backslash for "-", "+", ">", "#". The escaped "*" is no longer
    # parsed as a list marker.
    assert _escape_italic_text("* asterisk first") == r"\* asterisk first"
    assert _escape_italic_text("+ plus first") == r"\+ plus first"


def test_escape_italic_text_escapes_leading_blockquote():
    assert _escape_italic_text("> quoted thing") == r"\> quoted thing"


def test_escape_italic_text_escapes_leading_heading():
    assert _escape_italic_text("# heading-shaped") == r"\# heading-shaped"


def test_escape_italic_text_escapes_leading_ordered_list():
    """`1.` at the start would parse as an ordered list marker - the
    period must be escaped so the paragraph stays a paragraph."""
    assert _escape_italic_text("1. first item") == r"1\. first item"
    assert _escape_italic_text("42. answer") == r"42\. answer"


def test_escape_italic_text_passes_plain_text():
    assert _escape_italic_text("plain caption text") == "plain caption text"


def test_escape_italic_text_handles_empty():
    assert _escape_italic_text("") == ""
