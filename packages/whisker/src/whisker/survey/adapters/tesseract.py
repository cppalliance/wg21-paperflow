#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tesseract adapter: install the pinned Windows OCR runtime and emit markdown.

Tesseract is an OCR engine, not a PDF-to-Markdown converter. ``convert``
rasterizes each page with PyMuPDF, runs the LSTM engine, and joins TSV
paragraphs into running text. No headings, tables, or code fences are invented.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

from whisker.survey import runtime

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

EXIT_INFRA_ERROR = 3
OEM_LSTM = 1
PSM_AUTO = 3
RENDER_DPI = 300
LANG = "eng"

_DOWNLOAD_TIMEOUT_SECONDS = 120
_INSTALLER_TIMEOUT_SECONDS = 300
_CONVERT_TIMEOUT_SECONDS = 600
_VERSION_PROBE_TIMEOUT_SECONDS = 30
_GITHUB_TIMEOUT_SECONDS = 15
_DOWNLOAD_CHUNK_BYTES = 1024 * 1024

_GITHUB_LATEST_URL = (
    "https://api.github.com/repos/tesseract-ocr/tesseract/releases/latest"
)
# Official Windows builds print "tesseract v5.5.0.20241111".
_VERSION_RE = re.compile(r"tesseract\s+v?(\d+\.\d+\.\d+)", re.IGNORECASE)

# Tesseract TSV: level page_num block_num par_num line_num word_num
# left top width height conf text. Words are level 5. The text field may
# contain tabs, so split at most eleven times.
_TSV_WORD_LEVEL = 5
_TSV_FIELD_COUNT = 12

MODES: dict[str, dict[str, Any]] = {
    "lstm": {"oem": OEM_LSTM, "psm": PSM_AUTO, "dpi": RENDER_DPI, "lang": LANG},
}


# ---------------------------------------------------------------------------
# TSV -> markdown (pure; CI tests this without a binary)
# ---------------------------------------------------------------------------


def tsv_to_paragraphs(tsv_text: str) -> list[str]:
    """Turn one Tesseract TSV page into paragraph strings, document order."""
    paragraphs: dict[tuple[int, int, int], list[str]] = {}
    order: list[tuple[int, int, int]] = []
    for raw in tsv_text.splitlines():
        if not raw or raw.startswith("level"):
            continue
        parts = raw.split("\t", _TSV_FIELD_COUNT - 1)
        if len(parts) < _TSV_FIELD_COUNT:
            continue
        try:
            level = int(parts[0])
        except ValueError:
            continue
        if level != _TSV_WORD_LEVEL:
            continue
        word = parts[11].strip()
        if not word:
            continue
        try:
            key = (int(parts[1]), int(parts[2]), int(parts[3]))
        except ValueError:
            continue
        if key not in paragraphs:
            paragraphs[key] = []
            order.append(key)
        paragraphs[key].append(word)
    return [" ".join(paragraphs[key]) for key in order]


def render_markdown(
    *,
    version: str,
    oem: int,
    psm: int,
    dpi: int,
    lang: str,
    pages: list[str],
) -> str:
    """Wrap OCR page bodies in provenance YAML. No structural markup."""
    front = (
        "---\n"
        "generator: tesseract\n"
        f'tesseract_version: "{version}"\n'
        f"oem: {oem}\n"
        f"psm: {psm}\n"
        f"dpi: {dpi}\n"
        f"lang: {lang}\n"
        "---\n\n"
    )
    body = "\n\n".join(page.strip() for page in pages if page.strip())
    if body:
        return front + body + "\n"
    return front


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def _tesseract_root(venv_dir: Path) -> Path:
    """Runtime root is the parent of the private venv."""
    return venv_dir.parent


def _tesseract_exe(root: Path) -> Path:
    if os.name == "nt":
        return root / "tesseract" / "tesseract.exe"
    return root / "tesseract" / "tesseract"


def _tessdata_dir(root: Path) -> Path:
    return root / "tesseract" / "tessdata"


