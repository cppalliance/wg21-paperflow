#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Typed exception hierarchy for the collection layer.

Callers catch a specific subclass to distinguish stages (a missing blob is not a bad
source config is not an auth failure). All inherit :class:`HeraldError`, which the CLI
maps to ``error: ...`` on stderr with a non-zero exit code.
"""

from __future__ import annotations


class HeraldError(Exception):
    """Base class for all Herald collection-layer errors."""


class StorageError(HeraldError):
    """A storage-backend operation failed."""


class BlobNotFoundError(StorageError):
    """A content-addressed blob was requested but is absent from the blob store."""


class UnknownSourceError(StorageError):
    """A source id or uid was referenced that does not exist in the registry."""


class SourceConfigError(HeraldError):
    """A source's ``config_json`` is invalid for its kind."""


class CredentialError(HeraldError):
    """A credential reference could not be resolved (missing env var / secret)."""


class FetchError(HeraldError):
    """A fetch failed in a way the caller may want to classify."""


class RobotsDisallowedError(FetchError):
    """robots.txt disallows fetching the URL."""


class EdgeBlockError(FetchError):
    """An edge provider blocked the request (e.g. an AI-crawler 402/403)."""


class AuthRequiredError(FetchError):
    """The source requires authentication that is missing or rejected."""


class AdapterError(HeraldError):
    """A source adapter failed while polling."""


class FeasibilityError(AdapterError):
    """A runtime feasibility probe determined a source cannot be collected as configured."""


__all__ = [
    "HeraldError",
    "StorageError",
    "BlobNotFoundError",
    "UnknownSourceError",
    "SourceConfigError",
    "CredentialError",
    "FetchError",
    "RobotsDisallowedError",
    "EdgeBlockError",
    "AuthRequiredError",
    "AdapterError",
    "FeasibilityError",
]
