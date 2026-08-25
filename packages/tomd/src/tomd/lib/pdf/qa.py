"""Quality assurance metrics and scoring for Markdown conversion output.

Parses the Markdown output with mistune to validate structure from
the reader's perspective, not from pipeline internals.

DESIGN CONSTRAINT: compute_metrics() takes only a Markdown string.
No page count, no file format, no pipeline internals. Every signal
must be derivable from the Markdown text alone. This keeps scoring
format-agnostic (works on PDF output, HTML output, or any Markdown)
and prevents coupling between the scorer and the converter.
"""

import contextlib
import json
import logging
import os
import re
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ftfy.badness import badness as _ftfy_badness
import mistune
from paperstore.progress import ProgressCallback

from tomd.lib.batch import run_parallel_batch
from tomd.lib.metadata_yaml.format import FRONT_MATTER_ORDER, parse_front_matter

from ..wording_markup import WORDING_TAG_RE

__all__ = [
    "QABatchResult",
    "QAMetrics",
    "compute_metrics",
    "format_qa_report",
    "run_qa_batch",
    "write_qa_json_atomic",
]

_log = logging.getLogger(__name__)

_UNCERTAIN_MARKER = "tomd:uncertain"
_LOSSY_TABLE_MARKER = "tomd:lossy-table"
_WG21_DOC_NUM_RE = re.compile(r"[DPN]\d{3,5}R?\d*", re.IGNORECASE)

# Detection-only: a top-level block counts as a wording section when it
# carries an inline <ins>/<del> tag. tomd emits no wording div, so the
# inline tags (lib.wording_markup) are the only signal available.
_WORDING_BLOCK_TYPES = ("paragraph", "block_code", "block_html", "list", "heading")

# Intentionally broader than structure.py's _STRUCTURAL_CODE_RE.
# qa.py uses it for *detection* (scoring), so false positives just
# inflate a metric. structure.py uses it for *rescue* (promoting
# paragraphs to code blocks), where false positives corrupt output.
_STRUCTURAL_CODE_RE = re.compile(
    r"^\s*[{}]|"               # standalone brace lines
    r";\s*$|"                  # trailing semicolons (code statements)
    r"#include\s*<|"           # preprocessor includes
    r"\w+\s*\([^)]*\)\s*\{|"  # function_name(...) {
    r"\w+\s*\([^)]*\)\s*;|"   # declaration: name(...);
    r"^\s*template\s*<|"       # template declarations
    r"^\s*(?:namespace|class|struct|enum)\s+\w+\s*[:{]",  # type decl with brace or colon
    re.MULTILINE,
)

# ISO C++ normative specification-element labels from [structure.specifications],
# [requirements] section, and historical labels (C++17 "Requires").
# Source: https://eel.is/c++draft/structure#specifications
# Paragraphs starting with these labels are standard wording, not unfenced code,
# even when they end with semicolons (e.g. "Returns: substr(0).compare(str);").
_STANDARDESE_PREFIX_RE = re.compile(
    r"^\s*(?:"
    r"Effects|Returns|Equivalent to|Preconditions|Postconditions|"
    r"Constraints|Mandates|Complexity|Throws|Remarks|"
    r"Default|Expects|Result|Ensures|Let|"
    r"Constant When|Hardened preconditions|Synchronization|Error conditions|"
    r"Required behavior|Default behavior|Recommended practice|"
    r"Requires"
    r")\s*:",
    re.IGNORECASE,
)


@dataclass
class QAMetrics:
    """Per-document quality metrics computed purely from Markdown text."""
    file: str = ""
    total_chars: int = 0
    heading_count: int = 0
    max_heading_level: int = 0
    code_block_count: int = 0
    list_count: int = 0
    table_count: int = 0
    front_matter_count: int = 0
    has_doc_number: bool = False
    uncertain_count: int = 0
    unfenced_code_lines: int = 0
    paragraph_count: int = 0
    mojibake_count: int = 0
    heading_level_skips: int = 0
    wording_section_count: int = 0
    table_parse_errors: int = 0
    lossy_table_count: int = 0
    empty_output: bool = False
    score: int = 100
    issues: list[str] = field(default_factory=list)


