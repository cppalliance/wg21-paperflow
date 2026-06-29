#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Herald - C++ ecosystem ingestion + generation pipeline.

Each layer (collection, intelligence, writer, editorial) is a subpackage under ``herald.``;
only :mod:`herald.collection` is built today. This top-level namespace is deliberately cheap
to import.
"""

from __future__ import annotations

__version__ = "0.4.1"

__all__ = ["__version__"]
