# tapetum_llm: 8-Agent Research Synthesis + Planner Decision

Captured by Opus 4.8 (planner/decider) on 2026-06-29, synthesizing eight parallel
Composer-2.5 research agents that each read a disjoint slice of the existing
`packages/whisker/research/` corpus + whisker source. Goal: decide what the
advisory LLM lane (`tapetum_llm`) should actually adjudicate, and what existing
code is reusable. No new experiments were run; every claim traces to a prior
research doc or to whisker source (file:line).

Agent transcripts: opus-synthesis `48e916f4`, blind-spots `223c61b6`,
eval-design `5dfeb797`, decision-path `9d488754`, lane-3 `56b4bd90`,
doc-ai-repos `110751d9`, metric-tooling `72bc9652`, wg21-rubric `38af229a`.

---

## 1. The convergent finding (all 8 agents agree)

The original `tapetum_llm.md` draft ("adjudicate the *review* band: is the Markdown a
faithful conversion?") aims at the **wrong population**.

- The review band is ~53.7% of the corpus, but **186/205 review papers trip the
  spec-declared-benign `misaligned region(s)` flag** (`REGION_SOFT_COUNT=1`,
  `constants.py:47`; `00-EVIDENCE-BASELINE.md §3a`; opus-E). It is triage noise,
  not genuine ambiguity.
- The **high-value target is the false-pass blind spot**: token-preserving
  semantic corruption that *passes* the deterministic gate because
  `unigram_coverage` is order-blind multiset recall (`score.py:136-140,156-184`).
  Demonstrated, not hypothetical:
  - **Table row/cell swaps:** 76-paper row-swap attack → **74 pass, 2 review, 0 fail**
    (`03-adversary-gate-evasion.md:12-14`, `19-table-semantics.md`).
  - **Reading-order scramble in production:** `P4178R0` passes with `uni=0.952`,
    `cov=0.837` (11.5pp gap), 0 region flags (`23-false-negative-hunter.md:28`).
  - **Math structure loss:** `$\sqrt{n}$ -> $n$`, `$\frac{a}{b}$ -> a/b` collapse to
    identical `normalized_text`, `ref_nid=1.0` (`20-math-latex-fidelity.md`,
    `metrics.py:118-126,338-340`).
  - **Code identifier corruption inside fences**, **mojibake at `qa_score=80`**,
    **lossy tables at `qa=100`** all pass (`23-false-negative-hunter.md:16-20`).
- **Lane 3 `facts` (the designed catch for exactly this) runs on 0/382 papers.**
  It is built, tested, and dead because facts must be hand-authored against source
  (`facts.py:128-130`, `08-downstream-llm-consumer.md:10`, `00 §4`).
- There is a **symmetric false-fail problem**: 9/14 hard fails are cosmetic
  `heading_monotone` H2->H4 jumps on shippable WG21 wording papers
  (`gates.py:96-112`, `24-false-positive-hunter.md:8`).
- **Nothing is calibrated**: thresholds are PROVISIONAL, no labeled corpus, no
  measured TPR/FPR (`constants.py:11-15`, `00 §5`).

## 2. The decision

`tapetum_llm` pivots from "review-band triage" to **multi-axis conversion-fidelity
adjudication aimed at the false-pass blind spot**, with every LLM claim grounded
deterministically. Four concrete changes from the draft:

### 2a. Candidate selection (was: review band only)

Select advisory candidates from whisker sidecars (`<pid>.whisker.json`,
`sidecar_path`, read-only) by risk, not by tier alone:

- **PRIMARY (false-pass hunt): `verdict == "pass"` papers carrying gate-ignored
  risk signals** present on `WhiskerResult` but never in `_decide`:
  `lossy_table_count > 0`, `table_parse_errors > 0`, `mojibake_count > 0`, or a
  large `unigram_coverage - coverage` gap (reflow-vs-scramble), or table/math-heavy
  (`score.py:248-250`, `9d488754` open-Q1).
- **SECONDARY (non-benign review): `verdict == "review"` excluding region-only**
  (skip papers whose sole soft flag is `misaligned region(s)` with
  `unigram_coverage >= 0.95`).
- **RESCUE (false-fail): `heading_monotone`-only fails** on WG21 stable-name
  headings (advisory "likely shippable").

Never touches `score.py`/`gates.py`/`whisker --gate`. Reads sidecars; consumes raw
JSON dict (no `WhiskerResult.from_dict` exists; add a one-way deserializer inside
`tapetum_llm` only).

### 2b. Multi-axis WG21 rubric (was: single holistic verdict)

Per-element fidelity judging (marker `llm.py` sub-score pattern, `110751d9`), never
collapsed into one composite (anti-pattern: cross-axis compensation hides table
loss). WG21 element ranking + per-element "broken" criteria are ready-to-use from
`38af229a`:

1. Wording / ins-del / normative-diff tables (the deliverable of wording papers).
2. Code blocks + grammar productions (fenced, recoverable).
3. Stable-name labels `[rand.req.urng]`.
4. Tables (feature-test `__cpp_lib_*`, straw polls SF/F/N/A/SA): cell-level.
5. Cross-references `[P1234R5]` (revision letter correctness).
6. Math (sqrt/frac/exponent structure).

Report the **worst axis**; escalate on it (olmOCR macro-average / Docling
`low_grade` pattern, `110751d9`).

### 2c. Deterministic grounding of every LLM claim (the safety mechanism)

Every `EvidenceSpan` the LLM quotes is verified post-hoc with whisker's own
deterministic tooling before it is trusted (fidelity invariant; `72bc9652`):

- Quoted prose -> `check_anchors` / `normalized_text` substring (exact, optional
  bounded `max_diffs`). Ungrounded quote -> dropped.
- Table claims -> `teds()` + `grits_con` on cited table HTML.
- "content missing/present" -> `content_recall()`.

A verdict with no surviving grounded evidence is demoted to `review`. This is what
makes an *advisory LLM* output defensible.

### 2d. Cascade stays, band gets calibrated

fast (gemma-4-31B) -> deep (deepseek-v4-pro) on the ambiguous confidence band, but
`CONFIDENCE_AMBIGUOUS_LO/HI` are refit on a labeled holdout, not hand-set
(`5dfeb797`). The eval (below) answers "is DeepSeek-V4 overpowered?".

## 3. The open fork (planner needs SG's call)

- **Option A (advisory verdict):** emit `Adjudication` (multi-axis fidelity verdict +
  grounded evidence) per candidate. Pure advisory. Smallest scope. Matches the
  `Adjudication` model already built.
- **Option B (fact proposer):** emit DRAFT `<pid>.facts.jsonl` (`checked: "draft"`)
  to revive dead Lane 3 via existing `parse_facts_jsonl`/`check_facts`
  (`56b4bd90`). Compounds one LLM pass into permanent deterministic checks. New
  output schema + human-verify loop. Bigger value, bigger scope.
- **Option C:** A now, B as a second mode later.

**Planner recommendation: Option A now, designed so evidence spans ARE proto-facts**
(quote + axis + location), making Option B a cheap follow-on. Minimal pivot that
captures the research and keeps the compounding play one step away.

## 4. Eval plan (answers "overpowered?")

Stratified human holdout (15-30 papers), labeled against **source PDF/HTML**, blind
to tapetum output (`5dfeb797`, `26-corpus-data-strategist.md`):

- Strata: benign-region review, unigram-band review, low-ref_nid, table/math-heavy,
  high cov/uni gap; balance pdf/html.
- Metrics: 3-class agreement + Cohen's kappa vs human; triage value (review papers
  resolved); false-resolution rate; **$/paper**; latency p50/p95; escalation rate;
  evidence-grounding survival rate.
