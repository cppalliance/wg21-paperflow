"""Tests for lib.html.render."""

import re

from tomd.lib.html.extract import parse_html
from tomd.lib.html.render import (
    render_body,
    _fix_misnested_table_cells,
    _LOSSY_TABLE_MARKER,
    _MIXED_TABLE_MARKER,
)


class TestHeading:
    def test_atx_level(self):
        soup = parse_html("<h2>Introduction</h2>")
        md = render_body(soup, "mpark")
        assert "## Introduction" in md

    def test_strips_section_number_span(self):
        soup = parse_html(
            '<h1><span class="header-section-number">1</span> Abstract</h1>')
        md = render_body(soup, "mpark")
        assert "# Abstract" in md

    def test_preserves_leading_dotted_number(self):
        soup = parse_html("<h3>2.1.3 Details</h3>")
        md = render_body(soup, "mpark")
        assert "### 2.1.3 Details" in md

    def test_bold_suppressed(self):
        soup = parse_html("<h2><strong>Bold Heading</strong></h2>")
        md = render_body(soup, "mpark")
        assert "## Bold Heading" in md
        assert "**" not in md

    def test_h1_rooted_body_shifted_to_h2(self):
        # Body headings start at H2 (the front-matter title is the only H1).
        soup = parse_html(
            "<body><h1>Introduction</h1><h2>Background</h2>"
            "<h3>Detail</h3></body>")
        md = render_body(soup, "mpark")
        assert "## Introduction" in md
        assert "### Background" in md
        assert "#### Detail" in md
        assert not re.search(r"(?m)^# ", md)

    def test_h2_rooted_body_unchanged(self):
        # Already-correct papers must not be shifted (no blanket offset).
        soup = parse_html(
            "<body><h2>Introduction</h2><h3>Background</h3></body>")
        md = render_body(soup, "mpark")
        assert "## Introduction" in md
        assert "### Background" in md
        assert not re.search(r"(?m)^# ", md)


class TestParagraph:
    def test_collapses_whitespace(self):
        soup = parse_html("<p>Hello   \n  world</p>")
        md = render_body(soup, "mpark")
        assert "Hello world" in md

    def test_inline_code(self):
        soup = parse_html("<p>Use <code>std::vector</code> here.</p>")
        md = render_body(soup, "mpark")
        assert "`std::vector`" in md


class TestCodeBlock:
    def test_fenced(self):
        soup = parse_html('<pre class="sourceCode cpp"><code>int x = 1;</code></pre>')
        md = render_body(soup, "mpark")
        assert "```cpp" in md
        assert "int x = 1;" in md

    def test_language_from_class(self):
        soup = parse_html(
            '<div class="sourceCode"><pre class="sourceCode python">'
            '<code class="sourceCode python">print("hi")</code></pre></div>')
        md = render_body(soup, "mpark")
        assert "```python" in md

    def test_default_cpp_for_mpark(self):
        soup = parse_html("<pre><code>void f();</code></pre>")
        md = render_body(soup, "mpark")
        assert "```cpp" in md

    def test_no_default_for_unknown(self):
        soup = parse_html("<pre><code>void f();</code></pre>")
        md = render_body(soup, "unknown")
        assert "```\n" in md


class TestTable:
    def test_pipe_table(self):
        soup = parse_html("""
        <table>
          <tr><th>A</th><th>B</th></tr>
          <tr><td>1</td><td>2</td></tr>
        </table>
        """)
        md = render_body(soup, "mpark")
        assert "| A | B |" in md
        assert "| --- | --- |" in md
        assert "| 1 | 2 |" in md

    def test_pipe_escaped(self):
        soup = parse_html("""
        <table><tr><td>a|b</td><td>c</td></tr></table>
        """)
        md = render_body(soup, "mpark")
        assert r"a\|b" in md


class TestList:
    def test_unordered(self):
        soup = parse_html("<ul><li>One</li><li>Two</li></ul>")
        md = render_body(soup, "mpark")
        assert "- One" in md
        assert "- Two" in md

    def test_ordered(self):
        soup = parse_html("<ol><li>First</li><li>Second</li></ol>")
        md = render_body(soup, "mpark")
        assert "1. First" in md
        assert "2. Second" in md

    def test_nested(self):
        soup = parse_html("""
        <ul>
          <li>Parent
            <ul><li>Child</li></ul>
          </li>
        </ul>
        """)
        md = render_body(soup, "mpark")
        lines = md.strip().splitlines()
        parent_line = next(l for l in lines if "Parent" in l)
        assert "Child" not in parent_line
        assert "  - Child" in md
        assert md.count("Child") == 1, (
            f"Child appears {md.count('Child')} times, expected 1. md={md!r}")
        assert md.count("Parent") == 1

    def test_nested_three_levels(self):
        soup = parse_html("""
        <ul>
          <li>One
            <ul>
              <li>Two
                <ul><li>Three</li></ul>
              </li>
            </ul>
          </li>
        </ul>
        """)
        md = render_body(soup, "mpark")
        assert md.count("One") == 1
        assert md.count("Two") == 1
        assert md.count("Three") == 1
        assert "- One" in md
        assert "  - Two" in md
        assert "    - Three" in md

    def test_nested_ordered(self):
        soup = parse_html("""
        <ol>
          <li>First
            <ul><li>Bullet</li></ul>
          </li>
          <li>Second
            <ol><li>Sub</li></ol>
          </li>
        </ol>
        """)
        md = render_body(soup, "mpark")
        assert md.count("Bullet") == 1
        assert md.count("Sub") == 1
        assert "1. First" in md
        assert "  - Bullet" in md
        assert "2. Second" in md
        assert "  1. Sub" in md

    def test_nested_mixed_content(self):
        soup = parse_html("""
        <ul>
          <li>Before <strong>emphasis</strong>
            <ul><li>Nested</li></ul>
            after text
          </li>
        </ul>
        """)
        md = render_body(soup, "mpark")
        assert md.count("Nested") == 1
        assert "Before" in md
        assert "**emphasis**" in md
        assert md.count("after text") == 1

    def test_nested_multi_level(self):
        soup = parse_html("""
        <ul>
          <li>A
            <ul>
              <li>B
                <ol><li>C</li></ol>
              </li>
            </ul>
          </li>
        </ul>
        """)
        md = render_body(soup, "mpark")
        lines = md.strip().splitlines()
        a_line = next(l for l in lines if "A" in l and l.strip().startswith("-"))
        assert "B" not in a_line
        assert "C" not in a_line
        b_line = next(l for l in lines if "B" in l)
        assert "C" not in b_line


