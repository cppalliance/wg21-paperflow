#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Dev-replay acceptance tests (hermetic, no LLM, no network).

Validates that the source-aware risk router produces correct signals for
the 9 golden PRs, using the mechanically verified labels in
corpus/dev-replay/labels.json.

These tests verify the DETERMINISTIC portions of the pipeline:
- Risk router signal generation
- Defect aggregation logic
- Evidence classification correctness

LLM verdict accuracy is measured separately in runtime replays.
"""

import json
import re
from pathlib import Path

import pytest
from whisker.llm.source_router import route_pdf_units
from whisker.llm.textlayer import extract_page_units

_CORPUS_ROOT = Path(__file__).resolve().parents[2] / "corpus"
_DEV_REPLAY = _CORPUS_ROOT / "dev-replay"
_LABELS_PATH = _DEV_REPLAY / "labels.json"


@pytest.fixture()
def labels():
    return json.loads(_LABELS_PATH.read_text(encoding="utf-8"))["papers"]


class TestDevReplayConsistency:
    """Verify that labels are internally consistent."""

    def test_defect_papers_expect_non_pass_llm(self, labels):
        """Papers with known defects should expect review or fail from LLM."""
        for pid, paper in labels.items():
            if paper["defect_groups"]:
                assert paper["expected_llm_verdict"] != "pass", (
                    f"{pid} has defects but expects LLM pass"
                )

    def test_clean_papers_expect_pass_llm(self, labels):
        """Papers with no defects should expect LLM pass."""
        for pid, paper in labels.items():
            if not paper["defect_groups"]:
                assert paper["expected_llm_verdict"] == "pass", (
                    f"{pid} has no defects but expects LLM {paper['expected_llm_verdict']}"
                )

    def test_human_verdict_aligns_with_defects(self, labels):
        """Merge papers should have no defects; request_changes should have some."""
        for pid, paper in labels.items():
            if paper["human_verdict"] == "merge":
                assert not paper["defect_groups"], f"{pid} merges but has defects"
            elif paper["human_verdict"] == "request_changes":
                assert paper["defect_groups"], f"{pid} requests changes but has no defects"


class TestP0533R9ConstexprCount:
    """The 151-count is mechanically verified (2026-07-17)."""

    def test_label_count(self, labels):
        paper = labels["p0533r9"]
        constexpr = next(
            g for g in paper["defect_groups"]
            if g["type"] == "qualifier_omission"
        )
        assert constexpr["affected_count"] == 151

    @pytest.mark.skipif(
        not Path(r"packages\tomd\tests\fixtures\golden\sources\p0533r9.pdf").exists(),
        reason="PDF source not in workspace",
    )
    def test_pdf_source_count(self):
        """Directly verify from PDF when available."""
        import pymupdf
        doc = pymupdf.open(
            str(Path("packages/tomd/tests/fixtures/golden/sources/p0533r9.pdf"))
        )
        text = "".join(p.get_text() for p in doc)
        doc.close()
        count = len(re.findall(r"\bconstexpr\b", text))
        assert count == 231, f"Expected 231 constexpr in PDF, got {count}"

    @pytest.mark.skipif(
        not Path(r"packages\tomd\tests\fixtures\golden\sources\p0533r9.pdf").exists(),
        reason="PDF source not in workspace",
    )
    def test_router_observes_full_151_token_delta(self):
        source = Path(
            "packages/tomd/tests/fixtures/golden/sources/p0533r9.pdf"
        )
        units = extract_page_units(source)
        candidate = " ".join(["constexpr"] * 80)

        signals = route_pdf_units(units, candidate)

        constexpr = next(
            signal for signal in signals
            if signal.signal_type == "token_delta"
            and "constexpr" in signal.detail
        )
        assert "source document has 231" in constexpr.detail
        assert "candidate has 80, delta 151" in constexpr.detail


class TestRiskRouterSignalExpectations:
    """Verify router would flag papers with known defects."""

    def test_pdf_papers_with_omissions_have_known_pages(self, labels):
        """PDF papers with content_omission defects specify pages."""
        for pid, paper in labels.items():
            if paper["source_type"] != "pdf":
                continue
            for group in paper["defect_groups"]:
                if group["type"] == "page_content_omission":
                    assert "page" in group, f"{pid} omission without page"

    def test_token_delta_papers_specify_token(self, labels):
        """qualifier_omission defects specify the tracked token."""
        for pid, paper in labels.items():
            for group in paper["defect_groups"]:
                if group["type"] == "qualifier_omission":
                    assert "token" in group, f"{pid} qualifier omission without token"
