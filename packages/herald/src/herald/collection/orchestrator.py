#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Orchestrator: `run_sweep`, the composition point for the nine-component pipeline.

Not implemented in this PR. `run_sweep` is where a `SourceAdapter` is polled and each
`Candidate` flows through route -> normalize -> fetch -> change-detect -> extract -> dedup
-> observe -> commit, with the durable commit (and event emission) happening via
`StorageBackend.record_item`. The signature is reserved here so later milestones add the
body without moving the seam.
"""

from __future__ import annotations


def run_sweep(*args: object, **kwargs: object) -> object:  # pragma: no cover - later milestone
    """Run one sweep of a source. Implemented in a later milestone."""
    raise NotImplementedError("run_sweep lands with the orchestrator milestone")


__all__ = ["run_sweep"]
