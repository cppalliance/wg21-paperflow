"""
Distributed under the Boost Software License, Version 1.0. (See accompanying

file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

Official repository: https://github.com/cppalliance/wg21-paperflow
"""

import ast
from pathlib import Path

import pytest

import tomd.domain
from tomd.domain.front_matter import FRONT_MATTER_ORDER, is_blank_value

_DOMAIN_DIR = Path(tomd.domain.__file__).parent


def test_front_matter_order_is_the_contract():
    assert FRONT_MATTER_ORDER == ("title", "document", "date", "intent", "audience", "reply-to")


@pytest.mark.parametrize("value", [None, "", "   ", "\t\n", [], (), ["", "  "]])
def test_is_blank_value_blank(value):
    assert is_blank_value(value)


@pytest.mark.parametrize("value", ["x", " x ", ["", "a"], ("a",), 0])
def test_is_blank_value_not_blank(value):
    assert not is_blank_value(value)


def _imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize("path", sorted(_DOMAIN_DIR.glob("*.py")), ids=lambda p: p.name)
def test_domain_imports_nothing_outside_the_domain(path):
    outside = {m for m in _imported_modules(path) if m.startswith("tomd.") and not m.startswith("tomd.domain")}
    assert outside == set()
