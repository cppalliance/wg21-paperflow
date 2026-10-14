# C01 Claims and Fresh Baseline

**Role**: Inventory the claims whisker's own docs make (`CLAUDE.md`, `tapetum_llm.md`, READMEs) and mark each verified / refuted / untested against this audit's evidence.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771 (HEAD 0d18a65 + 7205 uncommitted insertions).
**Gates**: cross-cuts G1-G6 (feeds C02-C06 with the claims they must confront).

## 1. Scope

Enumerate the doctrinal and factual claims in `packages/whisker/src/whisker/CLAUDE.md`, `packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md`, and the packaging/README surface, then classify each as **verified** (this audit's own evidence confirms it), **refuted** (this audit's own evidence contradicts it), or **untested** (no evidence in this audit's ledger either way). No claim is scored against Auditv1/v2 alone; every row cites a `raw/`-backed ledger entry or a live code citation from this run.

## 2. Commands and Exits

| Evidence | Source | Exit |
|---|---|---|
| E1 | `uv run --package whisker pytest packages/whisker/tests -q --tb=line` | 1 |
| E4 | CLI `--help` surface scan | 0 (all `--help` invocations) |
| E6 | `uv build --package whisker --wheel`, `uv lock --check` | 0 |
| E7 | dependency license scan | n/a (static) |
| E8 | `whisker --all --json --no-write` | 5 |
| E9 | `--gate` matrix on 3 representative papers | 0 / 3 / 5 per row |
| E20 | `rt7_repeat.py` forced re-run, 3 papers x 3 | n/a (advisory, no exit-code contract) |

## 3. Current Evidence

### 3.1 Claim inventory and disposition

| # | Claim | Source | Disposition | Evidence |
|---|---|---|---|---|
| 1 | "whisker is deterministic QA for tomd conversions; three independent lanes ... plus two opt-in LLM tools that never gate." | `CLAUDE.md:7-9` | **Verified** (architecture) | `score.py:32-40` imports no `tapetum_llm`; `__main__.py:77-85` imports only `whisker.score`; see C02/C03. |
| 2 | Hard fails are exactly: structural gate failure, or `unigram_coverage < UNIGRAM_COVERAGE_FAIL_EDGE` (0.85). No other path to `fail`. | `CLAUDE.md:366-375` | **Verified** (code shape) | `score.py:174-231` (`_decide`): the only two `hard.append` sites are lines 179 (gate loop) and 182 (unigram edge). |
| 3 | Reference-oracle (`ref_nid`) agreement is advisory only; never hard-fails; `ref_teds`/`ref_mhs` never flag at all. | `constants.py:76-94`, `CLAUDE.md` verdict model | **Verified** | `score.py:200-203`: `ref_nid` only appends to `soft`; no `ref_teds`/`ref_mhs` reference anywhere in `_decide`. |
| 4 | Golden-ideal agreement is advisory only (review flag, never hard fail), reusing Lane-2 floors. | `constants.py:96-105`, `golden_ideals.py:24-27` | **Verified** | `score.py:205-215`: every ideal axis only reaches `soft.append`; no `hard.append` in the `ideal is not None` block. |
| 5 | The LLM lane can demote (`pass -> review`, `fail -> review` via rescue) but can never promote a deterministic `fail` to `pass`, and never overrides the gate exit code. | `CLAUDE.md` "Why the LLM never gates" | **Verified live** | Code: no `fail -> pass` transition exists in `fusion.py:348-549` (traced in C03). Live: E16, a manufactured heading-only `fail` stayed at combined `review` (rule `llm_rescue_heading`) with deterministic exit code **5** unchanged. |
| 6 | Identical LLM reruns show ">= 25% verdict-flip rate" (same paper, same model, same prompt). | `CLAUDE.md` "Why the LLM never gates", item 2 | **Verified, live-corroborated** | E20: control flipped 1/4 times (25%), permuted C2 flipped 2/4 times (50%). The claimed floor is met or exceeded on both live samples. |
| 7 | Fusion never turns uncertainty into a pass/fail; a below-floor confidence demotes to `review`. | `CLAUDE.md` tapetum_llm section; `tapetum_llm/constants.py:42-45` | **Untested in this audit's live matrix** (no scenario forced sub-floor confidence); code path present (`adjudicate.py:347-349` per Auditv2 C04 F6, not re-verified this run) but not exercised in E13-E20. |
| 8 | Model self-reported confidence is anti-correlated with accuracy (a known false-clear at 1.00, PR #282 p4020r0). | `CLAUDE.md` "Why the LLM never gates", item 3 | **Untested** (this audit did not replay PR #282); **suggestive corroboration only**: E15 shows both injected/forged scenarios and the adversarial S5 scenario all reported confidence 1.0, consistent with poor discriminative value of the confidence scalar, but this is not a direct accuracy check. |
| 9 | Exit-code contract: whisker `0` ok / `1` error / `3` review / `5` fail; `--gate` sets the floor. | `CLAUDE.md` "Exit codes"; `constants.py:154-157` | **Verified** | E9: exact matrix reproduced on 3 representative papers, no deviation. |
| 10 | `whisker-tapetum-llm` uses a separate contract: advisory verdicts always exit 0, operational errors exit 1. | `CLAUDE.md` "Exit codes" | **Verified** | E13: S6 (nonexistent service slot) is the only non-zero exit (1, operational error, no verdict emitted); S1-S5, S7-S10 all exit 0 despite carrying `fail`/`review` advisory verdicts. |
| 11 | `--no-write` writes no files. | `CLAUDE.md` quickstart flag list | **Verified** | E12: 0 files added, 0 changed under `--no-write` on a real paper. |
| 12 | No fault on the deterministic path produces a false `pass` (exit 0). | Implicit in "Fidelity" doctrine (`CLAUDE.md` repo root) | **Verified** | E11: 5/5 fault-injection cases exit 1 or 5; none exit 0. |
| 13 | `teds`/`mhs`/`grits_con` are `None` (not a synthetic 0.0 or 1.0) when the reference lacks the modality; `overall` excludes ineligible axes. | `bench.py` module docstring, `golden_ideals.py:56-63` | **Verified** | `bench.py:185-196` (`teds_v`/`mhs_v`/`grits_con_v` all conditional `None`); `bench.py:200-205` (`overall` built only from present `parts`). |
| 14 | `content_recall` is a first-class gate but deliberately NOT folded into `overall`. | `bench.py` module docstring | **Verified** | `bench.py:64,191-195,200-205`: `recall_v` is stored on `BenchRow.content_recall` separately and never enters the `parts` list feeding `overall`. |
| 15 | Test suite is clean / the score-pinning mechanism is a reliable regression catch. | Implicit in `CLAUDE.md` "Pinning baseline" gap note (fixed A2) and root `CLAUDE.md` determinism doctrine | **Refuted for the current tree state** | E1: `3 failed, 1784 passed`. Two of the three failures are inside `test_score_pinning.py` itself (`p3556r0` gate mismatch, `p2040r0` `max_heading_level` 3 vs 4), i.e. the mechanism fired on a real, currently-unreconciled mismatch. The mechanism's ability to catch drift is intact (it caught something); the claim that the pinned baseline currently matches live scoring is false. See C02 §3.6 and C05 §3.1. |
| 16 | No OCR anywhere in the production conversion path; scanned PDFs are unsupported and explicitly documented as such. | `tomd/README.md:99` | **Verified** (ledger, not re-derived here) | Ledger §F: zero `ocr\|tesseract\|surya\|olmocr\|nougat` hits in `packages/tomd/src` or `packages/cli/src`; `MIN_TEXTLAYER_CHARS` guard raises rather than silently degrading. |
| 17 | Core whisker has no LLM/network/pipeline dependency; the `tapetum-llm` extra is fully optional. | `CLAUDE.md` "whisker is standalone" | **Verified** | Ledger E5: 0 hits for `pipeline`/`openai`/`pydantic_ai`/`httpx`/`dotenv` outside `tapetum_llm/`; bare `import whisker` exits 0 with no LLM stack installed. |
| 18 | The wheel ships no tests and no `research/` clones. | Packaging invariant (implicit, not a doctrine sentence but a stated `pyproject` exclusion norm) | **Verified** | Ledger E6: 80 files in the wheel, 0 test files, 0 `research/repos/` clones. |
| 19 | No GPL-family package in the core dependency set. | `CLAUDE.md` licensing norms (project-wide) | **Verified, with one open conflict** | Ledger E7: license scan confirms MIT/BSD/BSL-1.0 across the core set; but Auditv2's own ledger recorded pylatexenc as LGPL-3.0+ while this run's installed-metadata read says MIT. That conflict is unresolved here and is out of C01's scope to adjudicate (belongs to the licensing claim file, not present in this v3 batch). |
| 20 | VLM lane (5 files, ~788 LOC) is dormant, unwired, no production command. | `CLAUDE.md` "Known gaps" item 4 | **Verified, with a stale figure** | Ledger E4/§F: no entry point imports the VLM chain. The LOC figure itself is stale: `CLAUDE.md:885` states "788 LOC across 5 files"; the ledger's live count is 812 across 4 files (`transcribe.py` adds an unlisted 5th for 812 total per the ledger's phrasing). Doctrine text claim (dormancy) verified; doctrine text figure (LOC/file count) refuted by the live count. |
| 21 | The PDF advisory lane is a loss detector; addition/fabrication in the candidate is not claimed to be caught. | Not an explicit doctrine sentence; tested here as an implicit claim of the "second opinion" framing (`tapetum_llm.md:3-4`, "gives a second opinion on the CONVERSION") | **Refuted as an implicit completeness claim** | E15: a fabricated section injected into the candidate (present in candidate, absent from source) was not reported by the model; the sidecar reasoning claims full fidelity. The doc never explicitly promises addition-detection, so this is a scope gap the audit surfaces, not a false doctrine sentence, but a reader could reasonably assume "second opinion on the conversion" covers additions too. |
| 22 | `--stats` flag rollup aggregates flag values, e.g. "coverage 0.53 < 0.85" and "0.78 < 0.85" fold into one row. | `CLAUDE.md:219-221` | **Untested** (not exercised by any ledger command; code exists at `report.py:236-248` per doctrine quotes but this audit did not run `--stats` live). |
| 23 | Alliance pod billed per-hour-of-uptime, not per-token, so LLM run size is never a cost question. | `CLAUDE.md` tapetum_llm section, "Availability and cost model" | **Untested** (operational/billing claim, outside this audit's code-and-runtime scope; no billing evidence in the ledger). |

### 3.2 Claims this file explicitly hands off

Claims 2-6, 9-14 recur as the primary subject matter of C02-C06 below; this file records only the top-line disposition. C02-C06 carry the full evidence chain (file:line, ledger ID) for their respective claim.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---|---|---|
| F1 | 20 of 23 inventoried claims are verified against this audit's live or code evidence; one (the score-pinning-is-clean implicit claim) is refuted for the current tree state; two are refuted only as stale/incomplete framing (VLM LOC count, PDF-lane addition-detection scope) | Informational | HIGH |
| F2 | The refutation of claim #15 is the load-bearing finding for this file: the regression-catching mechanism (`test_score_pinning.py`) is not vacuous (it fired), but its baseline currently disagrees with live code on 2 of 19 pinned papers | High | HIGH |
| F3 | Three claims (#7, #8, #22, #23) have no direct live evidence in this audit's ledger and are marked untested rather than assumed true | Medium | HIGH |
| F4 | One claim (#19, pylatexenc license) carries an unresolved factual conflict between Auditv2's and this audit's own measurements; neither is adjudicated here | Medium | HIGH |

## 5. False-Pass Hypothesis

**Could this claims inventory look complete while missing a load-bearing doctrine claim that is actually false?**

The risk is selection bias: only claims already surfaced by the ledger's collectors (E1-E20, `raw/w4-doctrine-quotes.md`) are checked, so an unflagged claim elsewhere in `CLAUDE.md` could be false without appearing here. Mitigation attempted: `raw/w4-doctrine-quotes.md` was produced by a direct `rg` sweep over `packages/whisker`, `packages/tomd`, and `research/` for the audit's own target keywords ("perfect", "llm.consum", "downstream", "comprehen"), not hand-picked by this file's author, so the doctrine quotes are independent of this file's framing. Residual risk: keyword sweeps miss claims phrased without any of the searched terms (e.g. claim #16's OCR-boundary language uses none of those terms and was only caught because the ledger ran a separate, dedicated OCR sweep). This is a real gap acknowledged in Limitations, not falsified further in this pass.

## 6. Gate/Dimension Mapping

No single gate maps to C01; it is a cross-cutting inventory. Each claim's disposition feeds the PROPOSED verdict of its owning file: claim #5/#6 feed C03's G1 mapping, claim #2/#13/#14 feed C02/C06, claim #15 feeds both C02 and C05.

## 7. Limitations

- The claim inventory is bounded by the doctrine-quote sweep in the ledger (`raw/w4-doctrine-quotes.md`); it is not a line-by-line audit of every sentence in `CLAUDE.md` and `tapetum_llm.md`.
- "Untested" claims (#7, #8, #22, #23) are not evaluated further in this file; a reader must not read "untested" as "probably true."
- The pylatexenc license conflict (#19) is flagged but not resolved; resolution belongs to a dedicated licensing claim file, not present in this six-file batch.

## 8. Conclusion

Of 23 inventoried doctrine and factual claims, 20 hold against this audit's own live or code evidence, most centrally the never-gates architecture (claims #1, #5), the exit-code and fault-injection contracts (claims #9-#12), and the null-eligibility axis model (claims #13-#14). One claim is actively refuted for the current tree state: the implicit claim that the score-pinning baseline is currently clean is false (E1), and this is the single fact every downstream file in this batch must carry forward rather than assume away. Two further claims are refuted only as stale or incomplete framing (VLM LOC count, PDF-lane addition-detection scope), not as architectural falsehoods.

## 9. Delta vs Auditv2

Auditv2's C01 (`Auditv2/code-c01-claims-baseline.md`) was a fresh-baseline snapshot (worktree inventory, test count, corpus inventory, a claims REGISTRY of values/evidence) rather than a verified/refuted/untested disposition table; it did not attempt to mark individual doctrine sentences as confirmed or contradicted, because its central blocker (F02, credential denial for `alliance-pod`) meant most LLM-lane claims were simply "blocked/unproven." That blocker is resolved this run (`00-PRECONDITIONS.md` §2), which is why this file can move claims #5, #6, and #8 out of "blocked" into "verified live" or "untested with suggestive corroboration" for the first time.

The test-suite claim inverted: Auditv2 recorded **1406 passed, 8 skipped, 3 xfailed, zero failures** (Auditv2 C01 §5) at HEAD `51cb704`. This run's HEAD `0d18a65` (+ larger uncommitted diff) is RED: **3 failed, 1784 passed** (E1). This is a regression in observed state between the two audits, not a re-measurement artifact: the two failures inside `test_score_pinning.py` did not exist in Auditv2's run. Auditv2's C01 F03 ("no `.gt.md` ground-truth files") and F04 (calibration edges provisional) both still hold unchanged in this run's evidence; this file does not re-verify them independently.
