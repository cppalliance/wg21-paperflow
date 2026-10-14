#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Mechanical enforcement of CLAUDE.md invariants, scoped to tomd + whisker.

These tests verify structural rules that are statically checkable:
front-matter ordering, H2-start in body, no print() in library modules,
no lazy imports, and __init__.py purity.

Scope is intentionally limited to the tomd and whisker packages; other
packages are owned by separate work streams.

Not checked here: D1-D11 runtime determinism, wrap_source usage (both
require runtime traces, not AST scanning).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from tomd.lib.metadata_yaml.format import FRONT_MATTER_ORDER

_PACKAGES = Path(__file__).resolve().parent.parent.parent

_SCANNED_PACKAGES = ("tomd", "whisker")

_GOLDEN_DIR = _PACKAGES / "tomd" / "tests" / "fixtures" / "golden"
_CORPUS_DIR = _PACKAGES / "whisker" / "corpus"

_FM_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n?", re.DOTALL)
_H1_RE = re.compile(r"^# \S", re.MULTILINE)

_CLI_MODULES = {"__main__.py", "cli.py", "qa_cli.py", "readback_cli.py", "report.py", "menu.py"}

# Pre-existing violations grandfathered in. New files must not appear here.
# Entries use forward-slash relative paths from packages/ for platform neutrality.
_KNOWN_LAZY_IMPORT_FILES = frozenset({
    "tomd/src/tomd/lib/pdf/docling_backend.py",
    "tomd/src/tomd/lib/pdf/emit.py",
    "tomd/src/tomd/lib/pdf/pipeline.py",
})

_KNOWN_H1_BODY_FILES = frozenset({
    "p2040r0.golden.md",
    "p3556r0.golden.md",
})


def _find_markdown_artifacts() -> list[Path]:
    """Collect all committed markdown artifacts to validate."""
    paths: list[Path] = []
    for g in _GOLDEN_DIR.glob("*.golden.md"):
        paths.append(g)
    for g in _CORPUS_DIR.glob("*.expected.md"):
        paths.append(g)
    return sorted(paths)


def _extract_fm_keys(md_text: str) -> list[str] | None:
    """Return front-matter keys in order, or None if no front matter."""
    m = _FM_RE.match(md_text)
    if not m:
        return None
    keys: list[str] = []
    for line in m.group("body").splitlines():
        if not line.strip() or line.startswith((" ", "\t", "-")):
            continue
        km = re.match(r"^([A-Za-z0-9_-]+)\s*:", line)
        if km:
            keys.append(km.group(1).lower())
    return keys


def _expected_order(found_keys: list[str]) -> list[str]:
    """Return the subset of FRONT_MATTER_ORDER matching found_keys, in order."""
    ordered = [k for k in FRONT_MATTER_ORDER if k in found_keys]
    extra = [k for k in found_keys if k not in FRONT_MATTER_ORDER]
    return ordered + extra


# ── Front-Matter Order ──────────────────────────────────────────────────────

_ARTIFACT_PATHS = _find_markdown_artifacts()


@pytest.mark.parametrize(
    "md_path",
    _ARTIFACT_PATHS,
    ids=[p.name for p in _ARTIFACT_PATHS],
)
def test_front_matter_order(md_path: Path):
    """YAML front-matter keys must follow FRONT_MATTER_ORDER from tomd."""
    md_text = md_path.read_text(encoding="utf-8")
    keys = _extract_fm_keys(md_text)
    if keys is None:
        pytest.skip("no front matter")
    expected = _expected_order(keys)
    assert keys == expected, (
        f"{md_path.name}: front-matter key order wrong\n"
        f"  got:      {keys}\n"
        f"  expected: {expected}"
    )


# ── H2 Rule (body headings start at H2, no H1 in body) ─────────────────────


@pytest.mark.parametrize(
    "md_path",
    _ARTIFACT_PATHS,
    ids=[p.name for p in _ARTIFACT_PATHS],
)
def test_no_h1_in_body(md_path: Path):
    """Body headings must start at H2; the H1 title is in front matter."""
    if md_path.name in _KNOWN_H1_BODY_FILES:
        pytest.xfail(f"pre-existing H1 violation in {md_path.name}")

    md_text = md_path.read_text(encoding="utf-8")
    fm_match = _FM_RE.match(md_text)
    body = md_text[fm_match.end():] if fm_match else md_text

    in_fence = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        assert not _H1_RE.match(line), (
            f"{md_path.name}: H1 heading found in body: {line!r}"
        )


