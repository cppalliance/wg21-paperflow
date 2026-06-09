"""Table of Contents detection.

Format-agnostic: operates on plain strings and returns indices.
No dependency on PDF or HTML converter types.
"""

import logging
import re

from . import SECTION_NUM_PREFIX_RE
from .similarity import similar

_log = logging.getLogger(__name__)

_TRAILING_PAGE_NUM_RE = re.compile(r"\s+\d{1,4}\s*$")
_DOT_LEADER_RE = re.compile(r"\s*[.·]{2,}[\s.·]*")
_SPACED_DOT_LEADER_RE = re.compile(r"(?:\. ){2,}\.")
# Tighter threshold for TOC *detection* (vs stripping in normalization).
# 5+ consecutive dots avoids false positives on ellipsis (...) and
# C++ variadic syntax (Args...) that appear heavily in WG21 papers.
_DOT_LEADER_DETECT_RE = re.compile(r"[.·]{5,}")

# Canonical Table-of-Contents line shape: a dot leader followed by a trailing
# page number ("Foo .......... 7"). A bare trailing number is intentionally
# not sufficient: body headings like "Step 1" / "Phase 2" carry one and must
# never be treated as TOC entries.
_TOC_LINE_RE = re.compile(r"[.·]{2,}\s*\d{1,4}\s*$")

_TOC_LABELS = frozenset({
    "table of contents",
    "table of content",
    "contents",
})

_WHITESPACE_RE = re.compile(r"\s+")

# Minimum length of a contiguous run that counts as a Table of Contents.
# Public because `pdf/structure.py:drop_leaked_toc_entries` (the
# companion pass that removes leaked TOC entries that `find_toc_indices`
# deliberately stops matching, #122) gates on the same run length. Shared
# so the two "what is a TOC" definitions cannot drift.
MIN_TOC_RUN = 3
_MAX_GAP = 3
_MAX_FUZZY_HEADINGS = 200

# A non-matching gap section is bridged into a TOC run only if its first line
# is trivial (a short label, a bare number, blank). A real prose paragraph
# exceeds this and breaks the run instead of being swallowed.
_MAX_BRIDGE_ENTRY_WORDS = 6


def _first_line(text: str) -> str:
    """Extract and strip the first line of a multi-line string."""
    return text.split("\n")[0].strip()


def has_dot_leader(text: str) -> bool:
    """Check for dot leaders in any form (compact or spaced).

    Uses _DOT_LEADER_DETECT_RE (5+ dots) instead of _DOT_LEADER_RE (2+)
    to avoid false positives on ellipsis and C++ variadic syntax.
    """
    return bool(_DOT_LEADER_DETECT_RE.search(text) or _SPACED_DOT_LEADER_RE.search(text))


def normalize_toc_entry(text: str) -> str:
    """Normalize text for TOC comparison.

    Strips trailing page numbers, dot leaders, section number prefixes.
    Collapses whitespace, lowercases.
    """
    text = _first_line(text)
    text = _DOT_LEADER_RE.sub(" ", text)
    text = _SPACED_DOT_LEADER_RE.sub(" ", text)
    text = _TRAILING_PAGE_NUM_RE.sub("", text)
    text = SECTION_NUM_PREFIX_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text).strip().lower()
    return text


def is_toc_label(text: str) -> bool:
    """Check if text is a TOC heading label."""
    normalized = text.strip().lower()
    normalized = _WHITESPACE_RE.sub(" ", normalized)
    return normalized in _TOC_LABELS


def _toc_structured(text: str) -> bool:
    """True if the first line is shaped like a TOC line (dot leader + page number).

    This is the one shape that lets a heading-kind section still count as a TOC
    entry: a genuine numbered TOC line such as "2.1 Foo .......... 7" that
    section numbering pushed into HEADING classification. A bare trailing
    number ("Step 1") does not qualify.
    """
    return bool(_TOC_LINE_RE.search(_first_line(text)))


def _bridgeable(text: str) -> bool:
    """True if a non-matching gap section is trivial enough to bridge a TOC run.

    Trivial means: blank, or (after stripping any section-number prefix) at most
    _MAX_BRIDGE_ENTRY_WORDS words with no sentence-terminal punctuation. A real
    prose paragraph fails this test and breaks the run rather than being
    swallowed into it.
    """
    line = _first_line(text)
    if not line:
        return True
    stripped = SECTION_NUM_PREFIX_RE.sub("", line).strip()
    if not stripped:
        return True
    if stripped[-1] in ".!?":
        return False
    return len(stripped.split()) <= _MAX_BRIDGE_ENTRY_WORDS