class TestWording:
    def test_wording_add_fence(self):
        soup = parse_html('<div class="wording-add"><p>New text</p></div>')
        md = render_body(soup, "mpark")
        assert ":::wording-add" in md
        assert ":::" in md.split(":::wording-add")[1]

    def test_wording_remove_fence(self):
        soup = parse_html('<div class="wording-remove"><p>Old text</p></div>')
        md = render_body(soup, "mpark")
        assert ":::wording-remove" in md

    def test_wording_mixed_fence(self):
        soup = parse_html('<div class="wording"><p>Spec text</p></div>')
        md = render_body(soup, "mpark")
        assert ":::wording\n" in md

    def test_ins_del_passthrough(self):
        soup = parse_html("<p><ins>added</ins> and <del>removed</del></p>")
        md = render_body(soup, "mpark")
        assert "<ins>added</ins>" in md
        assert "<del>removed</del>" in md


class TestBlockquote:
    def test_blockquote(self):
        soup = parse_html("<blockquote><p>Quoted text</p></blockquote>")
        md = render_body(soup, "mpark")
        assert "> Quoted text" in md


class TestInlineFormatting:
    def test_bold(self):
        soup = parse_html("<p><strong>bold</strong></p>")
        md = render_body(soup, "mpark")
        assert "**bold**" in md

    def test_italic(self):
        soup = parse_html("<p><em>italic</em></p>")
        md = render_body(soup, "mpark")
        assert "*italic*" in md

    def test_link(self):
        soup = parse_html('<p><a href="https://example.com">link</a></p>')
        md = render_body(soup, "mpark")
        assert "[link](https://example.com)" in md

    def test_anchor_link_plain(self):
        soup = parse_html('<p><a href="#section">section</a></p>')
        md = render_body(soup, "mpark")
        assert "section" in md
        assert "[" not in md

    def test_sub_sup_passthrough(self):
        soup = parse_html("<p>x<sub>2</sub> + y<sup>3</sup></p>")
        md = render_body(soup, "mpark")
        assert "<sub>2</sub>" in md
        assert "<sup>3</sup>" in md


class TestCollapseWhitespace:
    def test_collapses_spaces(self):
        md = render_body(parse_html("<p>hello   world</p>"), "mpark")
        assert "hello world" in md

    def test_strips_format_chars(self):
        md = render_body(parse_html("<p>hello\u200bworld</p>"), "mpark")
        assert "helloworld" in md

    def test_strips_and_trims(self):
        md = render_body(parse_html("<p>  hi  </p>"), "mpark")
        assert md.strip() == "hi"


class TestDocumentShell:
    def test_fragment_without_body(self):
        md = render_body(parse_html("<p>Frag</p>"), "mpark")
        assert "Frag" in md

    def test_full_document_with_body(self):
        html = "<html><head></head><body><p>In body</p></body></html>"
        md = render_body(parse_html(html), "mpark")
        assert "In body" in md


class TestStructuralTags:
    def test_hr(self):
        md = render_body(parse_html("<body><hr/><p>a</p></body>"), "mpark")
        assert "---" in md
        assert "a" in md

    def test_section_flattens(self):
        md = render_body(parse_html("<section><p>in</p></section>"), "mpark")
        assert "in" in md

    def test_main_article(self):
        md = render_body(parse_html("<main><p>m</p></main><article><p>a</p></article>"), "mpark")
        assert "m" in md and "a" in md


class TestHeadingEdgeCases:
    def test_secno_stripped_self_link_skipped(self):
        html = """<h2><span class="secno">3</span>Sec
        <a class="self-link" href="#x">#</a></h2>"""
        md = render_body(parse_html(html), "mpark")
        assert "## Sec" in md
        assert "self-link" not in md

    def test_heading_number_only_span_stripped(self):
        soup = parse_html('<h1><span class="header-section-number">1</span></h1>')
        md = render_body(soup, "mpark")
        assert md.strip() == "" or "# 1" not in md

    def test_inline_code_preserved_in_heading(self):
        soup = parse_html("<h2>The <code>foo_bar</code> section</h2>")
        md = render_body(soup, "mpark")
        assert "## The `foo_bar` section" in md

    def test_inline_code_preserved_with_skipped_number_span(self):
        soup = parse_html(
            '<h2><span class="header-section-number">3</span> '
            "<code>foo</code> bar</h2>"
        )
        md = render_body(soup, "mpark")
        assert "## `foo` bar" in md

    def test_link_preserved_in_heading(self):
        soup = parse_html(
            '<h2>See <a href="https://example.com/x">X</a> now</h2>'
        )
        md = render_body(soup, "mpark")
        assert "## See [X](https://example.com/x) now" in md


