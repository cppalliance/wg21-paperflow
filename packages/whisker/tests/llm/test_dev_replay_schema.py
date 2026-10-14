#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Schema validation for the dev-replay and holdout corpora.

Ensures committed labels and anchors are structurally valid so they can be
used as acceptance gates without runtime parse failures.
"""

import hashlib
import json
from pathlib import Path

import pytest
from whisker.llm.grounding import (
    CANDIDATE_AMBIGUOUS,
    CANDIDATE_PRESENT,
    GROUND_EXACT,
    GroundedSpan,
    classify_candidate_evidence,
)
from whisker.llm.models import EvidenceSpan

_CORPUS_ROOT = Path(__file__).resolve().parents[2] / "corpus"
_DEV_REPLAY = _CORPUS_ROOT / "dev-replay"
_HOLDOUT = _CORPUS_ROOT / "holdout"
_REPO_ROOT = Path(__file__).resolve().parents[4]

_VALID_STRATA = {
    "metadata", "headings", "prose", "punctuation",
    "code", "tables", "figures", "math",
}
_VALID_CANDIDATE_STATUSES = {
    "present_in_candidate", "candidate_not_found", "ambiguous",
}
_VALID_VERDICTS = {"pass", "review", "not-llm-readable"}
_VALID_SEVERITIES = {"low", "medium", "high", "critical"}


def _sha256_source_bytes(path: Path) -> str:
    """Fingerprint a binary source file (PDF) on its raw bytes.

    Source files are binary: byte-for-byte hashing is correct here and
    carries no checkout-dependent line-ending ambiguity (there are no text
    line endings to normalize in a PDF).
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_candidate_text(path: Path) -> str:
    """Fingerprint a text candidate (markdown) on line-ending-normalized text.

    H5 audit finding: candidate files are text, and git's ``core.autocrlf``
    checks them out as CRLF on Windows and LF elsewhere. Hashing raw bytes
    (``path.read_bytes()``) makes the fingerprint a property of the
    CHECKOUT, not the content: an unmodified file re-pinned on one OS then
    fails this test on every other OS/CI runner. Normalizing ``\\r\\n`` and
    lone ``\\r`` to ``\\n`` before encoding makes the fingerprint identical
    on CRLF and LF checkouts, so only real content drift can fail this
    check. Never call this on a binary source file.
    """
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _load_anchors(pid: str) -> list[dict]:
    path = _HOLDOUT / f"{pid}.anchors.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _candidate_dispositions(anchors: list[dict], markdown: str) -> list[str]:
    axes = {"code": "code", "tables": "tables", "math": "math"}
    source_grounded = [
        GroundedSpan(
            EvidenceSpan(
                axis=axes.get(anchor["stratum"], "structure"),
                quote=anchor["quote"],
                reason=anchor["anchor_id"],
            ),
            GROUND_EXACT,
        )
        for anchor in anchors
    ]
    return [
        item.candidate_status
        for item in classify_candidate_evidence(source_grounded, markdown)
    ]


