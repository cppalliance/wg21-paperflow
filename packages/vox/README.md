# vox

Reusable speech clients for spoken applications: a small `SttClient` / `TtsClient`
Protocol surface, pluggable provider adapters (Deepgram, Cartesia), offline
stubs, an `auto`/`stub`/named factory, and ephemeral browser-token minting for
browser-direct streaming STT.

`vox` has **no dependency on chatsmith** (or any application). Speech is not an LLM
concern, so it lives on its own and can be used by any package.

```python
from vox import VoxConfig, build_speech

stt, tts = build_speech(VoxConfig(tts_provider="stub", stt_provider="stub"))
result = tts.synthesize("hello")                 # -> TtsResult(audio=..., content_type=...)
text = stt.transcribe(result.audio, "audio/wav") # -> str
```

Install a provider extra to enable it, e.g. `uv sync --extra deepgram`. Without
the extra (or without a key), `build_speech` returns a stub so the app always runs.

Copyright (c) 2026 Will Pak (will@cppalliance.org). Distributed under the Boost
Software License, Version 1.0.
