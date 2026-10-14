#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Marker v2 adapter: install, version probe, and convert.

Handles:
- Creating a private venv with marker-pdf==<pinned>
- Downloading and verifying llama.cpp release assets
- Applying required surya patches programmatically
- Version probing (installed + latest upstream via PyPI)
- Subprocess-based PDF conversion with inference-failure detection
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from whisker.survey import runtime

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

EXIT_INFRA_ERROR = 3
RENDERER = "marker.renderers.markdown.MarkdownRenderer"

# Part of the adapter contract: config name -> keyword arguments for convert().
# The survey iterates this, so the set of measured configurations is the
# adapter's own business rather than something the runner has to know about.
# `fast` and `fast-disable-ocr` were byte-identical on three of four papers in
# the 2026-08 corpus, because WG21 papers are text-native and there is nothing
# for OCR to do. Both are kept so that stays a measurement rather than an
# assumption.
MODES: dict[str, dict[str, Any]] = {
    "balanced": {"mode": "balanced", "disable_ocr": False},
    "fast": {"mode": "fast", "disable_ocr": False},
    "fast-disable-ocr": {"mode": "fast", "disable_ocr": True},
}

_PYPI_URL = "https://pypi.org/pypi/marker-pdf/json"
_PYPI_TIMEOUT_SECONDS = 15

_LLAMA_RELEASE_URL_TEMPLATE = (
    "https://github.com/ggml-org/llama.cpp/releases/download/{release}/{asset}"
)

_HF_RESOLVE_URL_TEMPLATE = (
    "https://huggingface.co/{repo}/resolve/{revision}/{filename}"
)

_DOWNLOAD_CHUNK_BYTES = 1024 * 1024  # 1 MiB streaming buffer

_INFRA_FAILURE_PATTERNS = [
    re.compile(r"Layout inference failed", re.IGNORECASE),
    re.compile(r"Inference error", re.IGNORECASE),
    re.compile(r"failed to parse grammar", re.IGNORECASE),
    re.compile(r"leaving page empty", re.IGNORECASE),
    re.compile(r"Failed to initialize samplers", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------


def install(root: Path, lock: dict[str, Any]) -> None:
    """Install or repair the runtime cache at *root*.

    Resumable: each step checks whether its output already exists and is valid
    before doing expensive work (venv creation, pip install, downloads). Only
    missing or corrupt pieces are rebuilt.

    Steps:
    1. Create venv (skipped if venv python exists)
    2. pip install marker-pdf==<pinned> (skipped if correct version installed)
    3. Download + verify llama.cpp release (skipped if binary hash matches)
    4. Download + verify GGUF model files (skipped per-file if hash matches)
    5. Apply surya patches (idempotent)
    """
    runtime.ensure_layout(root)
    runtime.remove_sentinel(root)

    venv_dir = runtime.venv_dir(root)
    pinned = lock["marker_pdf_version"]

    # Step 1+2: venv + marker-pdf (skip if already correct)
    if _venv_has_marker(venv_dir, pinned):
        log.info("Venv already has marker-pdf==%s; skipping venv/pip", pinned)
    else:
        _create_venv(venv_dir)
        _install_marker(venv_dir, pinned)

    # Step 3: llama.cpp binary (skip if hash matches)
    _install_llama_cpp(root, lock)

    # Step 4: GGUF models (per-file skip logic inside)
    _install_gguf_models(root, lock)

    # Step 5: surya patches (idempotent)
    _apply_patches(venv_dir, lock)

    runtime.write_sentinel(root)
    log.info("Install complete: %s", root)


def _venv_has_marker(venv_dir: Path, expected_version: str) -> bool:
    """Return True if the venv exists and has the expected marker-pdf version."""
    v = installed_version(venv_dir)
    return v == expected_version


def _create_venv(venv_dir: Path) -> None:
    """Create a Python venv using the system/base interpreter."""
    log.info("Creating venv at %s", venv_dir)
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir), "--clear"],
        check=True,
        capture_output=True,
    )


def _pip_exe(venv_dir: Path) -> Path:
    """Return the pip executable path inside the venv."""
    if os.name == "nt":
        return venv_dir / "Scripts" / "pip.exe"
    return venv_dir / "bin" / "pip"


def _python_exe(venv_dir: Path) -> Path:
    """Return the Python executable inside the venv."""
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _install_marker(venv_dir: Path, version: str) -> None:
    """pip install marker-pdf==<version> into the venv."""
    pip = _pip_exe(venv_dir)
    pkg = f"marker-pdf=={version}"
    log.info("Installing %s into %s", pkg, venv_dir)
    subprocess.run(
        [str(pip), "install", pkg],
        check=True,
        capture_output=True,
    )


