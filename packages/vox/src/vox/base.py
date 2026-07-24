#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Protocols and shared types for the speech clients.

Adapters implement these Protocols so callers depend on behaviour, not on any
specific provider SDK.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class TtsResult:
    """Synthesized speech bytes and their content type."""

    audio: bytes
    content_type: str  # e.g. "audio/wav", "audio/mpeg"


@runtime_checkable
class SttClient(Protocol):
    """Transcribe one recorded utterance to text."""

    def transcribe(self, audio: bytes, content_type: str) -> str: ...


@runtime_checkable
class TtsClient(Protocol):
    """Synthesize one line of text to speech."""

    def synthesize(self, text: str) -> TtsResult: ...
