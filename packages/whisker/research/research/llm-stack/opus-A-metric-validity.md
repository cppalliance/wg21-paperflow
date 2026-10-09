# Opus Meta-Review A - Metric/Measurement Validity (llm-stack)

Scope: re-verify persona claims touching measurement and metric validity (sidecar
counts, verdict distributions, escalation rate, grounding-drop counts, confidence
histograms, LOC, test counts, throughput). Read-only. All numbers below were
reproduced this pass against the CURRENT on-disk / code state (not the 2026-07-03
baseline HEAD), then compared to what each persona asserted.

Reproduction harness (read-only):
- File counts: `Get-ChildItem data\whisker\*.tapetum.json | Measure` etc.
- Sidecar aggregation: `ConvertFrom-Json` over all 198 `*.tapetum.json`.
- LOC: `@(Get-Content <file>).Count` (physical lines, blanks included).
- Test fns: `Select-String -Pattern 'def test_'` over `test_*.py`.
- Code state: direct read of `model_backends.py` + grep.

**Reproduced ground truth (this pass):**
`data/whisker/*.tapetum.json` = **198**; `*.whisker.json` = **381**;
`data/paperstore/*.debug.tapetum_llm.md` = **200** (gap = **2**).
Verdicts over 198: **pass=74, review=106, fail=18**.
`escalated=true` = **0/198**. Confidence in `[0.35,0.65]` = **0/198**.
Confidence min=**0.85**, max=**1.00**, mean=**0.9586**. `tier1_model`=alliance-pod
on all 198; `tier2_model`=∅. `ungrounded_dropped>0` = **9/198**.
Fail confidence: 18/18 ≥ 0.95, mean **0.9539**. Review confidence: min 0.85,
median 0.95, 105/106 ≥ 0.90. Axis-disagreement papers = **123/198**.
whisker→tapetum cross-tab: review→review **94**, review→pass **71**,
review→fail **18**, pass→pass **3**, pass→review **3**, fail→review **9**.

---

## Verified claims (persona-file: claim -> CONFIRMED, evidence)

- **21 (Cascade-Calibration): `escalated=true` 0/198 and 0/198 confidences in `[0.35,0.65]`; histogram min=0.85 max=1.00 mean=0.9586 -> CONFIRMED (exact).** Reproduced over all 198 sidecars: 0 escalations, 0 in band, min/max/mean identical to the persona's reported `min=0.85, max=1.00, mean=0.9586`. This is the single most load-bearing metric claim in the whole roster and it is exact.
- **21: self-reported fail confidence anti-calibrated, 18/18 fails ≥ 0.95, mean 0.9539 -> CONFIRMED (exact).** Reproduced: fail n=18, all ≥ 0.95, mean 0.9539.
- **21: axis-disagreement present on 123/198 papers while overall confidence stays ≥ 0.95 -> CONFIRMED (exact).** Reproduced count of papers with >1 distinct per-axis verdict = 123.
- **21 / 16: escalation would be a no-op model swap; `tier1_model={alliance-pod}`, `tier2_model=∅` on all 198 -> CONFIRMED.** Reproduced: tier1=alliance-pod ×198, tier2 empty ×198.
- **21: whisker `review` → tapetum {review 94, pass 71, fail 18}; "upgrades to stricter = 21" -> CONFIRMED (exact).** Cross-tab reproduced: 94/71/18; stricter = review→fail(18)+pass→review(3)=21.
- **11 (False-Positive): review confidence min/median = 0.85/0.95, 105/106 reviews ≥ 0.90, 0/198 confidence < 0.50 -> CONFIRMED (exact).** Reproduced identically.
- **11: only 3 whisker-pass-channel papers become `review` (P3440R3, P3724R3, P4211R0) -> CONFIRMED.** Cross-tab pass→review = 3.
- **11: ~84/106 reviews are a single structure-axis cosmetic -> CONFIRMED (approx, off-by-one).** Reproduced 85/106 with `structure` as the sole non-pass axis. Persona's 84 used a slightly tighter predicate (structure+minor+review); magnitude and conclusion hold.
- **11 / 12 / 22 / baseline: `ungrounded_dropped>0` on 9 sidecars -> CONFIRMED (count).** Reproduced 9. (Denominator is 198, not 197: see downgrades.)
- **16 (Product-Skeptic): all 18 tapetum `fail` sidecars had whisker `review`; RESCUE 9/9 whisker-fail→{review}; selector split PRIMARY=6 / SECONDARY=185 / RESCUE=9 -> CONFIRMED.** Cross-tab: review→fail=18, fail→review=9, whisker-pass channel=6 (3 pass + 3 review), whisker-review sidecars=183 (+2 failed papers = 185 attempted SECONDARY), whisker-fail=9. Reconciles to 200 attempted / 198 adjudicated exactly.
- **baseline / multiple: `*.whisker.json`=381, `*.debug.tapetum_llm.md`=200 -> CONFIRMED.** Reproduced 381 and 200.
- **07 (Test-Suite) / baseline: whisker = 325 test fns across 20 files; `test_tapetum_llm.py` = 75 -> CONFIRMED (exact).** Reproduced 325/20 and 75.
- **LOC exact matches -> CONFIRMED:** `prompt.py`=519, `runner.py`=415, `adjudicate.py`=441, `cli.py`=355, `chunking.py`=244, `models.py`=124, `constants.py`=70, `grounding.py`=56 (physical line counts). These anchor persona 06/07/21 structural claims.
- **06 (Performance): batch loop is strictly serial (one `await adjudicate_paper` per PID, no concurrency knob) -> CONFIRMED (structural).** Verified in `cli.py`; independent of any runtime number.