def _paragraph_plain_text(node: dict) -> str:
    """Get plain text from a paragraph, excluding inline code and HTML."""
    parts = []
    for child in node.get("children", []):
        if child.get("type", "") == "text":
            parts.append(child.get("raw", ""))
    return " ".join(parts)


def _has_wording_markup(node: dict) -> bool:
    """True if a paragraph contains <ins> or <del> wording tags."""
    for child in node.get("children", []):
        if child.get("type", "") == "inline_html":
            raw = child.get("raw", "")
            if raw.startswith(("<ins", "<del", "</ins", "</del")):
                return True
    return False


def _looks_like_code(node: dict) -> bool:
    """True if a paragraph looks like an unfenced code block.

    Checks only the plain-text children (not codespan or inline_html).
    Looks for structural code patterns — braces, semicolons, function
    declarations — not single keywords that appear naturally in prose.
    Wording sections (<ins>/<del> markup) and standardese specification
    labels (Effects:, Returns:, etc.) are excluded since trailing
    semicolons in normative prose are expected, not missed code.
    """
    children = node.get("children", [])
    if not children:
        return False
    if _has_wording_markup(node):
        return False
    text_children = [c for c in children if c.get("type", "") == "text"]
    code_children = [c for c in children if c.get("type", "") == "codespan"]
    if code_children and not text_children:
        return False
    text = _paragraph_plain_text(node)
    if _STANDARDESE_PREFIX_RE.match(text.strip()):
        return False
    return bool(_STRUCTURAL_CODE_RE.search(text))


def _block_raw_text(node: dict) -> str:
    """Flatten a block token back to text for substring detection.

    mistune keeps inline HTML as ``inline_html`` children and fenced code
    as a ``raw`` string, so neither a plain ``raw`` read nor a text-only
    walk sees every ``<ins>`` / ``<del>``. This concatenates both.
    """
    parts = [node.get("raw", "")]
    stack = list(node.get("children", []))
    while stack:
        child = stack.pop()
        parts.append(child.get("raw", ""))
        stack.extend(child.get("children", []))
    return "".join(parts)


def _count_wording_blocks(tokens: list[dict]) -> int:
    """Count top-level blocks carrying inline wording markup."""
    return sum(
        1 for t in tokens
        if t.get("type", "") in _WORDING_BLOCK_TYPES
        and WORDING_TAG_RE.search(_block_raw_text(t))
    )


def _count_unfenced_code(paragraphs: list[dict]) -> int:
    """Count paragraphs that look like unfenced code blocks."""
    return sum(1 for p in paragraphs if _looks_like_code(p))


_MOJIBAKE_BADNESS_THRESHOLD = 3

_LONG_DOC_MIN_PARAGRAPHS = 10
_UNCERTAIN_MAX_PENALTY = 20
_UNCERTAIN_PENALTY_PER = 5
_NO_HEADINGS_PENALTY = 25
_NO_FRONT_MATTER_PENALTY = 10
_UNFENCED_MINOR_PENALTY = 15
_UNFENCED_PER_BLOCK = 5
_UNFENCED_MAJOR_THRESHOLD = 20
_UNFENCED_MAJOR_EXTRA = 15
_UNFENCED_MAX_PENALTY = 30
_NO_STRUCTURE_VARIETY_PENALTY = 10
_MOJIBAKE_MAX_PENALTY = 20
_MOJIBAKE_PENALTY_PER = 5
_HEADING_SKIP_MAX_PENALTY = 15
_HEADING_SKIP_PENALTY_PER = 5
_QA_BATCH_TIMEOUT_SEC = 120
_WORKER_POLL_INTERVAL = 0.5
_NEEDS_REVIEW_THRESHOLD = 70
_WORST_FILES_DISPLAY_LIMIT = 30


_CODE_FENCE_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)

_INLINE_CODE_RE = re.compile(r"``[^`]+``|`[^`]+`")

_AST_RENDERER = mistune.create_markdown(renderer="ast", plugins=["table"])


