#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Events: `collection_events` outbox builders and the cursor-driven consumer loop.

Delivery is at-least-once (replay-from-cursor), so every consumer must be idempotent.
"""

from __future__ import annotations

__all__: list[str] = []
