# 12 - redteam-ours

**Verdict:** usable-with-conditions — the fix-path implementation delivers most SYNTHESIS ranked fixes (schema extension, table/HTML hardening, math-surface fixes, vacuous-green CLI gate, grounding demotion, blind readback harness) but retains verified false-pass and readback-methodology exploit classes that make the 37/37 live score an overclaim until CI coverage and question scoring tighten.
**Confidence:** high

## Findings

- [CRITICAL] **Decoy-table false pass survives heading filter + all-occurrence matching.** `_check_table` passes when ANY cell occurrence satisfies neighbors (`facts.py:396-403`); `table_heading` only filters header-row substring match (`facts.py:388-390`), not table identity. Verified probe: real table scrambled (`GPU… | Yes`) + second table with same heading row and correct neighbors (`… | No`) → fact passes. Impact: token-preserving table corruption that leaves a decoy shadow table defeats table facts while all 37 corpus facts stay green; SYNTHESIS #3 (decoy exploit) is only half-closed.
- [HIGH] **Readback YES/NO types are not comprehension tests; questions embed the answer needle and scoring accepts sycophantic assent.** `_generate_question` puts `fact.text` verbatim into present/absent/code/xref questions (`readback.py:112-122,159-169`); `_evaluate_answer` accepts any answer starting with `"yes"` / `"no"` (`readback.py:183-186`). Verified: `_evaluate_answer(present, "YES", "Yes, definitely.")` → True without document content. Impact: 37/37 live readback (`00-baseline.md:50-52`) does not prove blind recovery; a cooperative model passes most corpus without reading.
- [HIGH] **Table readback scoring is substring-only on neighbor values.** `_evaluate_answer` for `FACT_TABLE` checks `_norm_cell(expected_val) in answer_lower` per neighbor (`readback.py:200-203`), not positional binding to the target cell. Verified: `"right cell is 18, column heading SF"` passes a fact expecting `right=8, heading=SF` because `"8"` ⊂ `"18"` and `"sf"` appears. Impact: false PASS on table readback inflates the anchor that justifies trusting Lane 3.
- [HIGH] **18 of 37 verified corpus facts are not CI-gated.** Only P4182R0 and P4185R0 ship `<pid>.expected.md`; P4234R0, N5040, P0876R23 have facts but no hermetic snapshot (`test_comprehension_corpus.py:40-44`; corpus dir has 2 expected vs 6 facts files). SYNTHESIS condition 1 (stratified corpus + holdout readback) is partially delivered (5 papers, 37 facts) but the deterministic gate proves only 17 facts in CI. Impact: 3 papers' facts are live-readback-only evidence.
- [MED] **`classify_paper` / `draft_facts_scaffold` misclassify `$$…$$` inside fenced code as display math.** `_DISPLAY_MATH_RE.findall(md)` runs fence-unaware on the whole document (`corpus_tools.py:40,76,208-216`). Verified (Python file probe): `extern int Image$$ER_ZI$$Base;` inside a ```cpp fence → `display_math_count=1`, draft math text `"ER_ZI"`. Impact: P4234R0 auto-drafts would propose nonsense math facts; stratification picks wrong stratum. Worth fixing before scaling `whisker corpus draft`.
- [MED] **`auto_baseline_checks` is implemented but not wired into `whisker facts` / guard.** Helper exists (`facts.py:631-674`); CHANGELOG.md:74-75 states "not yet wired into the `whisker facts` report." `_warn_vacuous_reports` only catches papers *with* a facts file and zero verified rows (`__main__.py:493-508`), not the ~198 zero-facts fleet. Impact: SYNTHESIS olmOCR-style fleet baseline (condition 2) is code-complete but operationally absent.
- [MED] **Readback transport errors are indistinguishable from comprehension FAIL.** `readback_paper` catches `httpx.HTTPError`, sets `answer = f"(error: {exc})"` (`readback.py:279-283`), then `_evaluate_answer` → False. CHANGELOG.md:105 documents "one transient pod read-timeout on a first attempt" during the 3-paper readback wave. Impact: spurious FAIL pollutes the anchor; no ERROR/ SKIP state for infra faults.
- [LOW] **Readback order/math questions still leak sequence/formula needles.** Order embeds every `fact.sequence` item in the question (`readback.py:131-136`); math embeds `fact.text` (`readback.py:124-129`). Table question phrasing fix is real (`readback.py:138-157`), but order/math remain Persona-22-visible. Impact: weakens holdout-readback credibility, not the deterministic gate.

### Readback question-type leak severity

| Type | Question leak | Eval leak | Severity |
|------|---------------|-----------|----------|
| present | embeds `fact.text` | startswith yes | CRITICAL |
| absent | embeds `fact.text` | startswith no | HIGH |
| code | embeds snippet | startswith yes | CRITICAL |
| xref | embeds ref | startswith yes | CRITICAL |
| image_ref | generic | startswith yes | HIGH |
| math | embeds formula hint | structural substring | HIGH |
| order | embeds all items | monotonic find only | HIGH |
| table | blind to expected values | neighbor substring | MED |

## False-pass hypothesis

Scramble P4182R0 Table A so `(CUDA, SYCL) | No` becomes `| Yes`, append a decoy pipe table with the same header row (`Category | …`) and a body row restoring `GPU device code (CUDA, SYCL) | No`. All 37 verified facts (including `tableA-gpu-coro-no`) still pass; Lane 2 unigram gate stays green. Deterministic gate does not detect the corruption class the SYNTHESIS ranked #3 to kill.

## False-fail hypothesis

Alliance-pod `httpx.ReadTimeout` at `readback.py:243` (`_REQUEST_TIMEOUT = 120.0`) on a cold or queued request yields `(error: …)` → scored FAIL (`readback.py:279-283`) even when a immediate retry would succeed; CHANGELOG.md:105 records this on the N5040/P4234R0/P0876R23 readback wave.

## Adoption candidate

none — self-target audit; no external module to port.

## What would change my mind

Committed `<pid>.expected.md` for all 5 corpus papers with CI passing on all 37 verified facts, plus a holdout readback rerun using questions that do not embed `fact.text`/`fact.sequence` and table scoring that binds neighbor values to the named cell (not document-wide substring), with `--corrupt` failing ≥90% and infra errors reported as ERROR not FAIL.

## SYNTHESIS fix-path delivery check (2026-07-06 ranked list)

| Promised fix | Delivered? | Anchor |
|--------------|------------|--------|
| Stratified corpus ≥30 papers / ≥300 facts | Partial (5 papers, 37 facts; 2 CI-gated) | `00-baseline.md:48-49`, `test_comprehension_corpus.py:40-44` |
| code/xref/image-ref + raw surface | Yes | `facts.py:70-76,257-265,451-470` |
| olmOCR-style auto baseline fleet-wide | Code only, not wired | `facts.py:631-674`, CHANGELOG.md:74-75 |
| Fail on zero verified facts | Yes | `__main__.py:493-508,745-763` |
| Heading-anchored + all-occurrence table match | Yes, but decoy-shadow remains | `facts.py:373-406` |
| HTML table parser | Yes | `tables.py:80-135`, `facts.py:341-345` |
| Math brace/case/display/backslash fixes | Yes | `facts.py:190-254`, canaries `test_facts.py:588-639` |
| #277 grounding demotion | Yes | `adjudicate.py:295-304` |
| Blind readback + corrupt control | Yes, methodology gaps above | `readback.py:106-313`, `readback_cli.py:85-215` |
