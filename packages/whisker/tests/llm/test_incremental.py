#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the incremental fingerprint system in the tapetum-llm CLI."""

from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from whisker.llm.cli import (
    _LANE_VERSION,
    _compute_fingerprint,
    _effective_model_contract,
    _fingerprint_matches,
    _llm_output_dir,
    _load_services_config,
    _pdf_prompt_contract,
    _pdf_schema_contract,
    _read_existing_fingerprint,
    _read_existing_sidecar_status,
    _sha256_file,
    _sha256_str,
    _text_prompt_contract,
    _text_schema_contract,
    _write_error_tombstone,
)
from whisker.llm.pdf_judge import PAGE_JUDGE_SYSTEM_PROMPT
from whisker.llm.unit_judge import (
    METADATA_CHECK_SYSTEM_PROMPT,
    UNIT_CHECK_SYSTEM_PROMPT,
)

_DUMMY_SCHEMA = '{"type":"object"}'


# ---------------------------------------------------------------------------
# Stub backend (minimal: get_paper_md_path + get_source_path)
# ---------------------------------------------------------------------------


class _FakeBackend:
    """Duck-typed backend for fingerprint tests."""

    def __init__(self, md_path: Path, source_path: Path, workspace: Path) -> None:
        self._md_path = md_path
        self._source_path = source_path
        self.workspace_dir = workspace

    def get_paper_md_path(self, pid: str) -> Path:
        return self._md_path

    def get_source_path(self, pid: str) -> Path:
        return self._source_path


def _make_backend(tmp_path: Path) -> _FakeBackend:
    md = tmp_path / "paperstore" / "p1r0.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("# Title\n\nBody text.", encoding="utf-8")
    src = tmp_path / "paperstore" / "p1r0.pdf"
    src.write_bytes(b"%PDF-1.4 fake pdf bytes")
    return _FakeBackend(md, src, tmp_path)


def _sidecar_dir(tmp_path: Path) -> Path:
    """Create the whisker/llm/ directory structure."""
    d = tmp_path / "whisker" / "llm"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# SHA helpers
# ---------------------------------------------------------------------------


