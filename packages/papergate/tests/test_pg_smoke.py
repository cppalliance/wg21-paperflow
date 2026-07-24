#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Smoke test: the package imports and exposes a version."""

from __future__ import annotations


def test_package_imports() -> None:
    import papergate

    assert papergate.__version__
