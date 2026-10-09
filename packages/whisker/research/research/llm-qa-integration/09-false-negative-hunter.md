# 09 - False-Negative-Hunter

**Verdict:** usable-with-conditions — the deterministic-gates + advisory-LLM split matches all 31 reference repos (00-baseline §2, 05-web Q1/Q4), but several olmOCR-style defect classes still false-pass both lanes when tokens are preserved and the LLM never runs or sanctions the corruption.
**Confidence:** high

## Findings

- [CRITICAL] **Math symbol/variable substitution passes gates + multiset recall + PDF lane.** Evidence: olmOCR `MathTest.run` requires exact string match OR KaTeX render equality (`packages/whisker/research/repos/olmocr/olmocr/bench/tests.py:592-608`; 05-web Q5: "math symbols" as machine-checkable facts). Whisker `content_recall`/`unigram_coverage` count token multiset only (`metrics.py:372-389`, `score.py:149-155`); swapping `x`→`y` in `$f(x)$`→`$f(y)$` leaves recall at 1.0. Lane 3 `FACT_MATH` checks presence of one expression on `_math_surface` (`facts.py:445-447`), not cross-equation variable integrity; fleet gate does not call `check_facts` (5-paper corpus only, `whisker/CLAUDE.md` comprehension section). PDF lane collapses all fidelity into one `structure` axis finding (`pdf_judge.py:382-387`) with no math-specific contract beyond generic "math" in the prompt (`pdf_judge.py:179-181`). Impact: olmOCR would fail a swapped-variable fact test; neither deterministic lane nor default full-run LLM (clean pass, selection gap in baseline §4) reliably catches it.

- [CRITICAL] **Table row/column permutation is token-preserving; olmOCR `TableTest` catches it, our fleet gate does not.** Evidence: olmOCR validates target cell plus directional neighbors with fuzzy floor (`tests.py:342-418`). Whisker has identical neighbor logic in `facts.py:_check_table` (`facts.py:387-390`, table type at `facts.py:466-467`) but Lane 3 gates only authored `checked: verified` facts (37 facts / ~381 papers, `whisker/CLAUDE.md`). Deterministic `_decide` never inspects table grids (`score.py:136-231`). Text-lane prompt explicitly names row/cell swap as the deterministic blind spot (`tapetum_llm.md:84-85`) yet `--review-all` skips clean-pass papers (baseline §4 selection gap; `adjudicate.py:98-100`). Impact: straw-poll column shift (SF/F/N/A permuted) ships at pass/1.00 unigram; olmOCR bench would fail one neighbor fact.

