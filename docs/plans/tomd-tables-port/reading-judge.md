# Reading judge: design (2026-11-18)

Status: steps 1–3 done (commit 16ca3f2; dev-side run 2026-11-19: +2.33 pts, see Step 3 result).

## Problem

When readers disagree, `select.select_tables` picks a reading by source priority and about eight pairwise overrides.
On the dev side, 285 regions have 2+ distinct readings that pass the rule checks:
- 44 regions: today's choice is wrong, though a right reading exists;
- 214 regions: today's choice is right;
- 27 regions: no reading is right.

Three attempts to decide better from pipeline evidence all failed:

| attempt | result |
|---|---|
| learned ranker | −0.47 pts |
| page checks used as rules | −1.8 to −4.4 pts |
| conservative switching | +0.5 pts at best |

The evidence the pipeline computes does not identify the right reading.

## Evidence for a judge

A model was shown the page crop and the readings: blind, shuffled, labelled A–F. It picked the reading a person would
understand as the table. Details are in `failure-commonalities-2026-11-13.md` in the poc work directory, under "Judge trial";
the tools are in `work/paperflow/tools/judge_*.py`.

| sample | better | worse | gain |
|---|---|---|---|
| 15 fixable + 15 right-today (stratified) | 14 | 0 | +1.60 measured |
| 60 random from the other 255 | 13 | 4 (−0.28) | +1.12 measured |
| pool estimate, every pick taken | | | +2.7 ± 2.6 pts |
| pool estimate, low-confidence picks ignored | 13 | 1 (−0.02) | +3.8 ± 1.9 pts |

Points are candidate-accuracy points from the loss breakdown. Three of the four losses came from crops that did not show
the whole table. The low-confidence rule was chosen after seeing the losses, so step 3 of the build order re-tests it.

## Design

### 1. Where it sits

tomd stays deterministic and makes no model calls. The judge follows the table gate's pattern (`table_gate.py`):
requests go out, and answers come back in on a later run.

```python
run_pipeline(path, reading_judge: Mapping[str, Mapping] | None = None)  # answers keyed by request id
result.judge_requests                                                  # one per disagreeing region
```

- tomd builds the requests and applies the answers, in the new module `lib/pdf/judge.py`.
  - A request holds the page pieces and the readings. tomd also provides the prompt text and the crop renderer.
  - An answer is `pick` (an index) and `confidence`.
- The resolver lives outside tomd, in `cli/reading_judge.py`. It answers from the paper's cache first, then (live)
  from the model. `convert_one_paper` converts a second time when there are answers. tomd gains no API dependency.
- With no answers, today's choice stands and the output is byte-identical, so the golden tests pass unchanged.
- A different pick can settle a later region differently. That region then gets a new request id and keeps today's
  choice until a later run answers it.

This changes a v1 rule in `packages/tomd/src/tomd/CLAUDE.md`: "No vision LLM", with auto-resolution deferred to v2.
The judge only chooses among readings tomd already made. It never writes text, so the "verbatim, structure only" rule
holds by construction. The CLAUDE.md entry changes with the build.

### 2. Which regions it sees

- The region has 2+ readings that pass `_is_bad`, and their normalised rows differ. That is the trial's scope, about
  285 regions per dev-side run.
- Regions whose readings span more than 4 pages keep today's choice. Fewer than 1% do.
- Out of scope for now:
  - regions where every reading fails a check (27 tables, 0.21 pts);
  - regions where only one reading exists.

### 3. The crop

- For each page any reading touches, take the union of all the readings' boxes on that page. Pad by 12 pt and render at
  150 dpi, with the long edge capped at 1568 px.
- Every page is included. The trial capped crops at 3 pages, and n5016-t3 lost 0.19 pts because the judge could not see
  the continuation.
- The crop is built from pipeline boxes only, never from truth regions (see memory: no truth-derived features).

### 4. The call

- The prompt is the trial prompt: structure first, words second, and if nothing is good, the closest reading.
- Readings are shown as rows, with ` | ` between cells and `·` for an empty cell.
- The order of readings is fixed by a hash of each reading's rows, not by source. That keeps the judge blind to source and
  makes the order stable from run to run.
- Structured output (`output_config.format`): `pick`, `confidence` (high, medium or low), `why`.
- Model: `claude-opus-5-5`, the trial model, at effort `medium`. A cheaper model is used only after its own trial.
- Size: median about 800 input tokens per region (mean 1,350, max 8,400), plus about 500 tokens of fixed instructions
  that can be cached.

### 5. Applying the answer

- `low` confidence, or no answer (error, refusal, timeout, parse failure): keep today's choice.
- Otherwise, take the picked reading. It goes through the same `_to_section` path, so the later repairs still run.
- Record the decision in section metadata as `judged: <source>/<confidence>`. That metadata is diagnosis only.

### 6. Determinism and cost: a decision cache

- Key: sha256 of
  - the model id,
  - the prompt version,
  - the crop PNG bytes,
  - the readings JSON.
- The value is the answer.
- The cache is a JSON file per paper, stored as a paperstore intermediate `<pid>.judge.json`.
  Benchmark runs use one cache directory per set.
