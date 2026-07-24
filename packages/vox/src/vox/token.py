#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Deepgram ephemeral-token grant (stdlib only, no SDK).

A browser that opens Deepgram's live STT WebSocket directly needs a short-lived
token, so the long-lived API key never leaves the server. This POSTs the raw key
to Deepgram's ``/v1/auth/grant`` endpoint and returns the grant it hands back.

Kept dependency-free (``urllib``, not the Deepgram SDK) and injectable: request
building is factored out and ``urlopen`` can be swapped, so it unit-tests with no
network.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

GRANT_TOKEN_URL = "https://api.deepgram.com/v1/auth/grant"

# Fallback TTL (seconds) when a caller does not specify one.
_DEFAULT_TTL_SECONDS = 60


class DeepgramTokenError(RuntimeError):
    """Raised when the grant-token endpoint returns a non-200 response."""


def build_grant_request(
    api_key: str, ttl_seconds: int = _DEFAULT_TTL_SECONDS
) -> urllib.request.Request:
    """Build the signed POST request for an ephemeral token. Pure, no network."""
    body = json.dumps({"ttl_seconds": ttl_seconds}).encode("utf-8")
    return urllib.request.Request(
        GRANT_TOKEN_URL,
        data=body,
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )


def grant_token(
    api_key: str,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    *,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    """Grant a short-lived Deepgram token; return the parsed JSON grant.

    ``urlopen`` is injectable so tests can supply a fake response without a
    network. Every failure mode -- HTTP error, unreachable host, timeout, or a
    malformed body -- is normalized to :class:`DeepgramTokenError`.
    """
    request = build_grant_request(api_key, ttl_seconds)
    try:
        with urlopen(request, timeout=10) as response:
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            payload = response.read()
    except urllib.error.HTTPError as exc:  # non-2xx status raises here by default
        detail = exc.read().decode("utf-8", "replace")
        raise DeepgramTokenError(f"Deepgram grant-token failed ({exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:  # DNS, refused, or timeout
        raise DeepgramTokenError(f"Deepgram grant-token unreachable: {exc}") from exc
    if status != 200:
        raise DeepgramTokenError(f"Deepgram grant-token failed ({status})")
    try:
        grant = json.loads(payload)
    except ValueError as exc:  # 200 with a body that is not JSON
        raise DeepgramTokenError("Deepgram grant-token returned a non-JSON body") from exc
    if not isinstance(grant, dict):
        raise DeepgramTokenError("Deepgram grant-token returned an unexpected JSON shape")
    return grant
