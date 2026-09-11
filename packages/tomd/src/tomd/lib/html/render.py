"""DOM-to-Markdown rendering for WG21 HTML papers."""

import html as _html
import json
import re
import urllib.parse
from collections import deque

from bs4 import BeautifulSoup, CData, Comment, ProcessingInstruction, Tag, NavigableString

from .. import CODE_LANG_LABELS, strip_format_chars, ALLOWED_LINK_SCHEMES
from ..wording_cleanup import strip_redundant_tags
from ..wording_markup import wording_tag_open
from .. import tables as _tables
from ..pdf.code_format import is_diagram_block

_BOLD_WRAP_RE = re.compile(r"^\*\*(.+)\*\*$")
_LOSSY_TABLE_MARKER = "<!-- tomd:lossy-table -->"
_DROPPED_SVG_MARKER = "<!-- tomd:svg-dropped -->"
_COLLAPSE_WS_RE = re.compile(r"\s+")

_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_LIST_CONTAINER_TAGS = frozenset({"ul", "ol"})
_BLOCK_TAGS = frozenset({
    "p", "pre", "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "ul", "ol", "blockquote", "div", "section",
    "dl", "hr", "figure",
})


_INLINE_PARENT_TAGS = frozenset({
    "p", "span", "a", "em", "i", "strong", "b",
}) | _HEADING_TAGS


def _fix_misnested_blocks(soup: BeautifulSoup) -> None:
    """Repair block elements wrongly nested inside inline parents by html.parser.

    html.parser does not auto-close inline-context tags (``<p>``, ``<h3>``,
    ``<em>``, etc.) when it encounters a block element. This pulls block
    children out to siblings, preserving surrounding inline content in
    wrapper elements of the same type.

    Uses a worklist to avoid rescanning the entire DOM on each fix.
    """

    def _has_block_child(tag: Tag) -> bool:
        return any(isinstance(c, Tag) and c.name in _BLOCK_TAGS for c in tag.children)

    worklist: deque[Tag] = deque(
        tag for tag in soup.find_all(_INLINE_PARENT_TAGS)
        if _has_block_child(tag)
    )

    while worklist:
        parent_tag = worklist.popleft()
        # A container can be queued twice (two children promoting blocks
        # into it); the second pop sees it already decomposed.
        if parent_tag.decomposed or parent_tag.parent is None:
            continue
        if not _has_block_child(parent_tag):
            continue

        tag_name = parent_tag.name
        tag_attrs = dict(parent_tag.attrs) if parent_tag.attrs else {}
        collected_inline: list = []

        def _flush_inline():
            if not collected_inline:
                return
            if not any(
                (isinstance(n, Tag) and n.get_text(strip=True))
                or (isinstance(n, NavigableString) and str(n).strip())
                for n in collected_inline
            ):
                collected_inline.clear()
                return
            wrapper = soup.new_tag(tag_name, **tag_attrs)
            for node in collected_inline:
                wrapper.append(node.extract())
            parent_tag.insert_before(wrapper)
            collected_inline.clear()

        children = list(parent_tag.children)
        for child in children:
            if isinstance(child, Tag) and child.name in _BLOCK_TAGS:
                _flush_inline()
                parent_tag.insert_before(child.extract())
            else:
                collected_inline.append(child)
        _flush_inline()
        container = parent_tag.parent
        parent_tag.decompose()
        # The promoted blocks now live in the enclosing element. If that
        # is itself an inline parent (block nested two or more inline
        # levels deep), re-queue it so the repair cascades upward.
        if (
            isinstance(container, Tag)
            and container.name in _INLINE_PARENT_TAGS
            and _has_block_child(container)
        ):
            worklist.append(container)



def _fix_misnested_list_items(soup: BeautifulSoup) -> None:
    """Promote <li> elements directly nested inside other <li> to siblings.

    html.parser does not auto-close <li> when it encounters a new <li>,
    causing successive list items to nest inside the first one. This walks
    all <li> tags and moves any direct child <li> to the correct sibling
    position. Properly wrapped sublists (<li><ul><li>...</li></ul></li>)
    are left alone so the renderer can indent them.

    Uses a worklist to avoid rescanning the entire DOM on each fix.
    """

    def _direct_li_children(li: Tag) -> list[Tag]:
        return li.find_all("li", recursive=False)

    worklist: deque[Tag] = deque(
        li for li in soup.find_all("li")
        if _direct_li_children(li)
    )

    while worklist:
        li = worklist.popleft()
        if li.parent is None:
            continue
        nested = _direct_li_children(li)
        if not nested:
            continue
        parent = li.parent
        for nested_li in nested:
            parent.append(nested_li.extract())
            if _direct_li_children(nested_li):
                worklist.append(nested_li)


_TABLE_CELL_TAGS = frozenset({"td", "th"})
_TABLE_SECTION_TAGS = ("tbody", "thead", "tfoot")


def _fix_misnested_table_cells(soup: BeautifulSoup) -> None:
    """Repair table rows and cells wrongly nested by html.parser.

    html.parser does not auto-close ``<td>``, ``<th>``, or ``<tr>`` when
    it encounters a new opening tag of the same type. This causes three
    kinds of mangling:

    0. ``<tbody>``/``<thead>``/``<tfoot>`` trapped inside a ``<td>``/
       ``<th>`` cell (the cell before the section tag was never closed).
       We unwrap these so their children become direct children of the
       cell, which lets phases 1 and 2 see the trapped rows. Section
       tags belonging to a legitimately nested ``<table>`` inside the
       cell are left alone.

    1. ``<tr>`` nested inside ``<td>``/``<th>`` instead of being a sibling
       row. We promote these to direct children of the table container
       (``<tbody>``, ``<thead>``, ``<tfoot>``, or ``<table>``).

    2. ``<td>``/``<th>`` nested inside another ``<td>``/``<th>`` instead
       of being siblings within the same ``<tr>``. We flatten these by
       repeatedly extracting nested cells.
    """
    for table in soup.find_all("table"):
        # Phase 0: unwrap section tags trapped inside cells. The
        # ownership guard restricts each pass of the outer loop to
        # sections whose nearest <table> is the current one: sections
        # of a legitimately nested <table> keep their structure, and
        # malformed nested tables are repaired in their own pass.
        for cell in table.find_all(_TABLE_CELL_TAGS):
            for section in cell.find_all(_TABLE_SECTION_TAGS):
                if section.find_parent("table") is table:
                    section.unwrap()

        container = (
            table.find(list(_TABLE_SECTION_TAGS), recursive=False)
            or table
        )
        # Phase 1: promote <tr> elements trapped inside cells to the
        # table container level.
        for cell in table.find_all(_TABLE_CELL_TAGS):
            nested_trs = cell.find_all("tr", recursive=False)
            for nested_tr in nested_trs:
                container.append(nested_tr.extract())

        # Phase 2: flatten <td>/<th> nested inside other <td>/<th>
        # within each <tr>.
        for tr in table.find_all("tr"):
            changed = True
            while changed:
                changed = False
                for cell in tr.find_all(_TABLE_CELL_TAGS, recursive=False):
                    nested = cell.find_all(
                        _TABLE_CELL_TAGS, recursive=False,
                    )
                    if nested:
                        for nested_cell in reversed(nested):
                            cell.insert_after(nested_cell.extract())
                        changed = True