class TestDevReplayLabels:
    @pytest.fixture()
    def labels(self):
        path = _DEV_REPLAY / "labels.json"
        assert path.exists(), "dev-replay/labels.json missing"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_schema_version(self, labels):
        assert labels["$schema"] == "dev-replay-labels-v1"

    def test_nine_papers(self, labels):
        assert len(labels["papers"]) == 9

    def test_all_papers_have_required_fields(self, labels):
        for pid, paper in labels["papers"].items():
            assert "pr" in paper, f"{pid} missing pr"
            assert "source_type" in paper, f"{pid} missing source_type"
            assert paper["source_type"] in {"pdf", "html"}, f"{pid} bad source_type"
            assert "human_verdict" in paper, f"{pid} missing human_verdict"
            assert "defect_groups" in paper, f"{pid} missing defect_groups"
            assert "expected_llm_verdict" in paper, f"{pid} missing expected_llm_verdict"
            assert "expected_det_verdict" in paper, f"{pid} missing expected_det_verdict"
            assert paper["expected_llm_verdict"] in _VALID_VERDICTS
            assert paper["expected_det_verdict"] in _VALID_VERDICTS

    def test_defect_groups_have_valid_structure(self, labels):
        for pid, paper in labels["papers"].items():
            for idx, group in enumerate(paper["defect_groups"]):
                assert "type" in group, f"{pid}[{idx}] missing type"
                assert "description" in group, f"{pid}[{idx}] missing description"
                assert "affected_count" in group, f"{pid}[{idx}] missing affected_count"
                assert group["affected_count"] > 0, f"{pid}[{idx}] count must be > 0"
                assert "severity" in group, f"{pid}[{idx}] missing severity"
                assert group["severity"] in _VALID_SEVERITIES, (
                    f"{pid}[{idx}] bad severity: {group['severity']}"
                )

    def test_p0533r9_constexpr_count_verified(self, labels):
        """The 151-count was mechanically verified on 2026-07-17."""
        paper = labels["papers"]["p0533r9"]
        constexpr_group = next(
            g for g in paper["defect_groups"]
            if g["type"] == "qualifier_omission"
        )
        assert constexpr_group["affected_count"] == 151
        assert constexpr_group["token"] == "constexpr"


