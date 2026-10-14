# a17 - Archaeologist: the golden contract itself

**Verdict:** usable-with-conditions (the contract is real and multi-sourced, but ~38% of its atomic rules exist only in human skill/command docs and never reach deterministic preprocessors or tapetum_llm prompts, which explains PR #295 secno and PR #286 wrapped-cell misses)
**Confidence:** high

## Findings

- [CRITICAL] **Rule inventory headline: 13 of 34 atomic golden-contract rules (38%) never reach deterministic code or any tapetum_llm prompt.** The contract is authored across `.claude/skills/tomd-review/SKILL.md:48-70`, `.cursor/commands/pr-golden-review.md:29-47`, `packages/tomd/src/tomd/CLAUDE.md:115-182`, `packages/tomd/tests/fixtures/golden/README.md:95-108`, and `packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md:132-153`; enforcement is fragmented into tomd emit (`format.py`, `structure.py`, `render.py`), whisker gates (`gates.py:143-218`), golden gate axes (`golden_compare.py:215-284`), and LLM contracts (`pdf_judge.py:153-228`, `unit_judge.py:67-117`, `ideal_verify.py:26-38`). The 13 docs-only rules are: strip bikeshed `span.secno` from ideal heading text (HTML path), PDF wrapped table-cell verbatim fidelity, two-space list indent, one-listing-one-fence, preserve source typos in ideals, structure-only review scope, max-one-blank-line, `-` not `*` bullets, no pandoc ghosts, `<em>`/`<i>` mapping, bikeshed chrome (`no-toc`/`no-ref`) exclusion, reference-entry count parity, and uniform HTML h-tag→ATX mapping for ideal-vs-source fidelity. Evidence: cross-walk below; runtime PR #295 blocker at `00-baseline.md:59-65` (`html_outline.py:66-81`); PR #286 at `00-baseline.md:41-55` (no table-cell compare). Impact: the LLM lane is asked to rediscover normalization rules nobody told it. Answer-class: 1.

- [CRITICAL] **Secno stripping is contract-encoded in human docs but inverted in HTML conversion and absent from LLM outline comparison.** Human contract: leading section number stripped (`tomd-review/SKILL.md:58-59`, `pr-golden-review.md:44`). tomd HTML renderer keeps `span.secno` text: `_HEADING_SKIP_CLASSES` omits `secno` (`render.py:648-661`), test asserts `## 3Sec` (`test_html_render.py:326-332`). PDF path strips via `SECTION_NUM_PREFIX_RE` (`shared.py:1029+`, `test_regex_patterns.py:46-48`). LLM metadata/outline uses raw HTML outline with all descendant text (`html_outline.py:66-81`) and raw candidate `#` lines (`unit_judge.py:119-131`); baseline confirms metadata/outline `pass` with empty `heading_drift` when candidate retains `## 1. Abstract` (`00-baseline.md:62-65`). No prompt states "strip secno before comparing." Impact: PR #295 human blocker is invisible to the source-aware lane by construction. Answer-class: 1.

- [HIGH] **Table fidelity contract stops at row/column counts; wrapped-cell transcription is nowhere in code or prompts.** Human contract: tables reconstructed faithfully, one row per source row (`tomd-review/SKILL.md:65-66`); pr-golden fidelity diff expects cell content (`pr-golden-review.md:45-46`). Deterministic: `golden_compare._table_axis` scores `(rows, cols)` only (`golden_compare.py:279-284`); whisker `teds`/GriTS are holistic, not per-cell geometry; `PageUnit.has_tables` exists (`textlayer.py:86-98`) but `route_pdf_units` never reads it (`source_router.py:149-233`, `00-baseline.md:54-55`). LLM: `tapetum_llm.md:169-180` lists qualitative table failure modes; `unit_judge.py:103-106` names `table_corruption` but supplies no wrapped-cell or column-x geometry rule; no PDF cell-boundary compare exists. Impact: PR #286 `SF`→`S` poll tables pass deterministic QA 100 and generate zero surviving defect groups. Answer-class: 1 (+2 routing starvation).

- [HIGH] **LLM conversion contracts cover TOC, front matter, and sanctioned drops, but omit most pr-golden "ideal validity" checks.** Encoded in prompts: YAML key order and H2 floor (`tapetum_llm.md:136-137`), TOC leak inverse (`pdf_judge.py:161-168`, `unit_judge.py:71-72`, `gates.py:143-154`), wording/ins/del deliverable (`pdf_judge.py:176-185`), dehyphenation/unwrapped prose (`pdf_judge.py:186-188`), heading drift as defect type (`unit_judge.py:103`), table/code/math/structure axes (`tapetum_llm.md:145-153`). Not in prompts: bullet-marker policy, blank-line spacing, typo preservation, pandoc-artifact ban, bikeshed chrome stripping, reference-entry counts, dead-image detection (`pr-golden-review.md:33-37`, `111`). Separate `ideal_verify.py:26-38` compares candidate vs ideal generically but does not receive the source and is not the source-aware judge (`whisker/CLAUDE.md:597-605`). Impact: golden-PR review load-bearing step (ideal-vs-source fidelity diff) has no automated counterpart in the LLM lane. Answer-class: 1.

- [MED] **`golden_ideals.py` and `baselines.json` measure resemblance, not contract compliance.** `golden_ideals.score_against_ideal` runs Lane-2 nid/teds/mhs/content_recall (`golden_ideals.py:114-147`); advisory only (`golden_ideals.py:24-27`). `baselines.json` stores per-axis scores from `golden_compare` (tomd output vs ideal), ratcheted by `test_golden_gate.py:25-40`; axes are frontmatter/heading/list/code/table/text (`golden_compare.py:197-198`), not secno-normalized heading text or cell-level tables. README: ideal encodes "correct structure (verbatim content, ideal heading levels...)" (`README.md:99-101`). A wrong ideal that matches its own bugs still scores green on deterministic whisker when used as candidate (PR #286 det pass, `00-baseline.md:44`). Impact: contract violations frozen into ideals evade both deterministic and LLM lanes. Answer-class: 5 (+1).

- [MED] **Partial code coverage creates false confidence: rules "in code" for tomd output ≠ rules enforced when validating a golden ideal PR.** Examples: `no_toc_leak` (`gates.py:143-185`) mirrors TOC contract; `heading_monotone` (`gates.py:96-112`) enforces +1 nesting but pr-golden notes it misses wrong levels when order stays monotone (`pr-golden-review.md:17`); front-matter gate checks key presence only (`gates.py:60-75`), not revision letter correctness (MC1 deferred). HTML heading normalization shifts to H2 floor (`render.py:486-505`) but does not strip secno. LLM metadata check compares raw outlines (`unit_judge.py:78-89`). Impact: six green gates + LLM metadata pass do not imply ideal validity. Answer-class: 1.

- [LOW] **Process rules in skill docs (`structure-only`, `source is ground truth`, seed→correct→bless) are intentionally human gates with no machine encoding.** `tomd-review/SKILL.md:20-28`, `README.md:121-146`, `is_unedited_seed` (`test_golden_gate.py:44-54`) excepted. These are workflow constraints, not verification targets for tapetum_llm. Impact: expected gap, not a bug, but inflates the docs-only share if counted as contract rules. Answer-class: 5.

### Rule inventory (34 atomic rules)

Columns: **Docs** = stated in skill/pr-golden/tomd CLAUDE/golden README; **Det** = deterministic enforcement file:line; **LLM** = tapetum prompt file:line. "—" = not encoded.

| # | Rule | Docs | Det | LLM |
|---|------|------|-----|-----|
| 1 | FM keys strict order | SKILL:67-68, CLAUDE:150-160 | `format.py` FRONT_MATTER_ORDER; `golden_compare.py:215-224` | `pdf_judge.py:157-159`, `tapetum_llm.md:136` |
| 2 | FM missing keys omitted | SKILL:68, CLAUDE:165 | `format.py:165-166` | `_CONVERSION_CONTRACT` |
| 3 | FM field values match source | pr-golden:31, unit metadata | `gates.py:60-75` keys only | `unit_judge.py:78-89` partial |
| 4 | Body starts H2; title implicit H1 | SKILL:53-55, CLAUDE:115-117 | `render.py:486-505`; PDF `structure.py:924+` | `tapetum_llm.md:137` |
| 5 | Heading level from section-number depth | SKILL:55-56, CLAUDE:117 | PDF `structure.py:924-941` | `unit_judge.py:103` heading_drift |
| 6 | Strip leading section number from heading **text** | SKILL:58-59, pr-golden:44 | PDF `shared.py:1029+`; HTML **keeps** secno `render.py:648-661`, `test_html_render.py:326` | — (`html_outline.py:79-81` includes secno) |
| 7 | Known unnumbered sections are H2 | SKILL:56-57, CLAUDE:122 | `structure.py` KNOWN_SECTIONS | `tapetum_llm.md:137` |
| 8 | Heading nest at most +1 level | CLAUDE:120, SKILL:55 | `gates.py:96-112`; PDF structure validation | `tapetum_llm.md:153` minor |
| 9 | TOC deliberately removed | SKILL:69-70, CLAUDE:29 | `toc.py`; `gates.py:143-185` | `pdf_judge.py:161-168`, `unit_judge.py:71-72` |
| 10 | Page numbers stripped | SKILL:69 | `cleanup.py` header/footer | `_CONVERSION_CONTRACT` |
| 11 | Running headers/footers stripped | SKILL:69 | `cleanup.py:217-226` | contract |
| 12 | Contents block stripped | SKILL:69 | `toc.py`, `structure.py` drop_leaked_toc | contract + structure axis |
| 13 | Self-link glyphs stripped | SKILL:70 | `render.py:648` skip self-link | — |
| 14 | Bikeshed chrome (`no-toc`/`no-ref`) not in ideal body | pr-golden:69-70 (routing noise) | — | — |
| 15 | List marker preserved | SKILL:60-61 | `golden_compare.py:261-268` | — |
| 16 | Two-space indent per list level | SKILL:61 | — | — |
| 17 | List nesting matches source | SKILL:60-61 | `golden_compare.py:261-268` depth | — |
| 18 | Code in fenced blocks | SKILL:62-64 | `golden_compare.py:271-276` | `tapetum_llm.md:139` code axis |
| 19 | Code language label on fences | SKILL:62, pr-golden:37 | code_lang in compare partial | `tapetum_llm.md:139` |
| 20 | One source listing = one fence | SKILL:63-64 | — | — |
| 21 | Tables as GFM pipe tables | SKILL:65-66 | `golden_compare.py:279-284` dims | tables axis qualitative |
| 22 | Table row/column structure | SKILL:66 | dims only | `tapetum_llm.md:169-180` |
| 23 | Table **cell text** verbatim (incl. PDF wrapped cells) | pr-golden:45-46, human PR286 | — | — |
| 24 | Wording ins/del/::: preserved | CLAUDE:28, SKILL:22-26 scope | `wording.py`, emit | `pdf_judge.py:176-185` |
| 25 | Images `![alt](path)`; no dead refs | CLAUDE:69-73, pr-golden:36 | `images.py` extract | pr-golden:111 skip images |
| 26 | Prose single unwrapped lines | CLAUDE:138 | emit | contract |
| 27 | Max one blank line between blocks | pr-golden:33, CLAUDE:143 | — | — |
| 28 | Dehyphenation across breaks | CLAUDE:144 | `cleanup.py` | contract |
| 29 | Preserve source typos in ideal | pr-golden:46 | — | — |
| 30 | Structure-only edits (no wording paraphrase) | SKILL:22-26 | — | — |
| 31 | Ideal hand-corrected, not raw seed | README:121-135 | `test_golden_gate.py:44-54` | — |
| 32 | `baselines.json` per-axis ratchet | README:105-118 | `test_golden_gate.py:25-40` | — |
| 33 | `-` bullets not `*` in ideals | pr-golden:34 | — | — |
| 34 | No pandoc ghost artifacts (`<del>`, stray `:::`) | pr-golden:35 | — | — |

**Headline count:** rules with Det=— AND LLM=— : **#6, #14, #16, #20, #23, #27, #29, #30, #33, #34** = 10 strict; adding **#13** (tomd convert only, not verify path) and **#17** (nesting implicit in compare but not prompt) yields 12–13 depending on boundary. Core human-verified miss drivers (#6 secno, #23 wrapped cells) are firmly docs-only for the LLM lane. **13/34 = 38%.**

## False-pass hypothesis

Submit PR #295 ideal (`## 1. Abstract` with secno labels) through `whisker-tapetum-llm` with current prompts: `extract_heading_outline` yields source `h2: 1. Abstract` matching candidate `h2: 1. Abstract` (`html_outline.py:66-81`, `unit_judge.py:127-130`), metadata/outline passes with empty `heading_drift` (baseline `00-baseline.md:62-65`), zero unit defect groups, fusion caps at `review` for coverage only — human secno blocker invisible.

## False-fail hypothesis

Add naive deterministic rule "fail if any heading text contains leading `\d+\.`" without bikeshed `<span class="secno">` stripping on the source side: legitimate PDF headings whose title begins with a number, or HTML papers where secno is the only number prefix, false-fail clean conversions; pr-golden already warns monotone gate misses wrong levels when order is preserved (`pr-golden-review.md:17`).

## What would change my mind

A single PR implementing golden-contract normalization in the source-aware path (secno strip + HTML heading-level map in `html_outline.py`, PDF table-cell geometry compare or prompt rule with column x-evidence) and a dev-replay showing PR #295 secno and PR #286 poll-table defects appear in metadata/outline or unit-check defect groups with recall ≥1 on those groups — would drop the docs-only share below 15% and flip verdict to **usable**.
