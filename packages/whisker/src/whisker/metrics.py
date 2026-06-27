#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Deterministic structural-fidelity metrics (no LLM, no external deps).

These score a converted Markdown document against a labeled ground-truth
Markdown, so they belong to the benchmark path (`whisker bench`), not the
no-ground-truth per-paper verdict.

- ``teds``  : table structural similarity, PubTabNet TEDS definition.
- ``mhs``   : heading-hierarchy similarity (Markdown Heading Similarity).
- ``text_nid``: 1 - normalized edit distance over the full text stream.

``teds`` is a verbatim port of the PubTabNet/OmniDocBench TEDS implementation
(``_bench_src/OmniDocBench/src/metrics/table_metric.py``): an lxml DOM walk into
APTED with the xpath-descendant denominator, so scores are comparable to the
published table leaderboards. ``mhs`` is APTED tree-edit-distance over a heading
tree, the SAME backend as ``teds`` (one tree-edit engine for both axes; a prior
hand-rolled Zhang-Shasha was retired after a 72/72 score-parity check). All three
return a similarity in [0, 1] where 1.0 means identical; they are deterministic
functions of their inputs.
"""

from __future__ import annotations

import logging
import re
from collections import Counter, deque
from contextlib import contextmanager

import mistune
from apted import APTED, Config
from apted.helpers import Tree
from lxml import etree
from lxml import html as lxml_html
from pylatexenc.latex2text import LatexNodes2Text
from rapidfuzz.distance import Levenshtein as _Lev

from whisker.gates import _split_front_matter

__all__ = [
    "clean_string",
    "content_recall",
    "content_tokens",
    "has_headings",
    "mhs",
    "normalized_edit_distance",
    "normalized_text",
    "replace_textcircle",
    "safe_latex_to_text",
    "teds",
    "text_nid",
    "textblock2unicode",
]


# -- Normalized edit distance (Levenshtein) ----------------------------------


def normalized_edit_distance(a: str, b: str) -> float:
    """Levenshtein distance normalized to [0, 1] (0 = identical).

    Uses ``rapidfuzz.distance.Levenshtein`` (MIT) and OmniDocBench's exact
    normalization (``distance / max(len)``). rapidfuzz is the MIT-licensed
    sibling of the GPL ``levenshtein`` package this replaced (same maintainer,
    same algorithm, score-identical: see tests/test_edit_distance_parity.py);
    its SIMD core keeps a full-document compare (tens of thousands of chars) at
    milliseconds instead of the minutes a pure-Python DP would take.
    Deterministic.
    """
    if not a and not b:
        return 0.0
    longest = max(len(a), len(b))
    return _Lev.distance(a, b) / longest if longest else 0.0


_WS_RE = re.compile(r"\s+")


def _normalize_text(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


# Content normalization ported VERBATIM from OmniDocBench
# (src/core/preprocess/{data_preprocess,text_postprocess}.py). The canonical
# entry point is ``normalized_text`` = ``clean_string(textblock2unicode(text))``,
# applied symmetrically to both converters' output (cf. OmniDocBench's
# norm_gt/norm_pred) so a text comparison measures CONTENT agreement, not
# formatting style. ``textblock2unicode`` folds inline LaTeX ($...$, \(...\)) to
# unicode via pylatexenc; ``clean_string`` then drops escapes, normalizes circled
# glyphs, and keeps only word characters + CJK (markdown syntax, headings, pipe
# tables, emphasis, reflow and whitespace all vanish before the edit distance).

# replace_textcircle: fold circled digits/letters and \textcircled{x} to their
# inner character so one side turning "①" into "1" does not look like a mismatch.
_CIRCLED_UNICODE_MAP = {chr(0x2460 + i): str(i + 1) for i in range(20)}
_CIRCLED_UNICODE_MAP.update({chr(0x24D0 + i): chr(ord("a") + i) for i in range(26)})
_CIRCLED_UNICODE_MAP.update({chr(0x24B6 + i): chr(ord("A") + i) for i in range(26)})
_TEXTCIRCLED_CMD_RE = re.compile(r"\\textcircled\s*\{\s*([^{}]+?)\s*\}")


def replace_textcircle(text: str) -> str:
    """Normalize circled numbers/letters and ``\\textcircled{...}`` to plain chars."""
    if text is None:
        return text
    text = str(text)
    text = _TEXTCIRCLED_CMD_RE.sub(lambda m: m.group(1).strip(), text)
    return "".join(_CIRCLED_UNICODE_MAP.get(char, char) for char in text)


_CLEAN_KEEP_RE = re.compile(r"[^\w\u4e00-\u9fff]")


def clean_string(input_string: str) -> str:
    """OmniDocBench content normalizer: keep alnum + CJK, drop everything else."""
    input_string = replace_textcircle(input_string)
    input_string = (
        input_string.replace("\\t", "").replace("\\n", "")
        .replace("\t", "").replace("\n", "")
        .replace("/t", "").replace("/n", "")
    )
    return _CLEAN_KEEP_RE.sub("", input_string)


# -- Inline LaTeX -> unicode (OmniDocBench textblock2unicode) -----------------
#
# pylatexenc is robust but can choke on malformed input, so OmniDocBench gates
# every call behind three pure-Python guards (likely_bad_latex, weak-input and
# plaintext-noise detectors). Those guards are ported verbatim below.
# shortcut: OmniDocBench additionally runs latex_to_text in a multiprocessing
# timeout harness (server-batch robustness against pathological hangs). We drop
# that harness: this is a deterministic single-paper tool, the guards reject the
# dangerous inputs (unbalanced/over-long), and inline snippets are short. If a
# corpus paper ever hangs pylatexenc, restore the OmniDocBench timeout wrapper.

_INLINE_REG = re.compile(r"\$(.*?)\$|\\\((.*?)\\\)")
_ENV_RE = re.compile(r"\\(begin|end)\{([^{}]+)\}")
_LEFT_RE = re.compile(r"\\left\b")
_RIGHT_RE = re.compile(r"\\right\b")
_INLINE_OPEN_RE = re.compile(r"\\\(")
_INLINE_CLOSE_RE = re.compile(r"\\\)")
_DISPLAY_OPEN_RE = re.compile(r"\\\[")
_DISPLAY_CLOSE_RE = re.compile(r"\\\]")
_UNESCAPED_DOLLAR_RE = re.compile(r"(?<!\\)\$")
_LATEX_SIGNAL_RE = re.compile(r"\\[A-Za-z]+|[_^{}$]|\\[\[\]()]]|&|%|#")
_NATURAL_WORD_RE = re.compile(r"[A-Za-z]{3,}")
_LATEX_COMMAND_RE = re.compile(r"\\[A-Za-z]+")
_MAX_LATEX_INPUT_LEN = 8000
_PYLATEXENC_LOGGER_NAMES = (
    "pylatexenc",
    "pylatexenc.latexwalker",
    "pylatexenc.latexwalker._walker",
    "pylatexenc.macrospec",
    "pylatexenc.macrospec._environmentbodyparser",
)


def _braces_balanced(line: str) -> bool:
    depth = 0
    idx = 0
    while idx < len(line):
        ch = line[idx]
        if ch == "\\" and idx + 1 < len(line) and line[idx + 1] in "{}[]()":
            idx += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False
        idx += 1
    return depth == 0


def _env_balanced(line: str) -> bool:
    stack: list[str] = []
    for match in _ENV_RE.finditer(line):
        kind, name = match.group(1), match.group(2)
        if kind == "begin":
            stack.append(name)
            continue
        if not stack or stack[-1] != name:
            return False
        stack.pop()
    return not stack


def _math_delims_balanced(line: str) -> bool:
    if len(_INLINE_OPEN_RE.findall(line)) != len(_INLINE_CLOSE_RE.findall(line)):
        return False
    if len(_DISPLAY_OPEN_RE.findall(line)) != len(_DISPLAY_CLOSE_RE.findall(line)):
        return False
    return len(_UNESCAPED_DOLLAR_RE.findall(line)) % 2 == 0


def _left_right_balanced(line: str) -> bool:
    return len(_LEFT_RE.findall(line)) == len(_RIGHT_RE.findall(line))


def _likely_bad_latex(line: str, latex_type: str = "formula") -> bool:
    stripped = str(line or "").strip()
    if not stripped:
        return False
    if 0 < _MAX_LATEX_INPUT_LEN < len(stripped):
        return True
    if not _braces_balanced(stripped):
        return True
    if not _env_balanced(stripped):
        return True
    if latex_type in {"formula", "inline", "display"}:
        if not _left_right_balanced(stripped):
            return True
        if not _math_delims_balanced(stripped):
            return True
    return False


def _looks_like_plaintext_formula_noise(line: str) -> bool:
    stripped = str(line or "").strip()
    if len(stripped) < 32:
        return False
    if len(_LATEX_SIGNAL_RE.findall(stripped)) > 2:
        return False
    if any(c in stripped for c in "{}$^_"):
        return False
    if any(tok in stripped for tok in (
        "\\frac", "\\sqrt", "\\left", "\\right", "\\begin", "\\end",
        "\\sum", "\\int", "\\alpha", "\\beta",
    )):
        return False
    return len(_NATURAL_WORD_RE.findall(stripped)) >= 6 and stripped.count(" ") >= 5


def _looks_like_weak_latex_input(line: str, latex_type: str = "formula") -> bool:
    stripped = str(line or "").strip()
    if not stripped:
        return True
    if stripped in {"\\", "\\\\"}:
        return True
    command_hits = len(_LATEX_COMMAND_RE.findall(stripped))
    word_hits = len(_NATURAL_WORD_RE.findall(stripped))
    backslash_hits = stripped.count("\\")
    math_signal_hits = sum(ch in "{}$^_=&%#" for ch in stripped)
    if stripped.endswith("\\") and not stripped.endswith("\\\\") and command_hits == 0:
        return True
    if backslash_hits > 0 and command_hits == 0 and math_signal_hits == 0:
        return True
    if latex_type in {"formula", "inline", "display"} and word_hits >= 2 and command_hits == 0 and math_signal_hits <= 1:
        return True
    if latex_type in {"formula", "inline", "display"} and word_hits >= 4 and command_hits <= 1 and math_signal_hits <= 2:
        return True
    return False


@contextmanager
def _suppress_pylatexenc_warnings():
    states = []
    for name in _PYLATEXENC_LOGGER_NAMES:
        logger = logging.getLogger(name)
        states.append((logger, logger.level))
        logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        for logger, level in states:
            logger.setLevel(level)


def safe_latex_to_text(latex: str, fallback: str | None = None, latex_type: str = "formula") -> str:
    """Convert LaTeX to unicode, falling back to the raw text when unsafe.

    Mirrors OmniDocBench's guard ladder (disable-flag, no-markup shortcut,
    plaintext-noise, weak-input, bad-latex) before invoking pylatexenc. Returns
    the fallback (or the stripped input) whenever conversion is skipped or fails.
    """
    stripped = str(latex or "").strip()
    if not stripped:
        return "" if fallback is None else fallback
    if "\\" not in stripped and "{" not in stripped and "}" not in stripped and "$" not in stripped:
        return stripped
    if _looks_like_plaintext_formula_noise(stripped):
        return stripped if fallback is None else fallback
    if _looks_like_weak_latex_input(stripped, latex_type=latex_type):
        return stripped if fallback is None else fallback
    if _likely_bad_latex(stripped, latex_type=latex_type):
        return stripped if fallback is None else fallback
    try:
        with _suppress_pylatexenc_warnings():
            return LatexNodes2Text().latex_to_text(stripped)
    except Exception:
        return stripped if fallback is None else fallback


def _should_skip_inline_textblock_formula(latex_text: str) -> bool:
    latex_text = str(latex_text or "").strip()
    if not latex_text:
        return False
    if len(latex_text) > 128:
        return True
    complex_tokens = (
        r"\begin{", r"\end{", r"\array", r"\matrix", r"\tabular",
        r"\cases", r"\align", r"\\", "&",
    )
    if any(token in latex_text for token in complex_tokens):
        return True
    return latex_text.count("{") != latex_text.count("}")


def textblock2unicode(text: str) -> str:
    """Fold inline LaTeX formulas (``$...$``, ``\\(...\\)``) to unicode in prose."""
    text = replace_textcircle(text)
    removal_positions = []
    for match in _INLINE_REG.finditer(text):
        content = match.group(1) if match.group(1) is not None else match.group(2)
        clean_content = re.sub(r"\\([\\_&%^])", "", content)
        try:
            if any(char in clean_content for char in r"\^_"):
                if clean_content.endswith("\\"):
                    clean_content += " "
                if _should_skip_inline_textblock_formula(clean_content):
                    continue
                unicode_content = safe_latex_to_text(
                    clean_content, fallback=clean_content, latex_type="formula"
                )
                removal_positions.append((match.start(), match.end(), unicode_content))
        except Exception:
            continue
    for start, end, unicode_content in sorted(removal_positions, reverse=True):
        text = text[:start] + unicode_content.strip() + text[end:]
    return text


def normalized_text(text: str) -> str:
    """OmniDocBench text axis normalizer: clean_string(textblock2unicode(text))."""
    return clean_string(textblock2unicode(text))


def text_nid(a: str, b: str) -> float:
    """Reading-order/text similarity: 1 - normalized edit distance.

    Returns a similarity in [0, 1] (1.0 = identical) after whitespace
    normalization, matching the OmniDocBench "Text Edit" axis reported as
    (1 - edit).
    """
    return 1.0 - normalized_edit_distance(_normalize_text(a), _normalize_text(b))


# -- Content recall (multiset bag-of-words) ----------------------------------

_CONTENT_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def content_tokens(text: str) -> list[str]:
    """Bag-of-words tokens for multiset content recall.

    Folds inline LaTeX and circled glyphs via ``textblock2unicode`` (the same
    content alphabet as the text-NID axis), lowercases, then splits on the
    Unicode word boundary so punctuation and whitespace separate tokens. Unlike
    ``normalized_text`` (which is ``clean_string``-flattened and therefore has
    NO word boundaries, collapsing a paragraph into a single token), this keeps
    token granularity, which recall requires. CJK runs group as single tokens,
    matching tomd's unigram tokenizer. Deterministic.
    """
    return _CONTENT_TOKEN_RE.findall(textblock2unicode(text).lower())


def content_recall(candidate: str, reference: str) -> float:
    """Multiset word recall of the reference content present in the candidate.

    The Unstructured ``cct-%missing`` complement (1 - fraction missing): the
    fraction of reference (ground-truth) word occurrences that also appear in
    the candidate, counting multiplicity. 1.0 means no reference content is
    missing. A dropped paragraph drives it down even when block-matched ``nid``
    stays high on the surviving blocks, the exact "a converter dropped a
    section" blind spot edit distance hides. Extra or duplicated candidate words
    are NOT penalized (additive drift is a separate, score-path signal). An
    empty reference yields 1.0 (nothing to recall). Deterministic.
    """
    ref = Counter(content_tokens(reference))
    if not ref:
        return 1.0
    hyp = Counter(content_tokens(candidate))
    matched = sum(min(count, hyp[token]) for token, count in ref.items())
    return matched / sum(ref.values())


# -- TEDS (tables) -----------------------------------------------------------
#
# Verbatim port of PubTabNet/OmniDocBench TEDS (Apache-2.0, IBM peter.zhong):
# _bench_src/OmniDocBench/src/metrics/table_metric.py. The only adaptations are
# privatizing the names, dropping the batch/CLI helpers, and a defensive
# zero-denominator guard. The algorithm (lxml DOM -> APTED, char-token cell
# content, xpath-descendant denominator, td-only content, strict tag/colspan/
# rowspan rename) is unchanged so scores match the published table leaderboards.


class _TableTree(Tree):
    def __init__(self, tag, colspan=None, rowspan=None, content=None, *children):
        self.tag = tag
        self.colspan = colspan
        self.rowspan = rowspan
        self.content = content
        self.children = list(children)

    def bracket(self):
        """Show tree using brackets notation."""
        if self.tag == "td":
            result = '"tag": %s, "colspan": %d, "rowspan": %d, "text": %s' % (
                self.tag, self.colspan, self.rowspan, self.content,
            )
        else:
            result = '"tag": %s' % self.tag
        for child in self.children:
            result += child.bracket()
        return "{{{}}}".format(result)


class _TedsConfig(Config):
    @staticmethod
    def maximum(*sequences):
        return max(map(len, sequences))

    def normalized_distance(self, *sequences):
        return float(_Lev.distance(*sequences)) / self.maximum(*sequences)

    def rename(self, node1, node2):
        """Compares attributes of trees."""
        if (
            (node1.tag != node2.tag)
            or (node1.colspan != node2.colspan)
            or (node1.rowspan != node2.rowspan)
        ):
            return 1.0
        if node1.tag == "td":
            if node1.content or node2.content:
                return self.normalized_distance(node1.content, node2.content)
        return 0.0


class _TEDS:
    """Tree-Edit-Distance-based Similarity (PubTabNet/OmniDocBench)."""

    def __init__(self, structure_only=False, ignore_nodes=None):
        self.structure_only = structure_only
        self.ignore_nodes = ignore_nodes
        self.__tokens__: list[str] = []

    def tokenize(self, node):
        """Tokenizes table cells (nested inline tags become literal tokens)."""
        self.__tokens__.append("<%s>" % node.tag)
        if node.text is not None:
            self.__tokens__ += list(node.text)
        for n in node.getchildren():
            self.tokenize(n)
        if node.tag != "unk":
            self.__tokens__.append("</%s>" % node.tag)
        if node.tag != "td" and node.tail is not None:
            self.__tokens__ += list(node.tail)

    def load_html_tree(self, node, parent=None):
        """Converts an lxml table node to the format required by apted."""
        if node.tag == "td":
            if self.structure_only:
                cell = []
            else:
                self.__tokens__ = []
                self.tokenize(node)
                cell = self.__tokens__[1:-1].copy()
            new_node = _TableTree(
                node.tag,
                int(node.attrib.get("colspan", "1")),
                int(node.attrib.get("rowspan", "1")),
                cell, *deque(),
            )
        else:
            new_node = _TableTree(node.tag, None, None, None, *deque())
        if parent is not None:
            parent.children.append(new_node)
        if node.tag != "td":
            for n in node.getchildren():
                self.load_html_tree(n, new_node)
        if parent is None:
            return new_node

    def evaluate(self, pred, true):
        """TEDS between a prediction and the ground truth (both HTML strings)."""
        if (not pred) or (not true):
            return 0.0
        parser = lxml_html.HTMLParser(remove_comments=True, encoding="utf-8")
        pred = lxml_html.fromstring(pred, parser=parser)
        true = lxml_html.fromstring(true, parser=parser)
        if pred.xpath("body/table") and true.xpath("body/table"):
            pred = pred.xpath("body/table")[0]
            true = true.xpath("body/table")[0]
            if self.ignore_nodes:
                etree.strip_tags(pred, *self.ignore_nodes)
                etree.strip_tags(true, *self.ignore_nodes)
            n_nodes_pred = len(pred.xpath(".//*"))
            n_nodes_true = len(true.xpath(".//*"))
            n_nodes = max(n_nodes_pred, n_nodes_true)
            if n_nodes == 0:
                # Two parseable but row-less tables: identical structure.
                # (OmniDocBench would divide by zero here; real corpora never hit
                # this because extracted tables always carry at least a row.)
                return 1.0
            tree_pred = self.load_html_tree(pred)
            tree_true = self.load_html_tree(true)
            distance = APTED(tree_pred, tree_true, _TedsConfig()).compute_edit_distance()
            return 1.0 - (float(distance) / n_nodes)
        else:
            return 0.0


def _normalize_table_html(table_html: str) -> str:
    """Wrap + normalize a table fragment the way OmniDocBench does pre-TEDS.

    Ensures an ``<html><body>`` wrapper (``evaluate`` keys off ``body/table``),
    converts ``<th>`` to ``<td>`` (PubTabNet ``load_html_tree`` drops th cell
    text), and unwraps ``thead``/``tbody``/``tfoot`` so rows sit directly under
    ``<table>``. Returns "" for empty input so ``evaluate`` maps it to 0.0.
    """
    s = (table_html or "").strip()
    if not s:
        return ""
    if "<body" not in s.lower():
        s = f"<html><body>{s}</body></html>"
    parser = lxml_html.HTMLParser(remove_comments=True, encoding="utf-8")
    root = lxml_html.fromstring(s, parser=parser)
    for th in root.xpath(".//th"):
        th.tag = "td"
    etree.strip_tags(root, "thead", "tbody", "tfoot")
    return etree.tostring(root, encoding="unicode")


def teds(html_a: str, html_b: str, *, structure_only: bool = False) -> float:
    """PubTabNet TEDS for two HTML tables (verbatim OmniDocBench algorithm).

    Both inputs are normalized (``th``->``td``, ``thead``/``tbody`` unwrapped,
    wrapped in ``<html><body>``) exactly as OmniDocBench's table preprocess does
    before scoring, then compared with APTED over the lxml DOM. Returns 1.0 for
    identical tables and 0.0 when either side has no parseable table (PubTabNet
    convention). With ``structure_only`` the cell text is ignored (TEDS-S).
    """
    pred = _normalize_table_html(html_a)
    true = _normalize_table_html(html_b)
    return _TEDS(structure_only=structure_only).evaluate(pred, true)


# -- MHS (heading hierarchy) -------------------------------------------------

# Shared with tomd QA (qa.py / check_content.py): the same CommonMark AST
# engine, so whisker measures headings the way tomd defines them.
_AST_RENDERER = mistune.create_markdown(renderer="ast", plugins=["table"])

# Inline node types whose ``raw`` carries literal heading text. Block and
# inline wrappers (heading, emphasis, strong, link, ...) recurse via children.
_INLINE_TEXT_TYPES = frozenset({"text", "codespan", "linebreak", "softbreak"})


def _collect_inline_text(node: dict, out: list[str]) -> None:
    """Walk a heading node, appending literal inline text to ``out``."""
    if node.get("type", "") in _INLINE_TEXT_TYPES:
        raw = node.get("raw", "")
        if raw:
            out.append(raw)
        return
    for child in node.get("children", []) or []:
        _collect_inline_text(child, out)


def _inline_text(node: dict) -> str:
    """Flatten a heading node's inline children to plain prose."""
    parts: list[str] = []
    _collect_inline_text(node, parts)
    return "".join(parts)


