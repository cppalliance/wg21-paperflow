#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Per-paper substring / section-order anchors (localized tripwires).

The fuzzy axes (nid/teds/mhs) and the coverage floor catch AGGREGATE text loss.
Anchors are the complement: author-curated assertions that a specific phrase MUST
or MUST NOT appear (optionally in document order) in the converted markdown. A
paper can pass the metric slack while silently dropping a critical phrase (the
markitdown red-team finding); a one-line anchor catches exactly that.

The field uses exact, normalized substring matching for this (markitdown
``must_include`` / ``must_not_include`` + ordered ``str.find`` chains; firecrawl
``toContain``; olmocr presence/absence/order facts). Fuzzy hit-rate only appears
where OCR/VLM noise is expected; tomd's deterministic path does not need it, so
anchors stay exact (no edit-distance threshold to tune, fully auditable).

Anchors are CONJUNCTIVE with the metric guard: an anchor miss is a hard fail even
when the numeric slack holds. This module is pure (returns data); the CLI reads
``<pid>.anchors.json`` and owns exit codes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from whisker.metrics import normalized_text

__all__ = [
    "ANCHOR_KIND",
    "AnchorCheck",
    "AnchorPattern",
    "AnchorReport",
    "AnchorSpec",
    "anchor_spec_from_dict",
    "check_anchors",
]

ANCHOR_KIND = "whisker-anchors"

SURFACE_NORMALIZED = "normalized"
SURFACE_RAW = "raw"
_VALID_SURFACES = {SURFACE_NORMALIZED, SURFACE_RAW}

# Only this small, named set of re flags is honored from JSON; an unknown flag is
# a hard error rather than a silent no-op (anchors are a trusted gate).
_FLAG_MAP = {
    "MULTILINE": re.MULTILINE, "M": re.MULTILINE,
    "IGNORECASE": re.IGNORECASE, "I": re.IGNORECASE,
    "DOTALL": re.DOTALL, "S": re.DOTALL,
}


@dataclass(frozen=True)
class AnchorPattern:
    id: str
    regex: str
    flags: str = ""


@dataclass(frozen=True)
class AnchorSpec:
    pid: str
    surface: str = SURFACE_NORMALIZED
    must_contain: tuple[str, ...] = ()
    must_not_contain: tuple[str, ...] = ()
    ordered: tuple[str, ...] = ()
    patterns: tuple[AnchorPattern, ...] = ()


@dataclass(frozen=True)
class AnchorCheck:
    id: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict:
        return {"id": self.id, "passed": self.passed, "detail": self.detail}


@dataclass(frozen=True)
class AnchorReport:
    pid: str
    checks: tuple[AnchorCheck, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failed(self) -> bool:
        return not self.passed

    def failures(self) -> list[AnchorCheck]:
        return [c for c in self.checks if not c.passed]

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "passed": self.passed,
            "checks": [c.to_dict() for c in self.checks],
        }


def _compile_flags(spec_flags: str) -> int:
    flags = 0
    for token in re.split(r"[|\s]+", spec_flags.strip()):
        if not token:
            continue
        if token not in _FLAG_MAP:
            raise ValueError(f"unknown regex flag {token!r} (allowed: {sorted(_FLAG_MAP)})")
        flags |= _FLAG_MAP[token]
    return flags


def _surface(md: str, surface: str) -> str:
    if surface == SURFACE_RAW:
        return md
    return normalized_text(md)


