#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Opaque owner identity.

The core is auth-agnostic: it knows only an opaque ``owner`` string (a user id in
production). Authentication and invitations live entirely in the host (the Django
site), never here. ``None`` means "unscoped" -- the local single-user mode, where
every session is visible.
"""

from __future__ import annotations

# An owner is an opaque principal id, or None for local single-user (unscoped).
Owner = str | None


def owner_matches(stored: Owner, requested: Owner) -> bool:
    """Authorization at the data layer.

    A ``requested`` of ``None`` (local single-user) matches any stored owner. A
    concrete owner matches only its own rows. Stores call this before returning a
    session so a scoped caller can never read another owner's data.
    """
    if requested is None:
        return True
    return stored == requested
