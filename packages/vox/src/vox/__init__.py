#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""vox: reusable speech (STT/TTS) clients with pluggable providers and stubs."""

from __future__ import annotations

from vox.audio import pcm16_wav
from vox.base import SttClient, TtsClient, TtsResult
from vox.config import VoxConfig
from vox.factory import build_speech, build_stt, build_tts
from vox.stubs import StubStt, StubTts
from vox.token import DeepgramTokenError, build_grant_request, grant_token

__version__ = "0.1.0"

__all__ = [
    "DeepgramTokenError",
    "SttClient",
    "StubStt",
    "StubTts",
    "TtsClient",
    "TtsResult",
    "VoxConfig",
    "__version__",
    "build_grant_request",
    "build_speech",
    "build_stt",
    "build_tts",
    "grant_token",
    "pcm16_wav",
]
