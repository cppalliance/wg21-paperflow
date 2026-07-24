#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Build the speech clients from a :class:`VoxConfig`.

Each provider auto-downgrades to a stub when its key is missing or its extra is
not installed, so the app always starts. Explicit provider names force a choice;
an unrecognized name is logged and falls back to the stub.
"""

from __future__ import annotations

import logging

from .base import SttClient, TtsClient
from .config import VoxConfig
from .stubs import StubStt, StubTts

log = logging.getLogger(__name__)

_STT_PROVIDERS = ("auto", "stub", "deepgram")
_TTS_PROVIDERS = ("auto", "stub", "cartesia")


def build_speech(config: VoxConfig) -> tuple[SttClient, TtsClient]:
    """Build both clients at once: ``(stt, tts)``."""
    return build_stt(config), build_tts(config)


def build_stt(config: VoxConfig) -> SttClient:
    provider = config.stt_provider
    if provider not in _STT_PROVIDERS:
        log.warning("Unknown stt_provider %r; using stub", provider)
        return StubStt()
    if provider == "deepgram" or (provider == "auto" and config.deepgram_api_key):
        try:
            from .stt.deepgram import DeepgramStt

            return DeepgramStt(
                config.deepgram_api_key,
                config.deepgram_model,
                config.keyterms,
                keyterm_limit=config.keyterm_limit,
            )
        except Exception as exc:  # noqa: BLE001  missing extra/key or bad config; degrade to stub
            log.warning("Deepgram STT unavailable (%s); using stub", exc)
    return StubStt()


def build_tts(config: VoxConfig) -> TtsClient:
    provider = config.tts_provider
    if provider not in _TTS_PROVIDERS:
        log.warning("Unknown tts_provider %r; using stub", provider)
        return StubTts()
    if provider == "stub":
        return StubTts()

    auto = provider == "auto"
    if provider == "cartesia" or (auto and config.cartesia_api_key):
        client = _try_cartesia(config)
        if client is not None:
            return client
    return StubTts()


def _try_cartesia(config: VoxConfig) -> TtsClient | None:
    try:
        from .tts.cartesia import CartesiaTts

        return CartesiaTts(config.cartesia_api_key, config.cartesia_voice_id, config.cartesia_model)
    except Exception as exc:  # noqa: BLE001  missing extra/key or bad config; degrade to stub
        log.warning("Cartesia TTS unavailable (%s)", exc)
        return None
