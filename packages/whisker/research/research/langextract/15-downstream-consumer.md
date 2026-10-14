# 15 - Downstream-Consumer

**Verdict:** usable-with-conditions (+ the aligner logic is technically reachable, but there is no clean import path for tapetum: `pip install langextract` drags mandatory cloud SDKs, the documented `lx.extract()` API always instantiates an LLM provider, and the self-hosted parse lane our pod uses is documented broken)
**Confidence:** high

## Findings
- [CRITICAL] `langextract` declares `google-genai` and `google-cloud-storage` as required runtime dependencies, not optional extras (`pyproject.toml:30-37`). A downstream `whisker[tapetum-llm]` install would pull Google cloud SDKs even if tapetum never calls Gemini.
  Impact: violates our model-sovereignty supply-chain posture; there is no published "aligner-only" extra to opt out.

- [HIGH] The documented entry point `lx.extract()` is inseparable from LLM provider construction: it always calls `factory.create_model()` (`extraction.py:334-340`), which loads the plugin registry (`factory.py:155-162`) and defaults to `model_id="gemini-3.5-flash"` (`extraction.py:49`). The README steers integrators here, not to `WordAligner`.
  Impact: tapetum cannot adopt "just the grounding stage" through the public API; bypass requires private submodule imports.

- [HIGH] Aligner-only use is possible but unbounded: `from langextract.resolver import WordAligner` loads ~881 transitive modules at runtime (reproduced import probe, 2026-07-03) with zero `google.*` imports, yet the aligner expects `data.Extraction` objects and runs through `Resolver.align()` → `WordAligner.align_extractions()` (`resolver.py:327-398`, `539-930`), not raw quote strings like our `EvidenceSpan.quote` (`grounding.py:43-54`).
  Impact: vendoring cost is ~1,727 LOC (resolver 1,213 + tokenizer 514, `00-baseline.md:24`) plus `absl-py`/`regex`/`numpy`/`pandas` deps vs our 56-line `ground_spans` with one `rapidfuzz` call.

- [HIGH] Self-hosted integrators on vLLM/lmdeploy report `<20%` JSON parse success; maintainer workaround `fence_output=False, use_schema_constraints=False` does not fix it (Issue #414, `05-web.md:56-58`). LangExtract has no vLLM `guided_json` path (`00-baseline.md:35`, grep 0 hits).
  Impact: the full pipeline is a trap for our Alliance pod lane; importing langextract to "fix grounding" still leaves the upstream parse stage broken on our stack.

- [MED] `resolver_params` documentation lists alignment tuning keys as Resolver settings (`extraction.py:130-145`), but `Resolver.__init__` rejects any unknown keyword with `TypeError` (`resolver.py:261-264`); alignment keys are peeled off and forwarded to `Annotator.annotate_text()` instead (`extraction.py:359-401`). v1.6.0 tests confirm the extract()-path passthrough works (`init_test.py:160-203`), but Issue #245 documents integrators who passed `fuzzy_alignment_threshold` directly to `Resolver(**resolver_params)` and hit `TypeError` (`05-web.md:96-98`).
  Impact: sharp edge for anyone vendoring `resolver.py` standalone and trusting the docstring contract.

- [MED] Top-level `import langextract as lx` eagerly imports `visualization` and `extraction` at module load (`__init__.py:27-28`), not lazy-only; `visualization.py` pulls notebook/HTML machinery (`visualization.py:34-40`).
  Impact: integrators following README `import langextract as lx` pay for the full surface area before choosing an aligner-only path.

- [LOW] Default `max_workers=10` and `batch_length=10` on `lx.extract()` (`extraction.py:57-58`) propagate into provider `infer()` calls; Issue #50 documents 429 storms at default parallelism (`05-web.md:30-32`).
  Impact: copy-paste integrators inherit concurrency defaults that conflict with our D11 serial-default invariant (`00-baseline.md:43`, `adjudicate.py:409`).

## False-pass hypothesis
An integrator replaces `ground_spans` with `Resolver.align()` and treats any non-`None` `char_interval` as trusted evidence. LangExtract accepts `MATCH_FUZZY` at coverage ≥0.75 and density ≥1/3 (`resolver.py:57-58`, `1377-1404`), looser than our `EVIDENCE_FUZZY_FLOOR=0.90` document-level partial match (`constants.py:50`, `grounding.py:51`). A paraphrased LLM quote can receive a char span the tapetum lane would have dropped.

## False-fail hypothesis
A verbatim evidence quote containing the WordAligner default delimiter U+241F (unit separator, `resolver.py:795`) triggers `ValueError: Delimiter ... appears inside extraction text` (`resolver.py:916-920`). Our substring grounding has no delimiter constraint (`grounding.py:49`). Unlikely in WG21 prose but possible in generated Unicode artifacts.

## What would change my mind
A published aligner-only distribution (no `google-genai` in required deps) exposing a single-call API like `align_quote(source: str, quote: str) -> CharInterval | None` with documented threshold semantics, plus Issue #414 closed with vLLM parse success ≥90% on the maintainer's reproducer.
