#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Guard: the root import-linter contracts protecting the D1/G1 epistemic
separation boundary (whisker core must not import `whisker.llm` or
`pipeline`) actually exist.

Auditv5 finding (softcap/M8): nothing in `packages/whisker/tests/` noticed if
someone deleted `[tool.importlinter]` from the root `pyproject.toml`. CI would
still catch a REAL violating import (the `lint-imports` job would simply have
nothing to check and pass vacuously), but the contract's continued EXISTENCE
had no test coverage from whisker's own suite. This test reads (never writes)
the root `pyproject.toml`, found by walking up from this file, and asserts the
section and both forbidden contracts are present with the right shape.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

_PYPROJECT_FILENAME = "pyproject.toml"


def _find_repo_root_pyproject() -> Path:
    """Walk up from this test file to the repo-root pyproject.toml.

    Never hardcode an absolute path: this file lives at
    packages/whisker/tests/, and the workspace root (the file that declares
    [tool.uv.workspace]) is an ancestor, not a fixed depth away.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / _PYPROJECT_FILENAME
        if candidate.is_file():
            data = tomllib.loads(candidate.read_text(encoding="utf-8"))
            if "workspace" in data.get("tool", {}).get("uv", {}):
                return candidate
    raise FileNotFoundError(
        f"could not find repo-root {_PYPROJECT_FILENAME} by walking up from {here}"
    )


@pytest.fixture(scope="module")
def root_pyproject() -> dict:
    path = _find_repo_root_pyproject()
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _contracts(root_pyproject: dict) -> list[dict]:
    return root_pyproject["tool"]["importlinter"]["contracts"]


def _contract_named(root_pyproject: dict, name: str) -> dict:
    for contract in _contracts(root_pyproject):
        if contract.get("name") == name:
            return contract
    raise AssertionError(f"no [[tool.importlinter.contracts]] entry named {name!r}")


class TestImportLinterSectionExists:
    def test_importlinter_section_present(self, root_pyproject):
        assert "importlinter" in root_pyproject.get("tool", {}), (
            "[tool.importlinter] is missing from the root pyproject.toml: "
            "the D1/G1 core-vs-advisory-lane separation boundary is no "
            "longer mechanically enforced in CI"
        )

    def test_root_packages_includes_whisker(self, root_pyproject):
        root_packages = root_pyproject["tool"]["importlinter"]["root_packages"]
        assert "whisker" in root_packages

    def test_at_least_two_contracts_declared(self, root_pyproject):
        assert len(_contracts(root_pyproject)) >= 2


class TestForbidTapetumLlmContract:
    """`whisker` core must not import `whisker.llm` (the advisory
    LLM lane). This is the mechanical proof behind D1 level 4 / G1."""

    _NAME = "Deterministic core must not import the advisory LLM lane"

    def test_contract_exists_and_is_forbidden_type(self, root_pyproject):
        contract = _contract_named(root_pyproject, self._NAME)
        assert contract["type"] == "forbidden"

    def test_forbids_tapetum_llm(self, root_pyproject):
        contract = _contract_named(root_pyproject, self._NAME)
        assert "whisker.llm" in contract["forbidden_modules"]

    def test_source_modules_cover_the_deterministic_core(self, root_pyproject):
        contract = _contract_named(root_pyproject, self._NAME)
        source_modules = set(contract["source_modules"])
        # The load-bearing deterministic modules named in CLAUDE.md's
        # "Three lanes" section; if any of these drop off the contract, the
        # separation boundary has a hole for that module.
        expected_core_modules = {
            "whisker.cli_common",
            "whisker.det.cli",
            "whisker.det.score",
            "whisker.metrics",
            "whisker.det.match",
            "whisker.gates",
            "whisker.facts",
            # The table-readability contract defines what a correctly readable
            # table is and judges the advisory lane against it, so it must not
            # be able to import that lane.
            "whisker.det.llm_readability",
        }
        missing = expected_core_modules - source_modules
        assert not missing, (
            f"deterministic-core modules missing from the forbidden-import "
            f"contract's source_modules: {sorted(missing)}"
        )


class TestForbidPipelineContract:
    """`whisker` core must not import `pipeline` (the LLM framework), keeping
    the core install standalone and LLM-free (D7 extras isolation)."""

    _NAME = "Deterministic core must not import the pipeline framework"

    def test_contract_exists_and_is_forbidden_type(self, root_pyproject):
        contract = _contract_named(root_pyproject, self._NAME)
        assert contract["type"] == "forbidden"

    def test_forbids_pipeline(self, root_pyproject):
        contract = _contract_named(root_pyproject, self._NAME)
        assert "pipeline" in contract["forbidden_modules"]

    def test_source_modules_cover_the_deterministic_core(self, root_pyproject):
        contract = _contract_named(root_pyproject, self._NAME)
        source_modules = set(contract["source_modules"])
        expected_core_modules = {
            "whisker.cli_common",
            "whisker.det.cli",
            "whisker.det.score",
            "whisker.metrics",
            "whisker.det.match",
            "whisker.gates",
            "whisker.facts",
            "whisker.det.llm_readability",
        }
        missing = expected_core_modules - source_modules
        assert not missing, (
            f"deterministic-core modules missing from the forbidden-import "
            f"contract's source_modules: {sorted(missing)}"
        )


def _whisker_package_dir() -> Path:
    """The ``src/whisker`` directory of this package."""
    return Path(__file__).resolve().parents[1] / "src" / "whisker"


def _top_level_modules() -> set[str]:
    """Every whisker top-level module as ``whisker.<stem>``.

    ``__init__.py`` is the package itself, not a module of it, so it is
    excluded; subpackages are covered by their own contract entries.
    """
    return {
        f"whisker.{path.stem}"
        for path in sorted(_whisker_package_dir().glob("*.py"))
        if path.stem != "__init__"
    }


class TestContractCoverageCompleteness:
    """Every whisker top-level module must appear in some contract's
    ``source_modules``: a module absent from every contract is a hole in
    the lane boundary. D5: ``whisker.__main__`` and ``whisker.menu`` were
    exactly such holes - the only two modules that (legitimately) reach
    the llm lane, and the two the contracts did not watch."""

    def test_every_top_level_module_is_covered(self, root_pyproject):
        covered: set[str] = set()
        for contract in _contracts(root_pyproject):
            covered.update(contract.get("source_modules", []))
        missing = _top_level_modules() - covered
        assert not missing, (
            f"whisker top-level modules missing from every import-linter "
            f"contract's source_modules: {sorted(missing)}"
        )


_ENTRY_MODULE_FILENAMES = ("__main__.py", "menu.py")


def _module_level_imported_names(path: Path) -> set[str]:
    """Absolute names imported by MODULE-LEVEL statements in ``path``.

    Function and class bodies are never inspected: function-local imports
    are the sanctioned deferred-crossing mechanism (menu.py reaches
    ``whisker.llm.cli`` lazily) and must not trip this guard. Module-level
    compound statements (``try``/``if``/``with`` ...) still execute their
    bodies eagerly at import time, so the walk descends into them: the
    classic ``try: from whisker.llm.cli import main / except ImportError``
    optional-extra idiom is a module-level crossing, not a deferred one.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()

    def visit(node: ast.AST) -> None:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
            return
        if isinstance(node, ast.ImportFrom):
            if node.level:
                # Relative import from inside the whisker package.
                base = "whisker"
                if node.module:
                    names.add(f"{base}.{node.module}")
                else:
                    names.update(f"{base}.{alias.name}" for alias in node.names)
            else:
                module = node.module or ""
                names.add(module)
                # `from whisker import llm` crosses the lane just the same:
                # record the fully qualified alias, not only the bare package.
                names.update(f"{module}.{alias.name}" for alias in node.names)
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return  # nested scope: deferred imports live here
        for child in ast.iter_child_nodes(node):
            visit(child)

    for statement in tree.body:
        visit(statement)
    return names