class TestCodeBlockExtended:
    def test_pre_without_code(self):
        md = render_body(parse_html("<pre>plain\nlines</pre>"), "mpark")
        assert "```" in md
        assert "plain" in md

    def test_language_hyphen_class(self):
        md = render_body(
            parse_html('<pre><code class="language-rust">let x;</code></pre>'),
            "mpark",
        )
        assert "```rust" in md

    def test_source_code_python_camel_class(self):
        md = render_body(
            parse_html('<pre><code class="sourceCodePython">x=1</code></pre>'),
            "mpark",
        )
        assert "```python" in md

    def test_source_code_on_parent_pre(self):
        md = render_body(
            parse_html(
                '<pre class="sourceCode cpp"><code>int y;</code></pre>'
            ),
            "mpark",
        )
        assert "```cpp" in md

    def test_bikeshed_no_default_lang_without_class(self):
        md = render_body(parse_html("<pre><code>x</code></pre>"), "bikeshed")
        assert md.startswith("```\n") or "\n```\n" in md
        assert "```cpp" not in md


class TestDivDispatch:
    def test_div_source_code_wraps_pre(self):
        html = (
            '<div class="sourceCode"><pre><code class="sourceCode cpp">z();'
            "</code></pre></div>"
        )
        md = render_body(parse_html(html), "mpark")
        assert "```cpp" in md

    def test_div_note_blockquote_style(self):
        md = render_body(
            parse_html('<div class="note"><p>Line one</p><p>Two</p></div>'),
            "mpark",
        )
        assert md.strip().startswith(">")
        assert "Line one" in md

    def test_div_example(self):
        md = render_body(parse_html('<div class="example"><p>ex</p></div>'), "mpark")
        assert "> ex" in md.replace("\n", " ") or "> ex" in md

    def test_plain_div_transparent(self):
        md = render_body(parse_html("<div><p>inner</p></div>"), "mpark")
        assert "inner" in md


class TestTableExtended:
    def test_nested_table_becomes_pipe(self):
        html = """
        <table>
        <tr><th>OuterA</th><th>OuterB</th></tr>
        <tr><td>1</td><td><table><tr><td>Inner</td></tr></table></td></tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<table>" not in md
        assert "OuterA" in md
        assert "Inner" in md

    def test_short_row_padding(self):
        html = """
        <table>
        <tr><th>A</th><th>B</th><th>C</th></tr>
        <tr><td>1</td><td>2</td></tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "| 1 | 2 |" in md or "| 1 | 2 | |" in md


class TestTbodyInCellUnwrap:
    """Phase 0 of _fix_misnested_table_cells: <tbody> trapped in a cell.

    WG21 papers (13/198 in the corpus, e.g. P2956R2) emit unclosed
    <td> tags followed by <tbody>; html.parser then nests the whole
    <tbody> inside the last open cell, hiding its rows from the
    renderer.
    """

    def test_trapped_tbody_code_cells_not_lost(self):
        # Models the P2956R2 construct. Without the unwrap, the second
        # header cell and the second code cell are silently dropped.
        html = """
        <table>
        <tr>
        <td>Source
        <td>Output
        <tbody>
        <tr>
        <td><pre>codeA</pre>
        <td><pre>codeB</pre>
        </tbody>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "Source" in md
        assert "Output" in md
        assert "codeA" in md
        assert "codeB" in md

    def test_trapped_tbody_avoids_lossy_path(self):
        # Without the unwrap this table renders via the lossy flat
        # reconstruction; with it, the regular pipe-table path applies.
        html = """
        <table>
        <tr>
        <td>Source
        <td>Output
        <tbody>
        <tr><td>codeA</td><td>codeB</td></tr>
        </tbody>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert _LOSSY_TABLE_MARKER not in md
        assert "| codeA | codeB |" in md

    def test_malformed_nested_table_repaired_locally(self):
        # A nested table with its own trapped <tbody> is repaired
        # within itself; its rows must not migrate into the outer
        # table during the outer table's pass.
        html = (
            "<table><tr><td>Outer"
            "<table><tr><td>InnerHdr"
            "<tbody><tr><td>InnerData</td></tr></tbody>"
            "</table>"
            "</td></tr></table>"
        )
        soup = parse_html(html)
        _fix_misnested_table_cells(soup)
        inner = soup.find("table").find("table")
        data_cell = soup.find(
            lambda t: t.name == "td" and t.get_text(strip=True) == "InnerData"
        )
        assert data_cell.find_parent("table") is inner

    def test_legit_nested_table_tbody_untouched(self):
        # The nearest-table guard: a <tbody> belonging to a valid
        # nested <table> inside a cell must keep its structure.
        html = (
            "<table><tr><td>"
            "<table><tbody><tr><td>Inner</td></tr></tbody></table>"
            "</td></tr></table>"
        )
        soup = parse_html(html)
        _fix_misnested_table_cells(soup)
        inner = soup.find("table").find("table")
        assert inner is not None
        assert inner.find("tbody") is not None


