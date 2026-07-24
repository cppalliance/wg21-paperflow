#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Zero-dependency stub adapters.

They let the whole loop run with no API keys and no network, which is what the
offline tests and the first-run showcase use. ``StubTts`` generates a short
pulsing tone so a visible avatar's mouth still moves.
"""

from __future__ import annotations

import math
from collections.abc import Iterator

from .audio import pcm16_wav
from .base import TtsResult


class StubStt:
    """Returns a fixed line; a text input box is the real no-key input path."""

    def transcribe(self, audio: bytes, content_type: str) -> str:
        return (
            "This is a stub transcription. Configure a speech-to-text provider "
            "(e.g. Deepgram) for real audio, or type your reply instead."
        )


class StubTts:
    """Generate a short pulsing tone (audio/wav) sized to the text length."""

    def __init__(self, sample_rate: int = 16000) -> None:
        self._sample_rate = sample_rate

    def synthesize(self, text: str) -> TtsResult:
        samples = _tone_samples(text, self._sample_rate)
        return TtsResult(audio=pcm16_wav(samples, self._sample_rate), content_type="audio/wav")


def _tone_samples(text: str, sample_rate: int) -> Iterator[float]:
    words = [w for w in text.split() if w] or ["..."]
    seconds = min(max(len(words) * 0.22, 0.6), 8.0)
    frame_count = int(seconds * sample_rate)
    carrier_hz = 180.0
    syllable_hz = 4.5  # mouth opens ~4-5 times a second
    for i in range(frame_count):
        t = i / sample_rate
        envelope = (0.5 * (1.0 + math.sin(2.0 * math.pi * syllable_hz * t))) ** 2
        yield 0.18 * envelope * math.sin(2.0 * math.pi * carrier_hz * t)