## Downgraded/dropped claims

- **Sidecar count 197 (baseline line 44; 12; 22) -> CORRECTED to 198.** Current disk holds 198 `*.tapetum.json`. The baseline's 197 (and the "3-file gap") is stale; the reproducible gap is now 2 (200 debug − 198 sidecars). Any claim written as `N/197` should read `N/198`.
- **Verdict distribution "73 pass" (baseline line 45; 12; 22) -> CORRECTED to 74 pass** (106 review, 18 fail = 198). One additional pass sidecar exists on current disk. Personas 11/16/21 (who used 74) are correct; personas 12/22 (73/197) are stale on both numerator and denominator. Note their *rate* framing (54% review) survives: 106/198 = 53.5%.
- **LOC `model_backends.py` = 768 (baseline) -> CORRECTED to 757.** The file shrank 11 lines with the retry-budget revert. Also stale: `services.py` 526→519, `agents.py` 172→171, `tools.py` 104→103, `tapetum_llm.md` 162→161. Small, but the model_backends delta is causally tied to the revert.
- **All `model_backends.py` line-number citations are stale offsets** (file 768→757). Personas cite `:76-85`, `:382-421`, `:409-416`, `:388-404`, `:311`; the live retry logic is now `:300` (`max_attempts`), `:302-413` (loop). Mechanisms still exist; only the offsets moved. Downgrade precision, not substance.
- **Pipeline test count 177 (baseline) -> reproduced 176** (loose `def test_`). Off by one plus a structural change: `test_truncation_retry.py` now holds 4 test fns (was ~6). Treat "177" as ~176.
- **Throughput 25-40 s/paper, 1.5-2 h / 200 papers (baseline line 49; 06) -> NOT reproduced read-only.** These are task-supplied runtime facts; no rerun was performed this pass. Persona 06's micro-benchmarks (2.5 ms setup, 37 ms grounding, 269 ms at 500k chars, 409 ms batch waste) are self-run and unverified here. The serial-loop *structure* is confirmed; the wall-clock magnitudes are unconfirmed and should be labeled task-supplied.
- **Persona 16 "PRIMARY delivered value = 1/6" and selector cov_gap breakdown (`cov_gap=0`, `lossy_table=2`, `mojibake=4`) -> substrate CONFIRMED, sub-labels UNVERIFIED.** The 6-paper whisker-pass channel and the 3 pass→review outcomes are reproduced; the per-signal risk breakdown requires re-running `select_candidates` and was not reproduced. The count scaffold holds; the "1 substantive vs 2 cosmetic" reading rests on `primary_concern` text I did not exhaustively re-parse.

