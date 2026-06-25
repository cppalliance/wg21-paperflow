#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Sources: the `SourceAdapter` Protocol seam and (later) concrete adapters.

Adapters yield a `Candidate` (`Discovered` | `Fetched`); they never touch storage or emit
events. Concrete transports are lazy-imported.
"""

from __future__ import annotations

from herald.collection.sources.base import PolledItem, SourceAdapter

__all__ = ["PolledItem", "SourceAdapter"]
