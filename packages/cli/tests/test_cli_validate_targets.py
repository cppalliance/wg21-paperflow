#
# Copyright (c) 2026 Henry Wang (henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Unit tests for ``cli.__main__._validate_targets``."""

from __future__ import annotations

from cli.__main__ import _validate_targets


def test_assay_accepts_paper_id():
    _validate_targets("assay", ["P4003R2"])