class TestHoldoutAnchors:
    @pytest.fixture()
    def manifest(self):
        return json.loads(
            (_HOLDOUT / "manifest.json").read_text(encoding="utf-8")
        )

    @pytest.fixture()
    def anchor_files(self, manifest):
        files = [
            _HOLDOUT / f"{pid}.anchors.jsonl"
            for pid in manifest["papers"]
        ]
        assert all(path.exists() for path in files)
        assert len(files) >= 2, "Need at least 2 holdout papers"
        return files

    def test_active_holdout_excludes_dev_replay(self, manifest):
        labels = json.loads(
            (_DEV_REPLAY / "labels.json").read_text(encoding="utf-8")
        )
        assert set(manifest["papers"]).isdisjoint(labels["papers"])
        assert "p0533r9" in manifest["quarantined"]

    def test_all_anchors_valid_schema(self, anchor_files):
        total = 0
        for path in anchor_files:
            for line_num, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not line.strip():
                    continue
                anchor = json.loads(line)
                assert "anchor_id" in anchor, f"{path.name}:{line_num}"
                assert "stratum" in anchor, f"{path.name}:{line_num}"
                assert anchor["stratum"] in _VALID_STRATA, (
                    f"{path.name}:{line_num} bad stratum: {anchor['stratum']}"
                )
                assert "quote" in anchor, f"{path.name}:{line_num}"
                assert "expected_candidate_status" in anchor, f"{path.name}:{line_num}"
                assert anchor["expected_candidate_status"] in _VALID_CANDIDATE_STATUSES
                total += 1
        assert total >= 48, f"Need >= 48 anchors total, got {total}"

    def test_strata_coverage(self, anchor_files):
        """Holdout must cover at least 4 distinct strata."""
        strata: set[str] = set()
        for path in anchor_files:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                anchor = json.loads(line)
                strata.add(anchor["stratum"])
        assert len(strata) >= 4, f"Only {len(strata)} strata covered: {strata}"

    def test_locked_candidate_dispositions(self, manifest):
        locked = manifest["locked_candidates"]
        assert set(locked) == set(manifest["papers"])
        assert "p0533r9" not in locked

        for pid in manifest["papers"]:
            fixture = locked[pid]
            source_path = _REPO_ROOT / fixture["source_path"]
            candidate_path = _REPO_ROOT / fixture["candidate_path"]
            assert _sha256_source_bytes(source_path) == fixture["source_sha256"], pid
            assert _sha256_candidate_text(candidate_path) == fixture["candidate_sha256"], (
                pid
            )

            anchors = _load_anchors(pid)
            actual = _candidate_dispositions(
                anchors,
                candidate_path.read_text(encoding="utf-8"),
            )
            for anchor, disposition in zip(anchors, actual, strict=True):
                assert disposition == anchor["expected_candidate_status"], (
                    f"{pid}:{anchor['anchor_id']}"
                )

    def test_candidate_fingerprint_tripwire_detects_content_drift(self, manifest):
        """The line-ending-normalized fingerprint still has teeth (H5).

        Re-pinning a holdout lock is exactly how a control silently dies.
        Prove the opposite: a deliberately altered in-memory copy of a real
        locked candidate must NOT hash to its pinned value, so genuine
        content drift on a future PR still fails
        ``test_locked_candidate_dispositions`` instead of being silently
        absorbed by the normalization.
        """
        locked = manifest["locked_candidates"]
        for pid in manifest["papers"]:
            fixture = locked[pid]
            candidate_path = _REPO_ROOT / fixture["candidate_path"]
            original = candidate_path.read_text(encoding="utf-8")
            tampered = original + "\nTRIPWIRE-CANARY-MUST-NOT-MATCH\n"
            tampered_hash = hashlib.sha256(
                tampered.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
            ).hexdigest()
            assert tampered_hash != fixture["candidate_sha256"], (
                f"{pid}: tripwire failed to detect tampered content"
            )

            # Also prove normalization alone (no content change) is a no-op:
            # re-encoding the SAME content with the opposite line ending
            # must still match, confirming the fix actually solves the
            # checkout-dependence bug rather than coincidentally matching.
            crlf_copy = original.replace("\r\n", "\n").replace("\r", "\n").replace(
                "\n", "\r\n"
            )
            crlf_hash = hashlib.sha256(
                crlf_copy.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
            ).hexdigest()
            assert crlf_hash == fixture["candidate_sha256"], (
                f"{pid}: fingerprint is not checkout-independent"
            )

    def test_case_and_punctuation_disposition_canaries(self, manifest):
        fixture = manifest["locked_candidates"]["p3714r0"]
        candidate_path = _REPO_ROOT / fixture["candidate_path"]
        candidate = candidate_path.read_text(encoding="utf-8")
        anchors = {
            anchor["anchor_id"]: anchor for anchor in _load_anchors("p3714r0")
        }

        case_anchor = anchors["p3714r0-prose-05"]
        assert _candidate_dispositions([case_anchor], candidate) == [
            CANDIDATE_PRESENT
        ]
        case_changed = candidate.replace("FLT_EVAL_METHOD", "flt_eval_method")
        assert _candidate_dispositions([case_anchor], case_changed) == [
            CANDIDATE_AMBIGUOUS
        ]

        punctuation_anchor = anchors["p3714r0-code-03"]
        assert _candidate_dispositions([punctuation_anchor], candidate) == [
            CANDIDATE_PRESENT
        ]
        punctuation_changed = candidate.replace(
            "assert(mul + z == sum(mul, z));",
            "assert(mul + z != sum(mul, z));",
        )
        assert _candidate_dispositions(
            [punctuation_anchor], punctuation_changed
        ) == [CANDIDATE_AMBIGUOUS]

    def test_quotes_exist_on_declared_source_pages(self, anchor_files):
        import pymupdf

        sources = (
            Path(__file__).resolve().parents[3]
            / "tomd"
            / "tests"
            / "fixtures"
            / "golden"
            / "sources"
        )
        for path in anchor_files:
            pid = path.name.split(".", maxsplit=1)[0]
            document = pymupdf.open(sources / f"{pid}.pdf")
            try:
                for line_num, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), start=1
                ):
                    anchor = json.loads(line)
                    page = anchor["source_location"]["page"]
                    page_text = document[page - 1].get_text()
                    assert anchor["quote"] in page_text, (
                        f"{path.name}:{line_num} quote absent from page {page}"
                    )
            finally:
                document.close()
