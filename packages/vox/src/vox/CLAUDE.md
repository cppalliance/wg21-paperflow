# vox - Agent Rules

## What this is

A reusable speech package: speech-to-text (STT) and text-to-speech (TTS) clients
with pluggable providers and offline stubs. vox has **no first-party
dependencies** (it never imports chatsmith or any other package), so any package
in the workspace can depend on it on its own.

The core is stdlib-only. Each provider is an optional extra; without the extra
(or its API key) the matching adapter is unavailable and the caller transparently
falls back to a stub, so the app always starts, offline, with no keys.

## Module layout

- `base.py` - the `SttClient` / `TtsClient` `Protocol`s and the `TtsResult`
  dataclass. Adapters implement these Protocols, so callers depend on behaviour,
  never on a specific provider SDK.
- `config.py` - `VoxConfig`, a plain value object (provider names, API keys,
  model ids, keyterms). Built by the caller and injected; vox never reads the
  environment itself (except the `vox` smoke CLI in `__main__.py`).
- `factory.py` - `build_speech` / `build_stt` / `build_tts`: provider selection
  with stub fallback. `auto` uses a provider when its key is set, else the stub;
  an explicit name forces it; an unknown name is logged and downgrades to a stub.
- `stubs.py` - `StubStt` / `StubTts`: deterministic offline clients for keyless
  dev and tests.
- `audio.py` - `pcm16_wav`, wrap raw PCM as a WAV container.
- `token.py` - `grant_token` / `build_grant_request` / `DeepgramTokenError`:
  mint a short-lived Deepgram token so the browser can open a live STT socket
  without ever seeing the long-lived key.
- `stt/deepgram.py` - `DeepgramStt` adapter (extra: `deepgram`).
- `tts/cartesia.py` - `CartesiaTts` adapter (extra: `cartesia`).
- `__main__.py` - the `vox say|transcribe` smoke CLI, so vox is verifiably
  usable on its own.

## Invariants

- **Lazy provider imports are deliberate.** The provider SDKs (`deepgram-sdk`,
  `cartesia`) are heavy optional extras, so their adapters are imported lazily
  inside the `build_*` factories, guarded by `try/except`. This is the
  optional-dependency exception to the repo-wide "imports at file level" rule:
  keeping them lazy is what lets `import vox` and the stub path work with no
  extras installed. Do not hoist these imports to module scope.
- **Always degrade to a stub, never crash.** Missing key, missing extra, or bad
  config logs a warning and returns the stub. The app must start regardless.
- **Protocols, not inheritance.** New providers implement the `base.py` Protocols
  and are wired through the `factory.py` selection; callers stay SDK-agnostic.
- Provider name lists (`_STT_PROVIDERS`, `_TTS_PROVIDERS`) are named constants.
- `logging`, not `print`, in library code. `__main__.py` is the CLI and owns
  stdout (results) and stderr (usage), matching the repo's CLI convention.
- `__init__.py` is re-exports only. Every `.py` file carries the BSL-1.0 header.

## Configuration (env, read only by the caller / CLI)

- `STT_PROVIDER` = `auto | stub | deepgram`; `DEEPGRAM_API_KEY`, `DEEPGRAM_MODEL`.
- `TTS_PROVIDER` = `auto | stub | cartesia`; `CARTESIA_API_KEY`,
  `CARTESIA_VOICE_ID`, `CARTESIA_MODEL`.

## Tests

Offline, no keys, provider extras not required:

```bash
uv run --package vox pytest packages/vox/tests
```