def _fix_misnested_dl_items(soup: BeautifulSoup) -> None:
    """Promote <dt>/<dd> chain-nested by html.parser to direct <dl> children.

    Bikeshed emits definition lists with implicit close tags. Python's
    html.parser does not apply HTML5 implied-end-tags, so each successive
    <dt>/<dd> nests inside the previous <dd>/<dt>, forming a chain
    (dt1 > dd1 > dt2 > dd2 > ...). This flattens every <dt>/<dd> back to a
    direct child of its owning <dl>.

    A <dt>/<dd> is misnested iff its direct parent is not the <dl>. We
    snapshot all dt/dd in document order, keep only those whose nearest
    <dl> ancestor is THIS dl (so a legitimately nested inner <dl> is left
    alone and repaired in its own pass), and re-append only the misnested
    ones in document order. Already-correct items and loose dl-level
    content keep their position. Single pass, no worklist; no-op on
    well-formed dls.
    """
    for dl in soup.find_all("dl"):
        items = [
            it for it in dl.find_all(["dt", "dd"])
            if it.find_parent("dl") is dl
        ]
        for it in items:
            if it.parent is not dl:
                dl.append(it.extract())


_INLINE_RENDER_TAGS = frozenset({
    "span", "a", "code", "em", "strong", "b", "i", "sub", "sup",
    "ins", "del", "mark", "small", "s", "u", "abbr", "cite",
    "dfn", "var", "kbd", "samp", "time", "data", "wbr",
    "h-", "f-serif",
})

_BARE_INLINE_TAGS = _INLINE_RENDER_TAGS | {"img", "tt-"}


def _wrap_bare_blockquote_inline(soup: BeautifulSoup) -> None:
    """Wrap bare inline runs under ``<blockquote>`` in ``<p>`` elements.

    Some papers place inline content (text nodes, ``<b>``, ``<a>``, ...)
    directly under ``<blockquote>`` without a ``<p>`` wrapper. The
    renderer treats every child as its own block, so a label like
    ``<b>ACTION</b>: text`` splits into two paragraphs and the bold
    markers are lost. Wrapping each run of consecutive inline children
    in a ``<p>`` routes them through the paragraph renderer, which
    keeps the run as one paragraph with inline formatting intact.
    Block-level children end the current run and stay untouched.

    A run is only wrapped if it contains a visible bare text node.
    A lone inline container (``<small>``/``<ins>`` holding an entire
    wording block) keeps its line structure; the paragraph renderer
    would collapse its internal newlines into one line. ``<br>`` ends
    the run: an explicit line break (poll tallies, addresses) must not
    be collapsed into the surrounding text.
    """
    for bq in soup.find_all("blockquote"):
        run: list = []

        def _flush() -> None:
            if not run:
                return
            has_bare_text = any(
                isinstance(n, NavigableString)
                and not isinstance(n, Comment)
                and str(n).strip()
                for n in run
            )
            if has_bare_text:
                p = soup.new_tag("p")
                run[0].insert_before(p)
                for node in run:
                    p.append(node.extract())
            run.clear()

        for child in list(bq.children):
            if isinstance(child, NavigableString) or (
                isinstance(child, Tag) and child.name in _BARE_INLINE_TAGS
            ):
                run.append(child)
            else:
                _flush()
        _flush()


_EELIS_MARGIN_CLASS = "marginalizedparent"
_EELIS_CHROME_DIV_CLASSES = (_EELIS_MARGIN_CLASS, "sourceLinkParent")


_EELIS_WORDING_DIV_CLASSES = ["wording", "hana_wording"]
_EELIS_HEADING_DEMOTION = 2


def _remove_class_token(tag: Tag, token: str) -> None:
    """Drop one class token, keeping co-occurring classes intact."""
    classes = tag.get("class", [])
    if token in classes:
        classes.remove(token)
    if not classes and "class" in tag.attrs:
        del tag["class"]


def _texpara_number_index(target: Tag) -> int:
    """Index in ``target.contents`` where a folded paragraph number lands.

    A texpara can start with block children (a table, a nested sub-para);
    prepending the number there would strand it in its own wrapper when
    _fix_misnested_blocks later promotes the block out. Anchor the number
    before the first prose child instead: a non-empty text node, an inline
    tag, or a ``div.sentence`` (still a div at fold time, renamed to span
    later in this pass).
    """
    for i, child in enumerate(target.contents):
        if isinstance(child, NavigableString):
            if str(child).strip():
                return i
        elif isinstance(child, Tag):
            if child.name not in _BLOCK_TAGS:
                return i
            if "sentence" in (child.get("class") or []):
                return i
    return 0


