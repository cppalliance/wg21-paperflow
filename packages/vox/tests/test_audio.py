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
import struct
import wave

from vox import pcm16_wav


def _decode_int16(data: bytes) -> list[int]:
    """Decode a mono 16-bit PCM WAV back to its little-endian int16 samples."""
    with wave.open(io.BytesIO(data), "rb") as wav:
        raw = wav.readframes(wav.getnframes())
    return list(struct.unpack("<" + "h" * (len(raw) // 2), raw))


def test_pcm16_wav_roundtrips_frames() -> None:
    data = pcm16_wav([0.0, 0.5, -0.5, 1.0, -1.0], sample_rate=8000)
    with wave.open(io.BytesIO(data), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 8000
        assert wav.getnframes() == 5
    # Decode the samples back: a wrong scale, endianness, or truncation would
    # corrupt these exact little-endian int16 values.
    assert _decode_int16(data) == [0, 16383, -16383, 32767, -32767]


def test_pcm16_wav_clamps_out_of_range() -> None:
    # Values beyond [-1, 1] must saturate at the int16 extremes, not overflow.
    data = pcm16_wav([5.0, -5.0], sample_rate=8000)
    with wave.open(io.BytesIO(data), "rb") as wav:
        assert wav.getnframes() == 2
    assert _decode_int16(data) == [32767, -32767]
