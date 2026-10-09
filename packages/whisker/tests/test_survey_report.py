#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for whisker.survey.report: schema, Aussagegrenzen, corpus_version."""

import json

import pytest
from whisker.survey.report import (
    AUSSAGEGRENZEN_TEXT,
    aussagegrenzen_text,
    build_report_json,
    render_report_md,
)


@pytest.fixture
def sample_report():
    """Build a minimal valid report for testing."""
    return build_report_json(
        competitor_name="marker",
        competitor_version="2.0.0",
        corpus_version=1,
        timestamp="2026-08-01T12:00:00+00:00",
        lane1={"tomd": [{"pid": "P1000R0", "stable": True}]},
        lane2={"tomd": [{"pid": "P1000R0", "nid": 0.95, "teds": 0.8, "mhs": 0.9, "overall": 0.88, "content_recall": 0.92}]},
        lane3={"tomd": [{"pid": "P1000R0", "verdict": "pass", "verified_count": 5, "passed": 5}]},
        lane2_aggregate={"tomd": {"overall": 0.88}},
    )


class TestReportSchema:
    """Report JSON schema validation."""

    def test_required_keys_present(self, sample_report):
        required_keys = {
            "schema_version",
            "kind",
            "competitor",
            "competitor_version",
            "corpus_version",
            "timestamp",
            "aussagegrenzen",
            "lane1_stability",
            "lane2_fidelity",
            "lane2_aggregate",
            "lane3_comprehension",
        }
        assert required_keys.issubset(sample_report.keys())

    def test_schema_version(self, sample_report):
        assert sample_report["schema_version"] == 1

    def test_kind(self, sample_report):
        assert sample_report["kind"] == "whisker-survey-report"

    def test_corpus_version_present(self, sample_report):
        assert sample_report["corpus_version"] == 1

    def test_corpus_version_propagates(self):
        report = build_report_json(
            competitor_name="marker",
            competitor_version="2.0.0",
            corpus_version=42,
            timestamp="2026-08-01T12:00:00+00:00",
            lane1={},
            lane2={},
            lane3={},
            lane2_aggregate={},
        )
        assert report["corpus_version"] == 42

    def test_aussagegrenzen_text_present(self, sample_report):
        assert sample_report["aussagegrenzen"] == AUSSAGEGRENZEN_TEXT
        assert "explorative" in sample_report["aussagegrenzen"]
        assert "five short WG21" in sample_report["aussagegrenzen"]
        assert "NOT claim general superiority" in sample_report["aussagegrenzen"]

    def test_tesseract_aussagegrenzen_names_ocr(self):
        text = aussagegrenzen_text("tesseract")
        assert "Tesseract" in text
        assert "OCR running text" in text
        assert "Marker" not in text

    def test_json_serializable(self, sample_report):
        text = json.dumps(sample_report)
        roundtrip = json.loads(text)
        assert roundtrip == sample_report


class TestReportMarkdown:
    """Markdown report rendering tests."""

    def test_render_contains_corpus_version(self, sample_report):
        md = render_report_md(sample_report)
        assert "Corpus version" in md
        assert "1" in md

    def test_render_contains_aussagegrenzen(self, sample_report):
        md = render_report_md(sample_report)
        assert "Aussagegrenzen" in md
        assert "explorative" in md
        assert "five short WG21" in md

    def test_render_contains_competitor(self, sample_report):
        md = render_report_md(sample_report)
        assert "marker" in md
        assert "2.0.0" in md

    def test_render_contains_lane_headers(self, sample_report):
        md = render_report_md(sample_report)
        assert "Lane 1" in md
        assert "Lane 2" in md
        assert "Lane 3" in md

    def test_render_preamble_is_case_study(self, sample_report):
        md = render_report_md(sample_report)
        assert "Fallstudie" in md or "case study" in md