def _normalize_eelis_wording(soup: BeautifulSoup) -> None:
    """Normalize eel.is-style standardese markup into renderable structure.

    Papers that paste wording from eel.is (or hana_wording derivatives) carry
    a div-per-sentence structure with navigation chrome that the generic div
    walk shreds into one paragraph per inline node. This pass rewrites that
    markup in place:

    - Headings inside ``div.wording``/``div.hana_wording`` demote by two
      levels (h1 -> h3, capped at h6) so clause titles nest under the
      paper's own section heading instead of colliding with the H1 title.
    - ``span.texttt`` (TeX monospace, e.g. header names like ``<memory>``)
      becomes ``<code>`` so the angle brackets survive as Markdown code
      spans instead of leaking as raw HTML tags.
    - ``span.codeblock`` (multi-line synopses) becomes ``<pre>`` with a
      ``<code class="cpp">`` child so the code renders as a highlighted
      fenced block instead of collapsing into prose.
    - Paragraph numbers from ``a.marginalized`` fold inline as a text prefix
      of their paragraph.
    - Navigation chrome (``div.marginalizedparent`` paragraph-number/link
      columns, ``div.sourceLinkParent`` GitHub ``#`` anchors) is dropped.
      This also removes the ``a.itemDeclLink`` link glyphs inside table cells.
    - ``div.sentence`` becomes ``<span>`` and ``div.texpara`` becomes ``<p>``
      so each prose paragraph renders as one coherent line.
    - The caption nodes of ``div.numberedTable`` ("Table 47 -- ...") wrap in
      one ``<p>`` instead of fragmenting per inline node.

    Gated on the presence of ``div.marginalizedparent``, which only this
    markup family produces. Documents without it are left untouched. The
    gate is document-wide on purpose: the renamed class names do not occur
    outside this family in the corpus, and region-scoping would miss
    wording fragments pasted outside a wording container.
    """
    margins = soup.find_all("div", class_=_EELIS_MARGIN_CLASS)
    if not margins:
        return

    # Demote wording-internal headings below the paper's own section
    # structure. The id-set guards against double demotion when
    # div.hana_wording nests inside div.wording.
    demoted: set[int] = set()
    for wording in soup.find_all("div", class_=_EELIS_WORDING_DIV_CLASSES):
        for heading in wording.find_all(_HEADING_TAGS):
            if id(heading) in demoted:
                continue
            demoted.add(id(heading))
            level = min(int(heading.name[1]) + _EELIS_HEADING_DEMOTION, 6)
            heading.name = f"h{level}"

    # Multi-line code synopses live in <span class='codeblock'> under
    # div.texpara, sometimes inside anonymous <span> wrappers. Rename to
    # <pre> with a code.cpp child so they render as highlighted fenced
    # blocks; _fix_misnested_blocks later promotes them out of the
    # paragraph that the texpara rename below creates.
    for span in soup.find_all("span", class_="codeblock"):
        if not span.get_text(strip=True) and span.find(True) is None:
            continue
        span.name = "pre"
        _remove_class_token(span, "codeblock")
        # _render_pre reads the code child via get_text(), which drops
        # <br> elements; materialize them as newlines first.
        for br in span.find_all("br"):
            br.replace_with("\n")
        code = soup.new_tag("code")
        code["class"] = ["cpp"]
        for child in list(span.children):
            code.append(child.extract())
        span.append(code)

    # Skip texttt runs inside the renamed <pre> blocks (their text is
    # already covered by the pre's code child) and texttt runs wrapping
    # a <pre> (a <code> ancestor would backtick-flatten the fence; the
    # span stays inline and the misnested-blocks repair promotes the
    # pre out of it).
    for span in soup.find_all("span", class_="texttt"):
        if span.find_parent("pre") is not None or span.find("pre") is not None:
            continue
        span.name = "code"
        _remove_class_token(span, "texttt")

    # Fidelity guard, before the number fold: content trapped inside a
    # chrome div (stray text, a misnested texpara) is rescued to siblings
    # after the div, where the fold below can still find and number it.
    for cls in _EELIS_CHROME_DIV_CLASSES:
        for div in soup.find_all("div", class_=cls):
            rescued = [
                child for child in list(div.contents)
                if (isinstance(child, Tag) and child.name != "a")
                or (isinstance(child, NavigableString) and str(child).strip())
            ]
            for child in reversed(rescued):
                div.insert_after(child.extract())

    # Fold paragraph and list-item numbers ("1", "(1.1)") into the content
    # they belong to. Prefer the sibling texpara (sibling-scoped on purpose:
    # a margin must not number a texpara nested in a following table or
    # sub-para, and a texpara takes at most one number). List items carry
    # their text as bare siblings of the margin, so margins inside a
    # content container (li, div.para) drop the number inline instead.
    # Margins with neither target lose their number along with the chrome.
    numbered: set[int] = set()
    for margin in margins:
        num_anchor = margin.find("a", class_="marginalized")
        number = num_anchor.get_text(strip=True) if num_anchor else ""
        if not number:
            continue
        parent = margin.parent
        in_content_container = isinstance(parent, Tag) and (
            parent.name == "li"
            or "para" in (parent.get("class") or [])
        )
        target = margin.find_next_sibling("div", class_="texpara")
        if target is not None and id(target) not in numbered:
            numbered.add(id(target))
            target.insert(_texpara_number_index(target), f"{number} ")
        elif in_content_container:
            # Padded on both sides: the margin can follow its content
            # (number as trailing marker), and whitespace collapse swallows
            # the extra space in the leading case.
            margin.insert_after(f" {number} ")

    for cls in _EELIS_CHROME_DIV_CLASSES:
        for div in soup.find_all("div", class_=cls):
            div.decompose()

    for div in soup.find_all("div", class_="sentence"):
        div.name = "span"
    for div in soup.find_all("div", class_="texpara"):
        div.name = "p"

    for div in soup.find_all("div", class_="numberedTable"):
        caption = soup.new_tag("p")
        for node in list(div.children):
            if isinstance(node, Tag) and node.name == "table":
                break
            caption.append(node.extract())
        if caption.get_text(strip=True) or caption.find(True) is not None:
            div.insert(0, caption)


def render_body(soup: BeautifulSoup, generator: str) -> str:
    """Render the HTML body to Markdown.

    Warning: this function may mutate the soup tree (extracting nested
    list elements). Do not reuse the soup object after calling this.
    """
    # Must run before _fix_misnested_blocks: the rename of div.texpara to
    # <p> can leave block children (tables, nested divs) inside the new
    # paragraph, which _fix_misnested_blocks then promotes to siblings.
    _normalize_eelis_wording(soup)
    _fix_misnested_blocks(soup)
    _fix_misnested_list_items(soup)
    _fix_misnested_table_cells(soup)
    _fix_misnested_dl_items(soup)
    _wrap_bare_blockquote_inline(soup)
    body = soup.find("body") or soup
    _normalize_heading_levels(body)
    parts: list[str] = []
    _render_children(body, parts, generator)
    return "\n\n".join(p for p in parts if p.strip())


def _normalize_heading_levels(body: Tag) -> None:
    """Shift body headings so the shallowest renders at H2.

    The front-matter contract reserves H1 for the document title, so body
    headings start at H2. HTML papers arrive both <h1>-rooted and <h2>-rooted,
    so shift every heading relative to the document's shallowest heading rather
    than applying a blanket offset (which would corrupt already-H2-rooted
    papers). Renaming the tags lets _render_heading pick up the shift through
    its existing int(el.name[1]) read.
    """
    headings = [
        el for el in body.find_all(list(_HEADING_TAGS))
        if _inline_text(el, _HEADING_EMPTY_CHECK_CLASSES).strip()
    ]
    if not headings:
        return
    offset = max(0, 2 - min(int(el.name[1]) for el in headings))
    if offset == 0:
        return
    for el in headings:
        level = min(int(el.name[1]) + offset, 6)
        el.name = f"h{level}"


def _render_children(element, parts: list[str], generator: str):
    """Render each child of element, appending Markdown strings to parts."""
    for child in element.children:
        # ProcessingInstruction is a NavigableString subclass, so an XML prolog
        # ("<?xml version=...?>", as shipped ahead of inline SVG) would otherwise
        # fall through to the text branch below and leak into the body.
        if isinstance(child, (Comment, ProcessingInstruction)):
            continue
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                parts.append(text)
        elif isinstance(child, Tag):
            rendered = _render_element(child, generator)
            if rendered is not None:
                parts.append(rendered)


def _render_element(el: Tag, generator: str) -> str | None:
    """Render a single HTML element to Markdown."""
    tag = el.name

    if tag in ("style", "script", "link", "meta", "head"):
        return None

    # An <svg> subtree is foreign-namespace vector geometry, not HTML content.
    # Walking it shreds every <text>/<tspan> into a standalone paragraph in draw
    # order with all geometry lost, so drop the subtree. Text-bearing figures
    # disclose the loss; decorative icon SVGs extract nothing either way.
    if tag == "svg":
        if any(t.get_text(strip=True) for t in el.find_all(("text", "tspan"))):
            return _DROPPED_SVG_MARKER
        return None

    if tag in _HEADING_TAGS:
        return _render_heading(el)

    if tag == "p":
        return _render_paragraph(el)

    if tag == "pre":
        return _render_pre(el)

    if tag == "code-block":
        return _render_code_block_custom(el)

    if tag == "div":
        return _render_div(el, generator)

    if tag == "ul":
        return _render_list(el, "-", generator)

    if tag == "ol":
        return _render_list(el, "1.", generator)

    if tag == "table":
        return _render_table(el)

    if tag == "img":
        # Images never reach markdown (#408): the LLM consumer cannot use
        # pixels. Visible captions (<figcaption>, inline text) render via
        # the normal DOM walk; the alt attribute is dropped with the tag.
        return None

    if tag == "blockquote":
        return _render_blockquote(el, generator)

    if tag == "dl":
        return _render_dl(el, generator)

    if tag == "hr":
        return "---"

    if tag == "section":
        parts: list[str] = []
        _render_children(el, parts, generator)
        return "\n\n".join(p for p in parts if p.strip())

    if tag in ("main", "article", "aside", "figure", "figcaption",
               "header", "footer", "nav", "details", "summary"):
        parts = []
        _render_children(el, parts, generator)
        return "\n\n".join(p for p in parts if p.strip())

    if tag in ("example-block", "note-block", "bug-block"):
        parts = []
        _render_children(el, parts, generator)
        inner = "\n\n".join(p for p in parts if p.strip())
        if inner:
            return "> " + inner.replace("\n", "\n> ")
        return None

    if tag == "abstract-block":
        parts = []
        _render_children(el, parts, generator)
        inner = "\n\n".join(p for p in parts if p.strip())
        if inner:
            return f"## Abstract\n\n{inner}"
        return None

    if tag == "tt-":
        text = el.get_text()
        return f"`{text}`" if text.strip() else None

    if tag == "code":
        if generator == "hatemplate" and "itemdeclcode" in (el.get("class") or []):
            text = el.get_text().strip("\n")
            return f"```cpp\n{text}\n```" if text.strip() else None
        code_div = el.find("div", class_="code")
        if code_div:
            text = code_div.get_text()
            text = text.strip("\n")
            return f"```cpp\n{text}\n```"

    if tag in _INLINE_RENDER_TAGS:
        return _render_inline(el)

    parts = []
    _render_children(el, parts, generator)
    result = "\n\n".join(p for p in parts if p.strip())
    return result if result else None


