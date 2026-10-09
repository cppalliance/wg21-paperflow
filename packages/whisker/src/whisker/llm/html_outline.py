#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Extract an h1-h6 heading outline from HTML source.

Pure-stdlib extraction (html.parser), no lxml/beautifulsoup dependency.
Used by the tapetum_llm text lane to give the LLM deterministic source
metadata for HTML papers: which headings exist at which level in the
source HTML. This is NOT a verdict signal (no whisker flags leak in);
it is source ground truth so the LLM can detect heading-level drift.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser

__all__ = [
    "SectionUnit",
    "extract_heading_outline",
    "extract_heading_outline_normalized",
    "extract_section_units",
    "format_outline",
    "normalize_heading_text",
]

# Longer heading text is truncated before LLM injection to keep the prompt
# compact; some papers have title-as-heading text over 200 chars.
_MAX_HEADING_DISPLAY_CHARS = 120
_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_BLOCK_TAGS = frozenset({
    "address", "article", "aside", "blockquote", "br", "dd", "div", "dl",
    "dt", "figcaption", "figure", "footer", "header", "hr", "li", "main",
    "nav", "ol", "p", "pre", "section", "table", "td", "th", "tr", "ul",
})
_WS_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)

# Classes on <span> elements that carry structural section numbering and
# should be stripped from heading text for normalized comparison.
_SECNO_CLASSES = frozenset({"secno", "header-section-number"})

# Leading section-number pattern stripped after joining text, to catch cases
# where the number wasn't wrapped in a secno span. Decimal (``1.`` / ``1.2.3``),
# Roman (``IV.``), and alphabetic (``A.``) labels are structural, not semantic.
_LEADING_SECNO_RE = re.compile(
    r"^(?:\d+(?:\.\d+)*\.?|[IVXLCDM]+\.|[A-Z]\.)\s+",
    re.IGNORECASE,
)

# Tags whose text content is never meaningful document text.
_INVISIBLE_TAGS = frozenset({"script", "style"})


def _get_classes(attrs: list[tuple[str, str | None]]) -> frozenset[str]:
    """Extract the set of CSS class names from an attribute list."""
    for name, value in attrs:
        if name == "class" and value:
            return frozenset(value.split())
    return frozenset()


@dataclass
class SectionUnit:
    """One heading-bounded section's structured source signals."""

    section_id: int
    tag: str
    title: str
    text: str
    content_tokens: int
    code_blocks: int
    has_tables: bool
    has_images: bool


class _HeadingExtractor(HTMLParser):
    """Collect h1-h6 tags with their text content."""

    def __init__(self, *, strip_secno: bool = False):
        super().__init__()
        self._in_heading: str | None = None
        self._text_buf: list[str] = []
        self._skip_depth: int = 0
        self._strip_secno = strip_secno
        self.headings: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _HEADING_TAGS:
            self._in_heading = tag
            self._text_buf = []
            self._skip_depth = 0
            return
        if self._in_heading and self._strip_secno and tag == "span":
            classes = _get_classes(attrs)
            if classes & _SECNO_CLASSES:
                self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == self._in_heading:
            text = " ".join("".join(self._text_buf).split()).strip()
            if self._strip_secno:
                text = _LEADING_SECNO_RE.sub("", text)
            if text:
                self.headings.append((self._in_heading, text))
            self._in_heading = None
            self._text_buf = []
            self._skip_depth = 0
            return
        if self._in_heading and self._skip_depth > 0 and tag == "span":
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_heading and self._skip_depth == 0:
            self._text_buf.append(data)


def normalize_heading_text(text: str) -> str:
    """Apply secno/leading-number normalization to a heading text string.

    Strips leading section-number patterns like ``1.``, ``1.2.3 ``, etc.
    Useful for comparison between source headings and candidate markdown headings.
    """
    return _LEADING_SECNO_RE.sub("", text).strip()


def extract_heading_outline(html_source: str) -> list[tuple[str, str]]:
    """Extract (tag, text) pairs from HTML, e.g. [("h1", "Title"), ("h2", "Abstract")].

    Returns headings in document order. Deterministic, no I/O.
    """
    parser = _HeadingExtractor()
    parser.feed(html_source)
    return parser.headings