def _parse_headings(md_text: str) -> list[tuple[int, str]]:
    """Return ordered (level, text) pairs from ATX and setext headings.

    Parsed via mistune's CommonMark AST (the engine tomd QA uses), so setext
    headings (``Title`` over ``=====``) count, inline markup in heading text is
    flattened to prose (``## **Bold** [x](u)`` -> ``Bold x``), and fenced code
    is suppressed by the parser. Front matter is stripped first (whisker's own
    ``gates._split_front_matter``) so its ``---`` fences are never misread as
    setext underlines. Only top-level headings are collected, matching tomd QA's
    documented limitation (headings nested in lists/blockquotes are skipped).
    """
    _, body = _split_front_matter(md_text)
    headings: list[tuple[int, str]] = []
    for token in _AST_RENDERER(body):
        if token.get("type") != "heading":
            continue
        level = token.get("attrs", {}).get("level", 0)
        text = _normalize_text(_inline_text(token))
        if level and text:
            headings.append((level, text))
    return headings


class _HeadingTree(Tree):
    """An ordered heading node for APTED (mirrors TEDS' ``_TableTree``).

    ``label`` is ``{"level": int, "text": str}``; children are ordered by
    document position. APTED's default ``Config.children`` reads ``.children``.
    """

    def __init__(self, label, *children):
        self.label = label
        self.children = list(children)