class TestDenormalizedTable:
    """Tables with rowspan/colspan are denormalized into flat pipe tables."""

    def test_rowspan_expanded(self):
        html = """
        <table>
        <tr><th>Day</th><th>Time</th></tr>
        <tr><td rowspan="2">Mon-Tue</td><td>09:00</td></tr>
        <tr><td>10:00</td></tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<table>" not in md
        assert "| Day | Time |" in md
        assert "| Mon-Tue | 09:00 |" in md
        assert "| Mon-Tue | 10:00 |" in md

    def test_colspan_expanded(self):
        html = """
        <table>
        <tr><th colspan="2">Header</th></tr>
        <tr><td>A</td><td>B</td></tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<table>" not in md
        assert "| Header | Header |" in md
        assert "| A | B |" in md

    def test_mixed_rowspan_colspan(self):
        html = """
        <table>
        <tr><th>X</th><th>Y</th><th>Z</th></tr>
        <tr><td rowspan="2">A</td><td colspan="2">B</td></tr>
        <tr><td>C</td><td>D</td></tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<table>" not in md
        lines = [l for l in md.splitlines() if l.startswith("|")]
        assert len(lines) == 4  # header + separator + 2 data rows
        assert "| A | B | B |" in md
        assert "| A | C | D |" in md

    def test_schedule_table_n5034(self):
        """Real-world schedule from N5034 with rowspan=5 and colspan=2."""
        html = """
        <table>
        <tr><th>Day</th><th>Start</th><th>Break</th><th>End</th></tr>
        <tr><td>Monday</td><td>9:00 AM</td><td rowspan="3">10:15</td><td rowspan="3">5:30 PM</td></tr>
        <tr><td>Tuesday</td><td rowspan="2">8:30 AM</td></tr>
        <tr><td>Wednesday</td></tr>
        <tr><td>Saturday</td><td>8:30 AM</td><td colspan="2">No breaks</td></tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<table>" not in md
        assert "| Monday | 9:00 AM | 10:15 | 5:30 PM |" in md
        assert "| Tuesday | 8:30 AM | 10:15 | 5:30 PM |" in md
        assert "| Wednesday | 8:30 AM | 10:15 | 5:30 PM |" in md
        assert "| Saturday | 8:30 AM | No breaks | No breaks |" in md

    def test_simple_table_no_spans_still_pipe(self):
        """Tables without spans should still render as pipe tables."""
        html = """
        <table>
        <tr><th>A</th><th>B</th></tr>
        <tr><td>1</td><td>2</td></tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<table>" not in md
        assert "| A | B |" in md
        assert "| 1 | 2 |" in md

    def test_br_in_cell_becomes_space(self):
        """Single-cell <br> stays as pipe table (below threshold)."""
        html = """
        <table>
        <tr><th>Col</th></tr>
        <tr><td>Line1<br>Line2</td></tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<table>" not in md
        assert "Line1 Line2" in md

    def test_br_multiline_cells_become_html_table(self):
        """Tables with 2+ cells containing <br> route to HTML table."""
        html = """
        <table>
        <thead><tr><th>Unary</th><th>Binary</th></tr></thead>
        <tbody><tr>
          <td>+q<br>-q<br>++q</td>
          <td>q + kind<br>q - kind<br>q * q2</td>
        </tr></tbody>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<table" in md
        assert "<br" in md
        assert _MIXED_TABLE_MARKER in md

    def test_single_br_cell_stays_pipe(self):
        """Only one cell with <br> stays as pipe table."""
        html = """
        <table>
        <thead><tr><th>A</th><th>B</th></tr></thead>
        <tbody><tr>
          <td>Line1<br>Line2</td>
          <td>No break here</td>
        </tr></tbody>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<table>" not in md
        assert "Line1 Line2" in md

    def test_code_table_blank_lines_no_paragraph_break(self):
        """Blank lines in <pre><code> must not break Markdown HTML block."""
        html = """
        <table>
        <tr><th>A</th><th>B</th></tr>
        <tr>
          <td><pre><code>line1;

line2;</code></pre></td>
          <td><pre><code>fix1;

fix2;</code></pre></td>
        </tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<table" in md
        assert "&#10;" in md
        assert "\n\n" not in md.split("<pre")[1].split("</pre>")[0]

    def test_code_table_multiple_consecutive_blank_lines(self):
        """2+ consecutive blank lines in <pre><code> must all be escaped."""
        html = """
        <table>
        <tr><th>A</th><th>B</th></tr>
        <tr>
          <td><pre><code>line1;


line3;</code></pre></td>
          <td><pre><code>fix1;



