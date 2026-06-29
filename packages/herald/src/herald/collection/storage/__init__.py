#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Storage: the `StorageBackend` ABC plus (later) the SQLite backend and blob store.

The ABC is ORM-agnostic so the same contract serves the SQLite dev/test backend and a
Postgres/Django backend in production.
"""

from __future__ import annotations

from herald.collection.storage.backend import UNSET, ConflictStrategy, StorageBackend, TableName

__all__ = ["StorageBackend", "UNSET", "TableName", "ConflictStrategy"]
