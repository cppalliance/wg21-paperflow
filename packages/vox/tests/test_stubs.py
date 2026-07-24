#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

from __future__ import annotations

from vox import StubStt, StubTts, TtsResult


def test_stub_tts_returns_playable_wav() -> None:
    result = StubTts().synthesize("hello there friend")
    assert isinstance(result, TtsResult)
    assert result.content_type == "audio/wav"
    # A RIFF/WAVE header and non-trivial body.
    assert result.audio[:4] == b"RIFF"
    assert result.audio[8:12] == b"WAVE"
    assert len(result.audio) > 44


def test_stub_tts_longer_text_is_longer_audio() -> None:
    short = StubTts().synthesize("hi")
    long = StubTts().synthesize("hi " * 40)
    assert len(long.audio) > len(short.audio)


def test_stub_stt_is_deterministic_text() -> None:
    # The stub returns one fixed line regardless of input, so the offline loop and
    # the showcase stay reproducible; assert the exact text and its input-independence.
    stub = StubStt()
    out = stub.transcribe(b"\x00\x01", "audio/wav")
    assert out == (
        "This is a stub transcription. Configure a speech-to-text provider "
        "(e.g. Deepgram) for real audio, or type your reply instead."
    )
    assert stub.transcribe(b"\xff\xfe\xfd", "audio/wav") == out
