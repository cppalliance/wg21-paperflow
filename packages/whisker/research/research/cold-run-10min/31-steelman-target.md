# 31 - Steelman: is 10 min cold the right product goal?

**Verdict:** usable-with-conditions — keep **~10 min cold** as the deploy-tax /
lane-bump SLA, not as a claim that nightly fleets currently cost 48 min; drop it
only if you redefine success as warm-only and stop shipping `_LANE_VERSION` bumps.
**Confidence:** high

**Return line:** **yes** — keep the 10 min cold target as the cold-re-adjudication
SLA (reachable via ranked waste levers with verdicts unchanged); do not confuse it
with the already-healthy ~65 s warm nightly path.

## Side A — Steelman: 48 min cold is fine; 10 min is the wrong product goal

- [CRITICAL] Tonight's ~48 min is **principled audit depth**, not a lost-batching
  bug. Fleet math: **2,289 calls × ~24 s / 16 slots ≈ 3,433 s** brackets the
  observed **2,883 s**; median **7** / mean **6.0** calls/paper vs the 07-09
  **~1 call/paper** era (`research/tapetum-llm-throughput/14-steelman.md:8-9`;
  `00-baseline.md` in that corpus). Impact: chasing 10 min by cutting the cascade
  risks buying the old false-pass surface the source-aware lane was built to close.

- [CRITICAL] Warm / incremental already owns the product the operator *lives in*.
  Warm wall **64.8 s** with **375/381** skips (`research/cold-run-10min/00-baseline.md:20`;
  speedup P46). Steady-state bare runs enable skip by default
  (`cli.py` incremental = `not args.force`); a no-change night is ~0 s LLM work;
  **10–30** changed papers ≈ **1–4 min** (`14-steelman.md:16`). Impact: the
  recurring operator wait is already sub-10 min without a cold SLA.

- [HIGH] Cold only fires on **lane bumps / `--force`**, not on every night.
  `_LANE_VERSION` bumps invalidate fingerprints (`cli.py:99-123`); speedup
  synthesis pegs true cold at ~every **7.5 days** at recent cadence
  (`research/tapetum-llm-speedup/SYNTHESIS.md:54-57`). Impact: optimizing a
  once-per-bump tax that nobody waits on overnight is mis-ranked vs finding quality
  on an advisory lane that never gates CI (`14-steelman.md:14,18`).

- [HIGH] Economics do not punish 48 min. Pod is **hourly uptime**, not per-token
  (`SERVICES.toml`; whisker cost model). Marginal dollar of an unattended cold
  pass on hardware already up ≈ **$0**; cloud Opus replay of ~2.3k calls would be
  hundreds of dollars; human golden QA at 3 min/paper ≈ **19 person-hours**
  (`14-steelman.md:14`). Impact: wall-clock as the primary KPI is the wrong
  scarcity signal.

- [MED] Concrete quality purchases justify the minutes: **P4231R0** metadata +
  verified `content_omission`; **P1000R8** unit check catches `table_corruption`
  the monolith missed (`14-steelman.md:11-13`). Impact: "get to 10 min" without a
  fidelity gate is how you reintroduce silent false passes.

## Side B — Steelman: keep the 10 min cold target (operator who wants it)

- [CRITICAL] Side A conflates **two SLAs**. Nightly warm (~65 s) is healthy;
  **cold re-adjudication** is the tax on *shipping* lane logic, prompt/schema
  changes, and A/B experiments. Every lever that improves quality still bumps
  `_LANE_VERSION` (now **11**, incl. HMAC/reorder; `cli.py:119-123`;
  `12-prefix-cache-code-auditor.md:9-10`). Impact: if cold stays ~50 min, the
  team ships fewer fidelity improvements because each bump costs a full hour of
  wall + attention.

- [CRITICAL] **~9–11 min is already a verified engineering envelope**, not a
  fantasy cut of the cascade. Speedup SYNTHESIS MODERATE package: metadata-fail
  short-circuit (~1341 s), HMAC+reorder APC, verdict-first/terse pass, dual-pod
  ~1.9× remainder → central **~596 s (9–11 min)** with **verdicts unchanged**
  on the short-circuit A/B (`research/tapetum-llm-speedup/SYNTHESIS.md:7-9,45-52`;
  `00-baseline.md:30-38`). Impact: the 10 min target disciplines *waste* (44.6%
  fusion-dead unit calls, 70% zero-defect units), not *depth*.

- [HIGH] Operator iteration velocity is the scarce resource Side A underweights.
  A/B of one routing change today = **~48–50 min** cold wall
  (`00-baseline.md:18-19`). At 10 min, five cold passes fit where one fits now.
  Impact: the fidelity program Side A defends *depends* on cheap cold
  re-adjudication; expensive cold freezes the cascade in its current wasteful shape.

- [HIGH] Honest waste is load-bearing for the target: **1047** fusion-dead unit
  calls after metadata fail/review; **111** no-source-packet slot burns; mostly
  refuted escalations (`14-steelman.md:26-30`; speedup P145). Impact: refusing a
  10 min target is refusing to prioritize verified free/near-free seconds; it is
  not a fidelity stance.

- [MED] Forbidden levers already bound the product goal: no slots→32, no c>32,
  no drop-verification, no cloud batch API (`00-baseline.md:49-55`). Impact: "10
  min cold" under those constraints *means* "ship CONSERVATIVE+MODERATE," which
  is exactly the operator's intended program.

## Reconciliation (both sides true in different frames)

| Frame | Right number | Why |
|-------|--------------|-----|
| Nightly bare fleet, fingerprints warm | ~65 s → ~10–15 s with tombstones | Side A wins; 10 min is irrelevant |
| N mailing deltas | ~N × 7.6 s amortized | Side A wins; already <10 min for normal nights |
| Lane bump / `--force` / full A/B | ~48–50 min today → **~10 min target** | Side B wins; this is the operator wait |
| Quality of cascade depth | keep 6-call grounded audit; trim fusion-dead | Both: do not return to 07-09 single-shot |

## False-pass hypothesis (if we drop the 10 min target)

Team treats 48 min as "the price of quality," never ships metadata-fail
short-circuit or APC reorder, and keeps paying **~1341 s** for unit calls that
cannot change verdicts. Inspect reports stay bloated; operator stops bumping the
lane; false passes like **P1000R8** table drift get fixed slower, not faster.

## False-fail hypothesis (if we keep 10 min as a hard KPI without gates)

Someone hits 10 min by raising slots to 32, packing units, or dropping
verification quotes — walls look green, MoE batch noise or ungated monolith
passes return, and advisory output becomes less defensible (`00-baseline.md:49-55`;
slots-32 regression +57% wall already forbids the naive concurrency cheat).

## What would change my mind

A measured calendar showing **≥30 days** with **zero** `_LANE_VERSION` /
`--force` / fleet A/B cold runs, plus warm always ≤90 s, would flip to **no** —
retire the 10 min cold target as a product goal and keep only waste-cleanup as
optional backlog. Conversely, if MODERATE levers after A/B still leave cold
**>20 min**, keep the target but reopen infra (dual-pod alive?) before accepting
48 min as permanent.