- [HIGH] **`auto_baseline_checks` + repeat-ngram mojibake logic exist but do not gate the fleet.** Evidence: `auto_baseline_checks` implemented (`facts.py:648-691`), thresholds named (`constants.py:190-197`), documented as "not yet wired" (`whisker/CLAUDE.md` known gaps #4). `mojibake_count` is recorded on the sidecar (`score.py:310-312`) and triggers LLM candidate selection only (`adjudicate.py:119-120`), never `_decide` (`score.py:287-297`). olmOCR per-page baseline tests reject repeating n-grams (`tests.py:520-526`, cited in per-page-judging `19-false-pass-hunter.md:14`). Impact: duplication/degeneration defects (page text copied twice) false-pass deterministic gate and LLM when selection gap applies; cheapest olmOCR-class fix is already written.

- [HIGH] **Cross-page section reorder false-passes: reorder signal computed but never gated.** Evidence: `coverage` (5-gram, order-sensitive) is explicitly NOT a verdict flag (`score.py:149-155`, `constants.py:20-36`); `unigram_coverage` stays high when all sections exist. `COV_UNIGRAM_GAP_TRIGGER=0.15` flags scramble for LLM `--review-all` only (`tapetum_llm/constants.py:82`, `adjudicate.py:121-124`), not in `_decide`. Per-page PDF escalation explicitly excludes document-wide reorder (`pdf_judge.py:216-217`). olmOCR `TextOrderTest` requires `before_match.start < after_match.start` (`tests.py:214-226`). Impact: pages 4–6 permuted in markdown matches per-page-judging false-pass hypothesis (`research/per-page-judging/19-false-pass-hunter.md:26-27`); both lanes accept.

- [HIGH] **Front-matter `document` revision corruption is LLM-only; deterministic gate checks keys, not values.** Evidence: `_gate_front_matter` requires only `title` and `document` keys present (`gates.py:34,60-75`); no WG21 id shape or revision-letter check. Conversion contract tells the LLM wrong revision is a defect (`tapetum_llm.md:45`) but PDF judge contract only maps title block to YAML keys (`pdf_judge.py:132-136`). Impact: `document: P1234R4` in front matter when source is P1234R5 passes all six hard gates; unigram identical; xrefs axis may catch IF LLM runs, not deterministic.

- [MED] **PDF-text lane sanctions figure-imaged text, hiding real prose loss.** Evidence: `_CONVERSION_CONTRACT` instructs judge never to flag text "rendered INSIDE a figure or image" as missing (`pdf_judge.py:147-149`). Converter misclassifying body prose as figure (common on diagram-heavy NB papers) yields LLM `content_missing=false` on escalation (`pdf_judge.py:220-222`). No deterministic counter-check. Impact: false pass on content that exists in PDF text layer but is contractually invisible to the judge; reference repos with pixel/VLM paths (MinerU, surya) do not share this specific sanction but also lack a deterministic prose oracle.

- [MED] **Pipe-in-cell table split has prompt coverage only, zero deterministic detector.** Evidence: text-lane table rules flag unescaped `|` splitting a cell (`tapetum_llm.md:85-86`). No match in `gates.py`, `facts.py`, or `tables.py` (repo grep). Token multiset unchanged when one cell becomes two columns. Impact: wide poll tables silently misread by downstream LLMs; marker retries on low self-score (`00-baseline.md:26`, `llm_table.py:213-225`) but production whisker path has no analogue.

- [LOW] **Cheapest deterministic detectors ranked (implementation cost ascending).**
  1. Wire `auto_baseline_checks` into `_decide` as soft/hard flags (~10 LOC glue; logic at `facts.py:648-691`, thresholds at `constants.py:190-197`) — closes olmOCR baseline + duplicate-content class.
  2. Promote existing `uni - cov > COV_UNIGRAM_GAP_TRIGGER` from LLM-only selector (`adjudicate.py:121-124`) to deterministic soft flag in `_decide` (~5 LOC) — closes cross-page reorder without new deps; signal already on every sidecar.
  3. `_gate_pipe_in_cell`: scan pipe-table rows for odd pipe count vs header (~15 LOC in `gates.py`, reuse `tables.parse_pipe_tables`) — closes pipe-in-cell class prompt mentions.
  4. HTML source↔markdown heading-outline diff via existing `html_outline.extract_heading_outline` + `metrics._parse_headings` (~30 LOC, golden-qa-gap T3.3; HTML-only).
  5. Per-page scoped `facts._check_table` against text-layer page slices (medium; olmOCR `TableTest` parity, reuses `facts.py`).
  6. olmOCR-style KaTeX render-compare for math facts (high; new Node/KaTeX dep, `tests.py:561-608`).

## False-pass hypothesis

A WG21 poll table where the SF/F/N/A/SA header row is permuted to F/SF/A/SA but every cell token remains in the markdown: `run_gates` passes (`gates.py:209-218`), `unigram_coverage=1.00`, `mojibake_count=0`, no `COV_UNIGRAM_GAP` soft flag in `_decide`. Full-run tapetum skips LLM on clean pass (selection gap, baseline §4). olmOCR `TableTest` with one verified neighbor fact fails (`tests.py:415-418`); whisker fleet accepts.

## False-fail hypothesis

Promoting `COV_UNIGRAM_GAP_TRIGGER` to a hard gate on a faithfully reflowed multi-column PDF: high `unigram_coverage` with low shingle `coverage` is documented as benign reflow (`score.py:149-155`, `constants.py:28-29`). A hard gate would false-fail papers tomd already ships today; soft review only is the safe operating point (golden-qa-gap T2.1 precedent for provisional edges).

## What would change my mind

Replay of three synthetic corruptions (math variable swap, table column permute, section reorder) through the live stack with (a) `auto_baseline_checks` + `COV_UNIGRAM_GAP` wired into `_decide` and (b) full-run LLM on all passes: if all three demote to review/fail with zero reflow false-fails on 10 known-clean papers, downgrade verdict to **usable** and defer table/math render checks to corpus authoring only.
