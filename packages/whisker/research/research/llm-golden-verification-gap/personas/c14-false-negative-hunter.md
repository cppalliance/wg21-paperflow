# c14 - False-negative hunter

**Verdict:** usable-with-conditions (Fourteen contract-grounded scenarios beyond the two known incidents share a repeatable kill pattern: eleven never emit a matching router signal, two more lose the defect unit to `MAX_UNIT_CHECKS`, and only one reaches the unit LLM on the wrong signal and false-clears; the table is systematic evidence that recall is lost upstream of grounding, not fixable by verification alone.)
**Confidence:** high

## Findings

- [CRITICAL] Eleven of fourteen new scenarios die at `source_router` with no signal whose semantics target the verified defect class. Evidence: PDF router reads only `token_delta`, `low_recall`, `missing_captions`, and title-presence `heading_drift` (`source_router.py:166-231`); HTML router adds `missing_code` block-count only (`source_router.py:248-314`); `PageUnit.has_tables` / `SectionUnit.has_tables` and list/table/inline structure are extracted then ignored (`textlayer.py:86-97`, `html_outline.py:43-55`, `source_router.py:191-231`). Impact: golden-contract defects that preserve word tokens (list cardinality, punctuation-only loss, delimiter debris, table permutations, fence language) are invisible before any unit call. Answer-class: 2.

- [CRITICAL] Scenario table (per-stage survival for golden-contract defects **excluding** the two baseline blockers SF poll-header cell and HTML `span.secno` labels). Stages: **Route** = matching `RiskSignal`; **Budget** = unit ID selected within `MAX_UNIT_CHECKS=5` (`constants.py:223`, `unit_judge.py:225-241`); **Prompt** = defect class named in `UNIT_CHECK_SYSTEM_PROMPT` / metadata prompt with contract rule stated; **Ground** = claim could survive `verify_unit_evidence` (`unit_judge.py:493-565`); **Report** = accepted into `defect_groups` and fusion inspect (`fusion.py:227-235`). **Kill** = first stage that prevents naming the defect in the merged report.