## Claims invalidated by the retry-budget revert

The revert is CONFIRMED in code: `packages/pipeline/src/pipeline/model_backends.py:300`
reads `max_attempts = min(2, request_limit)`; grep for `_RAW_JSON_MAX_ATTEMPTS`
returns nothing (constant deleted); the `_RETRY_MAX_TOKENS_GROWTH` docstring now
says "the current 1.5x / 2-attempt budget" (`:73`).

- **Baseline lines 48-49: "`_RAW_JSON_MAX_ATTEMPTS = 3`", "raised to 3 at `model_backends.py:76`" -> INVALIDATED.** Budget is back to 2; constant no longer exists.
- **06: "`_RAW_JSON_MAX_ATTEMPTS = 3` with full re-issue per failure" (`model_backends.py:76-85`) -> INVALIDATED.** The retry-heavy latency argument stands mechanically, but the "3-attempt" figure is wrong; worst case is 2 attempts.
- **07: CRITICAL/HIGH citing `min(_RAW_JSON_MAX_ATTEMPTS, request_limit)` with `=3`, and the test `test_double_corruption_recovers_on_third_attempt` (`test_truncation_retry.py:146-160`) -> INVALIDATED.** That test is DELETED (`test_truncation_retry.py` now has 4 fns: truncation_grows `:82`, malformation_nudges `:103`, growth_capped `:122`, persistent_truncation_raises `:132`; no `third_attempt`). Persona 07's "9/200 failure class at budget 2" is no longer historical, it is the LIVE state under the reverted code.
- **20 (Retry-Policy) core thesis -> INVALIDATED / moot.** "attempt 3 is empirically justified", "7/9 recovered at budget 3", "raising 2→3 was correct", and the recommendation to "trim malformation retries to 2 attempts" all assume a budget of 3 that no longer exists. Per the freshness note the accepted fix is a vLLM pod upgrade (#42287), not a pipeline edit. Persona 20's own "9/200 double-corruption at budget 2" is the current steady state.
- **The reproduced "198 sidecars / 2-file gap" does NOT reflect current-code steady state -> flagged.** 198 is real on disk, but it is the artifact of a budget-3 run (2 residual hard failures = P2728R11/R12). Under the reverted budget-2 code, a fresh 200-paper rerun re-enters the 9-failure class (≈191 sidecars). So every count I confirmed against disk is accurate for the persisted data, but "expected sidecar yield of this codebase" = ~191, not 198. Any adoption metric derived from 198 must carry this asterisk.

## Net assessment (3-6 sentences)

The measurement layer of this roster is unusually sound where it matters most:
persona 21's cascade-calibration numbers (0/198 escalations, 0/198 in-band,
mean confidence 0.9586, 18/18 overconfident fails, 123/198 axis disagreement) and
persona 11's review-confidence and cross-tab figures reproduced to the digit, and
the whisker→tapetum cross-tab (94/71/18/3/3/9) is exact. The one systematic error
is a denominator/numerator drift: the corpus grew from the baseline's 197/73-pass
to a current 198/74-pass, so personas anchored on 197 (12, 22) and the baseline
itself are stale by one paper, while personas that used 198/74 (11, 16, 21) are
correct. The retry-budget revert is the sharpest invalidator: it deletes
`_RAW_JSON_MAX_ATTEMPTS`, restores `min(2, request_limit)`, removes the
third-attempt test, and thereby moots persona 20's entire "budget-3 is justified"
thesis and persona 07's third-attempt test citation, while making the 9/200
failure class live again. Throughput magnitudes (25-40 s/paper) and the selector
risk-signal breakdown remain task-supplied/unverified and should not be treated as
reproduced. Net: trust the calibration and distribution metrics (verified), treat
all `/197` and `768-LOC` and `budget-3` figures as corrected, and footnote that the
198-sidecar count reflects a superseded budget-3 run rather than the current code.