def _python_exe(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _pip_exe(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "pip.exe"
    return venv_dir / "bin" / "pip"


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------


def install(root: Path, lock: dict[str, Any]) -> None:
    """Install or repair the Tesseract runtime at *root*.

    Windows only. The official setup EXE is NSIS and requires elevation if
    executed. Install unpacks it with a pinned 7-Zip SFX instead, so colleagues
    can ``whisker survey install tesseract`` without admin rights.
    """
    if os.name != "nt":
        raise RuntimeError(
            "The tesseract survey adapter pins the official Windows NSIS "
            f"installer ({lock['installer']['filename']}) and unpacks it with "
            "7-Zip. Install on Windows, or add a Linux artifact pin to "
            "tesseract.lock.json."
        )

    runtime.ensure_layout(root)
    runtime.remove_sentinel(root)

    venv = runtime.venv_dir(root)
    pymupdf_version = lock["pymupdf_version"]
    if not _venv_has_pymupdf(venv, pymupdf_version):
        _create_venv(venv)
        _install_pymupdf(venv, pymupdf_version)

    _install_windows_binary(root, lock)
    _install_tessdata(root, lock)

    runtime.write_sentinel(root)
    log.info("Install complete: %s", root)


def _venv_has_pymupdf(venv_dir: Path, expected: str) -> bool:
    python = _python_exe(venv_dir)
    if not python.is_file():
        return False
    try:
        result = subprocess.run(
            [
                str(python),
                "-c",
                "import importlib.metadata; "
                "print(importlib.metadata.version('pymupdf'))",
            ],
            capture_output=True,
            text=True,
            timeout=_VERSION_PROBE_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0 and result.stdout.strip() == expected


def _create_venv(venv_dir: Path) -> None:
    log.info("Creating venv at %s", venv_dir)
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir), "--clear"],
        check=True,
        capture_output=True,
    )


def _install_pymupdf(venv_dir: Path, version: str) -> None:
    pip = _pip_exe(venv_dir)
    pkg = f"pymupdf=={version}"
    log.info("Installing %s into %s", pkg, venv_dir)
    subprocess.run(
        [str(pip), "install", pkg],
        check=True,
        capture_output=True,
    )


def _download_verified(url: str, dest: Path, expected_sha: str) -> None:
    """Download *url* to *dest* unless the file already matches *expected_sha*."""
    if dest.is_file() and runtime.sha256_file(dest) == expected_sha:
        log.info("Already present and hashed: %s", dest.name)
        return

    log.info("Downloading %s", url)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "whisker-survey-tesseract"},
    )
    digest = hashlib.sha256()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as resp:
        with tmp.open("wb") as fh:
            while True:
                chunk = resp.read(_DOWNLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                digest.update(chunk)
                fh.write(chunk)
    actual = digest.hexdigest()
    if actual != expected_sha:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"hash mismatch for {dest.name}: "
            f"expected {expected_sha[:16]}... got {actual[:16]}..."
        )
    tmp.replace(dest)


def _sevenzip_exe(root: Path) -> Path:
    return root / "tools" / "7zip" / "7z.exe"


def _run_unpacker(args: list[str], *, timeout: int, label: str) -> None:
    """Run a pinned unpacker. Never execute the Tesseract setup EXE itself."""
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "")[-500:]
        raise RuntimeError(f"{label} failed (exit {result.returncode}): {detail}")


def _install_sevenzip(root: Path, lock: dict[str, Any]) -> Path:
    """Download 7zr + the 7-Zip SFX and extract 7z.exe without running a setup."""
    sevenz = _sevenzip_exe(root)
    if sevenz.is_file():
        return sevenz

    unpacker = lock["unpacker"]
    sevenzr_spec = unpacker["sevenzr"]
    sfx_spec = unpacker["sevenzip_sfx"]
    sevenzr = root / "temp" / sevenzr_spec["filename"]
    sfx = root / "temp" / sfx_spec["filename"]
    _download_verified(sevenzr_spec["url"], sevenzr, sevenzr_spec["sha256"])
    _download_verified(sfx_spec["url"], sfx, sfx_spec["sha256"])

    dest = sevenz.parent
    dest.mkdir(parents=True, exist_ok=True)
    log.info("Extracting 7-Zip SFX into %s", dest)
    _run_unpacker(
        [str(sevenzr), "x", "-y", f"-o{dest}", str(sfx)],
        timeout=_INSTALLER_TIMEOUT_SECONDS,
        label="7zr SFX extract",
    )
    if not sevenz.is_file():
        raise RuntimeError(f"7-Zip SFX extract did not write {sevenz}")
    return sevenz


