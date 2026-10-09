# 00 - Evidence Baseline: LLM-readability fix-path implementation (self-target)

Date: 2026-07-09. Target SHA: e66116a09bbe833a8080e9e60a95833ab339cf64 + UNCOMMITTED
working tree (+2,750 / -261 lines in `packages/whisker/`). Prior research that
produced the ranked fix path: `research/llm-readability/` (2026-07-06, same base SHA,
25 personas + 31-repo scan). This run evaluates the IMPLEMENTATION of that fix path.

## What the target is

The whisker package's Lane 3 comprehension hardening plus the new blind-readback
harness, implemented 2026-07-08/09:

- **A1 grounding demotion** (`packages/whisker/src/whisker/tapetum_llm/adjudicate.py:295-304`):
  a confident LLM `pass` whose evidence spans were ALL dropped by grounding demotes
  to `review`. Empty-evidence passes untouched.
- **A2 vacuous-green gate** (`packages/whisker/src/whisker/__main__.py`, `_warn_vacuous_reports`):
  `whisker facts` / `whisker guard` FAIL when a `.facts.jsonl` has zero
  `checked: verified` facts.
- **A3 schema extensions** (`packages/whisker/src/whisker/facts.py`): new fact types
  `code`, `xref`, `image-ref` (all default `surface: raw`); `surface: "raw"` mode
  (whitespace-collapse only, preserves operators/case, `_raw_surface` at facts.py:257);
  `auto_baseline_checks` (structural minimums: alnum floor, mojibake n-gram ratio).
- **A4 primitives hardening** (`packages/whisker/src/whisker/facts.py`,
  `packages/whisker/src/whisker/tables.py` NEW, 135 lines): `table_heading` anchor,
  all-occurrence cell matching (kills decoy-table first-match-wins), HTML `<table>`
  grid parser via stdlib `html.parser` feeding the same neighbor check as pipe tables,
  `_math_surface` preserves case + relational operators AND now folds `\[...\]`
  display math (multi-line) and undoubles `\\command` backslashes
  (facts.py:190-231, live-run driven fixes).
- **B1 blind readback harness** (`packages/whisker/src/whisker/tapetum_llm/readback.py`,
  374 lines; `readback_cli.py`, 219 lines): per verified fact, generates a
  comprehension question WITHOUT embedding the expected answer, sends paper markdown +
  question zero-shot to a self-hosted DeepSeek pod, evaluates the answer
  deterministically per fact type (`_evaluate_answer` readback.py:167), renders
  terminal PASS/FAIL + persists `<pid>.readback.md`. `--corrupt` adversarial control
  (scrambles tables/operators/exponents; readback.py:284). D1 exemption documented.
- **B2 corpus authoring tools** (`packages/whisker/src/whisker/corpus_tools.py`,
  268 lines): `classify_paper` (heuristic strata: tables/math/code/footnotes/images),
  `stratify_candidates` (zero-coverage papers by stratum), `draft_facts_scaffold`
  (draft `.facts.jsonl` skeletons).

## Size / runtime facts (reproduced 2026-07-09)

- facts.py 674 lines; tables.py 135; corpus_tools.py 268; readback.py 374;
  readback_cli.py 219; adjudicate.py 523; __main__.py 1033; metrics.py 693.
- Tests: **872 passed, 6 skipped, 5 xfailed** (`uv run --package whisker pytest
  packages/whisker/tests -q`, 4.78s).
- Comprehension corpus: **5 papers, 37 gated verified facts** (P4182R0 8, P4185R0 9,
  P4234R0 6, N5040 6, P0876R23 8; EXAMPLE excluded, no staged candidate).
- Live blind readback vs alliance-pod (DeepSeek-V4-Pro): P4182R0 8/8, P4185R0 9/9,
  P4234R0 6/6, N5040 6/6, P0876R23 8/8 = **37/37** after 4 live-run-driven fixes
  (display-math fold, backslash undoubling, cp1252 stdout, table-question blindness).
- A1 retro-audit over 381 production tapetum.json records: **0 demotions**; 0 of 252
  pass verdicts carry claimed evidence (model only cites evidence on review/fail),
  126 records overall carry evidence, partial drops occur (e.g. N5040 2 grounded /
  3 dropped). A1 is a defense line, not a live bug net, on the current prompt/model.
- Production inventory: 381 converted papers in `data/paperstore`, 381 tapetum
  advisory records (100% coverage), verdicts 252 pass / 120 review / 9 fail.

## Comparison questions (what the swarm must answer)

Each scan answers, for its assigned repo(s), with `file:line` anchors:

1. **Fact-assertion analog**: does the repo verify converted/extracted output via
   discrete, human- or machine-verified fact assertions (present/absent/order/
   table-cell/math/code/xref)? How does its design beat or lose to
   `whisker/facts.py`?
2. **Blind LLM readback analog**: does it validate output by having an LLM (or model)
   answer questions from the output blind? Question generation, answer scoring,
   leak prevention, adversarial controls vs `tapetum_llm/readback.py`.
3. **Table grid comparison**: how does it parse tables to grids and compare cell
   neighborhoods? Anything stronger than `whisker/tables.py` (135-line stdlib parser)?
4. **Corpus authoring / stratification**: how does it select benchmark documents and
   author ground truth at scale vs `corpus_tools.py` heuristics?
5. **Adoptable code**: name the single highest-leverage function/module we could port
   (license-compatible) into `packages/whisker/`, or "none".

## Comparison anchors in our code

- `packages/whisker/src/whisker/facts.py` (fact model + `check_facts`)
- `packages/whisker/src/whisker/tables.py` (pipe + HTML grid parsers)
- `packages/whisker/src/whisker/tapetum_llm/readback.py` (`_generate_question`,
  `_evaluate_answer`, `_corrupt_markdown`)
- `packages/whisker/src/whisker/corpus_tools.py` (`classify_paper`,
  `stratify_candidates`)
- `packages/whisker/src/whisker/tapetum_llm/adjudicate.py:295-304` (grounding demotion)
- `packages/whisker/src/whisker/metrics.py` (`textblock2unicode`, `normalized_text`)
- Prior per-repo scans: `research/llm-readability/repo-scan/<repo>.md` (2026-07-06).
  Read yours first; do NOT re-file its findings, extend them with the five questions
  above (the fix path they described is now implemented).

## Required report template

```
# NN - <Repo group>

**Verdict:** usable | usable-with-conditions | garbage   (+ 1 sentence: is OUR
implementation better/worse/equal for the compared concern)
**Confidence:** high | medium | low

## Findings
- [CRITICAL|HIGH|MED|LOW] <claim>. Evidence: <file:line OR runtime number from 00>.
  Impact: <why it makes the target more/less trustworthy or adoptable>.
  (3-8 findings, ranked)

## False-pass hypothesis
<one concrete case the repo's QA (or ours) would wrongly accept, or "none found">

## False-fail hypothesis
<one concrete case it would wrongly reject, or "none found">

## Adoption candidate
<single highest-leverage portable function/module with file:line + license, or "none">

## What would change my mind
<the single piece of evidence that would flip my verdict>
```
