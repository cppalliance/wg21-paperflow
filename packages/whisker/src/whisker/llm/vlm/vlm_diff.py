#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Deterministic diff: VLM transcription vs tomd-Markdown.

After the VLM produces a pixel-only transcription of the PDF and tomd
produces its conversion, this module scores their agreement using the
existing whisker metrics (text_nid, content_recall) and maps the result
to a tapetum-compatible sidecar with verdict + axis_findings.

The VLM saw only pixels (independence guarantee). The comparison is
fully deterministic (no LLM, no randomness). The sidecar format is
identical to the text-lane tapetum output so fusion.py works unchanged.

Library-pure: returns data, never persists.

Dormant status: this prototype is reachable only from the unwired VLM entry
point. It is retained as tested prior art and is not production coverage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from whisker.llm.vlm.transcribe import TranscriptionResult
from whisker.metrics import (
    content_recall,
    has_headings,
    mhs,
    normalized_text,
    text_nid,
)

logger = logging.getLogger(__name__)

__all__ = [
    "VlmDiffResult",
    "diff_vlm_vs_tomd",
    "NID_PASS_THRESHOLD",
    "NID_FAIL_THRESHOLD",
    "RECALL_PASS_THRESHOLD",
    "RECALL_FAIL_THRESHOLD",
]

NID_PASS_THRESHOLD = 0.85
"""text_nid above this = content agreement high enough to pass."""

NID_FAIL_THRESHOLD = 0.60
"""text_nid below this = substantial content mismatch = fail."""

RECALL_PASS_THRESHOLD = 0.90
"""Content recall above this = tomd captured most of the VLM's text."""

RECALL_FAIL_THRESHOLD = 0.70
"""Content recall below this = significant omissions = fail."""

MHS_REVIEW_THRESHOLD = 0.70
"""Heading similarity below this triggers a structure review flag."""


@dataclass
class VlmDiffResult:
    """Deterministic diff verdict between VLM transcription and tomd-Markdown."""

    pid: str
    source_kind: str
    verdict: str
    confidence: float
    text_nid: float
    content_recall: float
    mhs_score: float | None
    page_count: int
    axis_findings: list[dict] = field(default_factory=list)
    primary_concern: str = ""
    vlm_model: str = ""

    def to_sidecar_dict(self) -> dict:
        """Produce a tapetum-compatible sidecar dict for fusion.

        The format is deliberately identical to TapetumResult.to_dict()
        so fuse_verdicts works unchanged (reads verdict, axis_findings,
        confidence, status).
        """
        return {
            "pid": self.pid,
            "status": "ok",
            "source_kind": self.source_kind,
            "whisker_verdict": "",
            "suggested_verdict": self.verdict,
            "confidence": round(self.confidence, 4),
            "escalated": False,
            "escalation_signals": [],
            "tier1_model": self.vlm_model,
            "tier2_model": None,
            "axis_findings": sorted(
                self.axis_findings, key=lambda d: d.get("axis", "")
            ),
            "grounded_evidence": [],
            "ungrounded_dropped": 0,
            "primary_concern": self.primary_concern,
            "reasoning": (
                f"VLM-PDF-Lane diff: text_nid={self.text_nid:.4f}, "
                f"recall={self.content_recall:.4f}, "
                f"mhs={f'{self.mhs_score:.4f}' if self.mhs_score is not None else 'N/A'}, "
                f"pages={self.page_count}"
            ),
            "advisory": True,
            "vlm_diff": {
                "text_nid": round(self.text_nid, 4),
                "content_recall": round(self.content_recall, 4),
                "mhs": round(self.mhs_score, 4) if self.mhs_score is not None else None,
                "page_count": self.page_count,
                "source_kind": self.source_kind,
            },
            "schema_version": 2,
        }


def diff_vlm_vs_tomd(
    pid: str,
    transcription: TranscriptionResult,
    tomd_markdown: str,
    *,
    vlm_model: str = "",
) -> VlmDiffResult:
    """Score VLM transcription against tomd-Markdown deterministically.

    Returns a VlmDiffResult with verdict (pass/review/fail), per-axis
    findings, and the raw metrics. The verdict mapping:

    - **pass**: text_nid >= NID_PASS and recall >= RECALL_PASS
    - **fail**: text_nid < NID_FAIL or recall < RECALL_FAIL
    - **review**: everything else (ambiguous zone)
    """
    vlm_text = transcription.full_text
    tomd_text = tomd_markdown

    nid = text_nid(normalized_text(vlm_text), normalized_text(tomd_text))
    recall = content_recall(tomd_text, vlm_text)

    mhs_val: float | None = None
    if has_headings(vlm_text) or has_headings(tomd_text):
        mhs_val = mhs(tomd_text, vlm_text)

    findings: list[dict] = []
    concerns: list[str] = []

    text_verdict, text_severity = _score_to_axis(nid, NID_PASS_THRESHOLD, NID_FAIL_THRESHOLD)
    findings.append({
        "axis": "wording",
        "verdict": text_verdict,
        "severity": text_severity,
        "note": f"text_nid={nid:.4f} (VLM vs tomd content agreement)",
    })
    if text_verdict != "pass":
        concerns.append(f"text agreement {nid:.4f}")

    recall_verdict, recall_severity = _score_to_axis(recall, RECALL_PASS_THRESHOLD, RECALL_FAIL_THRESHOLD)
    findings.append({
        "axis": "structure",
        "verdict": recall_verdict,
        "severity": recall_severity,
        "note": f"content_recall={recall:.4f} (tomd coverage of VLM text)",
    })
    if recall_verdict != "pass":
        concerns.append(f"recall {recall:.4f}")

    if mhs_val is not None:
        mhs_verdict = "pass" if mhs_val >= MHS_REVIEW_THRESHOLD else "review"
        mhs_severity = "none" if mhs_verdict == "pass" else "minor"
        findings.append({
            "axis": "stable_names",
            "verdict": mhs_verdict,
            "severity": mhs_severity,
            "note": f"mhs={mhs_val:.4f} (heading structure similarity)",
        })
        if mhs_verdict != "pass":
            concerns.append(f"heading similarity {mhs_val:.4f}")

    overall = _overall_verdict(text_verdict, recall_verdict)
    confidence = min(nid, recall)

    return VlmDiffResult(
        pid=pid,
        source_kind="pdf",
        verdict=overall,
        confidence=confidence,
        text_nid=nid,
        content_recall=recall,
        mhs_score=mhs_val,
        page_count=transcription.page_count,
        axis_findings=findings,
        primary_concern="; ".join(concerns) if concerns else "VLM and tomd agree",
        vlm_model=vlm_model,
    )


def _score_to_axis(
    score: float, pass_threshold: float, fail_threshold: float
) -> tuple[str, str]:
    """Map a [0,1] score to (verdict, severity)."""
    if score >= pass_threshold:
        return "pass", "none"
    if score < fail_threshold:
        return "not-llm-readable", "major"
    return "review", "minor"


def _overall_verdict(text_verdict: str, recall_verdict: str) -> str:
    """Worst-of-two verdicts. fail > review > pass."""
    rank = {"not-llm-readable": 0, "review": 1, "pass": 2}
    worst = min(rank.get(text_verdict, 2), rank.get(recall_verdict, 2))
    for v, r in rank.items():
        if r == worst:
            return v
    return "review"