_HEADING_SKIP_CLASSES = frozenset({"self-link"})
# Emptiness gate stays number-blind: a heading whose only content is a clause
# number must not flip from dropped to real (would corrupt H2-root normalization).
_HEADING_EMPTY_CHECK_CLASSES = frozenset({"header-section-number", "secno", "self-link"})


def _render_heading(el: Tag) -> str | None:
    """Render a heading element to ATX Markdown."""
    if len(el.name) < 2 or not el.name[1].isdigit():
        return ""
    level = int(el.name[1])
    if not _inline_text(el, _HEADING_EMPTY_CHECK_CLASSES).strip():
        return None
    text = _inline_text(el, _HEADING_SKIP_CLASSES).strip()
    if not text:
        return None
    text = text.replace("\n", " ")
    text = re.sub(r"  +", " ", text)
    text = _BOLD_WRAP_RE.sub(r"\1", text)
    return f"{'#' * level} {text}"


def _is_code_paragraph(el: Tag) -> bool:
    """True if <p> contains only <span class="code"> children.

    The dascandy/fiets generator uses this pattern for standalone code
    declarations (e.g. constructor signatures). These should be emitted
    as fenced code blocks, not flattened to prose paragraphs.

    Targets <span class="code"> specifically, NOT <code> which is inline
    formatting in Bikeshed and other generators.
    """
    has_code_span = False
    for child in el.children:
        if isinstance(child, NavigableString):
            if child.strip():
                return False
        elif child.name == "span" and "code" in (child.get("class") or []):
            has_code_span = True
        else:
            return False
    return has_code_span


def _render_paragraph(el: Tag) -> str | None:
    """Render a paragraph to a single unwrapped line."""
    if _is_code_paragraph(el):
        text = el.get_text().strip()
        return f"```cpp\n{text}\n```" if text else None
    text = _collapse_whitespace(_inline_text(el))
    return text if text else None


def _collapse_whitespace(text: str) -> str:
    """Collapse runs of whitespace to single spaces, strip format chars."""
    text = strip_format_chars(text)
    return _COLLAPSE_WS_RE.sub(" ", text).strip()


# WG21 papers are C++ by default: a classless code block with no non-C++
# signal is labeled ``cpp`` so downstream pipelines (dissect/agora) can parse
# it as code. The default is conservative (issue #297): recognized non-C++/
# neutral classes and obvious non-C++ classless shapes are NOT relabeled
# ``cpp``, since the defect being fixed is false ``cpp`` labels. The recognized
# language set is shared with the PDF detector (``CODE_LANG_LABELS``).
_WG21_DEFAULT_CODE_LANG = "cpp"

# Recognized CSS classes that carry no programming language: prose/data,
# grammar, and ASCII-diagram blocks. A code element wearing one emits an
# unlabeled fence rather than a false ``cpp`` (corpus-observed on ``text``,
# ``txt``, ``ebnf``, ``diagram`` blocks). ``swift`` and other real languages
# stay in ``CODE_LANG_LABELS`` and are labeled with their own name.
_NEUTRAL_CODE_CLASSES = frozenset({"text", "txt", "ebnf", "diagram"})

# Classless-block content heuristics (high precision, avoid unlabeling real
# C++). Shell/console: a ``$`` prompt, a shebang, a ``git log`` transcript
# header, or a line-leading non-ambiguous shell command. JSON/data: an object
# or array. Grammar: a BNF ``::=`` rule.
_SHELL_PROMPT_RE = re.compile(r"^\s*\$ ")
_SHELL_COMMAND_RE = re.compile(
    r"^\s*(?:sudo\s+)?(?:git|cd|mkdir|rmdir|apt|apt-get|yum|dnf|brew|cmake|"
    r"curl|wget|chmod|chown|tar|unzip|ssh|scp|pip|pip3|npm|yarn|docker|"
    r"kubectl|gcc|clang\+\+|clang|g\+\+)(?:\s|$)"
)
_GIT_TRANSCRIPT_RE = re.compile(r"^\s*(?:commit [0-9a-f]{7,40}\b|Author:\s|Date:\s)")
# Line-anchored so it matches a pretty-printed JSON key, not any quoted string
# followed by a colon: an unanchored search fires on the everyday C++ ternary
# ``flag ? "yes" : "no"`` and unlabels real C++.
_JSON_KEY_RE = re.compile(r'^\s*"[^"]*"\s*:', re.MULTILINE)
_GRAMMAR_RULE_RE = re.compile(r"::=")

# A block of >= this many ``$``-prompt lines is a shell/console transcript
# even when the first line is preamble prose.
_MIN_SHELL_PROMPT_LINES = 2

# ASCII box border, e.g. ``+--------+`` or ``+----+----+``: only box-rule
# characters, with at least two corners and a run of rules. ``is_diagram_block``
# cannot see these (it requires ``|``/``\`` on the line and rejects any letter,
# so a box with a label inside it escapes detection entirely), and real C++
# never produces the shape.
_BOX_BORDER_CHARS = frozenset("+-= ")
_BOX_BORDER_RULE_CHARS = "-="
_BOX_BORDER_MIN_CORNERS = 2
_BOX_BORDER_MIN_RULES = 3


def _resolve_lang_token(token: str) -> str | None:
    """Map a lowercased language token to a fence lang, "" (neutral), or None.

    Returns ``""`` for a recognized neutral/non-code class (kept unlabeled),
    the canonical fence language for a recognized language, or ``None`` when
    the token is not recognized.
    """
    if token in _NEUTRAL_CODE_CLASSES:
        return ""
    return CODE_LANG_LABELS.get(token)


def _resolve_explicit_lang(token: str) -> str:
    """Resolve an author-declared token (``language-*`` / ``sourceCode*``).

    An unrecognized declaration is honored verbatim: an explicit class is the
    author's statement of intent, so ``language-fortran`` stays ``fortran``.
    """
    resolved = _resolve_lang_token(token)
    return resolved if resolved is not None else token


