#
# Copyright (c) 2026 Dmitriy Chukhin (dmitriy@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for ``pipeline.services`` loader and resolver contracts.

Covers:

- ``load_services``: config-shape checks (unknown backend, generic
  ``required_api_key_env`` mismatch). Env-agnostic at this layer; a
  missing env var does NOT raise here.
- ``resolve_pipeline_models``: env-var presence per pipeline-referenced
  service. Lazy validation so SERVICES.toml entries not referenced by
  any loaded pipeline stay inert.
- ``resolve_classifiers``: binding semantics (``None`` vs ``{}``),
  lazy instantiation, per-entry dedupe, provider precedence, and
  registry lookup errors.

No network, no real LLM, no pydantic-ai. Env-var manipulation uses
``monkeypatch``; registry manipulation uses ``monkeypatch.setitem``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline.classifier_backends import CLASSIFIER_BACKEND_REGISTRY, ClassifierBackend
from pipeline.errors import ServiceConfigError
from pipeline.model_backends import BACKEND_REGISTRY, ModelBackend
from pipeline.services import (
    ServiceRegistry,
    _instantiate_classifier,
    load_services,
    resolve_classifiers,
    resolve_pipeline_models,
)
from pipeline.transformer_backend import TransformerProvider


def _write_services_toml(tmp_path, body: str):
    p = tmp_path / "SERVICES.toml"
    p.write_text(body, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# load_services: returns ServiceRegistry; env-agnostic at load time
# ---------------------------------------------------------------------------


def test_load_services_returns_registry_with_api_key_envs(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERFLOW_TEST_KEY", raising=False)
    p = _write_services_toml(tmp_path, """
[services.s1]
backend = "llama3"
base_url = "https://example.invalid/v1"
api_key_env = "PAPERFLOW_TEST_KEY"
model = "test-model"
""")
    registry = load_services(p)
    assert isinstance(registry, ServiceRegistry)
    assert set(registry.services) == {"s1"}
    assert registry.api_key_envs["s1"] == "PAPERFLOW_TEST_KEY"


@pytest.mark.parametrize(
    "body",
    [
        # api_key_env field omitted entirely
        (
            'backend = "llama3"\n'
            'base_url = "http://localhost:8000/v1"\n'
            'model = "local-model"'
        ),
        # api_key_env field explicitly empty
        (
            'backend = "llama3"\n'
            'base_url = "http://localhost:8000/v1"\n'
            'api_key_env = ""\n'
            'model = "local-model"'
        ),
    ],
    ids=["field-omitted", "field-empty-string"],
)
def test_load_services_no_auth_styles_pass_empty_string(tmp_path, body):
    p = _write_services_toml(tmp_path, f"[services.s1]\n{body}\n")
    registry = load_services(p)
    assert registry.api_key_envs["s1"] == ""


def test_load_services_required_api_key_env_mismatch_raises(tmp_path):
    p = _write_services_toml(tmp_path, """
[services.s1]
backend = "anthropic"
api_key_env = "MY_OWN_KEY"
model = "claude-test"
""")
    with pytest.raises(ServiceConfigError) as exc_info:
        load_services(p)
    msg = str(exc_info.value)
    assert "anthropic" in msg
    assert "ANTHROPIC_API_KEY" in msg
    assert "MY_OWN_KEY" in msg


def test_required_api_key_env_class_attribute_enforced(tmp_path, monkeypatch):
    """Loader reads ``backend_cls.required_api_key_env`` generically.

    Regression guard against a future revert to a hardcoded
    ``svc.get("backend") == "anthropic"`` check that would silently
    skip new SDK-reads-env-directly backends.
    """

    class _SdkReadsEnvBackend(ModelBackend):
        thinking_capable = False
        tools_capable = False
        required_api_key_env = "SYNTH_KEY"

        def __init__(self, **kwargs) -> None:  # accept loader kwargs, ignore
            pass

        async def run(self, *args, **kwargs):
            raise NotImplementedError

    monkeypatch.setitem(BACKEND_REGISTRY, "synthetic", _SdkReadsEnvBackend)

    p = _write_services_toml(tmp_path, """
[services.s1]
backend = "synthetic"
api_key_env = "WRONG_KEY"
model = "test"
""")
    with pytest.raises(ServiceConfigError) as exc_info:
        load_services(p)
    msg = str(exc_info.value)
    assert "SYNTH_KEY" in msg
    assert "WRONG_KEY" in msg


def test_load_services_required_api_key_env_match_loads(tmp_path, monkeypatch):
    """Matching env-var name passes the shape check even if unset.

    Env-var presence is ``resolve_pipeline_models``'s job, not
    ``load_services``'s.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    p = _write_services_toml(tmp_path, """
[services.s1]
backend = "anthropic"
api_key_env = "ANTHROPIC_API_KEY"
model = "claude-test"
""")
    registry = load_services(p)
    assert "s1" in registry.services


# ---------------------------------------------------------------------------
# ServiceRegistry: structural immutability (MappingProxyType wrap)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("attr", ["services", "api_key_envs"])
def test_service_registry_mappings_are_read_only(attr):
    """Both mappings are wrapped, not just whichever the implementer remembered."""
    registry = ServiceRegistry(services={}, api_key_envs={})
    with pytest.raises(TypeError):
        getattr(registry, attr)["x"] = "evil"


# ---------------------------------------------------------------------------
# resolve_pipeline_models: env-var validation per pipeline-referenced service
# ---------------------------------------------------------------------------


def _registry_with(services, api_key_envs=None):
    """Build a tiny ServiceRegistry for tests."""
    if api_key_envs is None:
        api_key_envs = {name: "" for name in services}
    return ServiceRegistry(services=services, api_key_envs=api_key_envs)


def test_resolve_pipeline_models_success_no_auth():
    """No-auth service references resolve without env-var checks."""
    backend = MagicMock(spec=["run"])
    registry = _registry_with({"s1": backend})
    models = resolve_pipeline_models({"default": "s1"}, registry)
    assert models == {"default": backend}


def test_resolve_pipeline_models_requires_default_logical_name():
    """A pipeline that omits `default` is rejected at load time."""
    backend = MagicMock(spec=["run"])
    registry = _registry_with({"s1": backend})
    with pytest.raises(ServiceConfigError, match="default"):
        resolve_pipeline_models({"tool": "s1"}, registry)


def test_resolve_pipeline_models_rejects_unknown_service():
    """A logical name pointing at a service not in SERVICES.toml is rejected."""
    backend = MagicMock(spec=["run"])
    registry = _registry_with({"s1": backend})
    with pytest.raises(ServiceConfigError) as exc_info:
        resolve_pipeline_models({"default": "missing"}, registry)
    msg = str(exc_info.value)
    assert "default" in msg
    assert "missing" in msg


def test_resolve_pipeline_models_requires_env_var_set(monkeypatch):
    """Bound service with declared api_key_env must have it exported."""
    monkeypatch.delenv("PAPERFLOW_TEST_KEY", raising=False)
    backend = MagicMock(spec=["run"])
    registry = _registry_with(
        {"s1": backend},
        api_key_envs={"s1": "PAPERFLOW_TEST_KEY"},
    )
    with pytest.raises(ServiceConfigError) as exc_info:
        resolve_pipeline_models({"default": "s1"}, registry)
    msg = str(exc_info.value)
    assert "PAPERFLOW_TEST_KEY" in msg
    assert "default" in msg


@pytest.mark.parametrize("env_value", ["", "   ", "\n", "\t \n"])
def test_resolve_pipeline_models_rejects_whitespace_env_var(monkeypatch, env_value):
    monkeypatch.setenv("PAPERFLOW_TEST_KEY", env_value)
    backend = MagicMock(spec=["run"])
    registry = _registry_with(
        {"s1": backend},
        api_key_envs={"s1": "PAPERFLOW_TEST_KEY"},
    )
    with pytest.raises(ServiceConfigError, match="PAPERFLOW_TEST_KEY"):
        resolve_pipeline_models({"default": "s1"}, registry)


def test_resolve_pipeline_models_skips_unreferenced_services(monkeypatch):
    """Services declared in SERVICES.toml but unreferenced by the pipeline stay inert.

    KEY_A is set, KEY_B is not. Only s_a is referenced by the
    pipeline. Resolution must succeed without ever touching KEY_B.
    """
    monkeypatch.setenv("KEY_A", "value-a")
    monkeypatch.delenv("KEY_B", raising=False)
    a, b = MagicMock(spec=["run"]), MagicMock(spec=["run"])
    registry = _registry_with(
        {"s_a": a, "s_b": b},
        api_key_envs={"s_a": "KEY_A", "s_b": "KEY_B"},
    )
    models = resolve_pipeline_models({"default": "s_a"}, registry)
    assert models == {"default": a}


# ---------------------------------------------------------------------------
# resolve_classifiers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_transformer_provider_env(monkeypatch):
    monkeypatch.delenv("PAPERFLOW_TRANSFORMER_PROVIDER", raising=False)


def _classifier_toml(tmp_path, extra: str = "") -> Path:
    body = """
[classifiers.nli-small]
backend = "nli_cross_encoder"
model = "cross-encoder/nli-deberta-v3-small"

[classifiers.zeroshot-base]
backend = "zeroshot_v2"
model = "MoritzLaurer/deberta-v3-base-zeroshot-v2.0"

[classifiers.bad-backend]
backend = "no_such_backend"
model = "x"

[classifier_defaults]
selector = "nli-small"
other = "nli-small"

[transformer_providers.auto]
mode = "auto"
max_batch_size = 16
max_length = 128
executor_workers = 1

[transformer_provider_defaults]
default = "auto"
"""
    if extra:
        body = body.rstrip() + f"\n{extra}\n"
    p = tmp_path / "SERVICES.toml"
    p.write_text(body, encoding="utf-8")
    return p


class _ClfFake:
    def __init__(self, model_id: str, provider) -> None:
        self.model_id = model_id
        self.provider = provider


def _patch_fake_instantiate_classifier(monkeypatch, calls: list[str] | None = None):
    """Monkeypatch ``_instantiate_classifier`` and optionally record entry names."""

    def fake_inst(name, cfg, provider):
        if calls is not None:
            calls.append(name)
        return _ClfFake(cfg.get("model", name), provider)

    monkeypatch.setattr("pipeline.services._instantiate_classifier", fake_inst)
    return fake_inst


def test_resolve_classifiers_empty_when_no_defaults_and_no_binding(tmp_path):
    p = _write_services_toml(
        tmp_path,
        """
[services.s1]
backend = "llama3"
base_url = "http://localhost/v1"
model = "m"
""",
    )
    assert resolve_classifiers(None, path=p) == {}


def test_resolve_classifiers_fallback_without_binding(tmp_path, monkeypatch):
    p = _classifier_toml(tmp_path)
    calls: list[str] = []
    _patch_fake_instantiate_classifier(monkeypatch, calls)
    result = resolve_classifiers(None, path=p)
    # Both defaulted slots ("selector", "other") point at the same
    # inventory entry, so they share one instance.
    assert set(result) == {"selector", "other"}
    assert result["selector"] is result["other"]
    assert result["selector"].model_id == "cross-encoder/nli-deberta-v3-small"
    assert calls == ["nli-small"]


def test_resolve_classifiers_explicit_binding_does_not_merge_defaults(
    tmp_path, monkeypatch,
):
    p = _classifier_toml(tmp_path)
    calls: list[str] = []
    _patch_fake_instantiate_classifier(monkeypatch, calls)
    # Explicit binding is authoritative: defaults slots ("other") are
    # not merged in when the caller passes a non-None binding.
    result = resolve_classifiers({"selector": "zeroshot-base"}, path=p)
    assert set(result) == {"selector"}
    assert result["selector"].model_id.endswith("zeroshot-v2.0")
    assert calls == ["zeroshot-base"]


def test_resolve_classifiers_empty_dict_skips_defaults(tmp_path, monkeypatch):
    p = _classifier_toml(tmp_path)
    monkeypatch.setattr(
        "pipeline.services._instantiate_classifier",
        lambda *a, **k: _ClfFake("m", a[2]),
    )
    # {} is not None: no framework fallback, even when defaults exist.
    assert resolve_classifiers({}, path=p) == {}


def test_resolve_classifiers_unknown_entry_names_slot(tmp_path, monkeypatch):
    p = _classifier_toml(tmp_path)
    _patch_fake_instantiate_classifier(monkeypatch)
    with pytest.raises(ServiceConfigError, match="missing-entry") as exc_info:
        resolve_classifiers({"slot_a": "missing-entry"}, path=p)
    msg = str(exc_info.value)
    assert "slot_a" in msg


def test_resolve_classifiers_lazy_skips_unbound_bad_entry(tmp_path, monkeypatch):
    p = _write_services_toml(
        tmp_path,
        """
[classifiers.nli-small]
backend = "nli_cross_encoder"
model = "cross-encoder/nli-deberta-v3-small"

[classifiers.bad-backend]
backend = "no_such_backend"
model = "x"

[transformer_providers.auto]
mode = "auto"
max_batch_size = 16
max_length = 128
executor_workers = 1
""",
    )
    calls: list[str] = []
    _patch_fake_instantiate_classifier(monkeypatch, calls)
    result = resolve_classifiers({"only": "nli-small"}, path=p)
    assert set(result) == {"only"}
    assert result["only"].model_id == "cross-encoder/nli-deberta-v3-small"
    assert calls == ["nli-small"]


def test_resolve_classifiers_shares_instance_for_two_slots(tmp_path, monkeypatch):
    p = _classifier_toml(tmp_path)
    monkeypatch.setattr(
        "pipeline.services._instantiate_classifier",
        lambda *a, **k: _ClfFake("m", a[2]),
    )
    result = resolve_classifiers(
        {"a": "nli-small", "b": "nli-small"},
        path=p,
    )
    # Two slots bound to the same entry share one instance.
    assert set(result) == {"a", "b"}
    assert result["a"] is result["b"]


def test_resolve_classifiers_two_distinct_entries_stable_order(
    tmp_path, monkeypatch,
):
    p = _classifier_toml(tmp_path)
    calls: list[str] = []
    _patch_fake_instantiate_classifier(monkeypatch, calls)
    # Insertion order is non-alphabetical; D7 sorted-slot processing must
    # still yield deterministic slot-key order in the result dict.
    result = resolve_classifiers(
        {"selector": "nli-small", "routing_tagger": "zeroshot-base"},
        path=p,
    )
    assert list(result) == ["routing_tagger", "selector"]
    assert result["selector"].model_id == "cross-encoder/nli-deberta-v3-small"
    assert result["routing_tagger"].model_id.endswith("zeroshot-v2.0")
    assert calls == ["zeroshot-base", "nli-small"]


def test_resolve_classifiers_provider_override_beats_entry_pin(
    tmp_path, monkeypatch,
):
    p = _write_services_toml(
        tmp_path,
        """
[classifiers.pinned]
backend = "nli_cross_encoder"
model = "cross-encoder/nli-deberta-v3-small"
provider = "cpu-fp32"

[transformer_providers.auto]
mode = "auto"
max_batch_size = 16
max_length = 128
executor_workers = 1

[transformer_providers.cpu-fp32]
mode = "explicit"
device = "cpu"
dtype = "fp32"
batch_size = 8
max_length = 128
executor_workers = 1
""",
    )
    seen: list[str] = []

    def fake_inst(name, cfg, provider):
        seen.append(provider.name)
        return _ClfFake(cfg.get("model", name), provider)

    monkeypatch.setattr("pipeline.services._instantiate_classifier", fake_inst)
    resolve_classifiers({"s": "pinned"}, path=p, provider_override="auto")
    assert seen == ["auto"]


def test_resolve_classifiers_entry_pin_beats_table_default(tmp_path, monkeypatch):
    p = _write_services_toml(
        tmp_path,
        """
[classifiers.pinned]
backend = "nli_cross_encoder"
model = "cross-encoder/nli-deberta-v3-small"
provider = "cpu-fp32"

[transformer_providers.auto]
mode = "auto"
max_batch_size = 16
max_length = 128
executor_workers = 1

[transformer_providers.cpu-fp32]
mode = "explicit"
device = "cpu"
dtype = "fp32"
batch_size = 8
max_length = 128
executor_workers = 1

[transformer_provider_defaults]
default = "auto"
""",
    )
    seen: list[str] = []

    def fake_inst(name, cfg, provider):
        seen.append(provider.name)
        return _ClfFake(cfg.get("model", name), provider)

    monkeypatch.setattr("pipeline.services._instantiate_classifier", fake_inst)
    resolve_classifiers({"s": "pinned"}, path=p)
    assert seen == ["cpu-fp32"]


def test_resolve_classifiers_unknown_entry_provider_raises(tmp_path):
    p = _classifier_toml(
        tmp_path,
        """
[classifiers.pinned]
backend = "nli_cross_encoder"
model = "cross-encoder/nli-deberta-v3-small"
provider = "no-such-provider"
""",
    )
    with pytest.raises(ServiceConfigError, match="no-such-provider"):
        resolve_classifiers({"s": "pinned"}, path=p)


def test_resolve_classifiers_unknown_backend_raises(tmp_path):
    p = _classifier_toml(tmp_path)
    with pytest.raises(ServiceConfigError, match="no_such_backend"):
        resolve_classifiers({"slot": "bad-backend"}, path=p)


def test_resolve_classifiers_missing_services_toml_raises(tmp_path):
    missing = tmp_path / "missing" / "SERVICES.toml"
    with pytest.raises(FileNotFoundError, match="SERVICES.toml"):
        resolve_classifiers({"slot": "nli-small"}, path=missing)



def test_instantiate_classifier_overwrites_provider_from_config():
    class _StubClf(ClassifierBackend):
        init_kwargs: dict | None = None
        received_provider: TransformerProvider | None = None

        def __init__(self, model: str, provider: TransformerProvider, **kwargs) -> None:
            self.model_id = model
            self.provider = provider
            _StubClf.init_kwargs = kwargs
            _StubClf.received_provider = provider

        def classify(self, texts, candidate_labels, *, multi_label=True):
            return []

    CLASSIFIER_BACKEND_REGISTRY["stub_clf"] = _StubClf
    try:
        provider = TransformerProvider.from_toml(
            "auto",
            {
                "mode": "auto",
                "max_batch_size": 16,
                "max_length": 128,
                "executor_workers": 1,
            },
        )
        _instantiate_classifier(
            "test-entry",
            {
                "backend": "stub_clf",
                "model": "m",
                "provider": "cpu-fp32",
                "extra": "kept",
            },
            provider,
        )
        assert _StubClf.init_kwargs == {"extra": "kept"}
        assert "provider" not in (_StubClf.init_kwargs or {})
        assert _StubClf.received_provider is provider
        assert _StubClf.received_provider.name == "auto"
    finally:
        CLASSIFIER_BACKEND_REGISTRY.pop("stub_clf", None)