def _install_llama_cpp(root: Path, lock: dict[str, Any]) -> None:
    """Download the llama.cpp release zip and verify against lock hashes.

    Extracts the full archive (binary + companion DLLs) into llama.cpp/.
    Skips download if the binary has the correct hash AND companion libraries
    are present.
    """
    llama = lock["llama_cpp"]
    binary_name = llama["binary"]
    expected_bin_sha = llama["binary_sha256"]
    llama_dir = root / "llama.cpp"
    binary_path = llama_dir / binary_name

    # Skip if binary is valid AND companion libraries exist
    if binary_path.is_file():
        actual = runtime.sha256_file(binary_path)
        has_companions = any(llama_dir.glob("*.dll")) or any(llama_dir.glob("*.so"))
        if actual == expected_bin_sha and has_companions:
            log.info("llama.cpp binary and libs already valid; skipping download")
            return

    release = llama["release"]
    asset = llama["asset"]
    expected_zip_sha = llama["zip_sha256"]

    url = _LLAMA_RELEASE_URL_TEMPLATE.format(release=release, asset=asset)
    log.info("Downloading llama.cpp %s: %s", release, url)

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        data = resp.read()

    # Verify zip hash
    actual_sha = hashlib.sha256(data).hexdigest()
    if actual_sha != expected_zip_sha:
        raise RuntimeError(
            f"llama.cpp zip hash mismatch: expected {expected_zip_sha[:16]}... "
            f"got {actual_sha[:16]}..."
        )

    # Extract entire zip contents to llama.cpp/ (the binary depends on
    # companion DLLs like ggml.dll, llama.dll that ship in the same archive)
    llama_dir = root / "llama.cpp"
    llama_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        # Find the binary to determine the archive's internal prefix
        candidates = [n for n in zf.namelist() if n.endswith(binary_name)]
        if not candidates:
            raise RuntimeError(
                f"{binary_name} not found in {asset}; "
                f"contents: {zf.namelist()[:10]}"
            )
        # Determine prefix (e.g. "build/bin/") so we can flatten it
        member = candidates[0]
        prefix = member[: -len(binary_name)]

        for entry in zf.namelist():
            if entry.endswith("/"):
                continue
            # Strip the common prefix to flatten into llama_dir
            rel = entry[len(prefix):] if entry.startswith(prefix) else entry
            dest = llama_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(entry))

    # Verify binary hash
    actual_bin_sha = runtime.sha256_file(binary_path)
    if actual_bin_sha != expected_bin_sha:
        raise RuntimeError(
            f"{binary_name} hash mismatch: expected {expected_bin_sha[:16]}... "
            f"got {actual_bin_sha[:16]}..."
        )
    log.info("llama.cpp binary verified: %s", binary_path)


# ---------------------------------------------------------------------------
# GGUF model download
# ---------------------------------------------------------------------------


def gguf_model_path(root: Path, lock: dict[str, Any], filename: str) -> Path:
    """Return the deterministic on-disk path for a GGUF model file.

    Mirrors the HuggingFace Hub cache layout that surya resolves via HF_HOME:
    ``<root>/hf-home/hub/models--<org>--<repo>/snapshots/<revision>/<file>``
    """
    gguf = lock["gguf"]
    repo = gguf["repo"]
    revision = gguf["revision"]
    repo_dir_name = "models--" + repo.replace("/", "--")
    return root / "hf-home" / "hub" / repo_dir_name / "snapshots" / revision / filename


def _install_gguf_models(root: Path, lock: dict[str, Any]) -> None:
    """Download GGUF model files from the pinned HF revision and verify hashes.

    Resumable: skips files that already exist with the correct hash.
    On hash mismatch of an existing file, deletes and re-downloads once.
    """
    gguf = lock.get("gguf", {})
    repo = gguf.get("repo", "")
    revision = gguf.get("revision", "")
    files = gguf.get("files", [])

    if not files:
        log.info("No GGUF files specified in lockfile; skipping")
        return

    for gf in files:
        filename = gf["name"]
        expected_sha = gf["sha256"]
        target = gguf_model_path(root, lock, filename)

        # Resumable: check if already valid
        if target.is_file():
            actual_sha = runtime.sha256_file(target)
            if actual_sha == expected_sha:
                log.info("GGUF already valid, skipping: %s", filename)
                continue
            # Wrong hash: delete and re-download
            log.warning(
                "GGUF hash mismatch for %s (got %s..., expected %s...); "
                "re-downloading",
                filename, actual_sha[:12], expected_sha[:12],
            )
            target.unlink()

        # Download
        target.parent.mkdir(parents=True, exist_ok=True)
        url = _HF_RESOLVE_URL_TEMPLATE.format(
            repo=repo, revision=revision, filename=filename,
        )
        log.info("Downloading GGUF %s from %s", filename, url)
        _stream_download(url, target)

        # Verify hash
        actual_sha = runtime.sha256_file(target)
        if actual_sha != expected_sha:
            target.unlink(missing_ok=True)
            raise RuntimeError(
                f"GGUF hash verification failed for {filename}: "
                f"expected {expected_sha[:16]}... got {actual_sha[:16]}..."
            )
        log.info("GGUF verified: %s (%s)", filename, expected_sha[:12])


