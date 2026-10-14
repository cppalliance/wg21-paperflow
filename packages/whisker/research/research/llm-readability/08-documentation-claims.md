# 08 - Documentation-Claims

**Verdict:** usable-with-conditions — Lane 3 corpus, CI, and olmOCR-survey claims match the code; tapetum_llm grounding docs overstate protection while the #277 one-line fix remains unimplemented.
**Confidence:** high

## Findings

- [CRITICAL] **tapetum_llm docs claim grounding "never turns uncertainty into a pass/fail," but `adjudicate.py` exempts `pass` from ungrounded demotion.** Evidence: comment at `adjudicate.py:234-238` and matching prose in `CLAUDE.md:387-389`; demotion guard is `if suggested_verdict != VERDICT_PASS and not grounded:` at `adjudicate.py:237` (same condition baseline item 1, `00-baseline.md:71-76`). Impact: a confident advisory `pass` whose evidence spans were all dropped by `ground_spans` still clears; readers treating tapetum clears as grounded are misled.

- [HIGH] **#277 blocking condition 1 is documented as a one-line fix but is not in the code.** Evidence: `deepseek-v4-pro/SYNTHESIS.md:19` ("Fix: one code change" at `adjudicate.py:237`); baseline confirms unchanged at this SHA (`00-baseline.md:71-76`). `tapetum_llm.md:156` correctly scopes demotion to "verdict is not `pass`," but `CLAUDE.md:387-389` reads as if the gap were closed. Impact: ADOPT-gated safety work is still open while authority docs imply complete grounding protection.

- [MED] **Hermetic test-count claim in the POC report is stale.** Evidence: `comprehension-poc-report.md:152` says "356 passed"; runtime `uv run --package whisker pytest packages/whisker/tests` reports **674 passed, 6 skipped** (2026-07-06, no `WG21_DATA_DIR`). The underlying claim ("passes with no data dir") still holds: no whisker test references `WG21_DATA_DIR` (`packages/whisker/tests/` grep empty). Impact: numeric evidence in the POC is outdated; trust the mechanism, not the count.

- [MED] **`byte-identical to run_pipeline` is asserted but not enforced or re-verifiable in-repo.** Evidence: `CLAUDE.md:338-339`, `comprehension-poc-report.md:76-77,144-146`; no test or CI job compares `corpus/P4182R0.expected.md` to `run_pipeline` output (hermetic gate only runs `check_facts` on the committed snapshot, `test_comprehension_corpus.py:60-74`). Impact: if `tomd` regresses, the snapshot can drift while docs still claim byte identity; the claim rests on a one-time manual run, not ongoing proof.

- [LOW] **"Only olmOCR of 28 surveyed converters tests comprehension" is scoped correctly and matches the redteam survey.** Evidence: `facts.py:17-21`, `CLAUDE.md:42-43`, `comprehension-poc-report.md:31-32`; exactly **28** redteam reports under `packages/whisker/research/redteam/`; only `redteam/olmocr.md:3,15` documents deterministic present/absent/order/table/math fact assertions as the QA gate. External benchmarks with downstream QA (ParseBench, RealDocBench in `05-web.md` Q3) are outside that 28-repo converter survey. Impact: claim is defensible when read with its scope; it is not a global industry statement.

- [LOW] **CI matrix and hermetic comprehension gate claims are accurate.** Evidence: whisker in `.github/workflows/tests.yml:65`; `test_comprehension_corpus.py:8-19` reads committed `corpus/<pid>.expected.md` + facts with no backend; 5 comprehension tests pass including P4182R0 and P4185R0 canaries. Impact: the strongest operational claims in `CLAUDE.md:323-334` and `corpus/README.md:27-29` are trustworthy.

- [LOW] **"3x 8/8 blind read-back" is internally consistent but not machine-verifiable from code.** Evidence: `corpus/P4182R0.validation.md:43-48` records three runs at 8/8; `P4182R0.facts.jsonl` has 8 `"checked": "verified"` lines (`00-baseline.md:53-57`). No code contradicts this; it is manual, out-of-band evidence per baseline (`00-baseline.md:61-64`). Impact: anchor is documentation-only; absence of CI replay is correctly disclosed.

## False-pass hypothesis

A tapetum_llm tier-1 returns `suggested_verdict=pass` with high confidence and emits evidence spans that `ground_spans` drops (`grounding.py:36-56` returns `[], dropped>0`); because `adjudicate.py:237` skips demotion when verdict is `pass`, the advisory sidecar records a clear that docs describe as grounded but that has zero surviving quotes.

## False-fail hypothesis

None found for documentation-vs-code contradictions in Lane 3: the `table`/`math` canaries in `test_comprehension_corpus.py:77-116` confirm documented fail behavior on scrambled cells/formulas.

## What would change my mind

Land blocking condition 1 in `adjudicate.py` (demote confident `pass` when all emitted evidence is dropped), add a regression test matching `deepseek-v4-pro/SYNTHESIS.md:32`, and update `CLAUDE.md:387-389` to match — then re-run this cross-check.