- The same input returns the same answer, so reruns are reproducible (the MODELS.md goal) and cost nothing.
- Tests use a small fixture cache, so no test makes an API call.
- `--judge off|cache|live` on the CLI:
  - `off`, the default: no judge;
  - `cache`: answers from the cache only;
  - `live`: calls the API on a cache miss and writes the answer back.

Cost per run, Opus 5.5 ($4 / $20 per million tokens), at about 2k input and about 1k output tokens (thinking included) per
region:

| run | calls | cost |
|---|---|---|
| dev side, 8 sets | about 285 | about $7 |
| fresh7–9 check | about 130 (estimated) | about $3 |
| rerun with a full cache | 0 | $0 |

Sonnet 5.5 would cost about half; Haiku 5.5 about 1/50.

## Build order

Each step goes through the usual gate.

1. **`lib/pdf/judge.py` and the selection hook.** This step covers the request builder, the crop, the reading order,
   the cache lookup and the decision rule. Unit tests run on a fixture cache. Golden tests run with the judge off and
   must stay unchanged. Regenerate the API report.
2. **Live client in `cli`.** It uses the `anthropic` SDK with the key from the environment, which is never logged.
   One call fills the cache for one paper.
3. **Dev-side run** (about $7, needs your go):
   - fill the cache for all 8 dev-side sets;
   - gate run with `--judge cache`, compared against gd19;
   - this re-tests the low-confidence rule on all 285 regions, not a sample.
4. **One fresh7–9 check** (about $3), compared with gt16.
5. Only after step 4 holds: decide whether the judge is on by default in benchmark runs, and update `CLAUDE.md` and
   `MODELS.md`.

fresh10, the reserved pool and the new mailing stay untouched.

## Open issues

- The low-confidence rule was fitted after seeing the losses. Step 3 tests it on the whole pool.
- The ±2 pt range is wide. Step 3 replaces the estimate with a measurement.
- Measured gains are candidate points. The emitted tables score higher after repairs, so the gate run is the real number.
- Expected size: about +3 pts out of a selection ceiling of +5.6. The 20–30 pt target needs the other stages too:
  - tables no reader gets right (6.17 pts);
  - decks (3.31 pts);
  - tables nothing detected (1.63 pts).
- Answers stay stable only through the cache. A model or prompt change invalidates every cached answer and costs a
  full rerun.
- Running the pipeline needs an API key, and this shell has none in its environment.

## Step 3 result: dev-side gate run (2026-11-19)

- Requests: 436 over the 8 dev-side sets, more than the 285-region trial pool. The run also judges regions with no key
  table.
- Pass 1, without answers, matches gd19 exactly.
- Cache filled live with claude-opus-5-5 at medium effort for $4.77, about $0.011 per call. Every request was answered.
- Pass 2, with answers: **79.63% → 81.96% (+2.33 pts)**.
  - 44 tables better, 5 worse (−0.15).
  - False or formatting tables went from 213 to 204.
  - 6 of 8 sets gain; dev and fresh are flat; no set loses.
- The low-confidence rule ignored 9 switches.
- The 5 losses become missing tables. In 4 of them the judge picked a reading that joins two stacked tables shown in one
  crop. A prompt fix would reach about 5 tables and is not applied.

Next: step 4, one fresh7–9 check against gt16. At the measured rate it costs about $1.50.

## Step 4 result: fresh7–9 check (2026-11-19)

- Pass 1, without answers, matches gt16 exactly.
- 242 requests, all answered, for $2.15.
  - The judge kept today's choice in 181 regions.
  - It switched in 50 at high or medium confidence, and in 11 at low confidence (ignored).
- With answers: **78.57% → 81.16% (+2.59 pts)**.
  - 16 tables better, 2 worse (−0.11), both of them now missing tables.
  - False or formatting tables went from 169 to 158.

| set | gt16 | jt1 | better / worse |
|---|---|---|---|
| fresh7 | 80.87 | 86.15 | 9 / 1 |
| fresh8 | 85.99 | 86.20 | 5 / 1 |
| fresh9 | 65.26 | 68.77 | 2 / 0 |

The check gains as much as the dev side (+2.33), so the gain generalizes. Total API spend for steps 3–4 was $6.92.

## Open issues after step 4

- Picks that join two stacked tables shown in one crop cause most of the losses: 4 of 5 on the dev side. The two
  fresh losses are also missing tables and are not yet traced.
- Fixed after step 4 (2026-11-19):
  - `anthropic>=0.98` is now declared as a `cli` dependency. `uv.lock` gains two lines, and `uv lock --check` passes.
    The locked 0.98.1 accepts `output_config`.
  - The judge setup in `jobs.py` had landed in `run_download` instead of `run_convert`, so both commands raised
    NameError. The benchmark runs went through the poc tools and missed it. The run_convert test, run in a
    temporary environment with cli's dependencies, caught it, and it now passes.
- Step 5 is undecided: whether the judge is on by default, and the cost per paper in production (about $0.01 per
  disagreeing region).