_UNICODE_TOPIC_RE = re.compile(
    r"utf|unicode|transcod|encoding|charconv|replacement.character",
    re.IGNORECASE,
)

# Presence of the glyph-placeholder marker means tomd intentionally
# emitted U+FFFD for raster glyphs it could not decode to a codepoint
# (see lib/pdf/glyphs.py). Those are sanctioned placeholders, not
# decode-failure mojibake, so U+FFFD counting is suppressed for such
# papers. ftfy.badness() still flags real encoding corruption.
_GLYPH_PLACEHOLDER_MARKER_RE = re.compile(r"tomd:glyph-placeholders:")



def _count_mojibake(md_text: str) -> int:
    """Count encoding corruption signals in the markdown text.

    Two-layer detection:
    1. U+FFFD (replacement character): always means bytes were lost
       during decoding. Zero false positives. Source:
       https://bytetunnels.com/posts/some-characters-could-not-be-decoded-fixing-replacement-character-errors/
    2. ftfy.badness(): scores unlikely Unicode sequences that indicate
       UTF-8 decoded as Latin-1/CP-1252. Uses ~400 character classes
       tuned over years with ~1 false positive per 6M texts.
       We use the integer score, not the boolean is_bad(), because
       is_bad() has length-dependent false-positive rate on long
       technical documents.

    We require badness >= 3 to flag, because a score of 1-2 on a
    large document with math symbols or diacritics can be noise.

    U+FFFD inside fenced code blocks and inline code spans is
    suppressed: papers about encoding (e.g. P3904R1, P2728R11)
    intentionally demonstrate replacement characters in code.

    For papers whose title indicates they discuss Unicode encoding,
    U+FFFD counting is suppressed entirely since the replacement
    character is the paper's subject matter. It is likewise suppressed
    when the glyph-placeholder marker is present, because tomd then
    emitted U+FFFD itself as a sanctioned placeholder for undecodable
    raster glyphs (see lib/pdf/glyphs.py) rather than losing bytes.
    ftfy.badness() still provides an independent safety net for real
    encoding corruption in both cases.

    Decision: ftfy over custom regex. See plans/QA-001-extend-qa-scoring.md,
    Research Finding #1. Custom byte-pattern regex (e.g. [\\xc0-\\xdf][\\x80-\\xbf])
    false-positives on valid multi-byte Unicode in author names, math
    symbols, and C++ template syntax.

    Known limitations:
    - ftfy is NOT Markdown-aware (Research Finding #5). Math symbols
      in the 'numeric' category could interact with mojibake patterns,
      but the threshold of >= 3 mitigates this.
    - Does not detect encoding issues inside images or binary blobs.
    """
    prose = _CODE_FENCE_RE.sub("", md_text)
    prose = _INLINE_CODE_RE.sub("", prose)
    front = parse_front_matter(md_text)
    title = front.get("title", "")
    if (_UNICODE_TOPIC_RE.search(title)
            or _GLYPH_PLACEHOLDER_MARKER_RE.search(md_text)):
        count = 0
    else:
        count = prose.count("\ufffd")
    badness = _ftfy_badness(md_text)
    if badness >= _MOJIBAKE_BADNESS_THRESHOLD:
        count += 1
    return count


def _heading_level_skips(tokens: list[dict]) -> int:
    """Count heading level skips (ascending only).

    Matches markdownlint MD001 (heading-increment) semantics:
    only flags when heading level increases by more than 1.
    Decreasing levels (closing a subsection) are always allowed.
    Source: https://github.com/DavidAnson/markdownlint/blob/main/doc/md001.md
    W3C WAI: https://www.w3.org/WAI/tutorials/page-structure/headings/

    Limitation: only scans top-level tokens. Headings nested inside
    blockquotes or list items (in 'children' arrays) are not checked.
    For WG21 papers this is acceptable because headings never appear
    inside blockquotes. See plans/QA-001-extend-qa-scoring.md,
    Research Finding #4 (Mistune AST completeness).
    """
    headings = [t for t in tokens if t.get("type", "") == "heading"]
    if len(headings) < 2:
        return 0
    skips = 0
    for i in range(1, len(headings)):
        prev_level = headings[i - 1].get("attrs", {}).get("level", 0)
        curr_level = headings[i].get("attrs", {}).get("level", 0)
        if curr_level > prev_level and curr_level - prev_level > 1:
            skips += 1
    return skips