def _stream_download(url: str, dest: Path) -> None:
    """Stream a large file from *url* to *dest* without loading into memory."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        with dest.open("wb") as fh:
            while True:
                chunk = resp.read(_DOWNLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                fh.write(chunk)


# ---------------------------------------------------------------------------
# Patches
# ---------------------------------------------------------------------------


def _apply_patches(venv_dir: Path, lock: dict[str, Any]) -> None:
    """Apply known surya patches to the installed package."""
    site_packages = _find_site_packages(venv_dir)
    for patch_spec in lock.get("patches", []):
        patch_id = patch_spec["id"]
        rel_path = patch_spec["file"]
        target = site_packages / rel_path.replace("/", os.sep)
        if not target.is_file():
            log.warning("Patch target not found (skipped): %s", target)
            continue

        if patch_id == "surya-pattern-pcre":
            _apply_pattern_patch(target)
        elif patch_id == "surya-spawn-signal":
            _apply_spawn_patch(target)
        else:
            log.warning("Unknown patch id: %s", patch_id)

        log.info("Applied patch %s to %s", patch_id, target)


def _find_site_packages(venv_dir: Path) -> Path:
    """Locate the site-packages directory inside the venv."""
    if os.name == "nt":
        sp = venv_dir / "Lib" / "site-packages"
    else:
        # Find python3.x directory
        lib = venv_dir / "lib"
        pydirs = list(lib.glob("python3.*"))
        if not pydirs:
            raise RuntimeError(f"No python dir found in {lib}")
        sp = pydirs[0] / "site-packages"
    if not sp.is_dir():
        raise RuntimeError(f"site-packages not found: {sp}")
    return sp


def _apply_pattern_patch(path: Path) -> None:
    r"""Replace \d{1,4} with [0-9]{1,4} in surya prompts.py.

    This fixes ggml-org/llama.cpp#22314: the GBNF converter does not
    support PCRE \d shorthands.
    """
    content = path.read_text(encoding="utf-8")
    original = content
    content = content.replace(r"\d{1,4}", "[0-9]{1,4}")
    if content == original:
        log.info("Pattern patch: no \\d{1,4} found (already patched?)")
        return
    path.write_text(content, encoding="utf-8")
    log.info("Pattern patch applied: replaced \\d{1,4} with [0-9]{1,4}")


def _apply_spawn_patch(path: Path) -> None:
    """Replace os.kill(pid, 0) aliveness probe with Windows-safe _pid_alive.

    On Windows, os.kill(pid, 0) sends CTRL_C_EVENT across the console.
    """
    content = path.read_text(encoding="utf-8")

    # Check if already patched
    if "_pid_alive" in content:
        log.info("Spawn patch: _pid_alive already present (already patched?)")
        return

    # Insert the _pid_alive helper after the logger assignment
    pid_alive_code = '''
def _pid_alive(pid: int) -> bool:
    """Return True if process *pid* is still running (Windows-safe)."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259

        handle = kernel32.OpenProcess(
            wintypes.DWORD(PROCESS_QUERY_LIMITED_INFORMATION),
            wintypes.BOOL(False),
            wintypes.DWORD(pid),
        )
        if not handle:
            return False
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    else:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except OSError:
            return True

