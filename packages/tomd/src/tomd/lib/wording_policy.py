#
# Copyright (c) 2026 Luan Fonseca (luan@lincolnloop.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Shared wording-emit/cleanup policy.

The PDF emitter (``lib/pdf/emit.py`` and its ``lib/pdf/wording_emit.py``
helpers) and the post-render cleanup pass (``lib/wording_cleanup.py``)
make two decisions against the same contract:

- the **uniform-role threshold**: at or above this fraction of role-bearing
  characters, a directional wording div is "uniform" enough that the
  inline ``<ins>`` / ``<del>`` tags are redundant with the div itself, and
- the **implicit role** carried by each directional div class.

These two values are the single boundary the two stages must agree on. If
they drift apart, emit can promote a section while cleanup leaves the tags
(or vice versa). Keeping them here makes that contract explicit and shared.

Emit-only knobs (monospace dominance, code-promotion minimum lines,
maximum reconstructed indent) intentionally do NOT live here: they depend
on span-level structure the assembled Markdown has already collapsed, so
cleanup can never use them.
"""

from __future__ import annotations

# At or above this fraction of role-bearing visible characters, a
# directional wording div is uniform and its inline role tags are
# redundant with the div-level signal.
UNIFORM_ROLE_THRESHOLD = 0.95

_IMPLICIT_ROLE = {
    "wording-add": "ins",
    "wording-remove": "del",
    "wording": None,
}


def implicit_role_for(div_class: str) -> str | None:
    """Return the inline role implied by a wording div class.

    ``wording-add`` implies ``ins``, ``wording-remove`` implies ``del``,
    and the neutral ``wording`` div implies no role (it exists exactly to
    carry mixed diffs). Unknown classes return ``None``.
    """
    return _IMPLICIT_ROLE.get(div_class)
