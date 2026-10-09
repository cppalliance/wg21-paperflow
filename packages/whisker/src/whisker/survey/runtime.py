#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""External per-competitor runtime cache management.

Each competitor gets a version-bound runtime cache under
``%LOCALAPPDATA%/whisker/survey/<name>/<version>/``. The cache holds a private
venv, optional native binaries, optional HF model files, and temp directories.
Isolation environment overrides remain process-local. Marker-only llama.cpp /
GGUF keys are applied only when the lockfile carries them.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

_HASH_CHUNK_BYTES = 1024 * 1024  # 1 MiB read buffer for sha256
_INSTALL_SENTINEL = ".install_complete"

# Cache subdirectory layout
_VENV_SUBDIR = "venv"
_SUBDIRS = (_VENV_SUBDIR, "llama.cpp", "hf-home", "temp", "profile")


def _cache_base() -> Path:
    """Return the platform-appropriate base cache directory.

    Uses %LOCALAPPDATA% on Windows with a fallback to ~/.local/share.
    """
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "whisker" / "survey"
    # Fallback for non-Windows (XDG_DATA_HOME or ~/.local/share)
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "whisker" / "survey"
    return Path.home() / ".local" / "share" / "whisker" / "survey"


def cache_root(name: str, version: str) -> Path:
    """Return the versioned cache root for a competitor."""
    return _cache_base() / name / version


def venv_dir(root: Path) -> Path:
    """Return the private interpreter directory inside a runtime cache."""
    return root / _VENV_SUBDIR


def is_installed(root: Path) -> bool:
    """Return True if the cache at *root* has a valid install sentinel."""
    return (root / _INSTALL_SENTINEL).is_file()


def sha256_file(path: Path) -> str:
    """Return lowercase hex SHA-256 digest of *path*."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_HASH_CHUNK_BYTES), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_integrity(root: Path, lock: dict[str, Any]) -> list[str]:
    """Check critical files against lockfile hashes. Returns list of errors.

    Marker-shaped keys (``llama_cpp``, ``gguf``) are checked only when present.
    Any competitor may also pin ``artifacts`` as ``{relpath, sha256}`` pairs
    relative to *root*.
    """
    errors: list[str] = []

    llama = lock.get("llama_cpp")
    if llama:
        binary_name = llama["binary"]
        binary_path = root / "llama.cpp" / binary_name
        if not binary_path.is_file():
            errors.append(f"missing: {binary_path}")
        else:
            expected = llama["binary_sha256"]
            actual = sha256_file(binary_path)
            if actual != expected:
                errors.append(
                    f"hash mismatch: {binary_path.name} "
                    f"expected={expected[:16]}... got={actual[:16]}..."
                )

    hf_home = root / "hf-home"
    for gf in lock.get("gguf", {}).get("files", []):
        # Look for the GGUF anywhere under hf-home (hub structure varies)
        found = list(hf_home.rglob(gf["name"]))
        if not found:
            errors.append(f"missing GGUF: {gf['name']}")
        else:
            actual = sha256_file(found[0])
            if actual != gf["sha256"]:
                errors.append(
                    f"GGUF hash mismatch: {gf['name']} "
                    f"expected={gf['sha256'][:16]}... got={actual[:16]}..."
                )

    for art in lock.get("artifacts", []):
        relpath = art["relpath"]
        expected = art["sha256"]
        path = root / relpath
        if not path.is_file():
            errors.append(f"missing: {path}")
            continue
        actual = sha256_file(path)
        if actual != expected:
            errors.append(
                f"hash mismatch: {path.name} "
                f"expected={expected[:16]}... got={actual[:16]}..."
            )

    return errors


def teardown(root: Path) -> None:
    """Remove an existing runtime cache (for --refresh-runtime)."""
    if root.exists():
        log.info("Tearing down runtime cache: %s", root)
        shutil.rmtree(root, ignore_errors=True)


def ensure_layout(root: Path) -> None:
    """Create the cache subdirectory structure."""
    for sub in _SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)


def write_sentinel(root: Path) -> None:
    """Write the install-complete sentinel (only after a successful install)."""
    (root / _INSTALL_SENTINEL).write_text("ok\n", encoding="utf-8")


def remove_sentinel(root: Path) -> None:
    """Remove the sentinel to mark an incomplete/broken install."""
    sentinel = root / _INSTALL_SENTINEL
    if sentinel.exists():
        sentinel.unlink()


def build_env_dict(root: Path, lock: dict[str, Any]) -> dict[str, str]:
    """Construct the process-local environment overrides for a runtime cache.

    Isolation vars (HOME, TEMP, pip/uv caches, HF_HOME) are always set.
    Marker-only keys (LLAMA_CPP_BINARY, SURYA_GGUF_*) are added only when
    the lockfile carries ``llama_cpp`` / ``gguf``.
    """
    hf_home = root / "hf-home"
    temp_dir = root / "temp"
    profile_dir = root / "profile"

    env = {
        "HF_HOME": str(hf_home),
        "HUGGINGFACE_HUB_CACHE": str(hf_home / "hub"),
        "XDG_CACHE_HOME": str(hf_home),
        "PIP_CACHE_DIR": str(temp_dir / "pip-cache"),
        "UV_CACHE_DIR": str(temp_dir / "uv-cache"),
        "HOME": str(profile_dir),
        "USERPROFILE": str(profile_dir),
        "TEMP": str(temp_dir),
        "TMP": str(temp_dir),
    }

    llama = lock.get("llama_cpp")
    if llama:
        env["LLAMA_CPP_BINARY"] = str(root / "llama.cpp" / llama["binary"])

    gguf = lock.get("gguf") or {}
    if gguf:
        gguf_dir = _gguf_snapshot_dir(root, gguf)
        for gf in gguf.get("files", []):
            name = gf["name"]
            if "mmproj" in name:
                env["SURYA_GGUF_LOCAL_MMPROJ_PATH"] = str(gguf_dir / name)
            else:
                env["SURYA_GGUF_LOCAL_MODEL_PATH"] = str(gguf_dir / name)

    return env


def _gguf_snapshot_dir(root: Path, gguf: dict[str, Any]) -> Path:
    """Return the directory holding GGUF files for the pinned revision."""
    repo = gguf["repo"]
    revision = gguf["revision"]
    repo_dir_name = "models--" + repo.replace("/", "--")
    return root / "hf-home" / "hub" / repo_dir_name / "snapshots" / revision