class TestModuleLevelImportedNamesHelper:
    """Regression probes for the extraction helper itself: the entry-module
    guard is only as strong as its parser. Both positive spellings below
    were probe-verified to slip past the original ``tree.body``-only walk
    while the lane kept loading eagerly at startup."""

    @staticmethod
    def _names(tmp_path: Path, source: str) -> set[str]:
        probe = tmp_path / "probe.py"
        probe.write_text(source, encoding="utf-8")
        return _module_level_imported_names(probe)

    def test_try_except_nested_import_is_module_level(self, tmp_path):
        names = self._names(
            tmp_path,
            "try:\n"
            "    from whisker.llm.cli import main\n"
            "except ImportError:\n"
            "    main = None\n",
        )
        assert "whisker.llm.cli" in names

    def test_except_handler_body_import_is_module_level(self, tmp_path):
        names = self._names(
            tmp_path,
            "try:\n"
            "    import whisker\n"
            "except ImportError:\n"
            "    import whisker.llm\n",
        )
        assert "whisker.llm" in names

    def test_from_package_import_submodule_records_the_submodule(self, tmp_path):
        names = self._names(tmp_path, "from whisker import llm\n")
        assert "whisker.llm" in names

    def test_function_local_import_stays_invisible(self, tmp_path):
        names = self._names(
            tmp_path,
            "def main():\n"
            "    from whisker.llm.cli import main as cli_main\n"
            "    return cli_main\n",
        )
        assert not names


class TestEntryModulesNoModuleLevelLlmImport:
    """The entry modules may reach the advisory LLM lane only through
    deferred, function-local imports. A MODULE-LEVEL ``whisker.llm``
    import in either would make the deterministic core import the lane
    eagerly at startup, defeating the extras isolation the forbidden
    contracts exist to protect."""

    @pytest.mark.parametrize("filename", _ENTRY_MODULE_FILENAMES)
    def test_no_module_level_llm_import(self, filename):
        path = _whisker_package_dir() / filename
        names = _module_level_imported_names(path)
        crossings = sorted(
            name
            for name in names
            if name == "whisker.llm" or name.startswith("whisker.llm.")
        )
        assert not crossings, (
            f"whisker/{filename} imports {crossings} at module level; the "
            f"advisory LLM lane may only be reached through deferred "
            f"function-local imports"
        )