def find_toc_indices(
    texts: list[str],
    headings: set[str],
    structural_hints: list[bool] | None = None,
    full_texts: list[str] | None = None,
    is_heading: list[bool] | None = None,
    non_toc_indices: set[int] | None = None,
) -> set[int]:
    """Return indices of entries that form a Table of Contents.

    texts: ordered list of section first-line texts from the document
    headings: set of known heading texts to match against
    structural_hints: optional per-section booleans marking entries that
        look like TOC entries by structure (standalone page number on the
        second line at a consistent x position). Used as a fallback when
        headings is empty, e.g. in headingless wording-only papers.
    full_texts: optional full section texts (multi-line). When provided,
        dot-leader detection checks the full text, catching leaders on
        lines beyond the first.
    is_heading: optional per-section booleans marking which sections are
        themselves headings in the body. A heading cannot count as a TOC
        *match* (it would match itself against the heading set and the
        gap-fill would then swallow the prose between body headings, deleting
        the body of short papers) UNLESS its own text is shaped like a TOC
        line (see _toc_structured), which preserves stripping of a genuine
        numbered TOC entry that section numbering classified as a heading.
        This is the refined guard the pipeline passes in production.

    Production contract: any caller that passes a non-empty `headings` set
    derived from the document's own headings MUST also pass `is_heading`.
    Omitting it resurrects the body-deletion bug (every heading self-matches).
    A debug line is logged when the likely-misuse shape is seen.
    non_toc_indices: indices that cannot themselves be TOC entries (a
        heading is part of the document structure, not a forward pointer
        into it). They neither match a heading nor anchor a run, but the
        algorithm still walks past them as ordinary non-matches subject
        to the usual gap budget. This is a coarser alternative to
        is_heading (no _toc_structured exception); both guards coexist.

    Both texts and headings are normalized before comparison. Detects runs
    of MIN_TOC_RUN+ consecutive matches, bridging only trivial gap sections
    (see _bridgeable). Also includes any "Table of Contents" label immediately
    preceding a run.

    Companion pass: a heading-kind TOC whose entries lack the dot-leader shape
    is deliberately *not* matched here (the is_heading guard), so it leaks as
    empty duplicate headings; `pdf/structure.py:drop_leaked_toc_entries`
    removes those, gating on the same shared `MIN_TOC_RUN`. The two functions
    are the structural and the post-structure halves of one "what is a TOC"
    definition; keep them in sync.
    """
    if not texts:
        return set()
    if not headings and not structural_hints:
        return set()

    if headings and is_heading is None:
        _log.debug("no is_heading supplied; heading self-match guard inactive "
                   "(%d headings)", len(headings))

    skip = non_toc_indices or set()

    norm_headings = {normalize_toc_entry(h) for h in headings}
    norm_headings.discard("")

    # Fast exact-match set covers the common case; fuzzy matching only
    # runs on the residual. Without this, O(sections * headings) calls
    # to similar() make large documents (2000+ pages) hang.
    _exact_set = frozenset(norm_headings)

    def _matches_heading(text: str) -> bool:
        norm = normalize_toc_entry(text)
        if not norm:
            return False
        if norm in _exact_set:
            return True
        if len(norm_headings) > _MAX_FUZZY_HEADINGS:
            return False
        for h in norm_headings:
            if similar(norm, h):
                return True
        return False

    # Bare section-number line: digits/dots or single uppercase letter.
    # When the first line is just a number, try joining with line 2
    # for heading comparison (handles multi-line TOC entries where
    # MuPDF splits section number and title onto separate lines).
    _BARE_NUM_RE = re.compile(r"^(?:[A-Z]|\d+(?:\.\d+)*\.?)$")

    def _multi_line_match(ft_text: str) -> bool:
        lines = ft_text.split("\n")
        if len(lines) < 2:
            return False
        first = lines[0].strip()
        if not _BARE_NUM_RE.match(first):
            return False
        joined = first + " " + lines[1].strip()
        return _matches_heading(joined)

    matches = []
    for i, text in enumerate(texts):
        if i in skip:
            matches.append(False)
            continue
        ft = full_texts[i] if full_texts else text
        # Check dot-leaders per line to avoid false positives on body
        # paragraphs that happen to contain 5+ dots (ASCII art, code).
        has_dot = any(has_dot_leader(ln) for ln in ft.split("\n"))
        if norm_headings:
            # A body heading would match itself in the heading set; exclude it
            # unless its own text is shaped like a TOC line (a genuine numbered
            # TOC entry classified as a heading).
            if (is_heading
                    and i < len(is_heading)
                    and is_heading[i]
                    and not _toc_structured(text)):
                matches.append(False)
            else:
                first_match_ok = _matches_heading(_first_line(text))
                if not first_match_ok and not has_dot:
                    first_match_ok = _multi_line_match(ft)
                matches.append(has_dot or first_match_ok)
        else:
            matches.append(
                has_dot
                or bool(structural_hints
                        and i < len(structural_hints)
                        and structural_hints[i])
            )

    # Find the first match - everything before it is pre-TOC (title, metadata)
    first_match = -1
    for i, m in enumerate(matches):
        if m:
            first_match = i
            break

    if first_match < 0:
        return set()

    run_indices: list[int] = []
    seen_first_lines: set[str] = set()
    gap = 0

    for i in range(first_match, len(matches)):
        if matches[i]:
            first_line = _first_line(texts[i]).lower()
            if first_line in seen_first_lines:
                break
            seen_first_lines.add(first_line)
            if gap > 0:
                for g in range(i - gap, i):
                    run_indices.append(g)
            gap = 0
            run_indices.append(i)
        else:
            # Only trivial gap sections bridge a run; a real prose paragraph
            # breaks it rather than being swallowed in as phantom TOC content.
            if not _bridgeable(texts[i]):
                break
            gap += 1
            if gap > _MAX_GAP:
                break

    match_count = sum(1 for i in run_indices if matches[i])
    toc_indices: set[int] = set()
    if match_count >= MIN_TOC_RUN:
        toc_indices = set(run_indices)
        _log.debug("TOC block: %d entries (%d matched)",
                    len(run_indices), match_count)

    # Include "Table of Contents" / "Contents" label before the block
    if toc_indices:
        first = min(toc_indices)
        prev = first - 1
        if prev >= 0 and is_toc_label(_first_line(texts[prev])):
            toc_indices.add(prev)
            _log.debug("TOC label at index %d", prev)

    if toc_indices:
        _log.info("Detected TOC: %d entries detected", len(toc_indices))

    return toc_indices