def _lang_from_classes(classes: list[str]) -> str | None:
    """Resolve a code-fence language from a code element's CSS classes.

    Returns the fence language for a recognized language class, ``""`` for a
    recognized neutral/non-code class (prose, grammar, diagram) that must stay
    unlabeled, or ``None`` when no class is recognized (the caller then applies
    the content heuristic / cpp default). A bare class token counts only when
    it is a recognized language or neutral class, so styling classes such as
    ``highlight`` do not suppress detection on a sibling ``language-*`` class.
    """
    for cls in classes:
        if cls.startswith("sourceCode"):
            token = cls[len("sourceCode"):].lower()
            if token:
                return _resolve_explicit_lang(token)
            continue
        if cls.startswith("language-"):
            return _resolve_explicit_lang(cls[len("language-"):].lower())
        resolved = _resolve_lang_token(cls.lower())
        if resolved is not None:
            return resolved
    return None


def _looks_like_shell(text: str) -> bool:
    """True for an obvious shell/console/git transcript classless block."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return False
    first = lines[0]
    if first.lstrip().startswith("#!"):
        return True
    if _GIT_TRANSCRIPT_RE.match(first):
        return True
    if _SHELL_PROMPT_RE.match(first) or _SHELL_COMMAND_RE.match(first):
        return True
    prompt_lines = sum(1 for ln in lines if _SHELL_PROMPT_RE.match(ln))
    return prompt_lines >= _MIN_SHELL_PROMPT_LINES


def _looks_like_json(text: str) -> bool:
    """True for an obvious JSON/data classless block."""
    stripped = text.strip()
    if not stripped or stripped[0] not in "{[":
        return False
    try:
        parsed = json.loads(stripped)
    except (ValueError, RecursionError):
        parsed = None
    if isinstance(parsed, dict):
        return True
    if isinstance(parsed, list) and any(isinstance(x, (dict, str)) for x in parsed):
        return True
    # JSON with comments or trailing commas will not parse; a brace-opened
    # block with quoted keys is still a strong structural signal.
    return stripped[0] == "{" and _JSON_KEY_RE.search(stripped) is not None


def _looks_like_grammar(text: str) -> bool:
    """True for a BNF/EBNF grammar block (``::=`` production rule)."""
    return _GRAMMAR_RULE_RE.search(text) is not None


def _is_box_border_line(line: str) -> bool:
    """True for an ASCII box border line such as ``+--------+``."""
    stripped = line.strip()
    if not stripped or not all(ch in _BOX_BORDER_CHARS for ch in stripped):
        return False
    rules = sum(1 for ch in stripped if ch in _BOX_BORDER_RULE_CHARS)
    return (
        stripped.count("+") >= _BOX_BORDER_MIN_CORNERS
        and rules >= _BOX_BORDER_MIN_RULES
    )


def _looks_like_diagram(text: str) -> bool:
    """True for a text ASCII diagram (box-drawing / arrows / box / pipe-art).

    ``math_symbols=False``: ``§`` is WG21's clause-reference symbol and appears
    in ordinary C++ comments, so it must not unlabel a block.
    """
    lines = text.splitlines()
    if any(_is_box_border_line(ln) for ln in lines):
        return True
    return is_diagram_block(lines, math_symbols=False)


def _lang_from_content(text: str) -> str:
    """Pick a fence language for a classless code block.

    WG21 papers are C++ by default, so an ambiguous classless block is
    ``cpp``. Obvious non-C++ shapes (shell/console, JSON/data, grammar, ASCII
    diagrams) are detected first and left unlabeled rather than mislabeled.
    """
    if (
        _looks_like_shell(text)
        or _looks_like_json(text)
        or _looks_like_grammar(text)
        or _looks_like_diagram(text)
    ):
        return ""
    return _WG21_DEFAULT_CODE_LANG


def _render_pre(el: Tag) -> str:
    """Render a preformatted block as a fenced code block."""
    code_el = el.find("code")
    source = code_el or el
    lang = _detect_code_language(source)
    text = source.get_text().strip("\n")
    return f"```{lang}\n{text}\n```"


def _render_code_block_custom(el: Tag) -> str:
    """Render a <code-block> custom element (Jan Schultke's generator) as fenced code."""
    text = el.get_text()
    text = text.strip("\n")
    return f"```cpp\n{text}\n```"


def _detect_code_language(el: Tag) -> str:
    """Detect the fenced-code language for a ``<pre>``/``<code>`` element.

    An explicit language class on the element (or, for a ``<code>``, its parent
    ``<pre>``) wins, mapping recognized languages to their fence name and
    recognized neutral classes (``text``, ``ebnf``, ``diagram``, ...) to an
    unlabeled fence. Absent a recognized class, the block's content is
    inspected: obvious non-C++ shapes stay unlabeled and everything else falls
    back to the WG21 ``cpp`` default.
    """
    lang = _lang_from_classes(el.get("class", []))
    if lang is None and el.name == "code":
        parent = el.parent
        if parent and parent.name == "pre":
            lang = _lang_from_classes(parent.get("class", []))
    if lang is not None:
        return lang
    return _lang_from_content(el.get_text())


def _render_div(el: Tag, generator: str) -> str | None:
    """Render a div - dispatch by class."""
    classes = el.get("class", [])

    if "sourceCode" in classes:
        pre = el.find("pre")
        if pre:
            return _render_pre(pre)

    if "code" in classes:
        text = el.get_text()
        text = text.strip("\n")
        return f"```cpp\n{text}\n```"

    if any(c in classes for c in ("note", "example", "advisement")):
        parts = []
        _render_children(el, parts, generator)
        inner = "\n\n".join(p for p in parts if p.strip())
        if inner:
            return "> " + inner.replace("\n", "\n> ")

    if any(c in classes for c in ("wording", "wording-add", "wording-remove")):
        return _render_wording_div(el, generator)

    if generator == "hatemplate" and any(
        c in classes for c in ("para", "texpara", "sentence")
    ):
        return _render_eelis_block(el, generator)

    parts = []
    _render_children(el, parts, generator)
    result = "\n\n".join(p for p in parts if p.strip())
    return result if result else None


def _render_wording_div(el: Tag, generator: str) -> str:
    """Render a wording section's content, without a Pandoc fenced div.

    The div wrapper was noise in the output, so only its *role* is used,
    and only to decide whether the content's own inline ``<ins>`` /
    ``<del>`` tags are redundant with it (``lib.wording_cleanup``).
    """
    classes = el.get("class", [])
    # Class-selection precedence stays local. Do not reorder these.
    if "wording-add" in classes:
        div_class = "wording-add"
    elif "wording-remove" in classes:
        div_class = "wording-remove"
    else:
        div_class = "wording"
    parts = []
    _render_children(el, parts, generator)
    inner = "\n\n".join(p for p in parts if p.strip())
    return strip_redundant_tags(div_class, inner)


def _render_eelis_block(el: Tag, generator: str) -> str | None:
    """Render an eelis/draft (hatemplate) wording block.

    The .para / .texpara / .sentence divs are block-level wrappers around
    inline prose or a code synopsis. A synopsis (span.codeblock or <pre>)
    is fenced as C++; sentence prose is flowed into a single paragraph.
    Margin chrome (paragraph numbers, source links) is already removed by
    strip_boilerplate.
    """
    code = el.find("span", class_="codeblock") or el.find("pre")
    if code:
        text = code.get_text().strip("\n")
        return f"```cpp\n{text}\n```" if text.strip() else None
    # Sentences (and itemized sub-paragraphs) are block-level divs that abut
    # without whitespace; flow them as prose with a separating space so they
    # do not merge ("maximum limit.When limits..."). _collapse_whitespace
    # folds the resulting double spaces.
    for sentence in el.find_all("div", class_="sentence"):
        sentence.append(" ")
    text = _collapse_whitespace(_inline_text(el))
    return text or None


_CODE_BLOCK_TAGS = frozenset({"pre", "code-block"})

# Block-level tags that, inside an <li>, become indented continuation blocks
# rather than being flattened into the item label. Derived from _BLOCK_TAGS so
# the two cannot silently drift; the deltas are deliberate:
#   + code-block : Schultke custom code element, block-level here too
#   - headings   : a heading inside an <li> stays in the inline label (current
#                  behavior; headings-in-list-items are not real structure)
#   - section    : transparent wrapper; let its children flatten as today
#   - hr         : a rule inside an <li> has no continuation meaning (current
#                  behavior already drops it)
_LIST_ITEM_BLOCK_TAGS = (
    (_BLOCK_TAGS | {"code-block"}) - _HEADING_TAGS - {"section", "hr"}
)


def _indent(text: str, width: int = 2) -> str:
    """Indent every line by ``width`` spaces (list-continuation depth).

    Default 2 is the bullet-marker content column; ordered items pass their own
    marker width (``len(prefix) + 1``) so continuation blocks nest under the
    item instead of detaching.
    """
    pad = " " * width
    return "\n".join(pad + line for line in text.split("\n"))


def _render_list_item(li: Tag, prefix: str, generator: str) -> list[str]:
    """Render one ``<li>`` as a label line plus indented continuation blocks,
    preserving document order.

    The label is the leading inline run (text + inline tags, and a leading
    ``<p>``). The first block element and everything after it become indented
    continuation blocks in source order; inline text interleaved with or
    trailing those blocks becomes its own continuation paragraph, so it is
    neither merged into the label nor silently dropped. A nested list
    continuation stays tight (no blank line, matching today's sublist output);
    other blocks get a blank line so siblings do not lazily merge. Blocks are
    indented to the item's marker width so they nest under it.
    """
    width = len(prefix) + 1   # marker content column: '-' -> 2, '1.' -> 3
    label_run: list = []      # leading inline nodes
    trailing: list = []       # nodes from the first block onward, in order
    seen_block = False
    leading_p_used = False
    for child in list(li.children):
        is_block = isinstance(child, Tag) and child.name in _LIST_ITEM_BLOCK_TAGS
        if is_block and child.name == "p" and not seen_block and not leading_p_used:
            leading_p_used = True          # leading <p> is part of the label
            label_run.append(child)
            continue
        if is_block:
            seen_block = True
        (trailing if seen_block else label_run).append(child)

    label = _collapse_whitespace(_inline_text_nodes(label_run)).strip()

    cont: list[tuple[bool, str]] = []
    run: list = []

    def _flush_run() -> None:
        if run:
            txt = _collapse_whitespace(_inline_text_nodes(run)).strip()
            if txt:
                cont.append((False, _indent(txt, width)))
            run.clear()

    for node in trailing:
        if isinstance(node, Tag) and node.name in _LIST_ITEM_BLOCK_TAGS:
            _flush_run()
            rendered = _render_element(node, generator)
            if rendered:
                is_tight = node.name in _LIST_CONTAINER_TAGS   # nested <ol>/<ul>
                cont.append((is_tight, _indent(rendered, width)))
        else:
            run.append(node)
    _flush_run()

    lines: list[str] = []
    if label:
        lines.append(f"{prefix} {label}")
    elif cont:
        lines.append(prefix)             # bare marker; blocks follow indented
    for i, (is_tight, block) in enumerate(cont):
        # A blank line before the FIRST continuation of a label-less item would
        # trip CommonMark's "list item begins with a blank line" rule, producing
        # an empty item + a detached block. Suppress it there; with a label, or
        # for later continuations, the blank is correct and needed.
        if not is_tight and not (i == 0 and not label):
            lines.append("")
        lines.append(block)
    return lines


def _render_list(el: Tag, marker: str, generator: str) -> str | None:
    """Render an ordered or unordered list.

    Direct ``<li>`` children become list items (see ``_render_list_item``: a
    label plus document-order continuation blocks). Any other direct child (a
    nested list with no wrapping ``<li>``, or a loose
    ``<p>``/``<pre>``/``<blockquote>``/text) is a continuation of the preceding
    item, indented to that item's marker width and blank-line separated unless
    it is a nested list, rather than silently dropped; before the first item it
    is emitted standalone. Only ``<li>`` advances the item counter, so
    interspersed children do not perturb ordered-list numbering.
    """
    items: list[str] = []
    item_index = 0
    last_width = 2          # default; set by each <li>, read by trailing children
    # Materialize: _render_element may mutate descendants during iteration.
    for child in list(el.children):
        if isinstance(child, Tag) and child.name == "li":
            item_index += 1
            prefix = f"{item_index}." if marker == "1." else "-"
            last_width = len(prefix) + 1
            items.extend(_render_list_item(child, prefix, generator))
        elif isinstance(child, Tag):
            # Non-<li> direct child: a continuation of the preceding item (or
            # standalone before the first item).
            rendered = _render_element(child, generator)
            if rendered:
                if item_index:
                    if child.name not in _LIST_CONTAINER_TAGS:
                        items.append("")
                    items.append(_indent(rendered, last_width))
                else:
                    items.append(rendered)
        elif isinstance(child, NavigableString) and not isinstance(child, (Comment, CData)):
            text = _collapse_whitespace(str(child)).strip()
            if text:
                if item_index:
                    items.append("")
                    items.append(_indent(text, last_width))
                else:
                    items.append(text)
    return "\n".join(items) if items else None


def _has_spans(el: Tag) -> bool:
    """Return True if any cell uses colspan or rowspan."""
    for cell in el.find_all(["th", "td"]):
        if cell.get("colspan") or cell.get("rowspan"):
            return True
    return False



_BR_MULTILINE_MIN_CELLS = 2

def _has_br_multiline_cells(el: Tag) -> bool:
    """True when enough cells contain direct-child <br>, making pipe-table lossy."""
    count = 0
    for cell in el.find_all(["td", "th"]):
        if cell.find("br", recursive=False):
            count += 1
            if count >= _BR_MULTILINE_MIN_CELLS:
                return True
    return False


def _needs_flat_reconstruction(el: Tag) -> bool:
    """Return True for tables that need the descendant-walking flat path.

    This covers: nested <table> elements, parser-mangled nested cells,
    and block-level content inside cells.
    """
    if el.find("table"):
        return True
    for cell in el.find_all(["th", "td"]):
        if cell.find(["th", "td"]):
            return True
        if cell.find(["ol", "ul", "blockquote"]):
            return True
        if cell.find("p") and len(cell.find_all("p")) > 1:
            return True
    return False




def _cell_own_text(cell: Tag) -> str:
    """Get text directly owned by a cell, excluding nested cells/rows."""
    parts = []
    for child in cell.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag) and child.name not in ("td", "th", "tr",
                                                            "thead", "tbody",
                                                            "tfoot", "table"):
            parts.append(child.get_text(" ", strip=True))
    return " ".join(parts).strip()


