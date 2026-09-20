#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Tests for the competitor adapter contract and its resolution.

The point of these is cheapness. An adapter defect that surfaces here costs a
second; the same defect surfacing inside ``survey run`` costs however long the
install and conversions took to get there.
"""

import inspect
import sys
import types

import pytest
from whisker.survey import registry
from whisker.survey.adapters import (
    REQUIRED_ATTRS,
    AdapterContractError,
    load_adapter,
)


def _stub_module(name: str, attrs: tuple[str, ...]) -> str:
    """Register a throwaway module exposing *attrs*, and return its import path."""
    module = types.ModuleType(name)
    for attr in attrs:
        setattr(module, attr, {} if attr == "MODES" else (lambda *a, **k: None))
    sys.modules[name] = module
    return name


class TestContractEnforcement:
    """load_adapter must reject an incomplete adapter before anything runs."""

    def test_complete_adapter_loads(self):
        path = _stub_module("_whisker_test_complete_adapter", REQUIRED_ATTRS)
        assert load_adapter(path) is sys.modules[path]

    def test_missing_attribute_is_rejected(self):
        partial = tuple(a for a in REQUIRED_ATTRS if a != "convert")
        path = _stub_module("_whisker_test_partial_adapter", partial)
        with pytest.raises(AdapterContractError, match="convert"):
            load_adapter(path)

    def test_error_names_the_module_and_the_guide(self):
        path = _stub_module("_whisker_test_named_adapter", ())
        with pytest.raises(AdapterContractError) as excinfo:
            load_adapter(path)
        message = str(excinfo.value)
        assert path in message
        assert "ADDING-A-COMPETITOR.md" in message

    def test_import_error_is_not_disguised(self):
        # A typo in the registry is an ImportError, not a contract violation:
        # conflating them sends the reader looking for a missing function.
        with pytest.raises(ImportError):
            load_adapter("whisker.survey.adapters._does_not_exist")


class TestRegisteredAdapters:
    """Every adapter in the registry must satisfy the contract as shipped."""

    @pytest.mark.parametrize(
        "spec",
        registry.list_competitors(),
        ids=[s.name for s in registry.list_competitors()],
    )
    def test_registered_adapter_satisfies_contract(self, spec):
        adapter = load_adapter(spec.adapter)
        for attr in REQUIRED_ATTRS:
            assert hasattr(adapter, attr), f"{spec.name} lacks {attr}"

    @pytest.mark.parametrize(
        "spec",
        registry.list_competitors(),
        ids=[s.name for s in registry.list_competitors()],
    )
    def test_modes_map_to_convert_keywords(self, spec):
        """Every MODES entry must be accepted by that adapter's convert().

        The survey calls ``convert(..., **mode_cfg)``, so a stray key here is a
        TypeError raised only once the runtime is built and a conversion starts.
        """
        adapter = load_adapter(spec.adapter)
        assert adapter.MODES, f"{spec.name} declares no modes"

        params = inspect.signature(adapter.convert).parameters
        accepts_kwargs = any(
            p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()
        )
        for mode_name, mode_cfg in adapter.MODES.items():
            assert isinstance(mode_cfg, dict), f"{spec.name}/{mode_name} is not a dict"
            if accepts_kwargs:
                continue
            for key in mode_cfg:
                assert key in params, (
                    f"{spec.name}/{mode_name}: convert() has no parameter {key!r}"
                )

    @pytest.mark.parametrize(
        "spec",
        registry.list_competitors(),
        ids=[s.name for s in registry.list_competitors()],
    )
    def test_pinned_version_matches_lockfile(self, spec):
        """The pin is the lockfile's, so the two cannot drift apart."""
        lock = registry.load_lockfile(spec)
        assert spec.pinned_version in lock.values()

    @pytest.mark.parametrize(
        "spec",
        registry.list_competitors(),
        ids=[s.name for s in registry.list_competitors()],
    )
    def test_every_patch_states_a_retirement_condition(self, spec):
        """A patch without a retire_when becomes permanent by default."""
        for patch in spec.patches:
            assert patch.retire_when.strip(), f"{spec.name}/{patch.id}"
            assert patch.upstream_issue.strip(), f"{spec.name}/{patch.id}"