class TestShaHelpers:
    def test_sha256_str_deterministic(self):
        assert _sha256_str("hello") == _sha256_str("hello")
        assert _sha256_str("hello") != _sha256_str("world")

    def test_sha256_file_deterministic(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("content", encoding="utf-8")
        assert _sha256_file(f) == _sha256_file(f)

    def test_sha256_file_changes_with_content(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("v1", encoding="utf-8")
        h1 = _sha256_file(f)
        f.write_text("v2", encoding="utf-8")
        h2 = _sha256_file(f)
        assert h1 != h2


# ---------------------------------------------------------------------------
# Fingerprint computation
# ---------------------------------------------------------------------------


class TestComputeFingerprint:
    def test_lane_version_covers_fail_closed_source_checks(self):
        assert _LANE_VERSION == 26

    def test_lane_version_is_current(self):
        assert _LANE_VERSION == 26

    def test_pdf_contract_includes_source_aware_calls(self):
        prompt = _pdf_prompt_contract()
        schema = json.loads(_pdf_schema_contract())
        assert PAGE_JUDGE_SYSTEM_PROMPT in prompt
        assert METADATA_CHECK_SYSTEM_PROMPT in prompt
        assert UNIT_CHECK_SYSTEM_PROMPT in prompt
        assert "PageJudgment" in schema
        assert "MetadataOutlineCheck" in schema
        assert "UnitCheck" in schema
        assert "UnitCheckClear" in schema
        assert "UnitCheckDefects" in schema

    def test_text_contract_includes_source_aware_calls(self):
        pipeline_prompt = SimpleNamespace(
            system_prompt="base",
            steps=(
                SimpleNamespace(system_prompt="triage-specific"),
                SimpleNamespace(system_prompt=""),
                SimpleNamespace(system_prompt="deep-specific"),
            ),
        )
        prompt = _text_prompt_contract(pipeline_prompt)
        schema = json.loads(_text_schema_contract())
        assert prompt.startswith("base")
        assert "triage-specific" in prompt
        assert "deep-specific" in prompt
        assert METADATA_CHECK_SYSTEM_PROMPT in prompt
        assert UNIT_CHECK_SYSTEM_PROMPT in prompt
        assert "MetadataOutlineCheck" in schema
        assert "UnitCheck" in schema
        assert "UnitCheckClear" in schema
        assert "UnitCheckDefects" in schema

    def test_fingerprint_covers_every_lane_output_schema(self):
        """B1 guard: every pydantic output model dispatched to the LLM by
        this lane must be enumerated in both schema contracts that feed the
        fingerprint. Mechanical approximation: walk the known LLM-call
        output_type classes (models.py + pdf_judge.py) and assert each
        class name appears in at least one of the two contracts. This
        catches a class being added to an LLM call site and forgotten in
        _pdf_schema_contract/_text_schema_contract, the exact bug class
        that produced the missing UnitCheckClear/UnitCheckDefects gap.
        """
        from whisker.llm.models import (
            Adjudication,
            IdealVerification,
            MetadataOutlineCheck,
            UnitCheck,
            UnitCheckClear,
            UnitCheckDefects,
        )
        from whisker.llm.pdf_judge import PageJudgment, PdfJudgment

        # IdealVerification is covered separately via ideal_schema_sha256,
        # not the lane schema contracts; excluded here deliberately.
        lane_output_models = [
            Adjudication, MetadataOutlineCheck, UnitCheck,
            UnitCheckClear, UnitCheckDefects, PageJudgment, PdfJudgment,
        ]
        pdf_schema = _pdf_schema_contract()
        text_schema = _text_schema_contract()
        combined = pdf_schema + text_schema
        for model in lane_output_models:
            assert model.__name__ in combined, (
                f"{model.__name__} is an LLM output_type but is missing "
                "from both fingerprint schema contracts"
            )
        assert IdealVerification is not None

    def test_deterministic(self, tmp_path):
        backend = _make_backend(tmp_path)
        fp1 = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "model-a", _DUMMY_SCHEMA)
        fp2 = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "model-a", _DUMMY_SCHEMA)
        assert fp1 == fp2

    def test_contains_required_keys(self, tmp_path):
        backend = _make_backend(tmp_path)
        fp = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "model-a", _DUMMY_SCHEMA)
        for key in ("md_sha256", "source_sha256", "prompt_sha256",
                    "model", "lane_version", "lane", "schema_sha256",
                    "unit_check_mode",
                    "ideal_sha256", "ideal_prompt_sha256",
                    "ideal_schema_sha256", "ideal_model", "coverage_mode"):
            assert key in fp
        assert fp["ideal_sha256"] is None
        assert fp["ideal_prompt_sha256"] is None
        assert fp["ideal_schema_sha256"] is None
        assert fp["ideal_model"] is None
        assert fp["coverage_mode"] == "default"

    def test_unit_check_mode_toggle_invalidates_fingerprint(
        self, tmp_path, monkeypatch,
    ):
        """B1: flipping TAPETUM_VERDICT_FIRST changes which unit-check
        output schema is actually dispatched to the LLM even when neither
        schema's own JSON changed, so it must be part of the fingerprint."""
        backend = _make_backend(tmp_path)
        monkeypatch.setenv("TAPETUM_VERDICT_FIRST", "1")
        fp_on = _compute_fingerprint(
            "P1R0", backend, "pdf", "prompt", "model-a", _DUMMY_SCHEMA,
        )
        monkeypatch.setenv("TAPETUM_VERDICT_FIRST", "0")
        fp_off = _compute_fingerprint(
            "P1R0", backend, "pdf", "prompt", "model-a", _DUMMY_SCHEMA,
        )
        assert fp_on["unit_check_mode"] != fp_off["unit_check_mode"]
        assert fp_on != fp_off

    def test_coverage_mode_differs_default_vs_all_pages(self, tmp_path):
        backend = _make_backend(tmp_path)
        fp_default = _compute_fingerprint(
            "P1R0", backend, "pdf", "prompt", "model-a", _DUMMY_SCHEMA,
            coverage_mode="default",
        )
        fp_all = _compute_fingerprint(
            "P1R0", backend, "pdf", "prompt", "model-a", _DUMMY_SCHEMA,
            coverage_mode="all_pages",
        )
        assert fp_default["coverage_mode"] == "default"
        assert fp_all["coverage_mode"] == "all_pages"
        assert fp_default != fp_all

    def test_lane_version_matches_constant(self, tmp_path):
        backend = _make_backend(tmp_path)
        fp = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "model-a", _DUMMY_SCHEMA)
        assert fp["lane_version"] == _LANE_VERSION

    def test_changes_on_md_edit(self, tmp_path):
        backend = _make_backend(tmp_path)
        fp1 = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "model-a", _DUMMY_SCHEMA)
        backend._md_path.write_text("# Changed", encoding="utf-8")
        fp2 = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "model-a", _DUMMY_SCHEMA)
        assert fp1["md_sha256"] != fp2["md_sha256"]

    def test_changes_on_source_edit(self, tmp_path):
        backend = _make_backend(tmp_path)
        fp1 = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "model-a", _DUMMY_SCHEMA)
        backend._source_path.write_bytes(b"new source bytes")
        fp2 = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "model-a", _DUMMY_SCHEMA)
        assert fp1["source_sha256"] != fp2["source_sha256"]

    def test_changes_on_prompt_edit(self, tmp_path):
        backend = _make_backend(tmp_path)
        fp1 = _compute_fingerprint("P1R0", backend, "pdf", "prompt-v1", "model-a", _DUMMY_SCHEMA)
        fp2 = _compute_fingerprint("P1R0", backend, "pdf", "prompt-v2", "model-a", _DUMMY_SCHEMA)
        assert fp1["prompt_sha256"] != fp2["prompt_sha256"]

    def test_changes_on_model_change(self, tmp_path):
        backend = _make_backend(tmp_path)
        fp1 = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "model-a", _DUMMY_SCHEMA)
        fp2 = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "model-b", _DUMMY_SCHEMA)
        assert fp1["model"] != fp2["model"]

    def test_changes_on_lane_change(self, tmp_path):
        backend = _make_backend(tmp_path)
        fp1 = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "model-a", _DUMMY_SCHEMA)
        fp2 = _compute_fingerprint("P1R0", backend, "text", "prompt", "model-a", _DUMMY_SCHEMA)
        assert fp1["lane"] != fp2["lane"]

    def test_changes_on_schema_change(self, tmp_path):
        backend = _make_backend(tmp_path)
        schema_v1 = json.dumps({"type": "object", "properties": {"a": {"type": "string"}}}, sort_keys=True)
        schema_v2 = json.dumps({"type": "object", "properties": {"a": {"type": "string", "description": "at most 20 words"}}}, sort_keys=True)
        fp1 = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "model-a", schema_v1)
        fp2 = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "model-a", schema_v2)
        assert fp1["schema_sha256"] != fp2["schema_sha256"]

    def test_ideal_add_change_and_remove_change_fingerprint(self, tmp_path):
        backend = _make_backend(tmp_path)
        without = _compute_fingerprint(
            "P1R0", backend, "text", "prompt", "model-a", _DUMMY_SCHEMA
        )

        added = _compute_fingerprint(
            "P1R0",
            backend,
            "text",
            "prompt",
            "model-a",
            _DUMMY_SCHEMA,
            ideal_text="# Ideal v1",
        )
        changed = _compute_fingerprint(
            "P1R0",
            backend,
            "text",
            "prompt",
            "model-a",
            _DUMMY_SCHEMA,
            ideal_text="# Ideal v2",
        )
        removed = _compute_fingerprint(
            "P1R0", backend, "text", "prompt", "model-a", _DUMMY_SCHEMA
        )

        assert without["ideal_sha256"] is None
        assert added["ideal_sha256"] != changed["ideal_sha256"]
        assert added != without
        assert changed != added
        assert removed == without

    def test_ideal_fingerprint_records_verifier_identities_without_path(
        self,
        tmp_path,
    ):
        from whisker.llm.ideal_verify import IDEAL_VERIFY_PROMPT_CONTRACT

        backend = _make_backend(tmp_path)
        ideal_text = "# Ideal\n\nExact verifier input."

        fp = _compute_fingerprint(
            "P1R0",
            backend,
            "text",
            "prompt",
            "model-contract",
            _DUMMY_SCHEMA,
            ideal_text=ideal_text,
        )

        assert fp["ideal_sha256"] == _sha256_str(ideal_text)
        assert fp["ideal_prompt_sha256"] == _sha256_str(
            IDEAL_VERIFY_PROMPT_CONTRACT
        )
        assert fp["ideal_schema_sha256"]
        assert fp["ideal_model"] == "model-contract"
        assert ideal_text not in json.dumps(fp)

    def test_same_schema_same_hash(self, tmp_path):
        backend = _make_backend(tmp_path)
        schema = json.dumps({"type": "object", "properties": {"x": {"type": "integer"}}}, sort_keys=True)
        fp1 = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "model-a", schema)
        fp2 = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "model-a", schema)
        assert fp1["schema_sha256"] == fp2["schema_sha256"]