def _denormalize_table(el: Tag) -> list[list[str]]:
    """Expand rowspan/colspan into a flat rectangular grid of cell texts.

    Two-pass algorithm: builds a None-initialized 2D matrix, then fills it
    by walking <tr> elements and tracking pending rowspans per column.
    """
    trs = []
    containers = el.find_all(["thead", "tbody", "tfoot"], recursive=False)
    if containers:
        for c in containers:
            trs.extend(c.find_all("tr", recursive=False))
    else:
        trs = el.find_all("tr", recursive=False)

    if not trs:
        return []

    # First pass: determine grid dimensions
    max_cols = 0
    for tr in trs:
        col_count = 0
        for cell in tr.find_all(["th", "td"], recursive=False):
            try:
                col_count += int(cell.get("colspan", 1))
            except (ValueError, TypeError):
                col_count += 1
        if col_count > max_cols:
            max_cols = col_count
    num_rows = len(trs)

    if max_cols == 0:
        return []

    grid: list[list[str | None]] = [[None] * max_cols for _ in range(num_rows)]

    # Second pass: fill the grid
    for row_idx, tr in enumerate(trs):
        col_idx = 0
        for cell in tr.find_all(["th", "td"], recursive=False):
            # Skip columns already filled by previous rowspans
            while col_idx < max_cols and grid[row_idx][col_idx] is not None:
                col_idx += 1
            if col_idx >= max_cols:
                break

            text = _inline_text(cell).strip().replace("|", "\\|")
            text = _COLLAPSE_WS_RE.sub(" ", text)
            try:
                rs = int(cell.get("rowspan", 1))
            except (ValueError, TypeError):
                rs = 1
            try:
                cs = int(cell.get("colspan", 1))
            except (ValueError, TypeError):
                cs = 1

            for dr in range(rs):
                for dc in range(cs):
                    r, c = row_idx + dr, col_idx + dc
                    if r < num_rows and c < max_cols:
                        grid[r][c] = text

            col_idx += cs

    # Replace any remaining None with empty string
    return [[cell if cell is not None else "" for cell in row] for row in grid]