fix4;</code></pre></td>
        </tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<table" in md
        assert "&#10;" in md
        for segment in md.split("<pre")[1:]:
            inside = segment.split("</pre>")[0]
            assert "\n\n" not in inside, (
                f"raw blank line survived inside <pre>: {inside!r}"
            )

    def test_pipe_in_cell_escaped(self):
        """Pipe characters in cell content must be escaped."""
        html = """
        <table>
        <tr><th>Op</th></tr>
        <tr><td rowspan="2">a|b</td></tr>
        <tr></tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert r"a\|b" in md

    def test_nested_table_becomes_pipe(self):
        """Nested tables are reconstructed as pipe tables via flat path."""
        html = """
        <table>
        <tr><td><table><tr><td>Inner</td></tr></table></td></tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<table>" not in md
        assert "Inner" in md

    def test_block_content_in_cell_becomes_pipe(self):
        """Tables with block content (lists) in cells become pipe tables."""
        html = """
        <table>
        <tr><td rowspan="2">X</td><td><ul><li>Item</li></ul></td></tr>
        <tr><td>Y</td></tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<table>" not in md
        assert "X" in md

    def test_bikeshed_unclosed_tags_become_pipe(self):
        """Bikeshed-style tables with unclosed <td>/<th> become pipe tables."""
        html = """
        <table>
        <tr><th>Poll<th>SF<th>WF<th>Outcome
        <tr><td>Poll 1<td>11<td>4<td>Consensus
        <tr><td>Poll 2<td>5<td>3<td>No consensus
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<table>" not in md
        assert "Poll" in md
        assert "SF" in md
        assert "Consensus" in md
        pipe_lines = [l for l in md.splitlines() if l.strip().startswith("|")]
        assert len(pipe_lines) >= 4  # header + sep + 2 data rows


class TestLossyTableMarker:
    """Lossy table rendering paths emit <!-- tomd:lossy-table --> markers."""

    def test_rowspan_emits_marker(self):
        html = """
        <table>
        <tr><th>Day</th><th>Time</th></tr>
        <tr><td rowspan="2">Mon</td><td>09:00</td></tr>
        <tr><td>10:00</td></tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<!-- tomd:lossy-table -->" in md

    def test_colspan_emits_marker(self):
        html = """
        <table>
        <tr><th colspan="2">Header</th></tr>
        <tr><td>A</td><td>B</td></tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<!-- tomd:lossy-table -->" in md

    def test_simple_table_no_marker(self):
        html = """
        <table>
        <tr><th>A</th><th>B</th></tr>
        <tr><td>1</td><td>2</td></tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<!-- tomd:lossy-table -->" not in md

    def test_nested_table_emits_marker(self):
        html = """
        <table>
        <tr><td><table><tr><td>Inner</td></tr></table></td></tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<!-- tomd:lossy-table -->" in md

    def test_code_table_emits_marker(self):
        html = """
        <table>
        <tr><td><pre><code>int x = 1;</code></pre></td></tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert "<!-- tomd:lossy-table -->" in md

    def test_multiple_lossy_tables_multiple_markers(self):
        html = """
        <table>
        <tr><th colspan="2">T1</th></tr>
        <tr><td>A</td><td>B</td></tr>
        </table>
        <table>
        <tr><th>X</th></tr>
        <tr><td rowspan="2">Y</td></tr>
        <tr></tr>
        </table>
        """
        md = render_body(parse_html(html), "mpark")
        assert md.count("<!-- tomd:lossy-table -->") == 2


class TestDefinitionList:
    def test_dl_dt_dd(self):
        html = "<dl><dt>Term</dt><dd>Def</dd></dl>"
        md = render_body(parse_html(html), "mpark")
        assert "**Term**" in md
        assert ": Def" in md


class TestLinksExtended:
    def test_mailto_link(self):
        md = render_body(
            parse_html('<p><a href="mailto:a@b.co">Mail me</a></p>'),
            "mpark",
        )
        assert "[Mail me](mailto:a@b.co)" in md

    def test_disallowed_scheme_plain_text(self):
        md = render_body(
            parse_html('<p><a href="ftp://x.com">ftp</a></p>'),
            "mpark",
        )
        assert "ftp" in md
        assert "](" not in md

    def test_anchor_no_href_text_only(self):
        md = render_body(parse_html("<p><a>nohref</a></p>"), "mpark")
        assert "nohref" in md


class TestBlockquoteBareInline:
    """Bare inline content directly under <blockquote> (P3104R5).

    Papers emit <blockquote><b>ACTION</b>: text ... without a <p>
    wrapper. Without normalization, the label and its text split into
    separate paragraphs and the bold markers are lost.
    """

    def test_bare_label_and_text_stay_one_paragraph(self):
        html = (
            "<blockquote><b>ACTION</b>: Ask SG6 to look at the paper\n"
            "and bring up issues back to LEWG if exists. "
            "<p><b>POLL</b>: Forward the paper.</p></blockquote>"
        )
        md = render_body(parse_html(html), "bikeshed")
        assert (
            "> **ACTION**: Ask SG6 to look at the paper "
            "and bring up issues back to LEWG if exists." in md
        )
        assert "> **POLL**: Forward the paper." in md

    def test_block_children_end_the_run(self):
        # Inline run, then a table, then another inline run: the table
        # must stay a table and the runs must become two paragraphs.
        html = (
            "<blockquote>Before <i>table</i>"
            "<table><tr><td>X</td></tr></table>"
            "After text</blockquote>"
        )
        md = render_body(parse_html(html), "mpark")
        assert "> Before *table*" in md
        assert "| X |" in md
        assert "> After text" in md

    def test_br_ends_the_run(self):
        # An explicit <br> between bare text lines (poll tallies) must
        # keep the lines separate instead of collapsing them into one.
        html = "<blockquote>SF F N A SA<br>3 4 5 1 0</blockquote>"
        md = render_body(parse_html(html), "mpark")
        assert "SF F N A SA 3 4 5 1 0" not in md
        assert "> SF F N A SA" in md
        assert "> 3 4 5 1 0" in md

    def test_whitespace_only_nodes_no_empty_paragraph(self):
        # The whitespace between <p> siblings must not become a <p>.
        html = "<blockquote>\n  <p>One</p>\n  <p>Two</p>\n</blockquote>"
        md = render_body(parse_html(html), "mpark")
        assert md.count("One") == 1
        assert "> One" in md
        assert "> Two" in md


class TestBlockquoteExtended:
    def test_nested_paragraphs(self):
        md = render_body(
            parse_html("<blockquote><p>First</p><p>Second</p></blockquote>"),
            "mpark",
        )
        assert "> First" in md
        # The paragraphs stay separated by a blank quoted line; the
        # bare-inline wrap pass must not merge them.
        assert "> \n> Second" in md

    def test_empty_blockquote_omitted(self):
        md = render_body(parse_html("<blockquote></blockquote><p>x</p>"), "mpark")
        assert md.strip() == "x"


class TestListExtended:
    def test_ol_with_nested_ul(self):
        html = "<ol><li>Outer<ul><li>Inner</li></ul></li></ol>"
        md = render_body(parse_html(html), "mpark")
        assert "1. Outer" in md
        assert "  - Inner" in md


class TestTransparentInline:
    def test_mark_kbd_passthrough(self):
        md = render_body(
            parse_html("<p><mark>m</mark> <kbd>k</kbd></p>"),
            "mpark",
        )
        assert "m" in md and "k" in md


class TestSchultkeCustomElements:
    """Tests for Jan Schultke's custom HTML generator elements."""

    def test_code_block_fenced(self):
        html = '<code-block><h- data-h="kw">const</h-> <h- data-h="kw_type">int</h-> x = 42;</code-block>'
        md = render_body(parse_html(html), "schultke")
        assert "```cpp" in md
        assert "const int x = 42;" in md
        assert "```" in md.split("```cpp")[1]

    def test_code_block_multiline(self):
        html = (
            "<code-block>"
            '<h- data-h="kw">void</h-> <h- data-h="id">foo</h->() {\n'
            '  <h- data-h="kw">return</h->;\n'
            "}"
            "</code-block>"
        )
        md = render_body(parse_html(html), "schultke")
        assert "```cpp" in md
        assert "void foo()" in md
        assert "return" in md

    def test_code_block_works_with_any_generator(self):
        html = "<code-block>int x;</code-block>"
        md = render_body(parse_html(html), "unknown")
        assert "```cpp" in md
        assert "int x;" in md

    def test_example_block_becomes_blockquote(self):
        html = "<example-block><p>Example text</p></example-block>"
        md = render_body(parse_html(html), "schultke")
        assert "> Example text" in md

    def test_note_block_becomes_blockquote(self):
        html = "<note-block><p>Note content</p></note-block>"
        md = render_body(parse_html(html), "schultke")
        assert "> Note content" in md

    def test_bug_block_becomes_blockquote(self):
        html = "<bug-block><p>Bug report</p></bug-block>"
        md = render_body(parse_html(html), "schultke")
        assert "> Bug report" in md

    def test_tt_becomes_inline_code(self):
        html = "<p>Use <tt->std::vector</tt-> here</p>"
        md = render_body(parse_html(html), "schultke")
        assert "`std::vector`" in md

    def test_h_inline_passthrough(self):
        html = '<p>The <h- data-h="kw">const</h-> keyword</p>'
        md = render_body(parse_html(html), "schultke")
        assert "const" in md

    def test_f_serif_passthrough(self):
        html = "<p><f-serif>Some text</f-serif></p>"
        md = render_body(parse_html(html), "schultke")
        assert "Some text" in md


