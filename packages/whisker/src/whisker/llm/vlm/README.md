# vlm: Vision Language Model Lane (dormant)

Quarantined prototype for direct PDF-page QA via a Vision Language Model.

## Modules

| Module | Purpose |
|---|---|
| `vision.py` | Rasterize PDF pages to PNG via pymupdf. |
| `vision_task.py` | Run a single VLM inference call with retry/JSON extraction. |
| `transcribe.py` | Orchestrate page-by-page VLM transcription of a rasterized PDF. |
| `vlm_diff.py` | Diff VLM transcription against tomd markdown, produce a verdict. |
| `vlm_pipeline.py` | End-to-end: rasterize, transcribe, diff, return `VlmDiffResult`. |

## Status

**Dormant.** No production entry point imports these modules. The
reachability guard in `tests/test_vlm_lane.py` enforces this: it
AST-scans `__main__.py`, `menu.py`, and `llm/cli.py` and fails
if any of them reference VLM module names or symbols.

## Activation path

1. Deploy a self-hosted Vision Pod (olmocr or equivalent).
2. Add a `[services.vision-pod]` entry to `SERVICES.toml`.
3. Wire `vlm_pipeline.vlm_adjudicate_paper` into the advisory lane CLI.
4. Update or remove the reachability guard test.
