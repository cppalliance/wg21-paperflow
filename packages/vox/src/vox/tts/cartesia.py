#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Cartesia Sonic text-to-speech (WAV bytes). Requires the ``cartesia`` extra."""

from __future__ import annotations

from ..base import TtsResult

_OUTPUT_FORMAT = {
    "container": "wav",
    "encoding": "pcm_s16le",
    "sample_rate": 44100,
}


class CartesiaTts:
    def __init__(self, api_key: str, voice_id: str, model: str = "sonic-3"):
        from cartesia import Cartesia  # pyright: ignore[reportMissingImports]

        if not voice_id:
            raise ValueError("cartesia_voice_id is required for Cartesia TTS")
        self._client = Cartesia(api_key=api_key)
        self._voice_id = voice_id
        self._model = model

    def synthesize(self, text: str) -> TtsResult:
        chunks = self._client.tts.bytes(
            model_id=self._model,
            transcript=text,
            voice={"mode": "id", "id": self._voice_id},
            output_format=_OUTPUT_FORMAT,
        )
        audio = chunks if isinstance(chunks, bytes) else b"".join(chunks)
        return TtsResult(audio=audio, content_type="audio/wav")