- Overpowered experiment: fast-only vs cascade vs deep-only; override yield on
  escalated subset; Delta-kappa = kappa(cascade,human) - kappa(fast-only,human).
  Deep is unnecessary if fast-deep agreement > 90% and Delta-kappa < 0.05.
- Reuse `calibrate.py`: `calibrate_threshold`, `OperatingPoint`, `CalibrationResult`,
  `_confusion` (invert comparator: escalate iff confidence *inside* band).

## 5. Reusable code inventory (BSL-1.0 in-repo unless noted)

| Source | Reuse |
|---|---|
| `whisker.anchors` (`check_anchors`, `AnchorSpec`) | verify LLM-cited spans |
| `whisker.metrics` (`teds`, `mhs`, `text_nid`, `content_recall`, `normalized_text`) | ground claims by axis |
| `whisker.match` (`block_text_nid`) | local block NED for partial-doc claims |
| `whisker.facts` (`parse_facts_jsonl`, `facts_from_records`, `check_facts`) | Option B fact proposer |
| `whisker.score` (`sidecar_path`, `WhiskerResult`, `VERDICT_*`) | candidate selection (read-only) |
| `whisker.calibrate` (`calibrate_threshold`, `OperatingPoint`) | escalation-band fitting + eval |
| `grits-metric` (MIT), `apted` (MIT), `mistune` (BSD-3) | table cell-F1, tree edit, MD parse |

Cross-repo (marker/MinerU/olmOCR/etc.): patterns only (structured sub-scores,
normalize-before-compare, fact assertions, worst-stratum aggregation, repeat-tail
pre-gate). **Licenses not documented in the redteam notes -> verify before porting
any code.**

## 6. Anti-patterns to avoid (from doc-AI repos)

Corpus-mean-only gates; single `overall` composite; LLM as sole converter AND
validator; raw compare without normalization; synthetic perfect score on absent
modality (`teds=1.0` with no tables); LLM sub-scores as a hard CI gate. tapetum
stays advisory, serial, deterministic-where-it-can-be.

## 7. Residual open questions

1. Lane inputs: markdown-only vs source PDF/HTML excerpts/page-crops. Markdown-only
   cannot catch shared-extraction false-pass (both converters drop the same thing).
2. Evidence-span verification: exact-only vs per-span `max_diffs` tolerance.
3. Heading policy: exempt WG21 stable-name H2->H4 skips while still flagging real
   `mhs` heading-tree corruption.
4. Fork A/B/C (section 3).