def check_anchors(md: str, spec: AnchorSpec) -> AnchorReport:
    """Evaluate every anchor against the candidate markdown. Deterministic.

    Each check is an independent pass/fail with a human-readable detail. The
    rolled-up report passes only when every check passes (conjunctive).
    """
    haystack = _surface(md, spec.surface)
    checks: list[AnchorCheck] = []

    for i, needle in enumerate(spec.must_contain):
        ok = needle in haystack
        checks.append(AnchorCheck(
            f"must_contain[{i}]", ok,
            "" if ok else f"missing required text {needle!r}",
        ))

    for i, needle in enumerate(spec.must_not_contain):
        ok = needle not in haystack
        checks.append(AnchorCheck(
            f"must_not_contain[{i}]", ok,
            "" if ok else f"forbidden text present {needle!r}",
        ))

    # Ordered: every anchor must be found and their first occurrences must be
    # strictly increasing in document order.
    prev_pos = -1
    prev_needle: str | None = None
    for i, needle in enumerate(spec.ordered):
        pos = haystack.find(needle)
        if pos == -1:
            checks.append(AnchorCheck(
                f"ordered[{i}]", False, f"missing ordered anchor {needle!r}",
            ))
            # A missing anchor breaks the chain; do not advance prev_pos.
            continue
        if pos <= prev_pos:
            checks.append(AnchorCheck(
                f"ordered[{i}]", False,
                f"{needle!r} at {pos} not after {prev_needle!r} at {prev_pos}",
            ))
        else:
            checks.append(AnchorCheck(f"ordered[{i}]", True))
        prev_pos = pos
        prev_needle = needle

    for pat in spec.patterns:
        ok = re.search(pat.regex, haystack, _compile_flags(pat.flags)) is not None
        checks.append(AnchorCheck(
            f"pattern[{pat.id}]", ok,
            "" if ok else f"pattern {pat.regex!r} did not match",
        ))

    return AnchorReport(pid=spec.pid, checks=tuple(checks))


_KNOWN_KEYS = {
    "schema_version", "kind", "pid", "surface",
    "must_contain", "must_not_contain", "ordered", "patterns",
}


def _str_list(raw: object, field_name: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(s, str) for s in raw):
        raise ValueError(f"anchors '{field_name}' must be a list of strings")
    return tuple(raw)


def anchor_spec_from_dict(data: dict, pid: str) -> AnchorSpec:
    """Validate and build an ``AnchorSpec`` from a parsed ``<pid>.anchors.json``.

    Rejects an unknown ``kind``, unknown top-level keys, a bad ``surface``, and
    malformed patterns. The anchors file is trusted config but is hand-authored,
    so a typo must surface loudly rather than silently disabling a tripwire.
    """
    if not isinstance(data, dict):
        raise ValueError("anchors file must be a JSON object")
    kind = data.get("kind")
    if kind is not None and kind != ANCHOR_KIND:
        raise ValueError(f"anchors kind {kind!r} != {ANCHOR_KIND!r}")
    unknown = set(data) - _KNOWN_KEYS
    if unknown:
        raise ValueError(f"anchors file has unknown key(s): {sorted(unknown)}")
    surface = data.get("surface", SURFACE_NORMALIZED)
    if surface not in _VALID_SURFACES:
        raise ValueError(f"anchors surface {surface!r} not in {sorted(_VALID_SURFACES)}")

    raw_patterns = data.get("patterns", []) or []
    if not isinstance(raw_patterns, list):
        raise ValueError("anchors 'patterns' must be a list")
    patterns: list[AnchorPattern] = []
    for p in raw_patterns:
        if not isinstance(p, dict) or "regex" not in p:
            raise ValueError("each anchor pattern needs at least a 'regex'")
        pat = AnchorPattern(
            id=str(p.get("id", p["regex"])),
            regex=str(p["regex"]),
            flags=str(p.get("flags", "")),
        )
        # Validate flags + regex eagerly; re.error is not a ValueError, so wrap
        # it so the CLI's single ValueError handler reports a bad anchors file.
        try:
            re.compile(pat.regex, _compile_flags(pat.flags))
        except re.error as exc:
            raise ValueError(f"invalid anchor regex {pat.regex!r}: {exc}") from exc
        patterns.append(pat)

    return AnchorSpec(
        pid=pid,
        surface=surface,
        must_contain=_str_list(data.get("must_contain"), "must_contain"),
        must_not_contain=_str_list(data.get("must_not_contain"), "must_not_contain"),
        ordered=_str_list(data.get("ordered"), "ordered"),
        patterns=tuple(patterns),
    )
