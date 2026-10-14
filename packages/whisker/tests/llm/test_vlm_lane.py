#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the VLM-PDF-Lane modules: vision, transcribe, vlm_diff, routing."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from whisker.llm.cli import _source_kind
from whisker.llm.vlm.transcribe import (
    TRANSCRIPTION_SYSTEM_PROMPT,
    PageTranscription,
    TranscriptionResult,
)
from whisker.llm.vlm.vision import (
    MAX_PAGES,
    TARGET_PIXELS,
    RasterError,
    rasterize_pdf,
)
from whisker.llm.vlm.vlm_diff import (
    NID_FAIL_THRESHOLD,
    NID_PASS_THRESHOLD,
    RECALL_FAIL_THRESHOLD,
    RECALL_PASS_THRESHOLD,
    diff_vlm_vs_tomd,
)

# ---------------------------------------------------------------------------
# Vision rasterization tests
# ---------------------------------------------------------------------------

class TestVisionConstants:
    def test_max_pages_is_positive(self):
        assert MAX_PAGES > 0

    def test_target_pixels_is_reasonable(self):
        assert 1_000_000 < TARGET_PIXELS < 10_000_000


class TestRasterError:
    def test_raises_on_nonexistent_file(self, tmp_path):
        fake_pdf = tmp_path / "nonexistent.pdf"
        with pytest.raises(RasterError, match="Cannot open PDF"):
            rasterize_pdf(fake_pdf)

    def test_raises_on_non_pdf(self, tmp_path):
        not_a_pdf = tmp_path / "test.pdf"
        not_a_pdf.write_bytes(b"not a pdf")
        with pytest.raises(RasterError):
            rasterize_pdf(not_a_pdf)


# ---------------------------------------------------------------------------
# Transcription schema tests
# ---------------------------------------------------------------------------

class TestPageTranscription:
    def test_with_text(self):
        pt = PageTranscription(text="Hello world")
        assert pt.text == "Hello world"

    def test_with_null(self):
        pt = PageTranscription(text=None)
        assert pt.text is None

    def test_from_json(self):
        data = {"text": "Some markdown"}
        pt = PageTranscription.model_validate(data)
        assert pt.text == "Some markdown"

    def test_null_from_json(self):
        data = {"text": None}
        pt = PageTranscription.model_validate(data)
        assert pt.text is None


class TestTranscriptionResult:
    def test_full_text_concatenation(self):
        tr = TranscriptionResult(
            pid="P1234R0",
            page_transcriptions=["Page 1 content", "Page 2 content"],
            page_count=2,
        )
        assert "Page 1 content" in tr.full_text
        assert "Page 2 content" in tr.full_text

    def test_empty_transcription(self):
        tr = TranscriptionResult(pid="P1234R0", page_count=0)
        assert tr.full_text == ""

    def test_status_default_ok(self):
        tr = TranscriptionResult(pid="P1234R0")
        assert tr.status == "ok"


class TestTranscriptionPrompt:
    def test_prompt_contains_key_instructions(self):
        assert "OCR" in TRANSCRIPTION_SYSTEM_PROMPT
        assert "LaTeX" in TRANSCRIPTION_SYSTEM_PROMPT
        assert "hallucinate" in TRANSCRIPTION_SYSTEM_PROMPT
        assert "Markdown" in TRANSCRIPTION_SYSTEM_PROMPT
        assert "Convert tables to Markdown pipe tables." not in TRANSCRIPTION_SYSTEM_PROMPT
        assert "dual strategy" in TRANSCRIPTION_SYSTEM_PROMPT
        assert "HTML <table>" in TRANSCRIPTION_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# VLM diff tests
# ---------------------------------------------------------------------------

