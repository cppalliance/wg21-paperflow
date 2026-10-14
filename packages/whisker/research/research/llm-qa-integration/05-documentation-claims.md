# 05 - Documentation-Claims

**Verdict:** usable-with-conditions — the deterministic-gates-decide + advisory-LLM architecture is implemented as documented in code (`gates.py`, `score.py`, `fusion.py`, `cli.py`), but several authority docs and the 00-baseline fact sheet are stale on cascade triggers, test counts, and known-gap status; reference-repo READMEs oversell LLM roles where CI uses deterministic gates only.
**Confidence:** high

## Findings

- [HIGH] **whisker `CLAUDE.md` still documents confidence-only tier-2 escalation, but code now uses three derived uncertainty signals.** Evidence: `packages/whisker/src/whisker/CLAUDE.md:526-528` ("only a confidence inside the ambiguous band escalates"); contradicts `adjudicate.py:230-253` (`_escalation_signals`: `axis_conflict`, `ungrounded_evidence`, `confidence_ambiguous`) and `constants.py:23-26` (band alone dead; derived signals added). Impact: maintainers reading `CLAUDE.md` will misconfigure or under-test the cascade; the architecture is sounder than the stale prose claims.

- [HIGH] **whisker `CLAUDE.md` calls the advisory lane "deterministic" while `tapetum_llm.md` documents non-bit-stable LLM output.** Evidence: `CLAUDE.md:557-558` ("every call is serial and deterministic"); contradicts `tapetum_llm.md:29` ("token-level output on a hosted vLLM pod is not bit-stable under continuous batching and MoE expert routing"). Impact: overstates reproducibility of the advisory lane; does not invalidate the "never gates" invariant but misleads anyone treating tapetum sidecars as regression baselines.

- [HIGH] **Marker README benchmark tables present LLM Score as a peer headline metric without disclosing that CI gates only the heuristic scorer.** Evidence: `packages/whisker/research/repos/marker-v1.10.2/README.md:472-495` (side-by-side "Heuristic Score" and "LLM Score" tables, no CI caveat); `benchmarks/verify_scores.py:10-13` (CI check: `heuristic` mean >= 90 only); `benchmarks/overall/overall.py:93` (default `--scores heuristic`); `benchmarks/overall/overall.py:60-63` (LLM scorer failures caught and skipped); `.github/workflows/benchmarks.yml:30-31`. Impact: supports 00-baseline/05-web architecture claim (LLM judge advisory, deterministic CI) but Marker marketing oversells LLM-judge centrality — same anti-pattern our docs must avoid.

- [MED] **`tapetum_llm.md` opening paragraph contradicts its own mermaid and the implemented escalation gate.** Evidence: `tapetum_llm.md:3` ("only genuinely ambiguous calls escalate"); vs `tapetum_llm.md:12` (mermaid: "axis conflict, ungrounded evidence, ambiguous confidence") and `adjudicate.py:230-253`. Line 168 partially corrects the record but line 3 remains stale. Impact: authority doc inconsistency; newcomers read the wrong cascade story.

- [MED] **`00-baseline.md` test-count anchor is stale after `no_toc_leak` and subsequent test growth.** Evidence: `00-baseline.md:60` ("616 tests"); runtime `uv run --package whisker pytest packages/whisker/tests --collect-only` → **995 tests collected** (2026-07-16). `00-baseline.md:95` also cites "986 tests green" from the MC2 session. Impact: undermines trust in other numeric anchors in the baseline unless re-verified; gate-count anchor (`gates.py:209-218`, six gates incl. `no_toc_leak`) is still correct.

- [MED] **`00-baseline.md` "dead two-tier cascade" weakness is partially obsolete in code but still listed as open.** Evidence: `00-baseline.md:85` ("Dead two-tier cascade (0/198 escalations)"); code now adds derived triggers `constants.py:32-40`, `adjudicate.py:230-253`, tests `test_tapetum_llm.py:1254-1330`. Production sidecars may still show 0/198 until re-run; the *mechanism* is no longer band-only dead. Impact: baseline weakness table overstates current code state; re-run needed to close the empirical gap.

- [MED] **TOC-leak docs say the LLM lane "mirrors" the deterministic gate, but severity differs: gate hard-fails, prompt caps at review.** Evidence: `gates.py:143-185` (`no_toc_leak` hard fail); `tapetum_llm.md:62` (TOC leak: "verdict at least `review`"); `CLAUDE.md:510-512` ("verdict capped at `review` or worse" + mirrors gate). Impact: intentional asymmetry is documented but the word "mirrors" overstates alignment; deterministic path is stricter (fail) than advisory (review floor).

- [LOW] **pymupdf4llm/PyMuPDF README marketing implies LLM-in-the-loop conversion; code has none.** Evidence: `pymupdf4llm/README.md:26-28` ("Turn PDF … into clean, LLM-ready data"); `PyMuPDF/README.md:25,38` ("powering AI pipelines", "LLM-ready"); `00-baseline.md:39` ("pymupdf4llm: marketing name only"); grep over `pymupdf4llm/**/*.py` found zero `openai`/`gemini`/`gpt`/LLM API usage. Impact: confirms ecosystem pattern our baseline cites — LLM branding on deterministic extractors — not evidence we took the wrong QA path.

## False-pass hypothesis

A WG21 paper with token-preserving table cell swap or math-operator flip that keeps `unigram_coverage >= 0.95` receives whisker `pass` and is **never forwarded** to tapetum under default `--review-all` because `select_candidates` only pulls pass-tier papers with explicit risk signals (`adjudicate.py:96-109`; documented selection gap `CLAUDE.md:490-492`). The deterministic gate green-lights; the advisory lane never runs.

## False-fail hypothesis

`P3941R2`-class papers: high content recall (`uni=0.999`) with only `heading_monotone` H2→H4 jump (`gates.py:96-110` hard fail; persona evidence in `research/persona/opus-A-metric-validity.md:19`). Cosmetic typography fail despite faithful prose; fusion can rescue to `review` (`fusion.py:149-160`) but whisker `--gate` still exits fail on the deterministic verdict.

## What would change my mind

A full-corpus tapetum re-run after the derived-signal escalation patch showing `escalation_signals` populated on a material fraction of papers (e.g. `axis_conflict` > 10%) **and** tier-2 adjudications that change `suggested_verdict` vs tier-1 on labeled false-pass cases — proving the documented cascade is live in production, not only in unit tests.
