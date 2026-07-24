#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for SERVICES.toml loading and slot resolution."""

from __future__ import annotations

import textwrap

import pytest

from promptforge.services import (
    Service,
    ServiceResolver,
    load_services,
    parse_slot_map,
)

_TOML = """
[services.big-driver]
backend = "vllm_thinking"
base_url = "https://example.proxy.runpod.net/v1"
api_key = "sk-literal"
model = "deepseek-v4-pro"
max_context_window = 393216
tools_capable = true

[services.small-worker]
backend = "vllm_thinking"
base_url = "https://worker.proxy.runpod.net/v1"
api_key = "$MY_KEY_ENV"
model = "qwen3-14b"
tools_capable = false
"""


def _write(tmp_path, text):
    p = tmp_path / "SERVICES.toml"
    p.write_text(text, encoding="utf-8")
    return p


def test_load_services_parses_entries(tmp_path) -> None:
    services = load_services(_write(tmp_path, _TOML))
    big = services["big-driver"]
    assert big.base_url.endswith("/v1")
    assert big.model == "deepseek-v4-pro"
    assert big.tools_capable is True
    assert big.max_context_window == 393216
    assert services["small-worker"].tools_capable is False


def test_load_services_literal_api_key(tmp_path) -> None:
    services = load_services(_write(tmp_path, _TOML))
    assert services["big-driver"].api_key == "sk-literal"


def test_load_services_env_api_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MY_KEY_ENV", "sk-from-env")
    services = load_services(_write(tmp_path, _TOML))
    assert services["small-worker"].api_key == "sk-from-env"


def test_load_services_missing_env_is_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("MY_KEY_ENV", raising=False)
    services = load_services(_write(tmp_path, _TOML))
    assert services["small-worker"].api_key == ""


def test_parse_slot_map() -> None:
    body = textwrap.dedent(
        """
        - **default:** big-driver
        - **worker:** small-worker
        """
    )
    assert parse_slot_map(body) == {"default": "big-driver", "worker": "small-worker"}


def test_resolver_resolves_slot_and_default() -> None:
    services = {
        "big-driver": Service("big-driver", "url", "k", "m", tools_capable=True),
        "small-worker": Service("small-worker", "url2", "k2", "m2"),
    }
    resolver = ServiceResolver(services, {"default": "big-driver", "worker": "small-worker"})
    assert resolver.service("worker").name == "small-worker"
    # Unknown slot falls back to default.
    assert resolver.service("anything").name == "big-driver"


def test_resolver_raises_without_default() -> None:
    services = {"a": Service("a", "u", "k", "m")}
    resolver = ServiceResolver(services, {"worker": "a"})
    with pytest.raises(KeyError):
        resolver.service("missing")


def test_resolver_builds_and_caches_model() -> None:
    services = {"a": Service("a", "u", "k", "m")}
    built: list[str] = []

    def factory(service, max_tokens):
        built.append(service.name)
        return object()

    resolver = ServiceResolver(services, {"default": "a"}, model_factory=factory)
    m1 = resolver.model("default")
    m2 = resolver.model("default")
    assert m1 is m2  # cached per service
    assert built == ["a"]


def test_load_real_repo_services() -> None:
    # The shared inventory the pipeline package already uses; walk-up find.
    services = load_services()
    assert "h200x8-deepseek-v4-pro" in services
    assert services["h200x8-deepseek-v4-pro"].tools_capable is True
