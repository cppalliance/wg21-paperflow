#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Herald - C++ ecosystem ingestion + generation pipeline.

This top-level package is a thin namespace. The first implemented layer is the
collection layer under :mod:`herald.collection`; future layers (intelligence, writer,
editorial) are added as sibling subpackages. Importing :mod:`herald` is deliberately
cheap - no heavy optional dependencies are pulled in at import time.
"""

from __future__ import annotations

__version__ = "0.4.1"

__all__ = ["__version__"]