class TestEffectiveModelContract:
    @staticmethod
    def _services() -> dict[str, str]:
        return {
            "fast": "stable-alias",
            "deep": "stable-alias",
            "default": "stable-alias",
        }

    @staticmethod
    def _config(
        *,
        backend: str = "vllm_thinking",
        model: str = "model-a",
        base_url: str = "https://models.example/v1",
        api_key: str = "$MODEL_KEY",
        unrelated_model: str = "unrelated-a",
    ) -> str:
        return (
            "[services.stable-alias]\n"
            f'backend = "{backend}"\n'
            f'model = "{model}"\n'
            f'base_url = "{base_url}"\n'
            f'api_key = "{api_key}"\n'
            "max_context_window = 131072\n"
            "chars_per_token = 4.0\n"
            "token_multiplier = 1.3\n"
            "thinking_capable = true\n"
            "tools_capable = false\n"
            "stream = true\n\n"
            "[services.unrelated]\n"
            'backend = "vllm_thinking"\n'
            f'model = "{unrelated_model}"\n'
            'base_url = "https://unrelated.example/v1"\n'
            'api_key = "$UNRELATED_KEY"\n'
        )

    @staticmethod
    def _write_config(tmp_path: Path, text: str, name: str = "SERVICES.toml"):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8", newline="")
        return _load_services_config(path)

    def test_same_alias_changed_selected_model_invalidates(self, tmp_path):
        backend = _make_backend(tmp_path)
        config_a = self._write_config(
            tmp_path, self._config(model="model-a"), "a.toml"
        )
        config_b = self._write_config(
            tmp_path, self._config(model="model-b"), "b.toml"
        )
        contract_a = _effective_model_contract(
            self._services(),
            config_a,
        )
        contract_b = _effective_model_contract(
            self._services(),
            config_b,
        )

        fp_a = _compute_fingerprint(
            "P1R0", backend, "text", "prompt", contract_a, _DUMMY_SCHEMA
        )
        fp_b = _compute_fingerprint(
            "P1R0", backend, "text", "prompt", contract_b, _DUMMY_SCHEMA
        )

        assert fp_a["model"] != fp_b["model"]

    @pytest.mark.parametrize(
        ("field", "first", "second"),
        [
            ("backend", "vllm_thinking", "qwen3"),
            ("base_url", "https://one.example/v1", "https://two.example/v1"),
            ("max_context_window", 131072, 262144),
            ("tools_capable", False, True),
        ],
    )
    def test_selected_effective_field_change_invalidates(
        self, tmp_path, field, first, second
    ):
        config = self._write_config(tmp_path, self._config())
        config_a = json.loads(json.dumps(config))
        config_b = json.loads(json.dumps(config))
        config_a["services"]["stable-alias"][field] = first
        config_b["services"]["stable-alias"][field] = second

        assert _effective_model_contract(
            self._services(), config_a
        ) != _effective_model_contract(self._services(), config_b)

    def test_canonical_contract_ignores_format_unrelated_and_credentials(
        self, tmp_path
    ):
        lf = self._config(
            api_key="$MODEL_KEY",
            unrelated_model="unrelated-a",
        )
        crlf = (
            "# different comments\r\n"
            + self._config(
                api_key="rotated-literal-secret",
                unrelated_model="unrelated-b",
            ).replace("\n", "\r\n")
        )
        config_a = self._write_config(tmp_path, lf, "a.toml")
        config_b = self._write_config(tmp_path, crlf, "b.toml")
        contract_a = _effective_model_contract(self._services(), config_a)
        contract_b = _effective_model_contract(self._services(), config_b)

        assert contract_a == contract_b
        assert "rotated-literal-secret" not in contract_b
        assert "api_key" not in contract_b
        assert "unrelated" not in contract_b

    def test_contract_covers_all_effective_slots_and_sanitizes_url(self, tmp_path):
        config = self._write_config(
            tmp_path,
            self._config(
                base_url=(
                    "https://user:password@models.example:8443/v1"
                    "?api_key=also-secret"
                ),
            ),
        )
        contract = _effective_model_contract(self._services(), config)
        payload = json.loads(contract)

        assert payload["slots"] == {
            "deep": "stable-alias",
            "default": "stable-alias",
            "fast": "stable-alias",
        }
        assert payload["services"]["stable-alias"]["base_url"] == (
            "https://models.example:8443/v1"
        )
        assert "password" not in contract
        assert "also-secret" not in contract

    def test_cli_contains_no_private_pipeline_backend_access(self):
        from whisker.llm import cli

        source = inspect.getsource(cli)
        for attribute in ("_model", "_model_name", "_base_url", "_api_key"):
            assert f".{attribute}" not in source
            assert f'"{attribute}"' not in source


class TestHealthProbeConfig:
    @pytest.mark.parametrize(
        ("base_url", "expected_url"),
        [
            ("https://models.example/v1", "https://models.example/health"),
            ("https://models.example/v1/", "https://models.example/health"),
            ("https://models.example", "https://models.example/health"),
            ("https://models.example/", "https://models.example/health"),
        ],
    )
    def test_probe_uses_root_health_endpoint(
        self, monkeypatch, base_url, expected_url
    ):
        from whisker.llm import cli

        config = {
            "services": {
                "stable-alias": {
                    "base_url": base_url,
                }
            }
        }
        prompt = SimpleNamespace(services={"fast": "stable-alias"})
        calls = {}

        class Response:
            @staticmethod
            def raise_for_status():
                return None

        class Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return False

            async def get(self, url, *, headers):
                calls["url"] = url
                return Response()

        monkeypatch.setattr(cli.PipelinePrompt, "load", lambda *_args: prompt)
        monkeypatch.setattr(cli.httpx, "AsyncClient", lambda **_kwargs: Client())

        asyncio.run(cli._probe_llm_endpoint({}, config))

        assert calls["url"] == expected_url

    @pytest.mark.parametrize(
        ("raw_key", "env_value", "expected"),
        [
            ("$MODEL_KEY", "env-secret", "env-secret"),
            ("literal-secret", "", "literal-secret"),
        ],
    )
    def test_probe_resolves_config_credential_without_logging_it(
        self, monkeypatch, caplog, raw_key, env_value, expected
    ):
        from whisker.llm import cli

        if env_value:
            monkeypatch.setenv("MODEL_KEY", env_value)
        config = {
            "services": {
                "stable-alias": {
                    "base_url": "https://models.example/v1",
                    "api_key": raw_key,
                }
            }
        }
        prompt = SimpleNamespace(
            services={
                "fast": "stable-alias",
                "deep": "stable-alias",
                "default": "stable-alias",
            }
        )
        calls = {}

        class Response:
            @staticmethod
            def raise_for_status():
                return None

        class Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return False

            async def get(self, url, *, headers):
                calls["url"] = url
                calls["headers"] = headers
                return Response()

        monkeypatch.setattr(cli.PipelinePrompt, "load", lambda *_args: prompt)
        monkeypatch.setattr(cli.httpx, "AsyncClient", lambda **_kwargs: Client())

        asyncio.run(cli._probe_llm_endpoint({}, config))

        assert calls == {
            "url": "https://models.example/health",
            "headers": {"Authorization": f"Bearer {expected}"},
        }
        assert expected not in caplog.text

    def test_probe_override_selects_configured_service(self, monkeypatch):
        from whisker.llm import cli

        config = {
            "services": {
                "default-service": {
                    "base_url": "https://default.example/v1",
                    "api_key": "default-secret",
                },
                "override-service": {
                    "base_url": "https://override.example/v1",
                    "api_key_env": "OVERRIDE_KEY",
                },
            }
        }
        monkeypatch.setenv("OVERRIDE_KEY", "override-secret")
        prompt = SimpleNamespace(
            services={
                "fast": "default-service",
                "deep": "default-service",
                "default": "default-service",
            }
        )
        calls = {}

        class Response:
            @staticmethod
            def raise_for_status():
                return None

        class Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return False

            async def get(self, url, *, headers):
                calls["url"] = url
                calls["headers"] = headers
                return Response()

        monkeypatch.setattr(cli.PipelinePrompt, "load", lambda *_args: prompt)
        monkeypatch.setattr(cli.httpx, "AsyncClient", lambda **_kwargs: Client())

        asyncio.run(
            cli._probe_llm_endpoint(
                {"fast": "override-service"},
                config,
            )
        )

        assert calls["url"] == "https://override.example/health"
        assert calls["headers"] == {
            "Authorization": "Bearer override-secret"
        }