def _render_denormalized_table(el: Tag) -> str | None:
    """Render a table with rowspan/colspan as a flat denormalized pipe table."""
    rows = _denormalize_table(el)
    if not rows:
        return None

    num_cols = max(len(r) for r in rows)
    for r in rows:
        while len(r) < num_cols:
            r.append("")

    headers = [_BOLD_WRAP_RE.sub(r"\1", cell) for cell in rows[0]]

    lines = [_LOSSY_TABLE_MARKER]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * num_cols) + " |")
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _render_table_flat(el: Tag) -> str:
    """Render a table as a pipe table, handling parser-mangled DOM.

    When html.parser has mangled the tree (nested cells due to missing
    closing tags), we collect ALL <td>/<th> descendants in document order,
    extract their direct text via _cell_own_text, and use <tr> boundaries
    to reconstruct rows. Output is a standard Markdown pipe table.
    """
    all_cells = el.find_all(["td", "th"])

    if not all_cells:
        return el.get_text(" ", strip=True)

    rows: list[list[str]] = []
    current_row: list[str] = []

    seen: set[int] = set()
    for node in el.descendants:
        if not isinstance(node, Tag):
            continue
        if node.name == "tr" and current_row:
            rows.append(current_row)
            current_row = []
        elif node.name in ("td", "th"):
            nid = id(node)
            if nid in seen:
                continue
            seen.add(nid)
            text = _cell_own_text(node)
            text = _COLLAPSE_WS_RE.sub(" ", text).strip().replace("|", "\\|")
            current_row.append(text)
    if current_row:
        rows.append(current_row)

    if not rows:
        return el.get_text(" ", strip=True)

    num_cols = max(len(r) for r in rows)
    for r in rows:
        while len(r) < num_cols:
            r.append("")

    headers = [_BOLD_WRAP_RE.sub(r"\1", cell) for cell in rows[0]]

    lines = [_LOSSY_TABLE_MARKER]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * num_cols) + " |")
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _is_pure_code_table(el: Tag) -> bool:
    """Return True when the table is a headerless pure code dump.

    A table qualifies as pure code only when ALL of:
    1. It has no ``<th>`` header cells (no column labels to preserve).
    2. Every ``<td>`` data cell contains ``<pre>`` or ``<code-block>``.

    Tables with headers always go to the mixed renderer so that
    Before/After, Current/Proposed, and other comparison labels
    are preserved in the output.
    """
    if el.find("th"):
        return False
    td_cells = el.find_all("td")
    if not td_cells:
        return True
    return all(td.find(list(_CODE_BLOCK_TAGS)) for td in td_cells)


_ALLOWED_CELL_TAGS = frozenset({
    "a", "ins", "del", "em", "strong", "b", "i", "code",
    "sub", "sup", "br", "span", "mark", "s", "u",
})


def _cell_inner_html(cell: Tag) -> str:
    """Return sanitized inner HTML for a non-code table cell.

    Keeps safe inline tags (links, ins/del, emphasis) as HTML so they
    render correctly inside an HTML table. Strips all other tags but
    keeps their text content. Text nodes are HTML-escaped.
    """
    parts: list[str] = []
    for child in cell.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            parts.append(_html.escape(str(child)))
        elif isinstance(child, Tag):
            if child.name in _ALLOWED_CELL_TAGS:
                # An allowed inline wrapper (<span>, <a>, ...) can nest
                # <img>; str(child) would serialize the raw tag - and a
                # data: URI - into the cell. Images never reach
                # markdown (#408). Mutating the tree is safe here:
                # image extraction runs before rendering.
                for img in child.find_all("img"):
                    img.decompose()
                parts.append(str(child))
            else:
                parts.append(_html.escape(child.get_text()))
    return _COLLAPSE_WS_RE.sub(" ", "".join(parts)).strip()


def _render_mixed_code_table(el: Tag) -> str | None:
    """Render a table with mixed code and text cells as an HTML table.

    Preserves tabular structure with ``<pre><code>`` for code cells and
    plain escaped text for non-code cells. Keeps headers, row associations,
    and non-code content (checkmarks, status, URLs) that ``_render_code_table``
    would discard.
    """
    trs = []
    containers = el.find_all(["thead", "tbody", "tfoot"], recursive=False)
    if containers:
        for container in containers:
            trs.extend(container.find_all("tr", recursive=False))
    else:
        trs = el.find_all("tr", recursive=False)

    if not trs:
        return None

    num_cols = max(
        len(tr.find_all(["td", "th"], recursive=False)) for tr in trs
    )
    if num_cols == 0:
        return None

    # Shared markup (table tag, cell style, <pre><code> wrapping) lives in
    # lib/tables.py so HTML and PDF comparison tables render identically.
    style = _tables.cell_style(num_cols)
    parts: list[str] = [_tables.MIXED_TABLE_MARKER, _tables.TABLE_OPEN]

    for tr in trs:
        parts.append("<tr>")
        cells = tr.find_all(["td", "th"], recursive=False)
        for cell in cells:
            tag = cell.name
            code_el = cell.find(list(_CODE_BLOCK_TAGS))
            if code_el:
                parts.append(
                    _tables.code_cell(tag, code_el.get_text().strip(), style))
            else:
                parts.append(
                    _tables.text_cell(tag, _cell_inner_html(cell), style))
        parts.append("</tr>")

    parts.append(_tables.TABLE_CLOSE)
    return "\n".join(parts)