def _count_table_parse_errors(tokens: list[dict]) -> int:
    """Count tables with inconsistent column counts across rows."""
    errors = 0
    for t in tokens:
        if t.get("type", "") != "table":
            continue
        children = t.get("children", [])
        col_counts: set[int] = set()
        for child in children:
            if child.get("type", "") in ("table_head", "table_body"):
                for row in child.get("children", []):
                    if row.get("type", "") == "table_row":
                        col_counts.add(len(row.get("children", [])))
        if len(col_counts) > 1:
            errors += 1
    return errors



def compute_metrics(md_text: str, file: str = "") -> QAMetrics:
    """Compute QA metrics by parsing the Markdown output with mistune.

    Takes only the Markdown text. No page count, no format hints.
    Everything is derived from the text itself.
    """
    m = QAMetrics(file=file)
    m.total_chars = len(md_text)
    m.empty_output = m.total_chars == 0 or not md_text.strip()

    if m.empty_output:
        m.score, m.issues = 0, ["empty output"]
        return m

    tokens = _AST_RENDERER(md_text)

    headings = [t for t in tokens if t.get("type", "") == "heading"]
    m.heading_count = len(headings)
    if headings:
        m.max_heading_level = max(
            t.get("attrs", {}).get("level", 0) for t in headings)

    m.code_block_count = sum(1 for t in tokens if t.get("type", "") == "block_code")

    m.list_count = sum(1 for t in tokens if t.get("type", "") == "list")

    m.table_count = sum(1 for t in tokens if t.get("type", "") == "table")

    # Front matter: mistune doesn't parse YAML, so we check raw text.
    # The AST's leading thematic_break confirms the --- opener.
    fm_fields = parse_front_matter(md_text)
    m.front_matter_count = sum(1 for k in FRONT_MATTER_ORDER if k in fm_fields)
    doc_val = fm_fields.get("document", "")
    m.has_doc_number = bool(_WG21_DOC_NUM_RE.search(doc_val))

    m.uncertain_count = sum(
        1 for t in tokens
        if t.get("type", "") == "block_html" and _UNCERTAIN_MARKER in t.get("raw", "")
    )

    m.lossy_table_count = sum(
        1 for t in tokens
        if t.get("type", "") == "block_html" and _LOSSY_TABLE_MARKER in t.get("raw", "")
    )

    paragraphs = [t for t in tokens if t.get("type", "") == "paragraph"]
    m.paragraph_count = len(paragraphs)
    m.unfenced_code_lines = _count_unfenced_code(paragraphs)

    m.mojibake_count = _count_mojibake(md_text)
    m.heading_level_skips = _heading_level_skips(tokens)

    m.wording_section_count = _count_wording_blocks(tokens)
    m.table_parse_errors = _count_table_parse_errors(tokens)

    m.score, m.issues = _score(m)
    return m