class TestCliBudgetsAndDebug:
    def test_text_timeout_budgets_metadata_and_all_units(self, monkeypatch):
        from whisker.llm import cli

        monkeypatch.setattr(cli, "_PAPER_TIMEOUT_SECONDS", 100.0)
        monkeypatch.setattr(cli, "MAX_UNIT_CHECKS", 3)
        monkeypatch.setattr(cli, "UNIT_CHECK_TIMEOUT_SECONDS", 7.0)

        assert cli._text_lane_timeout_seconds() == 128.0

    def test_pdf_timeout_adds_pages_metadata_and_all_units(self, monkeypatch):
        from whisker.llm import cli

        monkeypatch.setattr(cli, "_PAPER_TIMEOUT_SECONDS", 100.0)
        monkeypatch.setattr(cli, "MAX_PAGE_ESCALATIONS", 2)
        monkeypatch.setattr(cli, "PAGE_ESCALATION_TIMEOUT_SECONDS", 11.0)
        monkeypatch.setattr(cli, "MAX_UNIT_CHECKS", 3)
        monkeypatch.setattr(cli, "UNIT_CHECK_TIMEOUT_SECONDS", 7.0)

        assert cli._pdf_judge_timeout_seconds(code_boundary=False) == 150.0
        assert cli._pdf_judge_timeout_seconds(None, code_boundary=False) == 150.0

    def test_pdf_timeout_scales_with_unit_count(self):
        from whisker.llm import cli
        from whisker.llm.constants import (
            MAX_PAGE_ESCALATIONS,
            MAX_UNIT_CHECKS,
            PAGE_ESCALATION_TIMEOUT_SECONDS,
            UNIT_CHECK_TIMEOUT_SECONDS,
        )

        expected_default = (
            cli._PAPER_TIMEOUT_SECONDS
            + MAX_PAGE_ESCALATIONS * PAGE_ESCALATION_TIMEOUT_SECONDS
            + (1 + MAX_UNIT_CHECKS) * UNIT_CHECK_TIMEOUT_SECONDS
        )
        assert cli._pdf_judge_timeout_seconds(code_boundary=False) == expected_default
        assert cli._pdf_judge_timeout_seconds(None, code_boundary=False) == expected_default

        unit_count = 40
        expected_scaled = (
            cli._PAPER_TIMEOUT_SECONDS
            + MAX_PAGE_ESCALATIONS * PAGE_ESCALATION_TIMEOUT_SECONDS
            + (1 + unit_count) * UNIT_CHECK_TIMEOUT_SECONDS
        )
        assert cli._pdf_judge_timeout_seconds(
            unit_count, code_boundary=False,
        ) == expected_scaled

    @staticmethod
    def _run_late_failure(
        tmp_path: Path,
        suffix: str,
        failing_call,
    ) -> str:
        from whisker.llm import cli

        source = tmp_path / f"p1r0{suffix}"
        source.write_text("source", encoding="utf-8")
        debug_path = tmp_path / "p1r0.debug.tapetum_llm.md"
        backend = MagicMock()
        backend.get_source_path.return_value = source
        backend.get_debug_md_path.return_value = debug_path
        model_backend = SimpleNamespace(
            max_context_window=131072,
            chars_per_token=4.0,
            token_multiplier=1.0,
            thinking_capable=True,
            tools_capable=False,
        )
        registry = SimpleNamespace(
            services={"stable-alias": model_backend},
            api_key_envs={},
        )
        prompt = SimpleNamespace(
            system_prompt="base",
            services={
                "fast": "stable-alias",
                "deep": "stable-alias",
                "default": "stable-alias",
            },
            steps=(),
        )
        args = cli._parse_args(["P1R0", "--debug", "--concurrency", "1"])

        def tombstone_after_debug(pid, received_backend, exc, **_kwargs):
            assert pid == "P1R0"
            assert received_backend is backend
            assert isinstance(exc, RuntimeError)
            assert debug_path.exists()
            assert "partial call" in debug_path.read_text(encoding="utf-8")

        patches = [
            patch.object(cli, "open_backend", return_value=backend),
            patch.object(cli, "load_services", return_value=registry),
            patch.object(cli, "_probe_llm_endpoint", new=AsyncMock()),
            patch.object(cli.PipelinePrompt, "load", return_value=prompt),
            patch.object(
                cli, "_write_error_tombstone", side_effect=tombstone_after_debug
            ),
        ]
        target = (
            patch.object(cli, "judge_pdf_extraction", side_effect=failing_call)
            if suffix == ".pdf"
            else patch.object(cli, "adjudicate_paper", side_effect=failing_call)
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], target:
            asyncio.run(cli._run(args))

        return debug_path.read_text(encoding="utf-8")

    def test_partial_pdf_debug_is_flushed_before_tombstone(self, tmp_path):
        async def fail_late(pid, backend, agent, *, debug_log=None, **_kwargs):
            debug_log.extend(["partial call", "partial output"])
            raise RuntimeError("late PDF failure")

        debug = self._run_late_failure(tmp_path, ".pdf", fail_late)
        assert "partial call" in debug
        assert "partial output" in debug

    def test_partial_html_debug_survives_before_tombstone(self, tmp_path):
        async def fail_late(pid, backend, **kwargs):
            path = backend.get_debug_md_path(pid, tool="tapetum_llm")
            path.write_text("partial call\npartial output", encoding="utf-8")
            raise RuntimeError("late HTML failure")

        debug = self._run_late_failure(tmp_path, ".html", fail_late)
        assert "partial call" in debug
        assert "partial output" in debug


# ---------------------------------------------------------------------------
# Fingerprint matching
# ---------------------------------------------------------------------------