class TestDascandyFietsCodeBlock:
    """Tests for dascandy/fiets generator div.code pattern."""

    def test_div_code_fenced(self):
        html = '<div class="code">int main() { return 0; }</div>'
        md = render_body(parse_html(html), "dascandy/fiets")
        assert "```cpp" in md
        assert "int main()" in md

    def test_div_code_with_spans(self):
        html = (
            '<div class="code">'
            '<span class="keyword">const</span> '
            '<span class="special">&amp;</span>x'
            "</div>"
        )
        md = render_body(parse_html(html), "dascandy/fiets")
        assert "```cpp" in md
        assert "const" in md

    def test_code_wrapping_div_code(self):
        """dascandy/fiets uses <code><div class='code'>...</div></code>."""
        html = '<code><div class="code">void f() {}</div></code>'
        md = render_body(parse_html(html), "dascandy/fiets")
        assert "```cpp" in md
        assert "void f()" in md


class TestCodeTable:
    """Tables containing <pre> blocks should extract code, not build pipe tables."""

    def test_table_with_pre_extracts_code_blocks(self):
        html = (
            "<table><tr>"
            '<td><pre class="highlight">int x = 1;</pre></td>'
            '<td><pre class="highlight">mov eax, 1</pre></td>'
            "</tr></table>"
        )
        md = render_body(parse_html(html), "bikeshed")
        assert "```cpp" in md
        assert "int x = 1;" in md
        assert "mov eax, 1" in md
        assert "|" not in md

    def test_code_table_preserves_all_pre_blocks(self):
        """Every <pre> in a table is emitted, even if content is identical."""
        html = (
            "<table><tr>"
            '<td><pre class="highlight">void f();</pre></td>'
            '<td><pre class="highlight">void f();</pre></td>'
            "</tr></table>"
        )
        md = render_body(parse_html(html), "bikeshed")
        assert md.count("void f();") == 2

    def test_table_without_pre_stays_pipe(self):
        html = "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
        md = render_body(parse_html(html), "bikeshed")
        assert "| A | B |" in md