def _score(m: QAMetrics) -> tuple[int, list[str]]:
    """Compute 0-100 quality score purely from Markdown structure."""
    score = 100
    issues: list[str] = []

    if m.empty_output:
        return 0, ["empty output"]

    is_long = m.paragraph_count >= _LONG_DOC_MIN_PARAGRAPHS

    if m.uncertain_count > 0:
        penalty = min(_UNCERTAIN_MAX_PENALTY, _UNCERTAIN_PENALTY_PER * m.uncertain_count)
        score -= penalty
        issues.append(f"{m.uncertain_count} uncertain regions")

    if m.lossy_table_count > 0:
        issues.append(f"{m.lossy_table_count} lossy tables")

    if m.heading_count == 0 and is_long:
        score -= _NO_HEADINGS_PENALTY
        issues.append("no headings")

    if m.front_matter_count == 0 and is_long:
        score -= _NO_FRONT_MATTER_PENALTY
        issues.append("no front matter")

    if m.unfenced_code_lines > _UNFENCED_PER_BLOCK:
        penalty = min(_UNFENCED_MINOR_PENALTY, m.unfenced_code_lines)
        if m.code_block_count == 0 and m.unfenced_code_lines > _UNFENCED_MAJOR_THRESHOLD:
            penalty = min(_UNFENCED_MAX_PENALTY, penalty + _UNFENCED_MAJOR_EXTRA)
        score -= penalty
        issues.append(f"{m.unfenced_code_lines} unfenced code lines")

    has_structure = (m.heading_count > 0) + (m.code_block_count > 0) + \
                    (m.list_count > 0) + (m.table_count > 0)
    if is_long and has_structure <= 1:
        score -= _NO_STRUCTURE_VARIETY_PENALTY
        issues.append(f"low variety ({has_structure} structural types)")

    # Mojibake: encoding corruption is always a conversion bug.
    # Capped at 20 to avoid dominating the score on documents
    # with a single corrupted paragraph.
    # Decision: plans/QA-001-extend-qa-scoring.md, Phase 2.
    if m.mojibake_count > 0:
        penalty = min(_MOJIBAKE_MAX_PENALTY, _MOJIBAKE_PENALTY_PER * m.mojibake_count)
        score -= penalty
        issues.append(f"{m.mojibake_count} mojibake sequences")

    # Heading level skips: matches markdownlint MD001.
    # A skip usually means the converter mis-detected heading depth.
    # Capped at 15 because heading structure is important but not
    # as severe as encoding corruption (mojibake).
    # Decision: plans/QA-001-extend-qa-scoring.md, Phase 3.
    if m.heading_level_skips > 0:
        penalty = min(_HEADING_SKIP_MAX_PENALTY, _HEADING_SKIP_PENALTY_PER * m.heading_level_skips)
        score -= penalty
        issues.append(f"{m.heading_level_skips} heading level skips")

    return max(0, score), issues


def _qa_one(item: tuple[str, str]) -> dict:
    """Score the Markdown for a single ``(paper_id, markdown_text)`` pair.

    Scoring failures (anything raised inside :func:`compute_metrics`) are
    converted in-process to ``QAMetrics(score=0, issues=["qa error: ..."])``
    so one malformed paper does not abort the batch. These appear as
    zero-score rows in ``QABatchResult.metrics``, not in
    ``QABatchResult.errors``. Only worker-level failures the in-process
    handler cannot see (process crash, ``ProcessPoolExecutor`` timeout) are
    routed to ``errors`` by :func:`run_parallel_batch`.
    """
    paper_id, md_text = item
    try:
        m = compute_metrics(md_text, file=paper_id)
        return asdict(m)
    except Exception as exc:
        _log.error("QA failed for %s: %s", paper_id, exc)
        m = QAMetrics(file=paper_id, score=0,
                      issues=[f"qa error: {exc}"])
        return asdict(m)


def _qa_metrics_from_dict(d: dict) -> QAMetrics:
    return QAMetrics(**d)


@dataclass(frozen=True)
class QABatchResult:
    """Outcome of a batch QA scoring run.

    ``metrics`` holds successfully scored papers (including in-process
    scoring failures rendered as zero-score rows; see :func:`_qa_one`).
    ``errors`` is the canonical list of worker-level failures and is what
    :func:`format_qa_report` renders. ``timed_out`` is a typed subset view
    of ``errors`` (paper ids only) for callers that need to enumerate just
    the timeouts without parsing error messages.
    """

    metrics: tuple[QAMetrics, ...]
    errors: tuple[tuple[str, str], ...]
    timed_out: tuple[str, ...]
    elapsed_sec: float


