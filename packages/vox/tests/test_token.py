#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

from __future__ import annotations

import io
import json
import urllib.error

import pytest
from vox import DeepgramTokenError, build_grant_request, grant_token
from vox.token import GRANT_TOKEN_URL


def test_build_grant_request_signs_and_targets_endpoint() -> None:
    req = build_grant_request("secret-key", ttl_seconds=45)
    assert req.full_url == GRANT_TOKEN_URL
    assert req.get_method() == "POST"
    assert req.headers["Authorization"] == "Token secret-key"
    assert json.loads(req.data) == {"ttl_seconds": 45}


class _FakeResponse:
    def __init__(self, payload: bytes, status: int = 200) -> None:
        self._payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._payload


def test_grant_token_parses_success() -> None:
    grant = {"access_token": "tok", "expires_in": 60}

    def fake_urlopen(request, timeout=10):
        return _FakeResponse(json.dumps(grant).encode())

    assert grant_token("k", urlopen=fake_urlopen) == grant


def test_grant_token_non_json_raises() -> None:
    def fake_urlopen(request, timeout=10):
        return _FakeResponse(b"not json")

    with pytest.raises(DeepgramTokenError):
        grant_token("k", urlopen=fake_urlopen)


def test_grant_token_http_error_is_normalized() -> None:
    # A 401 (bad key) raises HTTPError inside urlopen; the module promises to
    # surface it as a DeepgramTokenError carrying the status, not a raw urllib error.
    def fake_urlopen(request, timeout=10):
        raise urllib.error.HTTPError(
            GRANT_TOKEN_URL, 401, "Unauthorized", {}, io.BytesIO(b"bad key")
        )

    with pytest.raises(DeepgramTokenError, match="401"):
        grant_token("k", urlopen=fake_urlopen)


def test_grant_token_unreachable_is_normalized() -> None:
    # DNS failure / connection refused / timeout all normalize to DeepgramTokenError.
    def refused(request, timeout=10):
        raise urllib.error.URLError("connection refused")

    def timed_out(request, timeout=10):
        raise TimeoutError("timed out")

    with pytest.raises(DeepgramTokenError):
        grant_token("k", urlopen=refused)
    with pytest.raises(DeepgramTokenError):
        grant_token("k", urlopen=timed_out)


def test_grant_token_rejects_incomplete_grant() -> None:
    # A 200 can still carry an empty or error-shaped object; a grant missing its
    # documented fields must fail rather than return a token a caller cannot use.
    for body in (b"{}", b'{"access_token": "tok"}', b'{"expires_in": 60}', b'{"error": "nope"}'):

        def fake_urlopen(request, timeout=10, _body=body):
            return _FakeResponse(_body)

        with pytest.raises(DeepgramTokenError):
            grant_token("k", urlopen=fake_urlopen)


def test_grant_token_non_200_status_raises() -> None:
    # A response that returns without raising but reports a non-200 status still fails.
    def fake_urlopen(request, timeout=10):
        return _FakeResponse(b"{}", status=500)

    with pytest.raises(DeepgramTokenError, match="500"):
        grant_token("k", urlopen=fake_urlopen)
