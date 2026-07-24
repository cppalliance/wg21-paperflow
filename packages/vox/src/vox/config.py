#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Provider-selection config for the speech factory.

A plain value object injected into :func:`vox.factory.build_speech`. It is
deliberately application-agnostic: keyterms are supplied by the caller (e.g. a
chatsmith domain pack), not hardcoded here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VoxConfig:
    """All knobs for the STT/TTS clients. Blank keys select the stub adapter."""

    # Speech-to-text
    stt_provider: str = "auto"  # auto | stub | deepgram
    deepgram_api_key: str = ""
    deepgram_model: str = "nova-3"
    # Caller-supplied recognition keyterms (e.g. a domain glossary) and the
    # provider cap applied to them. vox stays domain-neutral.
    keyterms: list[str] = field(default_factory=list)
    keyterm_limit: int = 100

    # Text-to-speech
    tts_provider: str = "auto"  # auto | stub | cartesia
    cartesia_api_key: str = ""
    cartesia_voice_id: str = ""
    cartesia_model: str = "sonic-3"