# ── print() Prohibition in Library Modules ──────────────────────────────────


def _lib_python_files() -> list[Path]:
    """Collect tomd + whisker library .py files (not CLI entry points)."""
    files: list[Path] = []
    for pkg_name in _SCANNED_PACKAGES:
        src = _PACKAGES / pkg_name / "src"
        if not src.exists():
            continue
        for py_file in sorted(src.rglob("*.py")):
            if py_file.name in _CLI_MODULES:
                continue
            files.append(py_file)
    return files


_LIB_FILES = _lib_python_files()


@pytest.mark.parametrize(
    "py_path",
    _LIB_FILES,
    ids=[str(p.relative_to(_PACKAGES)) for p in _LIB_FILES],
)
def test_no_print_in_libs(py_path: Path):
    """Library modules must use logging, not print()."""
    try:
        tree = ast.parse(py_path.read_bytes(), filename=str(py_path))
    except SyntaxError:
        pytest.skip(f"syntax error in {py_path.name}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "print":
                pytest.fail(
                    f"{py_path.relative_to(_PACKAGES)}:{node.lineno}: "
                    f"print() call in library module"
                )


# ── Lazy Import Prohibition ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "py_path",
    _LIB_FILES,
    ids=[str(p.relative_to(_PACKAGES)) for p in _LIB_FILES],
)
def test_no_lazy_imports(py_path: Path):
    """No import statements inside functions in tomd/whisker."""
    rel = py_path.relative_to(_PACKAGES).as_posix()
    if rel in _KNOWN_LAZY_IMPORT_FILES:
        pytest.xfail(f"pre-existing lazy import in {rel}")

    try:
        tree = ast.parse(py_path.read_bytes(), filename=str(py_path))
    except SyntaxError:
        pytest.skip(f"syntax error in {py_path.name}")

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for child in ast.walk(node):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                pytest.fail(
                    f"{py_path.relative_to(_PACKAGES)}:{child.lineno}: "
                    f"lazy import inside function {node.name}()"
                )


# ── __init__.py Purity ──────────────────────────────────────────────────────

_ALLOWED_INIT_STMTS = (
    ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign, ast.Expr,
    ast.If,
)


def _init_files() -> list[Path]:
    """Collect all __init__.py files under tomd + whisker src/."""
    files: list[Path] = []
    for pkg_name in _SCANNED_PACKAGES:
        src = _PACKAGES / pkg_name / "src"
        if not src.is_dir():
            continue
        for init in sorted(src.rglob("__init__.py")):
            files.append(init)
    return files


_INIT_FILES = _init_files()


@pytest.mark.parametrize(
    "init_path",
    _INIT_FILES,
    ids=[str(p.relative_to(_PACKAGES)) for p in _INIT_FILES],
)
def test_init_only_reexports(init_path: Path):
    """__init__.py files must contain only imports, __all__, and __version__."""
    try:
        tree = ast.parse(init_path.read_bytes(), filename=str(init_path))
    except SyntaxError:
        pytest.skip(f"syntax error in {init_path.name}")

    for node in tree.body:
        if isinstance(node, _ALLOWED_INIT_STMTS):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in (
                        "__all__", "__version__",
                    ):
                        continue
                    pytest.fail(
                        f"{init_path.relative_to(_PACKAGES)}:{node.lineno}: "
                        f"non-reexport assignment in __init__.py"
                    )
            elif isinstance(node, ast.If):
                # Allow if TYPE_CHECKING / if __name__ == "__main__" guards
                pass
            elif isinstance(node, ast.Expr):
                if isinstance(node.value, (ast.Constant, ast.JoinedStr)):
                    continue
                pytest.fail(
                    f"{init_path.relative_to(_PACKAGES)}:{node.lineno}: "
                    f"non-docstring expression in __init__.py"
                )
            continue
        pytest.fail(
            f"{init_path.relative_to(_PACKAGES)}:{node.lineno}: "
            f"disallowed statement type {type(node).__name__} in __init__.py"
        )
