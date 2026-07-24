#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

from __future__ import annotations

from vox import StubStt, StubTts, VoxConfig, build_speech, build_stt, build_tts


def test_defaults_downgrade_to_stubs_without_keys() -> None:
    stt, tts = build_speech(VoxConfig())
    assert isinstance(stt, StubStt)
    assert isinstance(tts, StubTts)


def test_unknown_provider_falls_back_to_stub() -> None:
    assert isinstance(build_stt(VoxConfig(stt_provider="nope")), StubStt)
    assert isinstance(build_tts(VoxConfig(tts_provider="nope")), StubTts)


def test_explicit_stub_tts() -> None:
    assert isinstance(build_tts(VoxConfig(tts_provider="stub")), StubTts)


def test_deepgram_without_extra_falls_back_to_stub() -> None:
    # `deepgram` extra is not installed in the default test env, so even with a
    # key the factory must degrade to the stub rather than raise.
    stt = build_stt(VoxConfig(stt_provider="deepgram", deepgram_api_key="x"))
    assert isinstance(stt, StubStt)


def test_cartesia_without_extra_falls_back_to_stub() -> None:
    # Symmetric to the Deepgram case: the `cartesia` extra is absent, so even with
    # a key build_tts must degrade to the stub rather than raise ("always degrade").
    tts = build_tts(VoxConfig(tts_provider="cartesia", cartesia_api_key="x"))
    assert isinstance(tts, StubTts)