def _render_table(el: Tag) -> str | None:
    """Render a table as a Markdown pipe table.

    Tables whose cells contain <pre> or <code-block> elements are routed
    based on code-cell ratio: pure code tables (>=80% code data cells) go
    to ``_render_code_table``; mixed-content tables go to
    ``_render_mixed_code_table`` which preserves tabular structure.

    Tables with rowspan/colspan are denormalized into flat pipe tables.
    Tables with parser-mangled DOM (nested cells from unclosed tags) are
    reconstructed via descendant walking. Only tables with nested <table>
    elements or block-level cell content (pre, lists) fall back to the
    flat reconstruction path.
    """
    if el.find(_CODE_BLOCK_TAGS):
        if _is_pure_code_table(el):
            return _render_code_table(el)
        return _render_mixed_code_table(el)

    if _needs_flat_reconstruction(el):
        return _render_table_flat(el)

    if _has_spans(el):
        return _render_denormalized_table(el)

    if _has_br_multiline_cells(el):
        return _render_mixed_code_table(el)

    rows: list[list[str]] = []
    containers = el.find_all(["thead", "tbody", "tfoot"], recursive=False)
    if containers:
        tr_sources = containers
    else:
        tr_sources = [el]
    for src in tr_sources:
        for tr in src.find_all("tr", recursive=False):
            cells = []
            for td in tr.find_all(["th", "td"], recursive=False):
                cell_text = _inline_text(td).strip()
                cell_text = _COLLAPSE_WS_RE.sub(" ", cell_text)
                cells.append(cell_text.replace("|", "\\|"))
            if cells:
                rows.append(cells)

    if not rows:
        return None

    num_cols = max(len(r) for r in rows)
    for r in rows:
        while len(r) < num_cols:
            r.append("")

    headers = [_BOLD_WRAP_RE.sub(r"\1", cell) for cell in rows[0]]

    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * num_cols) + " |")
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _render_code_table(el: Tag) -> str | None:
    """Extract fenced code blocks from a table containing <pre> or <code-block>.

    Only reached for headerless pure-code tables (``_is_pure_code_table``);
    headered comparison tables go to ``_render_mixed_code_table``, which
    preserves the column labels and row structure. Here every non-empty block
    is emitted as its own fenced block behind a <!-- tomd:lossy-table -->
    marker.
    """
    blocks: list[str] = []
    for cb in el.find_all(_CODE_BLOCK_TAGS):
        text = cb.get_text().strip()
        if text:
            blocks.append(f"```cpp\n{text}\n```")
    if not blocks:
        return None
    return _LOSSY_TABLE_MARKER + "\n\n" + "\n\n".join(blocks)


def _render_blockquote(el: Tag, generator: str) -> str | None:
    """Render a blockquote with > prefix."""
    parts = []
    _render_children(el, parts, generator)
    inner = "\n\n".join(p for p in parts if p.strip())
    if not inner:
        return None
    return "> " + inner.replace("\n", "\n> ")


def _render_dl(el: Tag, generator: str) -> str | None:
    """Render a definition list as blank-line-separated entries.

    Each ``<dt>`` starts a new entry; the following ``<dd>`` (plus any
    extracted non-recursive code blocks) and loose text/other children
    attach to the current entry. Lines within an entry join with a single
    newline; entries are separated by a blank line. Comment/CData are not
    content.
    """
    entries: list[list[str]] = []
    current: list[str] = []

    def _flush() -> None:
        nonlocal current
        if current:
            entries.append(current)
        current = []

    for child in list(el.children):
        if not isinstance(child, Tag):
            if (isinstance(child, NavigableString)
                    and not isinstance(child, (Comment, CData))):
                text = _collapse_whitespace(str(child)).strip()
                if text:
                    current.append(text)
            continue
        if child.name == "dt":
            text = _inline_text(child).strip()
            _flush()
            if text:
                current.append(f"**{text}**")
        elif child.name == "dd":
            code_parts = []
            for cb in child.find_all(_CODE_BLOCK_TAGS, recursive=False):
                rendered = _render_element(cb.extract(), generator)
                if rendered:
                    code_parts.append(rendered)
            text = _inline_text(child).strip()
            if text:
                current.append(f": {text}")
            current.extend(code_parts)
        else:
            rendered = _render_element(child, generator)
            if rendered:
                current.append(rendered)
    _flush()

    if not entries:
        return None
    return "\n\n".join("\n".join(entry) for entry in entries)


def _render_inline(el: Tag) -> str:
    """Render an inline element."""
    return _inline_text(el)


def _inline_text(el: Tag, skip_classes: frozenset[str] = frozenset()) -> str:
    """Convert an element's content to inline Markdown text.

    `skip_classes` drops direct children carrying any of those classes (used
    by headings to strip section-number and self-link spans) while preserving
    inline formatting such as <code> on the remaining children.
    """
    return _inline_text_nodes(el.children, skip_classes)


def _inline_text_nodes(nodes, skip_classes: frozenset[str] = frozenset()) -> str:
    """Render a sequence of nodes (an element's children, or a contiguous
    subset of them) as inline Markdown text.

    Contributions are concatenated with no separator; the source's own
    whitespace text nodes carry the spacing, so rendering a run node-by-node
    matches ``_inline_text`` over the whole element exactly.

    `skip_classes` drops direct children carrying any of those classes (used
    by headings to strip section-number and self-link spans).
    """
    parts = []
    for child in nodes:
        if isinstance(child, (Comment, ProcessingInstruction)):
            continue
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag):
            tag = child.name

            if skip_classes and skip_classes.intersection(child.get("class") or []):
                continue

            if tag in ("style", "script"):
                continue

            # <svg> is phrasing content, so it reaches here from a <p>, <li>,
            # heading, cell or <a>, bypassing the block-level drop. No marker:
            # one would corrupt heading text and table cells.
            if tag == "svg":
                continue

            if tag in ("table", "thead", "tbody", "tfoot", "tr"):
                parts.append(child.get_text(" ", strip=True))
                continue

            inner = _inline_text(child)

            if tag == "code":
                stripped = inner.strip()
                if stripped:
                    parts.append(f"`{stripped}`")
                continue

            if tag in ("strong", "b"):
                stripped = inner.strip()
                if stripped:
                    parts.append(f"**{stripped}**")
                continue

            if tag in ("em", "i"):
                stripped = inner.strip()
                if stripped:
                    parts.append(f"*{stripped}*")
                continue

            if tag == "a":
                href = child.get("href", "")
                text = inner.strip()
                if href and text:
                    if href.startswith("#"):
                        parts.append(text)
                    else:
                        scheme = urllib.parse.urlparse(href).scheme.lower()
                        if scheme in ALLOWED_LINK_SCHEMES:
                            parts.append(f"[{text}]({href})")
                        else:
                            parts.append(text)
                elif text:
                    parts.append(text)
                continue

            if tag == "br":
                parts.append("\n")
                continue

            if tag == "img":
                # Inline <img> (typical: inside <p>): dropped like the
                # block path - no image syntax in markdown (#408).
                continue

            if tag == "ins":
                parts.append(wording_tag_open("ins", inner))
                continue

            if tag == "del":
                parts.append(wording_tag_open("del", inner))
                continue

            if tag == "sub":
                parts.append(f"<sub>{inner}</sub>")
                continue

            if tag == "sup":
                parts.append(f"<sup>{inner}</sup>")
                continue

            if tag == "tt-":
                stripped = inner.strip()
                if stripped:
                    parts.append(f"`{stripped}`")
                continue

            if tag in ("span", "div", "td", "th", "li", "dt", "dd",
                       "mark", "small", "s", "u", "abbr", "cite",
                       "dfn", "var", "kbd", "samp", "time", "data",
                       "wbr", "p", "figure", "figcaption",
                       "h-", "f-serif", "c-"):
                parts.append(inner)
                continue

            if tag in _HEADING_TAGS:
                parts.append(inner)
                continue

            parts.append(inner)

    return "".join(parts)