class TestVlmDiff:
    def _make_transcription(self, text: str) -> TranscriptionResult:
        return TranscriptionResult(
            pid="P1234R0",
            page_transcriptions=[text],
            page_count=1,
        )

    def test_identical_text_passes(self):
        text = "This is the exact same content in both versions."
        result = diff_vlm_vs_tomd(
            "P1234R0",
            self._make_transcription(text),
            text,
        )
        assert result.verdict == "pass"
        assert result.text_nid >= NID_PASS_THRESHOLD

    def test_completely_different_text_fails(self):
        vlm_text = "Alpha beta gamma delta epsilon."
        tomd_text = "Xylophone umbrella volcano walrus zebra."
        result = diff_vlm_vs_tomd(
            "P1234R0",
            self._make_transcription(vlm_text),
            tomd_text,
        )
        assert result.verdict == "not-llm-readable"

    def test_slightly_different_text_reviews(self):
        vlm_text = "The function returns true if the value is positive and false otherwise. " * 5
        tomd_text = "The function returns true if the value is positive. " * 5
        result = diff_vlm_vs_tomd(
            "P1234R0",
            self._make_transcription(vlm_text),
            tomd_text,
        )
        assert result.verdict in ("review", "pass")

    def test_source_kind_is_pdf(self):
        result = diff_vlm_vs_tomd(
            "P1234R0",
            self._make_transcription("text"),
            "text",
        )
        assert result.source_kind == "pdf"

    def test_sidecar_dict_format(self):
        result = diff_vlm_vs_tomd(
            "P1234R0",
            self._make_transcription("some content"),
            "some content",
        )
        sidecar = result.to_sidecar_dict()
        assert sidecar["pid"] == "P1234R0"
        assert sidecar["status"] == "ok"
        assert sidecar["advisory"] is True
        assert "source_kind" in sidecar
        assert sidecar["source_kind"] == "pdf"
        assert "suggested_verdict" in sidecar
        assert "confidence" in sidecar
        assert "axis_findings" in sidecar
        assert "vlm_diff" in sidecar
        assert sidecar["vlm_diff"]["source_kind"] == "pdf"

    def test_sidecar_dict_has_required_fields_for_fusion(self):
        """Fusion reads verdict, axis_findings, confidence, status."""
        result = diff_vlm_vs_tomd(
            "P1234R0",
            self._make_transcription("x"),
            "x",
        )
        sidecar = result.to_sidecar_dict()
        assert "suggested_verdict" in sidecar
        assert "confidence" in sidecar
        assert "status" in sidecar
        assert "axis_findings" in sidecar

    def test_axis_findings_sorted(self):
        result = diff_vlm_vs_tomd(
            "P1234R0",
            self._make_transcription("content"),
            "content",
        )
        sidecar = result.to_sidecar_dict()
        axes = [f["axis"] for f in sidecar["axis_findings"]]
        assert axes == sorted(axes)


# ---------------------------------------------------------------------------
# Whisker-local vision task tests (pipeline stays text-only, untouched)
# ---------------------------------------------------------------------------

class TestVisionTask:
    """The vision machinery lives in whisker, not in pipeline."""

    def test_pipeline_stays_text_only(self):
        """Pipeline signatures carry no vision parameters."""
        import inspect

        from pipeline.agents import AgentBackend
        from pipeline.model_backends import BACKEND_REGISTRY, ModelBackend
        from pipeline.tasks import run_task
        assert "user_media" not in inspect.signature(ModelBackend.run).parameters
        assert "user_media" not in inspect.signature(AgentBackend.run).parameters
        assert "user_media" not in inspect.signature(run_task).parameters
        assert "vllm_vision" not in BACKEND_REGISTRY

    def test_vision_agent_construction(self):
        from whisker.llm.vlm.vision_task import VisionAgent
        agent = VisionAgent(
            base_url="http://localhost:8000/v1", api_key="k",
            model="olmocr", service_name="vision-pod",
        )
        assert agent.max_tokens == 16384
        assert agent.service_name == "vision-pod"

    def test_run_vision_task_has_user_media(self):
        import inspect

        from whisker.llm.vlm.vision_task import run_vision_task
        sig = inspect.signature(run_vision_task)
        assert "user_media" in sig.parameters
        assert sig.parameters["user_media"].default is None

    def test_serial_dispatch_semaphore(self):
        """D11: one in-flight vision request at a time."""
        from whisker.llm.vlm import vision_task
        assert vision_task._VISION_TASK_CONCURRENCY == 1

    def test_retry_budget_finite(self):
        from whisker.llm.vlm.vision_task import MAX_VISION_ATTEMPTS
        assert 1 <= MAX_VISION_ATTEMPTS <= 3

    def test_extract_json(self):
        from whisker.llm.vlm.vision_task import (
            VisionTaskError,
            _extract_json,
        )
        assert _extract_json('noise {"text": "x"} tail') == '{"text": "x"}'
        with pytest.raises(VisionTaskError, match="No JSON object"):
            _extract_json("no json here")

    def test_schema_instruction_contains_schema(self):
        from whisker.llm.vlm.vision_task import _schema_instruction
        block = _schema_instruction(PageTranscription)
        assert "JSON schema" in block
        assert "text" in block


# ---------------------------------------------------------------------------
# Diff verdict mapping tests
# ---------------------------------------------------------------------------

class TestDiffVerdictMapping:
    """Verify threshold-to-verdict mapping is deterministic."""

    def _make_tr(self, text: str) -> TranscriptionResult:
        return TranscriptionResult(pid="T", page_transcriptions=[text], page_count=1)

    def test_thresholds_ordered(self):
        assert NID_FAIL_THRESHOLD < NID_PASS_THRESHOLD
        assert RECALL_FAIL_THRESHOLD < RECALL_PASS_THRESHOLD

    def test_empty_vs_empty_passes(self):
        result = diff_vlm_vs_tomd("T", self._make_tr(""), "")
        assert result.verdict == "pass"