def _install_windows_binary(root: Path, lock: dict[str, Any]) -> None:
    exe = _tesseract_exe(root)
    pinned = lock["tesseract_version"]
    if exe.is_file() and _parse_version(_probe_version(exe)) == pinned:
        log.info("tesseract.exe %s already present; skipping unpack", pinned)
        return

    sevenz = _install_sevenzip(root, lock)
    installer = lock["installer"]
    installer_path = root / "temp" / installer["filename"]
    _download_verified(installer["url"], installer_path, installer["sha256"])

    dest = root / "tesseract"
    dest.mkdir(parents=True, exist_ok=True)
    log.info("Extracting NSIS Tesseract installer into %s", dest)
    _run_unpacker(
        [str(sevenz), "x", "-y", f"-o{dest}", str(installer_path)],
        timeout=_INSTALLER_TIMEOUT_SECONDS,
        label="7z NSIS extract",
    )
    if not exe.is_file():
        raise RuntimeError(
            f"NSIS extract did not write tesseract.exe under {dest}"
        )


def _install_tessdata(root: Path, lock: dict[str, Any]) -> None:
    spec = lock["tessdata"]
    dest = _tessdata_dir(root) / spec["filename"]
    _download_verified(spec["url"], dest, spec["sha256"])


# ---------------------------------------------------------------------------
# Version probing
# ---------------------------------------------------------------------------


def _probe_version(exe: Path) -> str:
    """Return combined stdout/stderr of ``tesseract --version``."""
    result = subprocess.run(
        [str(exe), "--version"],
        capture_output=True,
        text=True,
        timeout=_VERSION_PROBE_TIMEOUT_SECONDS,
        cwd=str(exe.parent),
    )
    return (result.stdout or "") + "\n" + (result.stderr or "")


def _parse_version(probe_text: str) -> str | None:
    match = _VERSION_RE.search(probe_text)
    return match.group(1) if match else None


def installed_version(venv_dir: Path) -> str | None:
    """Return the Tesseract binary version, or None if it is not installed."""
    exe = _tesseract_exe(_tesseract_root(venv_dir))
    if not exe.is_file():
        return None
    try:
        return _parse_version(_probe_version(exe))
    except (subprocess.TimeoutExpired, OSError):
        return None


def latest_upstream_version() -> str | None:
    """Query GitHub releases for the latest Tesseract tag. Never raises."""
    try:
        req = urllib.request.Request(
            _GITHUB_LATEST_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "whisker-survey-tesseract",
            },
        )
        with urllib.request.urlopen(req, timeout=_GITHUB_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read())
        tag = str(data.get("tag_name") or "").lstrip("v")
        return tag or None
    except Exception as exc:
        log.debug("GitHub latest-version query failed: %s", exc)
        return None


def verify_patches(venv_dir: Path, lock: dict[str, Any]) -> list[str]:
    """Tesseract carries no source patches."""
    del venv_dir, lock
    return []


# ---------------------------------------------------------------------------
# Convert
# ---------------------------------------------------------------------------