| # | Scenario (contract rule; concrete anchor) | Route | Budget | Prompt | Ground | Report | Kill |
|---|-------------------------------------------|:-----:|:------:|:------:|:------:|:------:|------|
| 1 | **Ordered-list collapse** — nested ordinals must preserve item boundaries (`.claude/skills/tomd-review/SKILL.md` lists); PR #286 historical page 10: two groups 2+3 items → 1+1 (`PR286-LLM-FALSE-CLEAR.md` §5, page 10) | N | — | Y | — | N | **Router** |
| 2 | **Subordinate heading flatten** — visual sub-headings must become ATX headings, not prose; PR #286 pages 9–10 three flattened titles (`PR286-LLM-FALSE-CLEAR.md` §5) | Partial† | N | Partial | — | N | **Budget** |
| 3 | **Inline-code delimiter debris** — one listing, intact fences; PR #286 pages 12–13 rendered `` ` `` residue in code (`PR286-LLM-FALSE-CLEAR.md` §5, page 13) | N‡ | Y‡ | Y | — | N | **Model** |
| 4 | **Punctuation-only normative loss** — operators preserved in structure review; PR #286 page 7 missing `N>.` (`PR286-LLM-FALSE-CLEAR.md` §5.1) | N | — | Y | — | N | **Router** |
| 5 | **Inline-code adjacency** — space after `` ` `` significant; PR #295 `` `constexpr`contexts `` (`PR286-LLM-FALSE-CLEAR.md` §Validation, item 1) | N | — | Partial | — | N | **Router** |
| 6 | **Grave-accent MD consumption** — citation punctuation must not become code fences; PR #295 P3391 backticks (`PR286-LLM-FALSE-CLEAR.md` §Validation, item 2) | N | — | N | — | N | **Router** |
| 7 | **`<cite>` emphasis loss** — structural link/citation shape; PR #295 two `<cite>` units (`PR286-LLM-FALSE-CLEAR.md` §Validation, item 4) | N | — | N | — | N | **Router** |
| 8 | **Poll subsection depth** — top-level numbered poll should be `##`, not `###`; fixture `p4016r0.golden.md:53` `### Poll 1` vs contract H2 floor (`tomd-review/SKILL.md` headings) | N§ | — | Y | — | N | **Router** |
| 9 | **Fence language label** — every source listing needs `` ```cpp ``; `missing_code` compares counts only (`source_router.py:302-314`, `html_outline.py:145-146`) | N | — | Partial | — | N | **Router** |
| 10 | **Split code listing** — one source `<pre>` must be one fence; no router hook for fence cardinality vs source spans | N | — | Y | — | N | **Router** |
| 11 | **Table row/column swap** — GFM row fidelity; token multiset unchanged; `has_tables` unread (`source_router.py:191-231`) | N | — | Y | — | N | **Router** |
| 12 | **Dropped figure/image reference** — structure includes figures; `has_images` unused (`textlayer.py:93-94`, `html_outline.py:53`, `source_router.py:191-231`) | N | — | Partial | — | N | **Router** |
| 13 | **Front-matter key order** — fixed YAML order (`tomd-review/SKILL.md` front matter); no router signal; metadata LLM sees both sides but contract order not encoded (`unit_judge.py:78-91`) | N | — | Partial | Partial | N | **Router** |
| 14 | **Nested bullet indent** — two spaces per nesting level; no `<ol>`/`<li>`/indent compare in router (`source_router.py:70-142`) | N | — | N | — | N | **Router** |

† Page 9 routed medium `heading_drift` for unrelated prose fragments, not flattening class; displaced by lexical sort (`unit_judge.py:225-241`, historical PR #286 replay in `PR286-LLM-FALSE-CLEAR.md` §6.2). ‡ Page 13 checked for heading signal, not code; unit returned `pass` at confidence 1.0 (`PR286-LLM-FALSE-CLEAR.md` §6.4). § PDF `heading_drift` tests title token presence only (`source_router.py:218-221`), not ATX depth; HTML compares raw tag level, not golden depth+1 mapping.

- [HIGH] Budget starvation displaces real units even when pages are routed for unrelated signals. Evidence: baseline PR #286 routed pages 8/9 for non-table reasons but checked only 1,2,3,4,13 (`00-baseline.md` PR #286); historical replay left page 9 routed/unchecked and never routed page 10 (`PR286-LLM-FALSE-CLEAR.md` §6.2); sort key is severity then lexical `unit_id` (`unit_judge.py:225-241`). Impact: scenario 2 and the known SF-table case share the same kill stage despite different defect classes. Answer-class: 2.

- [HIGH] Contract-encoding gap blocks metadata and title-matching paths for normalization-only defects. Evidence: `html_outline.py:79-81` concatenates all heading descendants including `span.secno`; `route_html_units` matches `_text_key(source_title)` to candidate titles (`source_router.py:253-274`); metadata prompt never states secno-stripping or section-depth mapping (`unit_judge.py:78-91`, `tomd-review/SKILL.md:53-59`); baseline PR #295 metadata/outline `pass` with empty `heading_drift` (`00-baseline.md`). Impact: scenarios 8 and 13 cannot be enforced by outline compare even if a unit were checked. Answer-class: 1.

- [HIGH] Prompt taxonomy lists `table_corruption`, `code_loss`, and `punctuation_loss` but omits list cardinality, fence language, cite shape, and golden depth rules. Evidence: `UNIT_CHECK_SYSTEM_PROMPT` defect list (`unit_judge.py:102-106`); conversion contract explicitly sanctions YAML/TOC/reflow (`unit_judge.py:67-75`) without golden ideal rules; observed page-13 unit discussed headings/URLs, not delimiter debris (`PR286-LLM-FALSE-CLEAR.md` §6.4). Impact: scenario 3 reaches the model yet false-clears; scenarios 6–7, 14 lack describable taxonomy even if routed. Answer-class: 1 (missing rules) and 3 (capability miss on scenario 3).

- [MED] Grounding and aggregation are precision-only: zero generated claims yield zero verified groups. Evidence: `verify_unit_evidence` operates on model-emitted defects only (`unit_judge.py:493-565`); baseline PR #295 generated claims 0, accepted groups 0 (`00-baseline.md`); `verdict_matches_defects` accepts pass-with-empty-defects (`models.py:315-320`, `00-baseline.md`). Impact: all router-killed scenarios never reach grounding; scenario 3 fails before grounding because the model emits no defect quote. Answer-class: 4.

- [MED] Fusion `review` from `source_aware_review_cap` is not defect detection. Evidence: both baseline runs fused `review` with 0 accepted defect groups (`00-baseline.md` PR #286/295); `_accepted_unit_defects` requires `GROUND_EXACT` + `CANDIDATE_NOT_FOUND` (`fusion.py:219-235`). Impact: thirteen of fourteen scenarios produce coverage-capped `review` at most, not a named punch-list item. Answer-class: 4 and 5.

- [LOW] Full LLM verification of golden punch-list items is the wrong metric without deterministic tripwires for countable structure. Evidence: 0/31 surveyed repos gate on LLM (`00-baseline.md` stability facts); scenario table shows 12/14 defects never reach the unit LLM; only deterministic Lane 3 facts catch table cells when authored (`whisker/CLAUDE.md` Lane 3). Impact: honest ceiling is hybrid: LLM triage plus encoded contract checks, not 100% recall on skill-only rules. Answer-class: 5.

## False-pass hypothesis

P1068R11 historical candidate (pre-table-fix replay): pages 7, 9, 10, and 12–13 each carry a distinct golden-contract structural defect (punctuation loss, flattened sub-headings, collapsed ordered lists, inline delimiter debris). Deterministic whisker passes all gates with QA 100; the source-aware lane routes nine medium `heading_drift` pages, checks five unrelated units, emits zero accepted defect groups, and fuses `review` only via `source_aware_review_cap`—exactly the false-clear shape scenario rows 1–4 and 8–14 predict.

## False-fail hypothesis

P3953R0 HTML: `_SectionExtractor` includes `<script>`/`<style>` text in section bodies (`html_outline.py:168-172`), producing `section:6` `low_recall` 0.0437 (baseline `00-baseline.md`) and consuming budget on a polluted packet while secno-heading sections remain unchecked—routing noise masquerading as high-severity structural risk without a real golden defect.

## What would change my mind

A replay at baseline SHAs where each scenario row’s defect unit receives a dedicated router signal (or deterministic pre-check) **before** unit selection, the unit LLM emits a grounded `source_quote` for that defect, `verify_unit_evidence` returns `candidate_not_found` or equivalent structural refutation, and `defect_groups` lists the punch-list item in the inspect report—not merely `source_aware_review_cap` with zero groups.
