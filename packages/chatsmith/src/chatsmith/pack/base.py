#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Domain packs.

A pack is a directory of data (no code) that supplies everything domain-specific:
the pipeline prompt (persona + per-step instructions + model slots), the STT
glossary, mishearing hints, and UI branding/themes. Selecting a different pack
repurposes the whole app -- WG21, Boost, or any field -- with no code change.

``FileSystemPack`` reads such a directory; ``resolve`` picks a bundled pack by
name or an external one by path.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from chatsmith.pack.prompt import parse_sections, parse_services

_DEFAULT_KICKOFF = (
    "(The interview is starting now. Greet the subject warmly in one or two "
    "sentences, then ask for their name and one open first question.)"
)
_DEFAULT_REPLY = (
    "Reply to the latest utterance as the interviewer: briefly reflect what the "
    "subject said, then ask a single open question. One short turn, spoken aloud; "
    "no lists, headings, or stage directions."
)


class PackNotFoundError(FileNotFoundError):
    """Raised when a pack name/dir does not resolve to a readable pack directory."""


@dataclass(frozen=True)
class Branding:
    """Presentation identity a pack gives the GUI (character stays decoupled from code)."""

    name: str
    character: str
    display_name: str
    title: str
    themes: dict[str, Any]


@runtime_checkable
class DomainPack(Protocol):
    @property
    def name(self) -> str: ...
    def system_prompt(self) -> str: ...
    def reply_instruction(self) -> str: ...
    def kickoff_instruction(self) -> str: ...
    def normalize_system_prompt(self) -> str: ...
    def keyterms(self) -> list[str]: ...
    def corpus_by_category(self) -> dict[str, list[str]]: ...
    def mishearings(self) -> dict[str, str]: ...
    def services(self) -> dict[str, str]: ...
    def branding(self) -> Branding: ...


class FileSystemPack:
    """A :class:`DomainPack` backed by a directory of data files."""

    def __init__(self, root: Path):
        self._root = Path(root)
        manifest_path = self._root / "pack.toml"
        if not manifest_path.is_file():
            raise PackNotFoundError(f"pack manifest not found: {manifest_path}")
        self._manifest: dict[str, Any] = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        prompt_file = self._manifest.get("prompt", "prompt.md")
        prompt_path = self._root / prompt_file
        text = prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else ""
        self._sections = parse_sections(text)

    @property
    def name(self) -> str:
        return str(self._manifest.get("name") or self._root.name)

    def system_prompt(self) -> str:
        return self._sections.get("System Prompt", "").strip()

    def reply_instruction(self) -> str:
        return self._sections.get("Reply", "").strip() or _DEFAULT_REPLY

    def kickoff_instruction(self) -> str:
        return self._sections.get("Kickoff", "").strip() or _DEFAULT_KICKOFF

    def normalize_system_prompt(self) -> str:
        """Assemble the normalizer prefix: pack rules + mishearings + vocabulary."""
        rules = self._sections.get("Normalize", "").strip()
        parts: list[str] = [rules] if rules else []
        mishearings = self.mishearings()
        if mishearings:
            parts.append("\nCommon mis-hearings (misheard -> canonical):")
            parts.extend(f"- {heard} -> {canon}" for heard, canon in mishearings.items())
        corpus = self.corpus_by_category()
        if corpus:
            parts.append("\nReference vocabulary (canonical forms), by area:")
            for category, terms in corpus.items():
                if terms:
                    parts.append(f"- {category}: {', '.join(terms)}")
        return "\n".join(parts).strip()

    def keyterms(self) -> list[str]:
        path = self._root / str(self._manifest.get("keyterms", "keyterms.txt"))
        if not path.is_file():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        return [term.strip() for term in lines if term.strip()]

    def corpus_by_category(self) -> dict[str, list[str]]:
        return self._load_json_map(self._manifest.get("corpus", "corpus_by_category.json"))

    def mishearings(self) -> dict[str, str]:
        path = self._root / str(self._manifest.get("mishearings", "mishearings.json"))
        if not path.is_file():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items()}

    def services(self) -> dict[str, str]:
        # pack.toml [services] wins; otherwise parse the prompt's ## Services block.
        table = self._manifest.get("services")
        if isinstance(table, dict) and table:
            return {str(k).lower(): str(v) for k, v in table.items()}
        return parse_services(self._sections.get("Services", ""))

    def branding(self) -> Branding:
        themes_path = self._root / str(self._manifest.get("themes", "themes.json"))
        themes: dict[str, Any] = {}
        if themes_path.is_file():
            themes = json.loads(themes_path.read_text(encoding="utf-8"))
        return Branding(
            name=self.name,
            character=str(self._manifest.get("character", "Nova")),
            display_name=str(self._manifest.get("display_name", self.name)),
            title=str(self._manifest.get("title", self.name)),
            themes=themes,
        )

    def _load_json_map(self, filename: Any) -> dict[str, list[str]]:
        path = self._root / str(filename)
        if not path.is_file():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError(f"pack file {path.name}: expected a JSON object, got {type(data).__name__}")
        result: dict[str, list[str]] = {}
        for key, value in data.items():
            # A bare string would silently explode into per-character "terms"; require
            # a list so a pack author's shape mistake fails loudly instead.
            if not isinstance(value, list):
                raise TypeError(
                    f"pack file {path.name}: value for {str(key)!r} must be a list of "
                    f"strings, got {type(value).__name__}"
                )
            result[str(key)] = [str(t) for t in value]
        return result


def _bundled_packs_dir() -> Path:
    # chatsmith/pack/base.py -> chatsmith/packs
    return Path(__file__).resolve().parent.parent / "packs"


@lru_cache(maxsize=8)
def resolve(pack: str = "wg21", pack_dir: str = "") -> DomainPack:
    """Resolve the active pack: an external ``pack_dir`` if given, else bundled ``pack``."""
    root = Path(pack_dir) if pack_dir else _bundled_packs_dir() / pack
    if not (root / "pack.toml").is_file():
        raise PackNotFoundError(
            f"No pack at {root}. Set CHATSMITH_PACK to a bundled pack name "
            f"(e.g. 'wg21') or CHATSMITH_PACK_DIR to an external pack directory."
        )
    return FileSystemPack(root)
