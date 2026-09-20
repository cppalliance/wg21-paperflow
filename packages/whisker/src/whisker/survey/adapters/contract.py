#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""The contract a competitor adapter must satisfy, and the loader that enforces it.

``CompetitorSpec.adapter`` names a module path. Resolving it here rather than
importing a specific adapter at each call site is what makes the registry real:
adding a competitor becomes writing a module and a lockfile, with no edits to the
survey CLI. An earlier revision imported ``adapters.marker`` directly in five
places and branched on ``spec.name == "marker"``, so the registry described a
generality the code did not have.

Validation checks that the required names exist, not that their signatures match.
A missing attribute is caught here with a message naming the module and the gap,
which is far easier to act on than an AttributeError raised an hour into a run.

See ``benchmark/protocol/ADDING-A-COMPETITOR.md`` for the full walkthrough.
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

__all__ = ["REQUIRED_ATTRS", "AdapterContractError", "load_adapter"]

# Every adapter must expose these. Kept as data so the error message, the test
# that guards the contract, and the guide cannot drift apart.
REQUIRED_ATTRS: tuple[str, ...] = (
    # dict[str, dict[str, Any]]: config name -> keyword arguments for convert().
    # The survey iterates these, so a competitor with one mode declares one entry.
    "MODES",
    # install(root: Path, lock: dict) -> None. Idempotent and resumable: it is
    # called again on self-repair, so it must tolerate a half-built tree.
    "install",
    # convert(pdf_path, out_dir, pid, *, env_overrides, venv_dir, **mode) -> int.
    # Returns a process exit code; non-zero must still leave artifacts for
    # diagnosis rather than cleaning up after itself.
    "convert",
    # installed_version(venv_dir: Path) -> str | None. None when absent.
    "installed_version",
    # latest_upstream_version() -> str | None. None when the network is
    # unavailable; this must never raise, because status has to work offline.
    "latest_upstream_version",
    # verify_patches(venv_dir: Path, lock: dict) -> list[str] of failures.
    # An empty list means every locked patch is present and current.
    "verify_patches",
)


class AdapterContractError(RuntimeError):
    """An adapter module is missing part of the required interface."""


def load_adapter(module_path: str) -> ModuleType:
    """Import an adapter module and verify it satisfies the contract.

    Raises ``AdapterContractError`` on a missing attribute, and lets ImportError
    through unchanged so a typo in the registry is not disguised as a contract
    violation.
    """
    module = import_module(module_path)

    missing = [name for name in REQUIRED_ATTRS if not hasattr(module, name)]
    if missing:
        raise AdapterContractError(
            f"adapter {module_path} is missing: {', '.join(missing)}. "
            f"Required: {', '.join(REQUIRED_ATTRS)}. "
            "See benchmark/protocol/ADDING-A-COMPETITOR.md"
        )
    return module
