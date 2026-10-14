# 04 - API-Contract-Design

**Verdict:** usable-with-conditions — `lx.extract()` is the only stable contract surface; the two untyped dict kwargs and divergent defaults make any other entry path or minor typo a silent or misleading break.
**Confidence:** high

## Findings
- [CRITICAL] `resolver_params` is documented as configuring `resolver.Resolver` (`extraction.py:130-145`), but alignment keys are peeled off and routed to `Annotator`/`AlignmentPolicy`, not the constructor. `Resolver.__init__` still rejects any unknown key with `TypeError` (`resolver.py:261-264`). A typo like `fuzzy_alignment_treshold` therefore raises `Unknown key in resolver_params` (`extraction.py:377-379`) even though the key was never a Resolver parameter — the shipped failure class behind Issue #245 (https://github.com/google/langextract/issues/245). v1.6.0 fixed the *correctly spelled* alignment passthrough (`extraction.py:359-401`, `init_test.py:160-203`), but the doc/constructor split remains a live footgun for direct `Resolver(...)` use and misspelled keys.
  Impact: integrators cannot trust the docstring routing table; calibration knobs advertised in `skills/langextract-usage/references/resolver-params.md` fail opaquely on typos and on any code path that constructs `Resolver` directly.

- [HIGH] Default semantics diverge between `extract()` and `Annotator`, with no warning when bypassing the facade. `extract()` defaults: `max_char_buffer=1000`, `batch_length=10`, `suppress_parse_errors=True` (`extraction.py:53,57,365`); `Annotator.annotate_text` / `annotate_documents` defaults: `max_char_buffer=200`, `batch_length=1`, `suppress_parse_errors=False` (`annotation.py:213-214,295,536-537`). Baseline §3 correctly cites Annotator defaults but does not flag that `extract()` overrides them — a consumer reading `annotation.py` alone gets the wrong contract.
  Impact: tapetum-style integrators that call `Annotator` directly (or wrap langextract below `extract()`) get 5× smaller chunks, serial batches, and fail-fast parse behavior without any signal — a silent contract change vs README/examples that always show `lx.extract()`.

- [HIGH] `language_model_params` is an unvalidated merge into `ModelConfig.provider_kwargs` (`extraction.py:146-148,327-331`, `factory.py:287-317`) with no reserved-key collision check unless `output_schema` is active (`factory.py:288-294`). Keys are dropped when value is `None` (`extraction.py:328`), and provider classes silently discard unknown kwargs (Gemini keeps only `_API_CONFIG_KEYS`, `gemini.py:296-298`). Contrast: our `AgentBackend` + `StepPrompt` split typed constructor fields from a reserved-key `extra` bag with build-time capability validation (`agents.py:54-62`, `prompt.py:60-70`, `pipeline/CLAUDE.md` capability gate).
  Impact: self-hosted wiring (`model_url`, vLLM sampling overrides) appears accepted at `extract()` but may be no-ops per provider; no equivalent of our `CapabilityMismatchError` at construction time.

- [MED] Return shape is input-polymorphic: `str` → single `AnnotatedDocument`, `Iterable[Document]` → `list[AnnotatedDocument]` (`extraction.py:75,187-190,403-427`). The internal path streams (`annotation.py:221,297`) but `extract()` materializes a list for document iterables only. Our pipeline always returns validated Pydantic models from `AgentBackend.run(..., output_type=...)` (`agents.py:110-122`).
  Impact: wrapper code must branch on input type or always normalize; easy to write generic batch handling that breaks on string input.

- [MED] `model_url` docstring claims it is "only forwarded when the selected `language_model_type` accepts this argument" (`extraction.py:152-153`), but `extract()` always injects both `model_url` and `base_url` into provider kwargs (`extraction.py:311-312`). Gemini has neither parameter and filters `**kwargs` to `_API_CONFIG_KEYS` only (`gemini.py:166-184,296-298`), silently discarding both URLs. OpenAI/Ollama consume `base_url`/`model_url` respectively (`openai.py:110,149`, `ollama.py:194-243`).
  Impact: copy-pasting Ollama README config onto a Gemini `model_id` gives no error and no proxy — doc promises conditional forwarding, code gives provider-dependent silent drop.

- [MED] Explicit `None` in `resolver_params` means "omit key," not "reset to default." `fuzzy_alignment_threshold=None` is stripped and neither reaches `Resolver` nor `Annotator` (`extraction.py:362-364`, `init_test.py:461-468`). Callers cannot distinguish "library default" from "explicitly disabled override" without reading implementation.
  Impact: programmatic config builders that set `None` to clear overrides silently revert to hardcoded aligner defaults (`resolver.py:334`, `_FUZZY_ALIGNMENT_MIN_THRESHOLD` at `resolver.py:57`).

- [LOW] Public surface carries a v2.0.0 deprecation cliff: `_compat/` shims (`_compat/__init__.py:15-18`, `_compat/schema.py:33-35`, `_compat/registry.py:27-30`), `language_model_type` (`extraction.py:104-107,300-304`), legacy resolver format keys (`format_handler.py:411-418`), and lazy `__getattr__` submodules (`__init__.py:63-98`). Warnings fire at runtime, not import time — semver stability is aspirational, not guaranteed.
  Impact: any tapetum adapter pinning imports from `langextract.registry` or legacy resolver keys inherits breaking-change debt without a typed migration path.

## False-pass hypothesis
Integration test passes `resolver_params={"suppress_parse_errors": True}` through `extract()` and sees no exception on malformed JSON (`init_test.py:207-248`), while `Annotator` defaults `suppress_parse_errors=False` (`annotation.py:295`). A consumer unit-testing against `extract()` assumes fail-soft chunk parsing; production code calling `Annotator` directly fails the whole document on the same malformed output — tests green, runtime contract differs.

## False-fail hypothesis
User lowers fuzzy threshold via `resolver_params={"fuzzy_alignment_threshold": 0.5}` on CJK text; alignment still returns `char_interval=None` for many spans (Issue #334, https://github.com/google/langextract/issues/334) not because the threshold is ignored (v1.6.0 routes it correctly) but because tokenizer/regex alignment is wrong for the script — user blames the API knob, uninstalls, never reaches PR #480 substring fallback.

## What would change my mind
A published `ResolverParams` TypedDict (or dataclass) with a single routing table tested under semver, plus one canonical default profile re-exported by both `extract()` and `Annotator`, would flip this to **usable** for tapetum integration.