def convert(
    pdf_path: Path,
    out_dir: Path,
    pid: str,
    *,
    oem: int = OEM_LSTM,
    psm: int = PSM_AUTO,
    dpi: int = RENDER_DPI,
    lang: str = LANG,
    env_overrides: dict[str, str],
    venv_dir: Path,
) -> int:
    """Rasterize *pdf_path* and OCR it into ``{out_dir}/{pid}.md``."""
    python = _python_exe(venv_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    root = _tesseract_root(venv_dir)
    exe = _tesseract_exe(root)
    tessdata = _tessdata_dir(root)

    worker = _build_worker_script(
        pdf_path=pdf_path,
        out_dir=out_dir,
        pid=pid,
        exe=exe,
        tessdata=tessdata,
        oem=oem,
        psm=psm,
        dpi=dpi,
        lang=lang,
    )
    env = {**os.environ, **env_overrides}
    env["TESSDATA_PREFIX"] = str(root / "tesseract")

    try:
        result = subprocess.run(
            [str(python), "-c", worker],
            env=env,
            capture_output=True,
            text=True,
            timeout=_CONVERT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        log.error("Tesseract conversion timed out after %ss", _CONVERT_TIMEOUT_SECONDS)
        return EXIT_INFRA_ERROR
    if result.returncode != 0:
        log.error(
            "Tesseract conversion failed (exit %d): %s",
            result.returncode,
            (result.stderr or result.stdout or "(no output)")[-500:],
        )
    return result.returncode


def _build_worker_script(
    *,
    pdf_path: Path,
    out_dir: Path,
    pid: str,
    exe: Path,
    tessdata: Path,
    oem: int,
    psm: int,
    dpi: int,
    lang: str,
) -> str:
    """Inline worker that runs inside the isolated venv (PyMuPDF + tesseract)."""
    return f'''
import re
import subprocess
import sys
from pathlib import Path

import fitz

pdf_path = Path(r"{pdf_path}")
out_dir = Path(r"{out_dir}")
exe = Path(r"{exe}")
tessdata = Path(r"{tessdata}")
pid = "{pid}"
oem = {oem}
psm = {psm}
dpi = {dpi}
lang = "{lang}"
word_level = {_TSV_WORD_LEVEL}
field_count = {_TSV_FIELD_COUNT}

def tsv_to_paragraphs(tsv_text):
    paragraphs = {{}}
    order = []
    for raw in tsv_text.splitlines():
        if not raw or raw.startswith("level"):
            continue
        parts = raw.split("\\t", field_count - 1)
        if len(parts) < field_count:
            continue
        try:
            level = int(parts[0])
        except ValueError:
            continue
        if level != word_level:
            continue
        word = parts[11].strip()
        if not word:
            continue
        try:
            key = (int(parts[1]), int(parts[2]), int(parts[3]))
        except ValueError:
            continue
        if key not in paragraphs:
            paragraphs[key] = []
            order.append(key)
        paragraphs[key].append(word)
    return [" ".join(paragraphs[key]) for key in order]

probe = subprocess.run(
    [str(exe), "--version"], capture_output=True, text=True, cwd=str(exe.parent)
)
match = re.search(
    r"tesseract\\s+v?(\\d+\\.\\d+\\.\\d+)",
    (probe.stdout or "") + "\\n" + (probe.stderr or ""),
    re.IGNORECASE,
)
version = match.group(1) if match else "unknown"

doc = fitz.open(pdf_path)
zoom = dpi / 72
matrix = fitz.Matrix(zoom, zoom)
pages = []
try:
    for index, page in enumerate(doc, start=1):
        png = out_dir / f"{{pid}}-page-{{index}}.png"
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        pix.save(str(png))
        stem = out_dir / f"{{pid}}-page-{{index}}"
        ocr = subprocess.run(
            [
                str(exe), str(png), str(stem),
                "--oem", str(oem), "--psm", str(psm), "-l", lang,
                "--tessdata-dir", str(tessdata), "tsv",
            ],
            capture_output=True,
            text=True,
            cwd=str(exe.parent),
        )
        tsv_path = stem.with_suffix(".tsv")
        if ocr.returncode != 0 or not tsv_path.is_file():
            sys.stderr.write(ocr.stderr or ocr.stdout or "tesseract failed\\n")
            sys.exit({EXIT_INFRA_ERROR})
        pages.append(
            "\\n\\n".join(
                tsv_to_paragraphs(
                    tsv_path.read_text(encoding="utf-8", errors="replace")
                )
            )
        )
finally:
    doc.close()

front = (
    "---\\n"
    "generator: tesseract\\n"
    f'tesseract_version: "{{version}}"\\n'
    f"oem: {{oem}}\\n"
    f"psm: {{psm}}\\n"
    f"dpi: {{dpi}}\\n"
    f"lang: {{lang}}\\n"
    "---\\n\\n"
)
body = "\\n\\n".join(page.strip() for page in pages if page.strip())
md = front + (body + "\\n" if body else "")
(out_dir / f"{{pid}}.md").write_text(md, encoding="utf-8")
'''