class TestBikeshedInlineElements:
    """Bikeshed <c-> syntax highlight spans should pass through inline."""

    def test_c_dash_inside_code(self):
        html = '<p><code class="highlight"><c->std</c-><c->::</c-><c->vector</c-></code></p>'
        md = render_body(parse_html(html), "bikeshed")
        assert "`std::vector`" in md


class TestHtmlComments:
    def test_comment_content_not_rendered(self):
        """HTML comments must never appear in Markdown output."""
        html = "<p>Visible text.</p><!-- This comment should be invisible -->"
        md = render_body(parse_html(html), "mpark")
        assert "Visible text." in md
        assert "comment" not in md
        assert "invisible" not in md

    def test_comment_with_html_tags_not_rendered(self):
        """Commented-out HTML blocks (e.g. draft sections) must not leak into output."""
        html = (
            "<p>Before.</p>"
            "<!-- <h2>Draft Section</h2><p>Draft content</p> -->"
            "<p>After.</p>"
        )
        md = render_body(parse_html(html), "mpark")
        assert "Before." in md
        assert "After." in md
        assert "Draft Section" not in md
        assert "Draft content" not in md

    def test_comment_with_entities_not_rendered(self):
        """Entities inside comments (e.g. &lt; in commented-out code) must not appear."""
        html = (
            "<p>Intro.</p>"
            "<!-- <pre>template &lt;class T&gt; void f();</pre> -->"
            "<p>Body.</p>"
        )
        md = render_body(parse_html(html), "mpark")
        assert "Intro." in md
        assert "Body." in md
        assert "&lt;" not in md
        assert "&gt;" not in md
        assert "template" not in md

    def test_comment_between_inline_elements_not_rendered(self):
        """Comments inline between spans must not insert text into the output."""
        html = "<p>Hello<!-- drop this --> world</p>"
        md = render_body(parse_html(html), "mpark")
        assert "Hello world" in md
        assert "drop this" not in md

    def test_comment_in_heading_not_rendered(self):
        """Comments inside headings are stripped."""
        html = "<h2>Real Title<!-- draft annotation --></h2>"
        md = render_body(parse_html(html), "mpark")
        assert "## Real Title" in md
        assert "draft annotation" not in md


class TestListCodeExtraction:
    """<pre> and <code-block> inside <li> should be fenced, not flattened."""

    def test_li_with_pre_emits_fenced_code(self):
        html = "<ul><li>Description<pre>int x = 42;</pre></li></ul>"
        md = render_body(parse_html(html), "bikeshed")
        assert "- Description" in md
        assert "```" in md
        assert "int x = 42;" in md

    def test_li_with_code_block_emits_fenced_code(self):
        html = "<ul><li>Example<code-block>void f();</code-block></li></ul>"
        md = render_body(parse_html(html), "schultke")
        assert "- Example" in md
        assert "```cpp" in md
        assert "void f();" in md

    def test_li_without_code_stays_inline(self):
        html = "<ul><li>Plain text only</li></ul>"
        md = render_body(parse_html(html), "mpark")
        assert "- Plain text only" in md
        assert "```" not in md


class TestDlCodeExtraction:
    """<pre> and <code-block> inside <dd> should be fenced, not flattened."""

    def test_dd_with_pre_emits_fenced_code(self):
        html = "<dl><dt>Term</dt><dd>Def<pre>int x = 1;</pre></dd></dl>"
        md = render_body(parse_html(html), "bikeshed")
        assert "**Term**" in md
        assert ": Def" in md
        assert "```" in md
        assert "int x = 1;" in md

    def test_dd_with_code_block_emits_fenced_code(self):
        html = "<dl><dt>API</dt><dd>Usage:<code-block>f();</code-block></dd></dl>"
        md = render_body(parse_html(html), "schultke")
        assert "**API**" in md
        assert ": Usage:" in md
        assert "```cpp" in md
        assert "f();" in md

    def test_dd_without_code_stays_inline(self):
        html = "<dl><dt>Key</dt><dd>Value</dd></dl>"
        md = render_body(parse_html(html), "mpark")
        assert "**Key**" in md
        assert ": Value" in md
        assert "```" not in md


class TestCodeTableWithCodeBlock:
    """Tables with <code-block> should extract code like <pre> tables."""

    def test_table_with_code_block_extracts(self):
        html = (
            "<table><tr>"
            "<td><code-block>int x = 1;</code-block></td>"
            "<td><code-block>int y = 2;</code-block></td>"
            "</tr></table>"
        )
        md = render_body(parse_html(html), "schultke")
        assert "```cpp" in md
        assert "int x = 1;" in md
        assert "int y = 2;" in md
        assert "|" not in md


