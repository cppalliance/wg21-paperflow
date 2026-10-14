# a14 - Archaeologist: langextract + redteam + base64-blob-filter

**Verdict:** usable-with-conditions — langextract and base64 research landed targeted tapetum upgrades (monotonic char-offset grounding, pre-LLM binary stripping) that improve evidence precision and token hygiene but explicitly reject wholesale library adoption and never address golden-contract recall; redteam and buildvsbuy reinforce BUILD deterministic tripwires, not LLM verification of human-verified blockers.
**Confidence:** high

## Findings

- [CRITICAL] Langextract synthesis concluded **adopt-partially**: port the monotonic exact-occurrence DP and graded `char_interval` return into whisker; **reject** langextract as a dependency (unconditional Google Cloud SDKs, fail-soft chunk drops, injection-blind prompts, Tier-3 LCS gapped wrong-span oracle at `resolver.py:1403-1404` / `tests/fuzzy_alignment_cases_test.py:213-223`). Evidence: `packages/whisker/research/langextract/SYNTHESIS.md:6-7`, `17-18`, `20-21`, `32-38`. Impact: the study predicted precision/trace upgrades, not defect discovery. Answer-class: 4, 5.

- [HIGH] The recommended algorithm **was implemented** in `grounding.py`: monotonic DP port (`grounding.py:147-214`, comment at `:14-21`), `GroundedSpan` with `(start, end)` char intervals (`:86-94`), post-alignment guard rejecting intervals whose raw slice fails normalization (`:306-308`), document-level fuzzy fallback kept at `EVIDENCE_FUZZY_FLOOR` without LCS (`:324-331`, `constants.py:50`). Impact: fixes occurrence-blind first-hit grounding and inspect locatability; **zero RECALL power** per baseline § evidence verification (`00-baseline.md:84-85`). Answer-class: 4.

- [HIGH] Langextract char-offset work **deliberately omitted** Tier-3 LCS fuzzy, plural stemming, and the library itself. Evidence: `SYNTHESIS.md:17`, `37`; optional stem at `resolver.py:1275-1281` not present in `grounding.py` (no `_normalize_token` equivalent). Impact: avoids langextract's gapped MATCH_FUZZY false-grounding class (`20-grounding-alignment-specialist.md:18-19`); does not help the model **generate** poll-table or secno defects it never proposes. Answer-class: 4.

- [HIGH] **Redteam corpus does not study tapetum prompt-injection or LLM evasion.** The 28 `research/redteam/*.md` reports adversarially hunt gaps in whisker's **deterministic** `guard.py`/`calibrate.py` against external converter QA repos (`notes/redteam-synthesis.md:3-8`); grep finds no `wrap_source`, `inject_untrusted`, or tapetum LLM lane coverage. Impact: redteam cannot explain PR #286/#295 LLM recall=0 via injection; langextract's injection audit (`21-prompt-injection-auditor.md:7-8`) applies to **langextract**, while tapetum already wraps sources (`unit_judge.py:580-588`, `pdf_judge.py:632-636`). Answer-class: 5.

- [HIGH] Redteam **RECALL-relevant findings are deterministic-lane gaps**, not adversarial defeat of the LLM judge. Tier-3 deferred: table **detection recall** (tabula dual-counter monotonic guard, `redteam/tabula-java.md:51-53`, `:159`), set-F1/`%missing` content-recall axis (nougat/unstructured, `redteam-synthesis.md:43-44`), byte-exact golden output tier (`buildvsbuy/golden-exact-lane.md:93-95`). Impact: predicts PR #286 poll-table miss (`00-baseline.md:54-55`, no table-cell compare) and fuzzy-metric blind spots; does **not** model messy HTML defeating LLM detection — PR #295 failed because outline comparison never encoded secno stripping (`00-baseline.md:62-64`), not because the source evaded grounding. Answer-class: 1, 2, 5.

- [MED] TOC A/B experiment (`toc-ab-experiment.md:90-119`): **zero find-problems** in either variant across 37 facts; all 3 baseline fails and 2 TOC fails are **read-problems** (table column/cell misread). Net delta +1 (P0876R23 `F` vs `SF` heading) attributed to model variance, not navigation (`:95-103`). Impact: injecting prompt surface (TOC after front matter) does **not** encode golden-contract rules (class 1); confirms table-reading failures (class 3) orthogonal to document navigation. Answer-class: 1, 3.

- [MED] Base64-blob-filter research **was adopted** pre-LLM: firecrawl-pattern data-URI replacement + bare-line alphabet gate (`base64-blob-filter/SYNTHESIS.md:51-71`; implemented `chunking.py:54-99`, `constants.py:109-122`, disclosed `tapetum_llm.md:189`, `:217`). Impact: closes P2728 1.14 MB line choke (2.54 MB → ~150 KB per synthesis `:75-76`); prevents budget starvation on binary payloads (class 2) but irrelevant to PR #286 pages 8-9 displacement or PR #295 heading contract. Answer-class: 2.

- [LOW] Buildvsbuy evaluated external **metric/infra** packages, not an LLM verification product: **BUILD** stdlib difflib exact lane and Counter set-recall (`golden-exact-lane.md:93-95`, `set-f1-recall.md:244-250` rejects sklearn/nltk/rapidfuzz); **reject** PyPI TEDS dupes (`teds-tables.md:93-95`); **BUY** only zero-cost complements (`apted`, `grits-metric`, `mistune`). Langextract library rejected as dependency while algorithm port accepted (`langextract/16-product-decision-skeptic.md:3-4`, `:11-12`). Impact: ecosystem direction is deterministic tripwires + advisory LLM; aligns with baseline class 5 and `00-baseline.md:82` (0/31 repos gate on LLM). Answer-class: 5.

## False-pass hypothesis

PR #286: even with monotonic exact grounding, a model that checks page 13 headings and emits zero table-cell defect claims still passes evidence verification (0 accepted defect groups, `00-baseline.md:50-54`); `ground_spans` only validates quotes the model proposes. PR #295: `html_outline.py` source/candidate outline both read `1. Abstract` (`00-baseline.md:62-64`), so metadata/outline **pass** with empty `heading_drift` despite human-verified secno retention — a contract-encoding gap no langextract port or redteam guard axis catches.

## False-fail hypothesis

P2728-scale papers before base64 stripping: adjudicate/triage could choke or silently truncate on megabyte `data:image` lines (`base64-blob-filter/SYNTHESIS.md:9-12`), producing coverage-only `review` or missed units — a **budget/routing** false alarm unrelated to conversion quality. Post-adoption `strip_binary_payloads` (`chunking.py:54-71`) removes that failure mode without touching on-disk `paper.md`.

## What would change my mind

A redteam or langextract follow-on that measured tapetum **generation recall** (human-verified blockers → `UnitCheck.defects` non-empty) before and after monotonic grounding + base64 stripping on PR #286/#295 reruns, showing recall > 0 without adding deterministic table-cell compare or heading-normalization preprocessing — none of these three corpora contain that experiment; langextract persona 16 explicitly scoped grounding as trace prettiness with "zero effect" on the dominant JSON/runtime pain (`16-product-decision-skeptic.md:9`).