def extract_heading_outline_normalized(html_source: str) -> list[tuple[str, str]]:
    """Like extract_heading_outline but strips secno spans and leading numbers.

    Returns (tag, normalized_text) pairs. Structural labels like
    ``<span class="secno">1. </span>`` are excluded, and any residual
    leading ``N.M.`` pattern is stripped from the joined text.
    """
    parser = _HeadingExtractor(strip_secno=True)
    parser.feed(html_source)
    return parser.headings


class _SectionExtractor(HTMLParser):
    """Collect heading-bounded HTML sections and their local structure."""

    def __init__(self, *, strip_secno: bool = False) -> None:
        super().__init__(convert_charrefs=True)
        self._heading_tag: str | None = None
        self._heading_text: list[str] = []
        self._heading_skip_depth: int = 0
        self._strip_secno = strip_secno
        self._invisible_depth: int = 0
        self._current_tag: str | None = None
        self._current_title = ""
        self._content: list[str] = []
        self._code_blocks = 0
        self._has_tables = False
        self._has_images = False
        self.sections: list[SectionUnit] = []

    def _finish_section(self) -> None:
        if self._current_tag is None:
            return
        text = _WS_RE.sub(" ", "".join(self._content)).strip()
        self.sections.append(SectionUnit(
            section_id=len(self.sections),
            tag=self._current_tag,
            title=self._current_title,
            text=text,
            content_tokens=len(_WORD_RE.findall(text)),
            code_blocks=self._code_blocks,
            has_tables=self._has_tables,
            has_images=self._has_images,
        ))
        self._current_tag = None
        self._current_title = ""
        self._content = []
        self._code_blocks = 0
        self._has_tables = False
        self._has_images = False

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.lower()
        if tag in _INVISIBLE_TAGS:
            self._invisible_depth += 1
            return
        if tag in _HEADING_TAGS:
            self._finish_section()
            self._heading_tag = tag
            self._heading_text = []
            self._heading_skip_depth = 0
            return
        if self._heading_tag is not None:
            if self._strip_secno and tag == "span":
                classes = _get_classes(attrs)
                if classes & _SECNO_CLASSES:
                    self._heading_skip_depth += 1
            return
        if self._current_tag is None:
            return
        if tag in _BLOCK_TAGS:
            self._content.append(" ")
        if tag == "pre":
            self._code_blocks += 1
        if tag == "table":
            self._has_tables = True
        if tag == "img":
            self._has_images = True

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _INVISIBLE_TAGS:
            if self._invisible_depth > 0:
                self._invisible_depth -= 1
            return
        if tag == self._heading_tag:
            title = _WS_RE.sub(" ", "".join(self._heading_text)).strip()
            if self._strip_secno:
                title = _LEADING_SECNO_RE.sub("", title)
            self._current_tag = self._heading_tag
            self._current_title = title
            self._heading_tag = None
            self._heading_text = []
            self._heading_skip_depth = 0
            return
        if self._heading_tag is not None:
            if self._heading_skip_depth > 0 and tag == "span":
                self._heading_skip_depth -= 1
            return
        if (
            self._heading_tag is None
            and self._current_tag is not None
            and tag in _BLOCK_TAGS
        ):
            self._content.append(" ")

    def handle_data(self, data: str) -> None:
        if self._invisible_depth > 0:
            return
        if self._heading_tag is not None:
            if self._heading_skip_depth == 0:
                self._heading_text.append(data)
        elif self._current_tag is not None:
            self._content.append(data)

    def finish(self) -> list[SectionUnit]:
        self._finish_section()
        return self.sections


def extract_section_units(html_source: str) -> list[SectionUnit]:
    """Extract heading-bounded sections with punctuation-preserving text."""
    parser = _SectionExtractor()
    parser.feed(html_source)
    parser.close()
    return parser.finish()


def format_outline(headings: list[tuple[str, str]]) -> str:
    """Format heading outline for LLM injection.

    Example output:
        Source HTML heading outline:
        - h1: Title
        - h2: Abstract
        - h2: Motivation
        - h3: Background
        - h2: References
    """
    if not headings:
        return ""
    lines = ["Source HTML heading outline:"]
    for tag, text in headings:
        display = (
            text[:_MAX_HEADING_DISPLAY_CHARS] + "..."
            if len(text) > _MAX_HEADING_DISPLAY_CHARS
            else text
        )
        lines.append(f"- {tag}: {display}")
    return "\n".join(lines)
