#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Contract tests for the StorageBackend ABC and the SourceAdapter Protocol."""

from __future__ import annotations

import inspect

import pytest

from herald.collection.sources import SourceAdapter
from herald.collection.storage import StorageBackend

EXPECTED_METHODS = {
    "add_source",
    "get_source",
    "get_source_by_uid",
    "list_sources",
    "update_source",
    "remove_source",
    "set_enabled",
    "set_source_state",
    "due_sources",
    "set_next_run_at",
    "record_sweep",
    "get_cursor",
    "set_cursor",
    "get_url",
    "get_content",
    "record_item",
    "emit_events",
    "read_events",
    "get_consumer_cursor",
    "set_consumer_cursor",
    "consumer_lag",
    "record_metric_snapshot",
    "latest_metric",
    "add_person_candidate",
    "find_person_handle",
    "find_name_variants",
    "export_table",
    "import_rows",
    "close",
}


def test_backend_is_not_instantiable() -> None:
    with pytest.raises(TypeError):
        StorageBackend()  # type: ignore[abstract]


def test_backend_exposes_full_surface() -> None:
    missing = EXPECTED_METHODS - set(dir(StorageBackend))
    assert not missing, f"missing methods: {missing}"


def test_every_surface_method_is_abstract() -> None:
    # Every contract method must be abstract so a partial backend cannot be instantiated.
    assert EXPECTED_METHODS <= StorageBackend.__abstractmethods__


def test_expected_methods_matches_abstract_set_exactly() -> None:
    # Self-maintaining: a new abstract method that is not added to EXPECTED_METHODS (or a
    # removed one) fails here, so the full-surface gate cannot silently go stale.
    assert set(StorageBackend.__abstractmethods__) == EXPECTED_METHODS


def test_record_item_commit_inputs_are_keyword_only() -> None:
    sig = inspect.signature(StorageBackend.record_item)
    params = [p for n, p in sig.parameters.items() if n != "self"]
    assert params, "record_item should take commit inputs"
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in params)


def test_list_sources_filters_are_keyword_only() -> None:
    sig = inspect.signature(StorageBackend.list_sources)
    params = [p for n, p in sig.parameters.items() if n != "self"]
    assert {"enabled", "role", "kind", "state", "parent_id"} <= {p.name for p in params}
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in params)


def test_complete_subclass_can_instantiate() -> None:
    # Proves the surface is implementable: a subclass that overrides every abstract method
    # (here with stubs) is concrete.
    namespace = {name: (lambda self, *a, **k: None) for name in StorageBackend.__abstractmethods__}
    concrete = type("StubBackend", (StorageBackend,), namespace)
    instance = concrete()  # must not raise
    assert isinstance(instance, StorageBackend)


def test_source_adapter_poll_window_is_keyword_only() -> None:
    sig = inspect.signature(SourceAdapter.poll)
    assert sig.parameters["window"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["cursor"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD


def test_source_adapter_is_runtime_checkable() -> None:
    class Dummy:
        kind = None

        def poll(self, cursor, *, window=None):  # pragma: no cover - shape only
            ...

    assert isinstance(Dummy(), SourceAdapter)