class TestFingerprintMatching:
    def _write_sidecar(self, tmp_path, pid, fingerprint):
        """Write a fake tapetum sidecar with a fingerprint block."""
        d = tmp_path / "whisker" / "det"
        d.mkdir(parents=True, exist_ok=True)
        # whisker sidecar (for sidecar_path)
        det_sc = d / f"{pid.lower()}.whisker.json"
        det_sc.write_text(json.dumps({"pid": pid}), encoding="utf-8")

        llm_d = tmp_path / "whisker" / "llm"
        llm_d.mkdir(parents=True, exist_ok=True)
        sc = llm_d / f"{pid.lower()}.whisker.tapetum.json"
        sc.write_text(
            json.dumps({"pid": pid, "fingerprint": fingerprint}),
            encoding="utf-8",
        )
        return sc

    def test_no_sidecar_returns_false(self, tmp_path):
        backend = _make_backend(tmp_path)
        fp = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "m", _DUMMY_SCHEMA)
        assert not _fingerprint_matches("P1R0", backend, fp)

    def test_matching_fingerprint_returns_true(self, tmp_path):
        backend = _make_backend(tmp_path)
        fp = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "m", _DUMMY_SCHEMA)
        self._write_sidecar(tmp_path, "P1R0", fp)
        assert _fingerprint_matches("P1R0", backend, fp)

    def test_changed_md_returns_false(self, tmp_path):
        backend = _make_backend(tmp_path)
        fp = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "m", _DUMMY_SCHEMA)
        self._write_sidecar(tmp_path, "P1R0", fp)
        backend._md_path.write_text("# Changed markdown", encoding="utf-8")
        fp_new = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "m", _DUMMY_SCHEMA)
        assert not _fingerprint_matches("P1R0", backend, fp_new)

    def test_read_existing_fingerprint_none_when_missing(self, tmp_path):
        backend = _make_backend(tmp_path)
        assert _read_existing_fingerprint("P1R0", backend) is None

    def test_read_existing_fingerprint_returns_block(self, tmp_path):
        backend = _make_backend(tmp_path)
        fp = {"md_sha256": "abc", "lane_version": 1}
        self._write_sidecar(tmp_path, "P1R0", fp)
        assert _read_existing_fingerprint("P1R0", backend) == fp

    @pytest.mark.parametrize("fingerprint", [None, [], "bad", 7])
    def test_read_existing_fingerprint_rejects_wrong_type(
        self, tmp_path, fingerprint
    ):
        backend = _make_backend(tmp_path)
        self._write_sidecar(tmp_path, "P1R0", fingerprint)
        assert _read_existing_fingerprint("P1R0", backend) is None

    def test_old_sidecar_without_schema_sha256_invalidated(self, tmp_path):
        """Sidecars written before the schema_sha256 field was added
        must not match a new fingerprint that includes the field."""
        backend = _make_backend(tmp_path)
        fp_new = _compute_fingerprint("P1R0", backend, "pdf", "prompt", "m", _DUMMY_SCHEMA)
        fp_old = {k: v for k, v in fp_new.items() if k != "schema_sha256"}
        self._write_sidecar(tmp_path, "P1R0", fp_old)
        assert not _fingerprint_matches("P1R0", backend, fp_new)

    def test_fleet_skips_on_all_pages_sidecar(self, tmp_path):
        backend = _make_backend(tmp_path)
        fp_all = _compute_fingerprint(
            "P1R0", backend, "pdf", "prompt", "m", _DUMMY_SCHEMA,
            coverage_mode="all_pages",
        )
        self._write_sidecar(tmp_path, "P1R0", fp_all)
        fp_default = _compute_fingerprint(
            "P1R0", backend, "pdf", "prompt", "m", _DUMMY_SCHEMA,
            coverage_mode="default",
        )
        assert _fingerprint_matches("P1R0", backend, fp_default)

    def test_all_pages_does_not_skip_on_default_sidecar(self, tmp_path):
        backend = _make_backend(tmp_path)
        fp_default = _compute_fingerprint(
            "P1R0", backend, "pdf", "prompt", "m", _DUMMY_SCHEMA,
            coverage_mode="default",
        )
        self._write_sidecar(tmp_path, "P1R0", fp_default)
        fp_all = _compute_fingerprint(
            "P1R0", backend, "pdf", "prompt", "m", _DUMMY_SCHEMA,
            coverage_mode="all_pages",
        )
        assert not _fingerprint_matches("P1R0", backend, fp_all)

    def test_exhaustive_skips_on_all_pages_sidecar(self, tmp_path):
        backend = _make_backend(tmp_path)
        fp_all = _compute_fingerprint(
            "P1R0", backend, "pdf", "prompt", "m", _DUMMY_SCHEMA,
            coverage_mode="all_pages",
        )
        self._write_sidecar(tmp_path, "P1R0", fp_all)
        fp_exhaustive = _compute_fingerprint(
            "P1R0", backend, "pdf", "prompt", "m", _DUMMY_SCHEMA,
            coverage_mode="exhaustive",
        )
        assert _fingerprint_matches("P1R0", backend, fp_exhaustive)

    def test_fleet_skips_on_exhaustive_sidecar(self, tmp_path):
        backend = _make_backend(tmp_path)
        fp_exhaustive = _compute_fingerprint(
            "P1R0", backend, "pdf", "prompt", "m", _DUMMY_SCHEMA,
            coverage_mode="exhaustive",
        )
        self._write_sidecar(tmp_path, "P1R0", fp_exhaustive)
        fp_default = _compute_fingerprint(
            "P1R0", backend, "pdf", "prompt", "m", _DUMMY_SCHEMA,
            coverage_mode="default",
        )
        assert _fingerprint_matches("P1R0", backend, fp_default)

    def test_different_content_no_superset_skip(self, tmp_path):
        backend = _make_backend(tmp_path)
        fp_all = _compute_fingerprint(
            "P1R0", backend, "pdf", "prompt", "m", _DUMMY_SCHEMA,
            coverage_mode="all_pages",
        )
        self._write_sidecar(tmp_path, "P1R0", fp_all)
        backend._md_path.write_text("# Changed markdown", encoding="utf-8")
        fp_default = _compute_fingerprint(
            "P1R0", backend, "pdf", "prompt", "m", _DUMMY_SCHEMA,
            coverage_mode="default",
        )
        assert not _fingerprint_matches("P1R0", backend, fp_default)

    def test_force_flag_bypasses_superset(self, tmp_path):
        """Full run with --force re-evaluates despite superset sidecar."""
        from whisker.llm import cli
        from whisker.llm.pdf_judge import PdfJudgeResult

        backend = _make_backend(tmp_path)
        fp_all = _compute_fingerprint(
            "P1R0", backend, "pdf_textlayer_judge", "prompt", "m",
            _DUMMY_SCHEMA, coverage_mode="all_pages",
        )
        self._write_sidecar(tmp_path, "P1R0", fp_all)
        backend.list_all_paper_ids = lambda: ["P1R0"]

        model_backend = SimpleNamespace(
            max_context_window=131072,
            chars_per_token=4.0,
            token_multiplier=1.0,
            thinking_capable=True,
            tools_capable=False,
        )
        registry = SimpleNamespace(
            services={"stable-alias": model_backend},
            api_key_envs={},
        )
        prompt = SimpleNamespace(
            system_prompt="base",
            services={
                "fast": "stable-alias",
                "deep": "stable-alias",
                "default": "stable-alias",
            },
            steps=(),
        )
        judged: list[str] = []

        async def capture_judge(pid, _backend, agent, **kwargs):
            judged.append(pid)
            return PdfJudgeResult(
                pid=pid,
                verdict="review",
                confidence=0.9,
                reasoning="captured",
                judge_model="stable-alias",
            )

        args = cli._parse_args(["--force", "--concurrency", "1"])
        with (
            patch.object(cli, "open_backend", return_value=backend),
            patch.object(cli, "load_services", return_value=registry),
            patch.object(cli, "_probe_llm_endpoint", new=AsyncMock()),
            patch.object(cli.PipelinePrompt, "load", return_value=prompt),
            patch.object(
                cli, "_effective_model_contract", return_value="m",
            ),
            patch.object(cli, "_pdf_prompt_contract", return_value="prompt"),
            patch.object(cli, "_pdf_schema_contract", return_value=_DUMMY_SCHEMA),
            patch.object(cli, "_text_prompt_contract", return_value="prompt"),
            patch.object(cli, "_text_schema_contract", return_value=_DUMMY_SCHEMA),
            patch.object(cli, "find_ideals_dir", return_value=None),
            patch.object(cli, "judge_pdf_extraction", side_effect=capture_judge),
            patch.object(
                cli, "_persist_lane_result", return_value=Path("out.json"),
            ),
            patch.object(cli, "_pdf_page_count", return_value=3),
        ):
            asyncio.run(cli._run(args))

        assert judged == ["P1R0"]

    def test_all_pages_does_not_skip_default_mode_sidecar(self, tmp_path):
        """Prior default-mode sidecar must not skip an --all-pages re-run."""
        from whisker.llm import cli
        from whisker.llm.pdf_judge import PdfJudgeResult

        backend = _make_backend(tmp_path)
        fp_default = _compute_fingerprint(
            "P1R0", backend, "pdf_textlayer_judge", "prompt", "m",
            _DUMMY_SCHEMA, coverage_mode="default",
        )
        self._write_sidecar(tmp_path, "P1R0", fp_default)

        model_backend = SimpleNamespace(
            max_context_window=131072,
            chars_per_token=4.0,
            token_multiplier=1.0,
            thinking_capable=True,
            tools_capable=False,
        )
        registry = SimpleNamespace(
            services={"stable-alias": model_backend},
            api_key_envs={},
        )
        prompt = SimpleNamespace(
            system_prompt="base",
            services={
                "fast": "stable-alias",
                "deep": "stable-alias",
                "default": "stable-alias",
            },
            steps=(),
        )
        judged: list[dict] = []

        async def capture_judge(pid, _backend, agent, **kwargs):
            judged.append(kwargs)
            return PdfJudgeResult(
                pid=pid,
                verdict="review",
                confidence=0.9,
                reasoning="captured",
                judge_model="stable-alias",
            )

        args = cli._parse_args(
            ["P1R0", "--all-pages", "--incremental", "--concurrency", "1"]
        )
        with (
            patch.object(cli, "open_backend", return_value=backend),
            patch.object(cli, "load_services", return_value=registry),
            patch.object(cli, "_probe_llm_endpoint", new=AsyncMock()),
            patch.object(cli.PipelinePrompt, "load", return_value=prompt),
            patch.object(
                cli, "_effective_model_contract", return_value="m",
            ),
            patch.object(cli, "_pdf_prompt_contract", return_value="prompt"),
            patch.object(cli, "_pdf_schema_contract", return_value=_DUMMY_SCHEMA),
            patch.object(cli, "_text_prompt_contract", return_value="prompt"),
            patch.object(cli, "_text_schema_contract", return_value=_DUMMY_SCHEMA),
            patch.object(cli, "find_ideals_dir", return_value=None),
            patch.object(cli, "judge_pdf_extraction", side_effect=capture_judge),
            patch.object(
                cli, "_persist_lane_result", return_value=Path("out.json"),
            ),
            patch.object(cli, "_pdf_page_count", return_value=3),
        ):
            asyncio.run(cli._run(args))

        assert len(judged) == 1
        assert judged[0].get("all_pages") is True