class TestCodeParagraphDetection:
    """<p> with only <span class="code"> children -> fenced code block."""

    def test_span_code_only_paragraph_becomes_fenced(self):
        html = (
            '<p><span class="code">'
            '<span class="keyword">constexpr</span> '
            'basic_cstring_view() noexcept;'
            '</span></p>'
        )
        md = render_body(parse_html(html), "dascandy/fiets")
        assert "```cpp" in md
        assert "constexpr basic_cstring_view() noexcept;" in md

    def test_mixed_content_paragraph_stays_prose(self):
        html = '<p>Use <span class="code">std::vector</span> here.</p>'
        md = render_body(parse_html(html), "dascandy/fiets")
        assert "```" not in md
        assert "std::vector" in md

    def test_multiple_span_code_children(self):
        html = (
            '<p>'
            '<span class="code">template&lt;class T&gt;</span> '
            '<span class="code">auto foo() -&gt; T;</span>'
            '</p>'
        )
        md = render_body(parse_html(html), "dascandy/fiets")
        assert "```cpp" in md

    def test_code_element_not_matched(self):
        """<code> is inline formatting, not dascandy/fiets span.code."""
        html = '<p><code class="highlight">std::vector</code></p>'
        md = render_body(parse_html(html), "bikeshed")
        assert "```cpp" not in md

    def test_empty_paragraph_not_matched(self):
        html = "<p>   </p>"
        md = render_body(parse_html(html), "dascandy/fiets")
        assert md.strip() == "" or "```" not in md


class TestListChildDrop:
    """Non-<li> direct children of a list are rendered, not silently dropped."""

    def _md(self, html):
        return render_body(parse_html(html), "mpark")

    def test_renders_nested_list_direct_child(self):
        # Outer <ol> has no <li> of its own, only a nested <ol>: the inner list
        # is the content and renders standalone at top level (not indented).
        md = self._md("<ol><ol><li>inner</li></ol></ol>")
        assert "inner" in md
        assert "1. inner" in md
        assert "  1. inner" not in md  # standalone: no outer item to indent under

    def test_ol_ol_wording_content_recovered(self):
        # P4179R0's real shape: the synopsis <pre> sits inside a <blockquote>
        # inside the <li>. Part 1 recovers the CONTENT (the list is no longer
        # dropped). The <pre> stays flattened by _inline_text (the deferred
        # <li>-internal flattening), so we assert presence, not a code fence.
        md = self._md(
            "<div><ol><ol>"
            "<li><p>Add a feature-test macro</p>"
            "<blockquote><pre>#define __cpp_lib_x</pre></blockquote></li>"
            "<li><p>Modify</p>"
            "<blockquote><pre>namespace std {}</pre></blockquote></li>"
            "</ol></ol></div>"
        )
        assert "__cpp_lib_x" in md
        assert "namespace std {}" in md

    def test_renders_loose_paragraph_child_indented(self):
        md = self._md("<ul><li>a</li><p>note</p></ul>")
        assert "note" in md
        assert "\n  note" in md  # indented under the preceding item

    def test_renders_direct_child_pre_fenced(self):
        # A <pre> that is a direct child of the list (not <li>-internal) renders
        # as a fenced block via the normal element dispatch.
        md = self._md("<ol><li>Add:</li><pre>code();</pre></ol>")
        assert "code();" in md
        assert "```" in md

    def test_renders_direct_child_blockquote(self):
        md = self._md("<ul><li>a</li><blockquote>quoted</blockquote></ul>")
        assert "quoted" in md
        assert ">" in md

    def test_renders_loose_text_child(self):
        md = self._md("<ul><li>a</li>loose text here</ul>")
        assert "loose text here" in md

    def test_non_li_child_before_first_item_standalone(self):
        md = self._md("<ol><p>intro</p><li>a</li></ol>")
        assert "intro" in md
        assert "1. a" in md
        assert "  intro" not in md  # no preceding item: standalone, not indented

    def test_ordered_numbering_counts_only_li(self):
        md = self._md("<ol><li>a</li><p>x</p><li>b</li></ol>")
        assert "1. a" in md
        assert "2. b" in md
        assert "3." not in md  # the <p> does not advance the counter

    def test_comment_child_produces_no_output(self):
        md = self._md("<ul><li>a</li><!-- secret build note --></ul>")
        assert "secret" not in md
        assert "build note" not in md

    def test_whitespace_text_between_items_no_spurious_item(self):
        md = self._md("<ul><li>a</li>\n   \n<li>b</li></ul>")
        assert md == "- a\n- b"

    def test_nested_sublist_in_li_unchanged(self):
        md = self._md("<ul><li>a<ul><li>b</li></ul></li></ul>")
        assert md == "- a\n  - b"

    def test_code_block_in_li_unchanged(self):
        md = self._md("<ol><li>x<pre>code</pre></li></ol>")
        assert "1. x" in md
        assert "```" in md
        assert "code" in md


class TestDlChildDrop:
    """Non-dt/dd direct children of a <dl> are rendered, not silently dropped."""

    def _md(self, html):
        return render_body(parse_html(html), "mpark")

    def test_renders_non_dt_dd_child(self):
        md = self._md("<dl><dt>term</dt><dd>def</dd><p>note</p></dl>")
        assert "note" in md

    def test_comment_child_produces_no_output(self):
        md = self._md("<dl><dt>t</dt><dd>d</dd><!-- c --></dl>")
        assert "c " not in md and "\nc" not in md

    def test_dt_dd_unchanged(self):
        md = self._md("<dl><dt>term</dt><dd>def</dd></dl>")
        assert "**term**" in md
        assert ": def" in md