'''

    # Insert after 'logger = get_logger()' or similar logger line
    insert_point = content.find("\ndef _cache_dir")
    if insert_point == -1:
        # Fallback: insert before the first function definition after imports
        insert_point = content.find("\ndef ")
        if insert_point == -1:
            log.warning("Spawn patch: cannot find insertion point")
            return

    content = content[:insert_point] + "\n" + pid_alive_code + content[insert_point:]

    # Replace the os.kill(pid, 0) probe pattern with the cross-platform helper
    content = re.sub(
        r"(\s+)try:\s*\n\s+os\.kill\(pid,\s*0\)\s*#[^\n]*\n\s+except ProcessLookupError:\s*\n",
        r"\1if not _pid_alive(pid):\n",
        content,
    )

    path.write_text(content, encoding="utf-8")
    log.info("Spawn patch applied: _pid_alive replaces os.kill(pid, 0)")


def verify_patches(venv_dir: Path, lock: dict[str, Any]) -> list[str]:
    """Verify all patches are applied. Returns list of errors."""
    errors: list[str] = []
    site_packages = _find_site_packages(venv_dir)

    for patch_spec in lock.get("patches", []):
        patch_id = patch_spec["id"]
        rel_path = patch_spec["file"]
        target = site_packages / rel_path.replace("/", os.sep)

        if not target.is_file():
            errors.append(f"patch target missing: {rel_path}")
            continue

        content = target.read_text(encoding="utf-8")
        if patch_id == "surya-pattern-pcre":
            if r"\d{1,4}" in content:
                errors.append(f"patch {patch_id} not applied: \\d still present")
        elif patch_id == "surya-spawn-signal":
            if "_pid_alive" not in content:
                errors.append(f"patch {patch_id} not applied: _pid_alive missing")

    return errors


# ---------------------------------------------------------------------------
# Version probing
# ---------------------------------------------------------------------------


def installed_version(venv_dir: Path) -> str | None:
    """Return the marker-pdf version installed in the venv, or None."""
    python = _python_exe(venv_dir)
    if not python.is_file():
        return None
    try:
        result = subprocess.run(
            [str(python), "-c",
             "import importlib.metadata; "
             "print(importlib.metadata.version('marker-pdf'))"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def latest_upstream_version() -> str | None:
    """Query PyPI for the latest marker-pdf version (requires network)."""
    try:
        req = urllib.request.Request(
            _PYPI_URL,
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=_PYPI_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read())
            return data.get("info", {}).get("version")
    except Exception as exc:
        log.debug("PyPI query failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Convert
# ---------------------------------------------------------------------------


def convert(
    pdf_path: Path,
    out_dir: Path,
    pid: str,
    *,
    mode: str = "balanced",
    disable_ocr: bool = False,
    env_overrides: dict[str, str],
    venv_dir: Path,
) -> int:
    """Run a Marker v2 conversion as a subprocess inside the isolated venv.

    Returns the process exit code. Exit code 3 indicates inference failure
    (output files still written for diagnosis).
    """
    python = _python_exe(venv_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build the worker script inline (runs inside the marker venv)
    worker_code = _build_worker_script(pdf_path, out_dir, pid, mode, disable_ocr)

    env = {**os.environ, **env_overrides}

    result = subprocess.run(
        [str(python), "-c", worker_code],
        env=env,
        capture_output=True,
        text=True,
    )

    # Check for inference failures in stderr
    if result.returncode == 0:
        for line in result.stderr.splitlines():
            for pat in _INFRA_FAILURE_PATTERNS:
                if pat.search(line):
                    log.warning(
                        "Inference failure detected in stderr: %s", line.strip()
                    )
                    return EXIT_INFRA_ERROR

    if result.returncode != 0:
        log.error(
            "Marker conversion failed (exit %d): %s",
            result.returncode,
            result.stderr[-500:] if result.stderr else "(no stderr)",
        )

    return result.returncode


def _build_worker_script(
    pdf_path: Path,
    out_dir: Path,
    pid: str,
    mode: str,
    disable_ocr: bool,
) -> str:
    """Generate the inline Python script for the marker worker subprocess."""
    return f'''
import json, logging, sys
from pathlib import Path
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import convert_if_not_rgb, text_from_rendered

config = {{"mode": "{mode}"}}
{"config['disable_ocr'] = True" if disable_ocr else ""}

artifact_dict = create_model_dict()
converter = PdfConverter(
    artifact_dict=artifact_dict,
    config=config,
    renderer="{RENDERER}",
)
rendered = converter(r"{pdf_path}")
markdown_text, _ext, images = text_from_rendered(rendered)

md_path = Path(r"{out_dir}") / "{pid}.md"
md_path.write_text(markdown_text, encoding="utf-8")

if images:
    for img_name, img_data in images.items():
        img_path = Path(r"{out_dir}") / img_name
        img_path.parent.mkdir(parents=True, exist_ok=True)
        img_data = convert_if_not_rgb(img_data)
        img_data.save(str(img_path))
'''
