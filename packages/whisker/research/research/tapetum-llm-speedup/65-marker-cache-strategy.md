# 65 - marker-Cache-Strategy

**Verdict:** usable-with-conditions (+ marker confirms whole-file output skip is the ecosystem norm, but its open-source stack has no version-aware fingerprint, no LLM response memoization, and no cross-run page/block reuse; our fingerprint incremental is already ahead on invalidation safety, while marker's inference-server reuse is the only directly portable infra pattern)
**Confidence:** high

## Findings

- [CRITICAL] Marker has **no version/config fingerprint** on incremental skip: batch CLI checks only whether `{base}.{md|html|json}` exists, then returns without converting. Evidence: `marker/output.py:50-55` (`output_exists`), `marker/scripts/convert.py:72-73` (`skip_existing` gate), `marker/scripts/convert.py:132-135` (flag defaults **False**). Impact: on a marker upgrade or config change, `--skip_existing` silently serves **stale** outputs (0 s saved on cold re-run, **high quality risk** if treated as fresh). Our `_LANE_VERSION` + multi-field fingerprint (`cli.py:566-661`) invalidates on logic/prompt/schema/model change; marker has no equivalent in OSS.

- [HIGH] Skip granularity is **whole document only**, opt-in, and absent from single-file/API paths. Evidence: skip applies in `process_single_pdf` only (`convert.py:62-73`); `convert_single.py:25-40` always converts; FastAPI `server.py:95-141` always runs `_convert_pdf` with no cache/dedup; README `163` documents resume semantics. Impact: marker cannot skip individual pages/blocks across runs; a one-page fix still re-runs the full VLM+LLM pipeline (~same wall as our whole-paper re-judge on partial markdown change). Quality risk: low for skip itself; **no wall-clock lever** for our per-unit fingerprint gap.

- [HIGH] **No LLM response caching or memoization** anywhere in the conversion stack. Evidence: `marker/services/openai.py:61-128`, `marker/services/gemini.py:43-131` (fresh client call per block/page prompt); `marker/processors/llm/llm_meta.py:39-73` (ThreadPoolExecutor fan-out, no response store). Impact: 0 s saving on our ~2284-call cold fleet; confirms call-volume reduction must come from routing/packing, not marker-style reuse. Quality risk: none (pattern absent).

- [MED] **Model-weight / inference-server reuse** is real but scoped to **within a batch process**, not cross-run incremental. Evidence: parent spawns `SuryaInferenceManager` once, workers attach via `SURYA_INFERENCE_URL` (`convert.py:192-196`); `marker/models.py:23-37` (thin clients, shared GPU server); benchmark workers build `PdfConverter` once (`benchmarks/inference.py:107-108`); Modal example persists HF artifacts to a volume (`examples/marker_modal_deployment.py:30-69`). Impact: avoids per-worker model reload (~minutes on cold start, not our 3003 s judge wall); **~0 s** on an already-warm 24/7 pod. Quality risk: none.

- [MED] **In-memory within-document caches** exist but are not persisted or reused across runs. Evidence: `cache_pdftext_pages` holds raw pdftext for table cell assignment (`marker/providers/pdf.py:84-88`, `221-222`); released after table pass (`marker/processors/table.py:96-98`); block structure index is a runtime O(1) lookup (`marker/schema/blocks/base.py:110-127`). Impact: shaves pdftext re-extraction inside one conversion (negligible vs our ~20 s/call LLM latency). Quality risk: none.

- [LOW] Benchmark harness uses the same **existence-only** page skip (size > 10 B). Evidence: `benchmarks/inference.py:127-128`. Impact: resume for olmOCR-bench reruns only; same stale-output hazard on marker version bump. Quality risk: medium if benchmark scores are compared across marker versions without wiping `--out`.

- [LOW] Streamlit demo caches UI/session artifacts only (`@st.cache_data` / `@st.cache_resource` in `marker/scripts/common.py:17-83`), not conversion outputs or LLM responses. Impact: irrelevant to fleet judge runs. Quality risk: none.

## False-pass hypothesis

Adopting marker-style `--skip_existing` (file existence only) for tapetum sidecars without our fingerprint fields would let papers **pass unchanged** after a judge prompt, schema, or `_LANE_VERSION` bump even when findings would differ: marker's own pattern at `convert.py:72-73` + `output.py:50-55` has no invalidation hook, so stale outputs look fresh.

## False-fail hypothesis

Our whole-paper fingerprint re-runs the full 6-call cascade when any markdown byte changes (`00-baseline.md:57-59`); marker would behave the same on a non-skipped doc (full reconversion including all LLM block processors in `llm_meta.py:39-73`). Marker does **not** false-fail less than us on partial edits; it simply offers an optional whole-file skip that we already beat on safety.

## What would change my mind

A documented marker/Datalab **hosted** API fingerprint (source hash + converter version + config hash) in production code outside this OSS clone would flip the verdict to `usable` for cross-run incremental design; none appears in `research/repos/marker` today.
