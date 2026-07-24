#
# Copyright (c) 2026 Will Pak (will@cppalliance.org)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
# Official repository: https://github.com/cppalliance/wg21-paperflow
#

"""Tiny smoke CLI so vox is verifiably usable on its own.

  vox say "hello there" out.wav      synthesize text to a WAV file
  vox transcribe clip.wav            transcribe an audio file to stdout

Uses the stub providers unless the relevant env keys/extras are configured, so
it runs offline out of the box.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .config import VoxConfig
from .factory import build_stt, build_tts


def _config_from_env() -> VoxConfig:
    env = os.environ
    return VoxConfig(
        stt_provider=(env.get("STT_PROVIDER") or "auto").strip(),
        deepgram_api_key=(env.get("DEEPGRAM_API_KEY") or "").strip(),
        deepgram_model=(env.get("DEEPGRAM_MODEL") or "nova-3").strip(),
        tts_provider=(env.get("TTS_PROVIDER") or "auto").strip(),
        cartesia_api_key=(env.get("CARTESIA_API_KEY") or "").strip(),
        cartesia_voice_id=(env.get("CARTESIA_VOICE_ID") or "").strip(),
        cartesia_model=(env.get("CARTESIA_MODEL") or "sonic-3").strip(),
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    command, rest = args[0], args[1:]
    config = _config_from_env()

    if command == "say":
        if not rest:
            print("usage: vox say TEXT [OUT.wav]", file=sys.stderr)
            return 2
        text = rest[0]
        out = Path(rest[1]) if len(rest) > 1 else Path("vox-out.wav")
        result = build_tts(config).synthesize(text)
        out.write_bytes(result.audio)
        print(f"wrote {len(result.audio)} bytes ({result.content_type}) -> {out}")
        return 0

    if command == "transcribe":
        if not rest:
            print("usage: vox transcribe CLIP.wav", file=sys.stderr)
            return 2
        clip = Path(rest[0])
        audio = clip.read_bytes()
        text = build_stt(config).transcribe(audio, "audio/wav")
        print(text)
        return 0

    print(f"unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
