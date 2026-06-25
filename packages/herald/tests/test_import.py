#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Import smoke tests - cheap, no network, run on every OS in CI."""

from __future__ import annotations

import importlib
import subprocess
import sys

import pytest

COLLECTION_SUBPACKAGES = [
    "storage",
    "events",
    "change",
    "normalize",
    "fetch",
    "extract",
    "dedup",
    "sources",
    "persons",
    "schedule",
    "registry",
    "obs",
]


def test_import_herald_has_version() -> None:
    import herald

    assert isinstance(herald.__version__, str)
    assert herald.__version__


def test_collection_imports() -> None:
    import herald.collection
    import herald.collection.orchestrator  # noqa: F401

    assert herald.collection.HeraldError is not None


@pytest.mark.parametrize("name", COLLECTION_SUBPACKAGES)
def test_collection_subpackage_imports(name: str) -> None:
    mod = importlib.import_module(f"herald.collection.{name}")
    assert mod is not None


def test_cli_no_args_returns_zero() -> None:
    from herald.__main__ import main

    assert main([]) == 0


def test_cli_version_exits_zero() -> None:
    from herald.__main__ import main

    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0


def test_import_pulls_no_heavy_deps() -> None:
    # In a clean interpreter, importing the package (and its light vocabulary) must not
    # drag in heavy optional transports/extractors. Run isolated to avoid pollution from
    # other tests in the session.
    code = (
        "import sys; import herald, herald.collection, herald.collection.records, "
        "herald.collection.enums, herald.collection.storage; "
        "heavy = {'aiohttp', 'trafilatura', 'feedparser', 'pydantic', 'tldextract', "
        "'protego', 'stamina', 'structlog', 'zstandard'}; "
        "leaked = heavy & set(sys.modules); "
        "assert not leaked, leaked"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