# ---------------------------------------------------------------------------
# Schema auto-invalidation with real Pydantic models
# ---------------------------------------------------------------------------


class TestSchemaAutoInvalidation:
    """Verify that the real output schemas produce stable, distinct hashes."""

    def test_pdf_and_text_schemas_differ(self):
        from whisker.llm.models import Adjudication
        from whisker.llm.pdf_judge import PdfJudgment

        pdf_json = json.dumps(PdfJudgment.model_json_schema(), sort_keys=True)
        text_json = json.dumps(Adjudication.model_json_schema(), sort_keys=True)
        assert _sha256_str(pdf_json) != _sha256_str(text_json)

    def test_schema_hash_stable_across_calls(self):
        from whisker.llm.models import Adjudication

        s1 = json.dumps(Adjudication.model_json_schema(), sort_keys=True)
        s2 = json.dumps(Adjudication.model_json_schema(), sort_keys=True)
        assert _sha256_str(s1) == _sha256_str(s2)

    def test_field_description_change_invalidates(self, tmp_path, monkeypatch):
        """Changing a Field description in the output model must produce
        a different schema hash, which invalidates the fingerprint."""
        from whisker.llm.models import Adjudication

        schema_before = json.dumps(
            Adjudication.model_json_schema(), sort_keys=True,
        )
        hash_before = _sha256_str(schema_before)

        monkeypatch.setattr(
            Adjudication.model_fields["reasoning"],
            "description",
            "CHANGED: totally different description for testing",
        )
        Adjudication.model_rebuild(force=True)

        schema_after = json.dumps(
            Adjudication.model_json_schema(), sort_keys=True,
        )
        hash_after = _sha256_str(schema_after)

        assert hash_before != hash_after, (
            "Schema hash must change when a Field description changes"
        )


# ---------------------------------------------------------------------------
# Error tombstone fingerprint + --retry-errors
# ---------------------------------------------------------------------------