def run_qa_batch(
    items: list[tuple[str, str]],
    *,
    workers: int = 1,
    timeout: int = _QA_BATCH_TIMEOUT_SEC,
    on_progress: ProgressCallback | None = None,
) -> QABatchResult:
    """Score a batch of converted papers and return ranked metrics.

    CLI-adjacent: callers format output via :func:`format_qa_report`.

    *items* is a list of ``(paper_id, markdown_text)`` pairs. Each markdown
    string is scored independently via :func:`compute_metrics`. Uses
    *workers* parallel processes (default 1 = sequential); *timeout* is
    seconds of no progress before aborting remaining items.
    """
    batch_items = [(pid, (pid, md)) for pid, md in items]

    run = run_parallel_batch(
        batch_items,
        _qa_one,
        workers=workers,
        timeout_sec=timeout,
        poll_interval_sec=_WORKER_POLL_INTERVAL,
        on_progress=on_progress,
    )

    results: list[QAMetrics] = []
    errors: list[tuple[str, str]] = []
    for item_id, outcome in run.outcomes:
        if isinstance(outcome, Exception):
            errors.append((item_id, str(outcome)))
        else:
            results.append(_qa_metrics_from_dict(outcome))

    for pid in run.timed_out:
        errors.append((pid, f"timeout (no progress for {timeout}s)"))

    results.sort(key=lambda r: r.score)
    return QABatchResult(
        metrics=tuple(results),
        errors=tuple(errors),
        timed_out=tuple(run.timed_out),
        elapsed_sec=run.elapsed_sec,
    )


def format_qa_report(
    results: Sequence[QAMetrics],
    errors: Sequence[tuple[str, str]] = (),
) -> str:
    """Return the ranked QA report text for stdout."""
    total = len(results)
    lines: list[str] = []

    lines.append(f"\ntomd QA Report: {total} files")
    lines.append("=" * 40)

    if total == 0:
        lines.append("\nNo papers were scored.")
        if errors:
            lines.append(f"\nErrors: {len(errors)}")
            for pid, msg in errors[:10]:
                lines.append(f"  {pid}: {msg}")
        return "\n".join(lines) + "\n"

    buckets = {"90-100": 0, "70-89": 0, "50-69": 0, "0-49": 0}
    for r in results:
        if r.score >= 90:
            buckets["90-100"] += 1
        elif r.score >= 70:
            buckets["70-89"] += 1
        elif r.score >= 50:
            buckets["50-69"] += 1
        else:
            buckets["0-49"] += 1

    lines.append("\nScore Distribution:")
    for label, count in buckets.items():
        pct = 100 * count / total if total else 0
        lines.append(f"  {label}: {count:>6}  ({pct:.1f}%)")

    needs_review = sum(1 for r in results if r.score < _NEEDS_REVIEW_THRESHOLD)
    lines.append(
        f"\nFiles needing review (score < {_NEEDS_REVIEW_THRESHOLD}): "
        f"{needs_review}"
    )
    lines.append(
        f"Files probably OK (score >= {_NEEDS_REVIEW_THRESHOLD}):   "
        f"{total - needs_review}"
    )

    worst = [r for r in results if r.score < 100][:_WORST_FILES_DISPLAY_LIMIT]
    if worst:
        lines.append(f"\nWorst {len(worst)} files:")
        lines.append(f"  {'Score':>5}  {'File':<40}  Issues")
        lines.append(f"  {'-----':>5}  {'-' * 40}  {'-' * 40}")
        for r in worst:
            name = r.file
            if len(name) > 40:
                name = name[:37] + "..."
            issue_str = ", ".join(r.issues) if r.issues else "ok"
            lines.append(f"  {r.score:>5}  {name:<40}  {issue_str}")

    if errors:
        lines.append(f"\nErrors: {len(errors)}")
        for pid, msg in errors[:10]:
            lines.append(f"  {pid}: {msg}")

    return "\n".join(lines) + "\n"


def write_qa_json_atomic(path: Path, results: Sequence[QAMetrics]) -> None:
    """Atomically write per-paper QA metrics as JSON."""
    rows = [asdict(r) for r in results]
    path.parent.mkdir(parents=True, exist_ok=True)
    json_bytes = json.dumps(rows, indent=2).encode("utf-8")
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(tmp_fd, json_bytes)
        os.close(tmp_fd)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.close(tmp_fd)
        except OSError:
            pass
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise
