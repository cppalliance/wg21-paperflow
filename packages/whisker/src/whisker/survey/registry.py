#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Competitor registry for the whisker survey monitor.

Each registered competitor is a ``CompetitorSpec`` that names an adapter module,
a pinned version, and a lockfile containing reproducibility hashes.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PatchSpec:
    """A named, versioned source patch applied at install time."""

    id: str
    version: int
    file: str
    description: str
    upstream_issue: str
    retire_when: str


@dataclass(frozen=True)
class CompetitorSpec:
    """Immutable descriptor for a registered competitor project."""

    name: str
    display_name: str
    pinned_version: str
    adapter: str
    lockfile_path: Path
    patches: list[PatchSpec] = field(default_factory=list)


def _locks_dir() -> Path:
    """Return the absolute path to the ``locks/`` data directory."""
    ref = resources.files("whisker.survey.locks")
    # importlib.resources on 3.12+ returns a Traversable; cast to Path
    return Path(str(ref))


def _load_lock(path: Path) -> dict[str, Any]:
    """Load and return parsed JSON from a lockfile."""
    return json.loads(path.read_text(encoding="utf-8"))


def _patches_from_lock(lock: dict[str, Any]) -> list[PatchSpec]:
    """Extract PatchSpec list from a parsed lockfile."""
    specs: list[PatchSpec] = []
    for p in lock.get("patches", []):
        specs.append(PatchSpec(
            id=p["id"],
            version=p["version"],
            file=p["file"],
            description=p["description"],
            upstream_issue=p["upstream_issue"],
            retire_when=p["retire_when"],
        ))
    return specs


# ---------------------------------------------------------------------------
# Registry: ordered list of competitors
# ---------------------------------------------------------------------------

_REGISTRY: list[CompetitorSpec] = []


def _register_marker() -> None:
    """Register marker-pdf as the first competitor."""
    lock_path = _locks_dir() / "marker.lock.json"
    lock = _load_lock(lock_path)
    patches = _patches_from_lock(lock)
    spec = CompetitorSpec(
        name="marker",
        display_name="Marker v2 (marker-pdf)",
        pinned_version=lock["marker_pdf_version"],
        adapter="whisker.survey.adapters.marker",
        lockfile_path=lock_path,
        patches=patches,
    )
    _REGISTRY.append(spec)


_register_marker()


def _register_tesseract() -> None:
    """Register Tesseract OCR as the second competitor."""
    lock_path = _locks_dir() / "tesseract.lock.json"
    lock = _load_lock(lock_path)
    spec = CompetitorSpec(
        name="tesseract",
        display_name="Tesseract OCR",
        pinned_version=lock["tesseract_version"],
        adapter="whisker.survey.adapters.tesseract",
        lockfile_path=lock_path,
        patches=_patches_from_lock(lock),
    )
    _REGISTRY.append(spec)


_register_tesseract()


def list_competitors() -> list[CompetitorSpec]:
    """Return all registered competitors (ordered)."""
    return list(_REGISTRY)


def get_competitor(name: str) -> CompetitorSpec | None:
    """Look up a competitor by name (case-insensitive)."""
    key = name.lower()
    for spec in _REGISTRY:
        if spec.name.lower() == key:
            return spec
    return None


def load_lockfile(spec: CompetitorSpec) -> dict[str, Any]:
    """Load the parsed lockfile for a given competitor spec."""
    return _load_lock(spec.lockfile_path)