class TestErrorTombstoneFingerprint:
    """Error tombstones carry a fingerprint so a warm run can skip them,
    and ``--retry-errors`` opts back into re-evaluation."""

    @staticmethod
    def _write_error_sidecar(
        tmp_path: Path, pid: str, fingerprint: dict | None,
    ) -> Path:
        """Write a fake ``status="error"`` tapetum sidecar, optionally with
        a fingerprint block (omitted entirely to simulate a legacy
        tombstone written before this feature)."""
        d = tmp_path / "whisker" / "det"
        d.mkdir(parents=True, exist_ok=True)
        det_sc = d / f"{pid.lower()}.whisker.json"
        det_sc.write_text(json.dumps({"pid": pid}), encoding="utf-8")

        llm_d = tmp_path / "whisker" / "llm"
        llm_d.mkdir(parents=True, exist_ok=True)
        sc = llm_d / f"{pid.lower()}.whisker.tapetum.json"
        payload: dict = {"pid": pid, "status": "error", "error": "RuntimeError"}
        if fingerprint is not None:
            payload["fingerprint"] = fingerprint
        sc.write_text(json.dumps(payload), encoding="utf-8")
        return sc

    def test_error_tombstone_has_fingerprint(self, tmp_path):
        """_write_error_tombstone persists the fingerprint block when given
        one, so a subsequent warm run can compare against it."""
        backend = _make_backend(tmp_path)
        fp = _compute_fingerprint(
            "P1R0", backend, "pdf_textlayer_judge", "prompt", "m", _DUMMY_SCHEMA,
        )

        _write_error_tombstone(
            "P1R0", backend, RuntimeError("boom"), fingerprint=fp,
        )

        out_path = _llm_output_dir("P1R0", backend) / "p1r0.whisker.tapetum.json"
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert payload["status"] == "error"
        assert payload["fingerprint"] == fp

    def test_error_tombstone_without_fingerprint_omits_key(self, tmp_path):
        """When no fingerprint is supplied (the pre-fingerprint-computation
        failure path), the tombstone stays legacy-shaped: no fingerprint
        key at all, not a null placeholder."""
        backend = _make_backend(tmp_path)

        _write_error_tombstone("P1R0", backend, RuntimeError("boom"))

        out_path = _llm_output_dir("P1R0", backend) / "p1r0.whisker.tapetum.json"
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert payload["status"] == "error"
        assert "fingerprint" not in payload

    @staticmethod
    def _run_with_error_sidecar(
        tmp_path: Path,
        *,
        with_matching_fingerprint: bool,
        extra_args: list[str],
    ) -> list[str]:
        """Run the CLI over one PID against a pre-seeded error sidecar and
        return the list of pids that actually reached the judge call
        (empty means the paper was skipped).

        ``with_matching_fingerprint=True`` seeds the tombstone with a
        fingerprint that matches what the run will freshly compute (the
        normal warm-run case). ``False`` seeds a legacy tombstone with no
        fingerprint block at all.
        """
        from whisker.llm import cli
        from whisker.llm.pdf_judge import PdfJudgeResult

        backend = _make_backend(tmp_path)
        fp = (
            _compute_fingerprint(
                "P1R0", backend, "pdf_textlayer_judge", "prompt", "m",
                _DUMMY_SCHEMA,
            )
            if with_matching_fingerprint
            else None
        )
        TestErrorTombstoneFingerprint._write_error_sidecar(
            tmp_path, "P1R0", fp,
        )
        backend.list_all_paper_ids = lambda: ["P1R0"]

        model_backend = SimpleNamespace(
            max_context_window=131072,
            chars_per_token=4.0,
            token_multiplier=1.0,
            thinking_capable=True,
            tools_capable=False,
        )
        registry = SimpleNamespace(
            services={"stable-alias": model_backend},
            api_key_envs={},
        )
        prompt = SimpleNamespace(
            system_prompt="base",
            services={
                "fast": "stable-alias",
                "deep": "stable-alias",
                "default": "stable-alias",
            },
            steps=(),
        )
        judged: list[str] = []

        async def capture_judge(pid, _backend, agent, **kwargs):
            judged.append(pid)
            return PdfJudgeResult(
                pid=pid,
                verdict="review",
                confidence=0.9,
                reasoning="captured",
                judge_model="stable-alias",
            )

        args = cli._parse_args(
            ["P1R0", "--incremental", "--concurrency", "1", *extra_args]
        )
        with (
            patch.object(cli, "open_backend", return_value=backend),
            patch.object(cli, "load_services", return_value=registry),
            patch.object(cli, "_probe_llm_endpoint", new=AsyncMock()),
            patch.object(cli.PipelinePrompt, "load", return_value=prompt),
            patch.object(cli, "_effective_model_contract", return_value="m"),
            patch.object(cli, "_pdf_prompt_contract", return_value="prompt"),
            patch.object(cli, "_pdf_schema_contract", return_value=_DUMMY_SCHEMA),
            patch.object(cli, "_text_prompt_contract", return_value="prompt"),
            patch.object(cli, "_text_schema_contract", return_value=_DUMMY_SCHEMA),
            patch.object(cli, "find_ideals_dir", return_value=None),
            patch.object(cli, "judge_pdf_extraction", side_effect=capture_judge),
            patch.object(
                cli, "_persist_lane_result", return_value=Path("out.json"),
            ),
            patch.object(cli, "_pdf_page_count", return_value=3),
        ):
            asyncio.run(cli._run(args))

        return judged

    def test_error_tombstone_skipped_on_warm_run(self, tmp_path):
        """A matching fingerprint on an error tombstone skips the paper
        when --retry-errors is NOT set."""
        judged = self._run_with_error_sidecar(
            tmp_path, with_matching_fingerprint=True, extra_args=[],
        )
        assert judged == []

    def test_error_tombstone_retried_with_flag(self, tmp_path):
        """--retry-errors forces re-evaluation even though the fingerprint
        matches the existing error tombstone."""
        judged = self._run_with_error_sidecar(
            tmp_path,
            with_matching_fingerprint=True,
            extra_args=["--retry-errors"],
        )
        assert judged == ["P1R0"]

    def test_error_tombstone_without_fingerprint_always_runs(self, tmp_path):
        """A legacy error tombstone with no fingerprint block never
        skips, regardless of --retry-errors."""
        judged = self._run_with_error_sidecar(
            tmp_path, with_matching_fingerprint=False, extra_args=[],
        )
        assert judged == ["P1R0"]

    def test_read_existing_sidecar_status_none_when_missing(self, tmp_path):
        backend = _make_backend(tmp_path)
        assert _read_existing_sidecar_status("P1R0", backend) is None

    def test_read_existing_sidecar_status_reads_error(self, tmp_path):
        backend = _make_backend(tmp_path)
        self._write_error_sidecar(tmp_path, "P1R0", None)
        assert _read_existing_sidecar_status("P1R0", backend) == "error"


# ---------------------------------------------------------------------------
# A2/B3: live warm-run skip behavior (INFO logging, footer breakdown,
# fusion recompute) exercised through the full cli._run path.
# ---------------------------------------------------------------------------


class _MultiPidBackend:
    """Duck-typed backend serving several distinct pids from one tmp_path."""

    def __init__(self, tmp_path: Path, pids: list[str]) -> None:
        self.workspace_dir = tmp_path
        self._md: dict[str, Path] = {}
        self._src: dict[str, Path] = {}
        for pid in pids:
            md = tmp_path / "paperstore" / f"{pid.lower()}.md"
            md.parent.mkdir(parents=True, exist_ok=True)
            md.write_text(f"# {pid}\n\nBody text.", encoding="utf-8")
            src = tmp_path / "paperstore" / f"{pid.lower()}.html"
            src.write_text(f"<html>{pid}</html>", encoding="utf-8")
            self._md[pid] = md
            self._src[pid] = src

    def get_paper_md_path(self, pid: str) -> Path:
        return self._md[pid]

    def get_source_path(self, pid: str) -> Path:
        return self._src[pid]

    def list_all_paper_ids(self) -> list[str]:
        return list(self._md)


def _seed_matching_tapetum_sidecar(
    tmp_path: Path, pid: str, fp: dict, *, det_verdict: str = "pass",
) -> None:
    """Seed a successful (non-error) tapetum sidecar with a fingerprint that
    will compare equal to a freshly computed one, plus a matching det
    sidecar so fusion recompute has something real to chew on."""
    det_dir = tmp_path / "whisker" / "det"
    det_dir.mkdir(parents=True, exist_ok=True)
    (det_dir / f"{pid.lower()}.whisker.json").write_text(
        json.dumps({
            "pid": pid, "verdict": det_verdict,
            "hard_flags": [], "soft_flags": [],
        }),
        encoding="utf-8",
    )
    llm_dir = tmp_path / "whisker" / "llm"
    llm_dir.mkdir(parents=True, exist_ok=True)
    (llm_dir / f"{pid.lower()}.whisker.tapetum.json").write_text(
        json.dumps({
            "pid": pid,
            "status": "ok",
            "suggested_verdict": "pass",
            "confidence": 0.9,
            "axis_findings": [],
            "evaluated_at": "2020-01-01T00:00:00+00:00",
            "fusion": {"combined_verdict": "review", "combined_rule": "stale"},
            "fingerprint": fp,
        }),
        encoding="utf-8",
    )


class TestWarmRunVisibilityAndFusionRefresh:
    """A2 (INFO skip logs + footer breakdown) and B3 (fusion recompute on
    skip), exercised end to end through ``cli._run``."""

    @staticmethod
    def _services_harness():
        model_backend = SimpleNamespace(
            max_context_window=131072,
            chars_per_token=4.0,
            token_multiplier=1.0,
            thinking_capable=True,
            tools_capable=False,
        )
        registry = SimpleNamespace(
            services={"stable-alias": model_backend},
            api_key_envs={},
        )
        prompt = SimpleNamespace(
            system_prompt="base",
            services={
                "fast": "stable-alias",
                "deep": "stable-alias",
                "default": "stable-alias",
            },
            steps=(),
        )
        return registry, prompt

    def test_skip_logs_at_info_footer_breaks_down_and_refreshes_fusion(
        self, tmp_path,
    ):
        from whisker.llm import cli
        from whisker.llm.fusion import fuse_verdicts
        from whisker.llm.models import TapetumResult

        backend = _MultiPidBackend(tmp_path, ["P1R0", "P2R0"])
        registry, prompt = self._services_harness()

        fp = _compute_fingerprint(
            "P1R0", backend, "text", "prompt", "m", _DUMMY_SCHEMA,
        )
        # Det verdict changed (fail) since the tapetum sidecar was written,
        # so a stale fusion block (review) would mispair with the fresh det
        # sidecar if it were not recomputed on skip (B3).
        _seed_matching_tapetum_sidecar(tmp_path, "P1R0", fp, det_verdict="not-llm-readable")

        judged: list[str] = []

        async def capture_adjudicate(pid, _backend, **kwargs):
            judged.append(pid)
            return TapetumResult(
                pid=pid,
                whisker_verdict="pass",
                suggested_verdict="pass",
                confidence=0.9,
                escalated=False,
                tier1_model="mock",
                tier2_model=None,
            )

        args = cli._parse_args(
            ["P1R0", "P2R0", "--incremental", "--concurrency", "1"]
        )
        with (
            patch.object(cli, "open_backend", return_value=backend),
            patch.object(cli, "load_services", return_value=registry),
            patch.object(cli, "_probe_llm_endpoint", new=AsyncMock()),
            patch.object(cli.PipelinePrompt, "load", return_value=prompt),
            patch.object(cli, "_effective_model_contract", return_value="m"),
            patch.object(cli, "_pdf_prompt_contract", return_value="prompt"),
            patch.object(cli, "_pdf_schema_contract", return_value=_DUMMY_SCHEMA),
            patch.object(cli, "_text_prompt_contract", return_value="prompt"),
            patch.object(cli, "_text_schema_contract", return_value=_DUMMY_SCHEMA),
            patch.object(cli, "find_ideals_dir", return_value=None),
            patch.object(cli, "adjudicate_paper", side_effect=capture_adjudicate),
            patch.object(
                cli, "_persist_result", return_value=Path("out.json"),
            ),
            patch.object(
                cli.logger, "info", wraps=cli.logger.info,
            ) as mock_info,
        ):
            asyncio.run(cli._run(args))

        # Only the non-matching paper reached the LLM call.
        assert judged == ["P2R0"]

        # Batch mode routes per-paper progress through a debug-level
        # logger, so intercept logger.info directly (bypassing stream/
        # handler plumbing) to check what was actually elevated to INFO.
        info_messages = [
            (call.args[0] % call.args[1:]) if call.args[1:] else call.args[0]
            for call in mock_info.call_args_list
        ]

        # A2: the skip line is logged at INFO, not swallowed by batch's
        # debug-level per_paper_log, and names the reason.
        assert any(
            "P1R0 [text] skipped (fingerprint match)" in m
            for m in info_messages
        )

        # A2: the footer breaks skips down by reason.
        footer = next(m for m in info_messages if "total:" in m)
        assert "1 evaluated" in footer
        assert "1 fingerprint" in footer
        assert "0 superset" in footer
        assert "0 tombstone" in footer

        # B3: fusion was recomputed against the CURRENT (fail) det sidecar,
        # not left at the stale "review" value from the old tapetum sidecar.
        tap_path = (
            tmp_path / "whisker" / "llm" / "p1r0.whisker.tapetum.json"
        )
        refreshed = json.loads(tap_path.read_text(encoding="utf-8"))
        assert refreshed["fusion"]["combined_verdict"] == "not-llm-readable"
        # The warm marker is untouched by a fingerprint skip.
        assert refreshed["evaluated_at"] == "2020-01-01T00:00:00+00:00"

        # Sanity: fuse_verdicts independently agrees with what got persisted.
        det = json.loads(
            (tmp_path / "whisker" / "det" / "p1r0.whisker.json").read_text(
                encoding="utf-8",
            )
        )
        expected = fuse_verdicts(det, refreshed).to_dict()
        assert refreshed["fusion"]["combined_verdict"] == expected["combined_verdict"]


class TestWouldSkipFlag:
    """A2: ``--would-skip`` is a pure dry run: prints decisions, makes no
    LLM call, no health probe, and writes no sidecar or report."""

    def test_would_skip_prints_decisions_without_side_effects(
        self, tmp_path, capsys,
    ):
        from whisker.llm import cli

        backend = _MultiPidBackend(tmp_path, ["P1R0", "P2R0"])
        registry, prompt = self._services_harness_static()

        fp = _compute_fingerprint(
            "P1R0", backend, "text", "prompt", "m", _DUMMY_SCHEMA,
        )
        _seed_matching_tapetum_sidecar(tmp_path, "P1R0", fp)

        probe = AsyncMock()
        adjudicate = AsyncMock()

        args = cli._parse_args(
            ["P1R0", "P2R0", "--incremental", "--would-skip"]
        )
        with (
            patch.object(cli, "open_backend", return_value=backend),
            patch.object(cli, "load_services", return_value=registry),
            patch.object(cli, "_probe_llm_endpoint", new=probe),
            patch.object(cli.PipelinePrompt, "load", return_value=prompt),
            patch.object(cli, "_effective_model_contract", return_value="m"),
            patch.object(cli, "_pdf_prompt_contract", return_value="prompt"),
            patch.object(cli, "_pdf_schema_contract", return_value=_DUMMY_SCHEMA),
            patch.object(cli, "_text_prompt_contract", return_value="prompt"),
            patch.object(cli, "_text_schema_contract", return_value=_DUMMY_SCHEMA),
            patch.object(cli, "find_ideals_dir", return_value=None),
            patch.object(cli, "adjudicate_paper", new=adjudicate),
        ):
            exit_code = asyncio.run(cli._run(args))

        assert exit_code == 0
        probe.assert_not_called()
        adjudicate.assert_not_called()
        assert not (
            tmp_path / "whisker" / "llm" / "p2r0.whisker.tapetum.json"
        ).exists()
        assert not (tmp_path / "whisker" / "llm" / "report-merged.md").exists()

        out = capsys.readouterr().out
        assert "P1R0: skip (fingerprint match)" in out
        assert "P2R0: run" in out

    @staticmethod
    def _services_harness_static():
        return TestWarmRunVisibilityAndFusionRefresh._services_harness()