# ---------------------------------------------------------------------------
# Fidelity error path tests
# ---------------------------------------------------------------------------

class TestFidelityErrorPaths:
    def test_raster_error_on_too_many_pages(self):
        with pytest.raises(RasterError, match="exceeds cap"):
            with patch("whisker.llm.vlm.vision.pymupdf") as mock_pymupdf:
                mock_doc = MagicMock()
                mock_doc.page_count = MAX_PAGES + 1
                mock_pymupdf.open.return_value = mock_doc
                rasterize_pdf(Path("fake.pdf"), max_pages=MAX_PAGES)


# ---------------------------------------------------------------------------
# Source-kind routing tests
# ---------------------------------------------------------------------------

class TestVlmLaneReachabilityGuard:
    """Auditv5 finding (D3/M8): the dormant VLM lane (`vlm_pipeline.py`,
    `transcribe.py`, `vision_task.py`, `vlm_diff.py`, `vision.py`, ~800 LOC)
    has no production entry point but had no test asserting that. This
    AST-scans the actual production CLI surfaces (whisker's top-level
    `__main__.py`, `menu.py`, and the advisory lane's own `llm/cli.py`)
    and fails loudly if any of them come to import or reference the VLM
    modules. If someone later wires the VLM lane in, THIS test must fail and
    force a deliberate audit re-check rather than letting the wiring land as
    silent scope creep.

    Pure static analysis: no VLM import, no LLM call, hermetic.
    """

    _SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "whisker"

    _ENTRY_POINTS = (
        _SRC_ROOT / "__main__.py",
        _SRC_ROOT / "menu.py",
        _SRC_ROOT / "llm" / "cli.py",
    )

    # Module names and the one currently-dormant symbol per module that
    # would prove real wiring, not just an incidental docstring mention.
    _BANNED_MODULES = frozenset({
        "vlm_pipeline", "transcribe", "vision_task", "vlm_diff", "vision",
    })
    _BANNED_SYMBOLS = frozenset({"vlm_adjudicate_paper"})

    @staticmethod
    def _imported_module_leaf_names(tree: ast.Module) -> set[str]:
        """Every module name a file imports, either `import x.y.z` (leaf
        `z`) or `from x.y import z` (module `y`, not the imported name)."""
        leaves: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    leaves.add(alias.name.rsplit(".", 1)[-1])
            elif isinstance(node, ast.ImportFrom) and node.module:
                leaves.add(node.module.rsplit(".", 1)[-1])
        return leaves

    @staticmethod
    def _referenced_names(tree: ast.Module) -> set[str]:
        """Every bare Name/Attribute identifier appearing anywhere (catches
        `vlm_adjudicate_paper(...)` even if imported under an alias)."""
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
        return names

    def test_entry_points_exist(self):
        """Sanity check: if these paths go stale, the guard below is vacuous."""
        for path in self._ENTRY_POINTS:
            assert path.is_file(), f"expected production entry point missing: {path}"

    def test_no_production_entry_point_imports_the_vlm_lane(self):
        violations: list[str] = []
        for path in self._ENTRY_POINTS:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            imported = self._imported_module_leaf_names(tree)
            hit_modules = imported & self._BANNED_MODULES
            if hit_modules:
                violations.append(
                    f"{path}: imports dormant VLM module(s) {sorted(hit_modules)}"
                )

            referenced = self._referenced_names(tree)
            hit_symbols = referenced & self._BANNED_SYMBOLS
            if hit_symbols:
                violations.append(
                    f"{path}: references dormant VLM symbol(s) {sorted(hit_symbols)}"
                )

        assert not violations, (
            "The dormant VLM lane appears wired into a production entry "
            "point. This is a deliberate architectural decision (see "
            "CLAUDE.md known gap #4, 'VLM lane is unwired') that requires "
            "an explicit audit re-check, not a silent landing:\n"
            + "\n".join(violations)
        )


class TestSourceKindRouting:
    def test_pdf_detection(self):
        backend = MagicMock()
        backend.get_source_path.return_value = Path("/data/P1234R0.pdf")
        assert _source_kind("P1234R0", backend) == "pdf"

    def test_html_detection(self):
        backend = MagicMock()
        backend.get_source_path.return_value = Path("/data/P1234R0.html")
        assert _source_kind("P1234R0", backend) == "html"

    def test_htm_detection(self):
        backend = MagicMock()
        backend.get_source_path.return_value = Path("/data/P1234R0.htm")
        assert _source_kind("P1234R0", backend) == "html"

    def test_unknown_extension(self):
        backend = MagicMock()
        backend.get_source_path.return_value = Path("/data/P1234R0.docx")
        assert _source_kind("P1234R0", backend) == "unknown"

    def test_missing_source(self):
        backend = MagicMock()
        backend.get_source_path.side_effect = Exception("not found")
        assert _source_kind("P1234R0", backend) == "unknown"
