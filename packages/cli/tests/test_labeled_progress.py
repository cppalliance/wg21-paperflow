#
# Copyright (c) 2026 Leo Chen (leo.chen0412@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Unit tests for ``cli.jobs._labeled_progress``."""

from __future__ import annotations

from cli.jobs import _labeled_progress
from paperstore.progress import ProgressEvent


def _ev(name: str) -> ProgressEvent:
    return ProgressEvent(step=1, total=5, name=name, pct=20.0)


def test_labeled_progress_prefixes_name():
    events: list[ProgressEvent] = []
    handler = _labeled_progress("Mailing", events.append)
    assert handler is not None
    handler(_ev("fetch"))
    assert events[0].name == "Mailing fetch"


def test_labeled_progress_done_renames_to_label():
    events: list[ProgressEvent] = []
    handler = _labeled_progress("Mailing", events.append)
    assert handler is not None
    handler(_ev("done"))
    assert events[0].name == "Mailing"


def test_labeled_progress_idempotent_prefix():
    events: list[ProgressEvent] = []
    handler = _labeled_progress("Mailing", events.append)
    assert handler is not None
    handler(_ev("Mailing fetch"))
    assert events[0].name == "Mailing fetch"


def test_labeled_progress_null_callback_returns_none():
    assert _labeled_progress("Mailing", None) is None
