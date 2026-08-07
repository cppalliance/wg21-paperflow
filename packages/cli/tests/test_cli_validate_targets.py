#
# Copyright (c) 2026 Henry Wang (henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Unit tests for ``cli.__main__._validate_targets``."""

from __future__ import annotations

import pytest

from cli.__main__ import _validate_targets


def test_assay_accepts_paper_id():
    _validate_targets("assay", ["P4003R2"])


def test_assay_rejects_bare_year():
    with pytest.raises(SystemExit) as exc_info:
        _validate_targets("assay", ["2026"])
    assert exc_info.value.code == 1


def test_assay_rejects_year_month():
    with pytest.raises(SystemExit) as exc_info:
        _validate_targets("assay", ["2026-01"])
    assert exc_info.value.code == 1


def test_agora_rejects_bare_year():
    with pytest.raises(SystemExit) as exc_info:
        _validate_targets("agora", ["2026"])
    assert exc_info.value.code == 1
