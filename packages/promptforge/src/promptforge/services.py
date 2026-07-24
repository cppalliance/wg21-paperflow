#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Service resolution from the shared ``SERVICES.toml`` inventory.

PromptForge reaches its models through the same ``SERVICES.toml`` the
``pipeline`` package defines: a pure infrastructure inventory of endpoints and
their capabilities, with API keys taken from the environment. This module reads
only the connection facts PromptForge needs (base URL, key, model, whether the
endpoint can do tool calls) rather than constructing pipeline's pydantic-bound
backends, which keeps PromptForge free of pydantic.

A pipeline document maps logical slots (used by Lua ``model("slot")``) to
service names in its own ``## Services`` block, mirroring ``assay.md``. A
``ServiceResolver`` ties the two together and hands back a ready ``Model``.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

_SERVICES_FILENAME = "SERVICES.toml"
_SLOT_RE = re.compile(r"^\s*-\s*\*\*([\w -]+):\*\*\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Service:
    """Connection facts for one LLM endpoint."""

    name: str
    base_url: str
    api_key: str
    model: str
    tools_capable: bool = False
    max_context_window: int = 131072


def _find_services_toml() -> Path | None:
    """Walk up from the current directory to find SERVICES.toml."""
    here = Path.cwd()
    for directory in (here, *here.parents):
        candidate = directory / _SERVICES_FILENAME
        if candidate.is_file():
            return candidate
    return None


def load_services(path: str | Path | None = None) -> dict[str, Service]:
    """Parse SERVICES.toml into a name-to-:class:`Service` map.

    API-key resolution mirrors the pipeline loader: ``$ENV`` expands from the
    environment, a bare literal is used as-is, and the legacy ``api_key_env``
    names an env var. A missing env var yields an empty key (validation is the
    caller's concern, lazily, only for services it actually uses).
    """
    resolved = Path(path) if path is not None else _find_services_toml()
    if resolved is None or not resolved.is_file():
        raise FileNotFoundError(
            f"{_SERVICES_FILENAME} not found (searched upward from cwd)"
        )

    config = tomllib.loads(resolved.read_text(encoding="utf-8"))
    services: dict[str, Service] = {}
    for name, entry in config.get("services", {}).items():
        services[name] = Service(
            name=name,
            base_url=entry.get("base_url", ""),
            api_key=_resolve_api_key(entry),
            model=entry.get("model", ""),
            tools_capable=bool(entry.get("tools_capable", False)),
            max_context_window=int(entry.get("max_context_window", 131072)),
        )
    return services


def _resolve_api_key(entry: dict[str, Any]) -> str:
    raw = entry.get("api_key", "")
    env = entry.get("api_key_env", "")
    if isinstance(raw, str) and raw.startswith("$"):
        return os.environ.get(raw[1:], "")
    if raw:
        return raw
    if env:
        return os.environ.get(env, "")
    return ""


def parse_slot_map(body: str) -> dict[str, str]:
    """Parse a ``## Services`` block into a logical-slot -> service-name map.

    Accepts ``- **slot:** service-name`` bullets; keys are lowercased.
    """
    return {
        m.group(1).strip().lower(): m.group(2).strip()
        for m in _SLOT_RE.finditer(body)
        if m.group(2).strip()
    }


def build_model(service: Service, *, max_tokens: int = 4096) -> Any:
    """Build an OpenAI-compatible model for a service (default factory)."""
    from promptforge.inference import OpenAIToolModel

    return OpenAIToolModel(
        model=service.model,
        base_url=service.base_url,
        api_key=service.api_key,
        max_tokens=max_tokens,
    )


class ServiceResolver:
    """Resolve Lua ``model(slot)`` names to concrete models.

    A slot resolves through the pipeline's ``## Services`` map to a service
    name, then to a :class:`Service`. Missing slots fall back to ``default``.
    Built models are cached per service so one backend is shared across the
    sections that use it.
    """

    def __init__(
        self,
        services: dict[str, Service],
        slot_map: dict[str, str],
        *,
        model_factory: Callable[..., Any] = build_model,
        max_tokens: int = 4096,
    ) -> None:
        self._services = services
        self._slot_map = slot_map
        self._factory = model_factory
        self._max_tokens = max_tokens
        self._models: dict[str, Any] = {}

    def service(self, slot: str) -> Service:
        name = self._slot_map.get(slot) or self._slot_map.get("default")
        if name is None:
            raise KeyError(f"no service for slot '{slot}' and no 'default' slot")
        if name not in self._services:
            raise KeyError(
                f"slot '{slot}' maps to service '{name}', not in SERVICES.toml; "
                f"available: {sorted(self._services)}"
            )
        return self._services[name]

    def model(self, slot: str) -> Any:
        service = self.service(slot)
        if service.name not in self._models:
            self._models[service.name] = self._factory(service, max_tokens=self._max_tokens)
        return self._models[service.name]
