#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

from __future__ import annotations

from chatsmith.identity import owner_matches


def test_unscoped_request_sees_every_owner() -> None:
    # requested=None is local single-user mode: it matches any stored owner,
    # including an unowned row.
    assert owner_matches("alice", None) is True
    assert owner_matches(None, None) is True


def test_scoped_request_matches_its_own_rows() -> None:
    assert owner_matches("alice", "alice") is True


def test_scoped_request_rejects_another_owner() -> None:
    # The core authorization guarantee: a scoped caller can never read another
    # owner's data.
    assert owner_matches("alice", "bob") is False


def test_scoped_request_rejects_unowned_row() -> None:
    # A concrete owner must not fall through to an unowned (None) row; only the
    # unscoped local mode may.
    assert owner_matches(None, "alice") is False
