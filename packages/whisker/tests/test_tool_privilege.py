#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Least-privilege guard: whisker's advisory LLM lane exposes zero
model-callable tools.

AST-scans every module in `llm/` and fails if any of the patterns in
`_BANNED_PATTERNS` appear: a `@tool` decorator, a `FunctionTool(...)`
constructor call, a non-empty `tools=[...]` kwarg on an `Agent()` /
`AgentBackend()` constructor call, or the literal string
`parallel_tool_calls=True` (project rule D4). Pure static analysis: no
`pipeline` import, no LLM call, hermetic.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Callable, NamedTuple

import pytest

_PACKAGES = Path(__file__).resolve().parent.parent.parent
_TAPETUM_LLM_DIR = _PACKAGES / "whisker" / "src" / "whisker" / "llm"

_AGENT_CONSTRUCTOR_NAMES = frozenset({"Agent", "AgentBackend"})
_PARALLEL_TOOL_CALLS_RE = re.compile(r"parallel_tool_calls\s*=\s*True")

_BANNED_PATTERNS = frozenset({
    "tool_decorator",
    "function_tool_constructor",
    "tools_kwarg_nonempty",
    "parallel_tool_calls_true",
})


class _Violation(NamedTuple):
    pattern: str
    lineno: int
    detail: str


def _callee_name(node: ast.expr) -> str | None:
    """Return the trailing name of a call target: `Agent` or `pkg.Agent`."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _decorator_names(decorator: ast.expr) -> list[str]:
    """Every Name.id / Attribute.attr appearing anywhere in a decorator
    expression, covering both `@tool` and `@tool(...)` forms."""
    names: list[str] = []
    for node in ast.walk(decorator):
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
    return names


def _scan_tool_decorator(tree: ast.Module, source: str) -> list[_Violation]:
    violations: list[_Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if "tool" in _decorator_names(decorator):
                    violations.append(_Violation(
                        "tool_decorator", decorator.lineno,
                        f"@tool decorator on {node.name}()",
                    ))
    return violations


def _scan_function_tool_constructor(tree: ast.Module, source: str) -> list[_Violation]:
    violations: list[_Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _callee_name(node.func) == "FunctionTool":
            violations.append(_Violation(
                "function_tool_constructor", node.lineno,
                "FunctionTool(...) constructor call",
            ))
    return violations


def _scan_tools_kwarg(tree: ast.Module, source: str) -> list[_Violation]:
    violations: list[_Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _callee_name(node.func) not in _AGENT_CONSTRUCTOR_NAMES:
            continue
        for kw in node.keywords:
            if kw.arg != "tools":
                continue
            if isinstance(kw.value, ast.List) and kw.value.elts:
                violations.append(_Violation(
                    "tools_kwarg_nonempty", kw.value.lineno,
                    f"tools=[...] with {len(kw.value.elts)} entries on "
                    f"{_callee_name(node.func)}()",
                ))
    return violations


def _scan_parallel_tool_calls(tree: ast.Module, source: str) -> list[_Violation]:
    violations: list[_Violation] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        if _PARALLEL_TOOL_CALLS_RE.search(line):
            violations.append(_Violation(
                "parallel_tool_calls_true", lineno, line.strip(),
            ))
    return violations


_SCANNERS: dict[str, Callable[[ast.Module, str], list[_Violation]]] = {
    "tool_decorator": _scan_tool_decorator,
    "function_tool_constructor": _scan_function_tool_constructor,
    "tools_kwarg_nonempty": _scan_tools_kwarg,
    "parallel_tool_calls_true": _scan_parallel_tool_calls,
}


def _scan_file(py_path: Path) -> list[_Violation]:
    source = py_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(py_path))
    violations: list[_Violation] = []
    for pattern in _BANNED_PATTERNS:
        violations.extend(_SCANNERS[pattern](tree, source))
    return violations


def _tapetum_llm_files() -> list[Path]:
    if not _TAPETUM_LLM_DIR.is_dir():
        return []
    return sorted(_TAPETUM_LLM_DIR.rglob("*.py"))


_TAPETUM_LLM_FILES = _tapetum_llm_files()


@pytest.mark.parametrize(
    "py_path", _TAPETUM_LLM_FILES, ids=[p.name for p in _TAPETUM_LLM_FILES],
)
def test_no_model_callable_tools(py_path: Path):
    """The advisory LLM lane must register zero model-callable tools."""
    violations = _scan_file(py_path)
    assert not violations, "\n".join(
        f"{py_path.relative_to(_PACKAGES)}:{v.lineno}: [{v.pattern}] {v.detail}"
        for v in violations
    )


def test_tapetum_llm_dir_was_scanned():
    """Guard against a silent zero-file collection (directory move/rename)."""
    assert _TAPETUM_LLM_FILES, (
        f"no .py files found under {_TAPETUM_LLM_DIR}; the guard scanned nothing"
    )
