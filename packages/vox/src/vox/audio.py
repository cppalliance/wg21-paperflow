#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Shared audio helpers for the speech adapters."""

from __future__ import annotations

import io
import struct
import wave
from collections.abc import Iterable


def pcm16_wav(samples: Iterable[float], sample_rate: int) -> bytes:
    """Encode float samples in [-1, 1] as a mono 16-bit PCM WAV."""
    if sample_rate <= 0:
        raise ValueError(f"sample_rate must be positive, got {sample_rate}")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        frames = bytearray()
        for value in samples:
            clamped = max(-1.0, min(1.0, value))
            frames += struct.pack("<h", int(clamped * 32767))
        wav.writeframes(bytes(frames))
    return buffer.getvalue()