class _MhsConfig(Config):
    """APTED cost model for the heading tree.

    Unit insert/delete and a fractional rename equal to the normalized edit
    distance between heading texts: the exact cost model the retired
    Zhang-Shasha implementation used, so scores are unchanged.
    """

    def __init__(self, structure_only: bool = False):
        self.structure_only = structure_only

    def delete(self, node):
        return 1.0

    def insert(self, node):
        return 1.0

    def rename(self, node1, node2):
        if self.structure_only:
            return 0.0
        a = node1.label if isinstance(node1.label, dict) else {}
        b = node2.label if isinstance(node2.label, dict) else {}
        return normalized_edit_distance(a.get("text", ""), b.get("text", ""))


def _node_count(root: _HeadingTree) -> int:
    total = 0
    stack = [root]
    while stack:
        node = stack.pop()
        total += 1
        stack.extend(node.children)
    return total


def _build_heading_tree(md_text: str) -> _HeadingTree:
    """Nest headings by level into a tree under a synthetic root."""
    root = _HeadingTree({"level": 0, "text": "\x00root"})
    stack: list[tuple[int, _HeadingTree]] = [(0, root)]
    for level, text in _parse_headings(md_text):
        node = _HeadingTree({"level": level, "text": text})
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1] if stack else root
        parent.children.append(node)
        stack.append((level, node))
    return root


def has_headings(md_text: str) -> bool:
    """True if the document has at least one heading (mhs eligibility signal).

    The reference is authoritative: when the ground truth has no heading
    hierarchy there is nothing for ``mhs`` to measure, so bench records the axis
    as ineligible (``None``) rather than a synthetic 1.0 that would inflate the
    corpus mean (the opendataloader-pdf null-eligibility rule).
    """
    return bool(_parse_headings(md_text))


def mhs(md_a: str, md_b: str, *, structure_only: bool = False) -> float:
    """Markdown Heading Similarity between two documents.

    Builds a heading tree nested by level and scores APTED tree edit distance
    (the same engine as ``teds``), normalized like TEDS. The synthetic root is
    shared, so two documents with no headings score 1.0.
    """
    tree_a = _build_heading_tree(md_a)
    tree_b = _build_heading_tree(md_b)
    n_a = _node_count(tree_a)
    n_b = _node_count(tree_b)
    denom = max(n_a, n_b)
    if denom <= 1:
        return 1.0
    dist = APTED(tree_a, tree_b, _MhsConfig(structure_only)).compute_edit_distance()
    return max(0.0, 1.0 - dist / denom)
