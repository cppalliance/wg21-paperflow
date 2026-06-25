VERDICT: BUILD-IMPROVE (design) - Exclude ineligible axes from overall; match opendataloader

# Build vs Buy: Null-Axis Eligibility and Overall Aggregation

Research date: 2026-06-25. Scope: per-axis eligibility when GT lacks a modality (tables, headings), and how `overall` should aggregate. **No whisker source was modified.**

Hard constraints: deterministic, no LLM, permissive license only, Python >=3.12, lib funcs return data.

Evidence sources: `packages/whisker/src/whisker/{bench.py,guard.py,constants.py,metrics.py}`, `notes/{redteam-synthesis.md,cross-repo-qa-research.md}`, `research/redteam/{opendataloader-pdf,nougat,marker,PDF-Extract-Kit,surya,img2table,MinerU}.md`. Line citations under `research/repos/<name>/` refer to pinned clones used during the 28-repo red-team pass; **`research/repos/` is empty in this workspace snapshot** — repo evidence is taken from those red-team reads, not live greps here.

---

## 1. Current aggregation (`bench.py` symbols)

### 1.1 Per-paper `overall` is a flat unweighted mean of three axes

Module docstring states the contract explicitly:

```12:17:packages/whisker/src/whisker/bench.py
- ``overall`` : mean(nid, teds, mhs),
```

`run_bench` implements it as a literal three-way arithmetic mean with no weights or eligibility mask:

```157:165:packages/whisker/src/whisker/bench.py
        bm = block_metrics(candidate_md, reference_md)
        nid_v = bm.nid
        teds_v = _table_score(candidate_md, reference_md)
        mhs_v = mhs(candidate_md, reference_md)
        overall = (nid_v + teds_v + mhs_v) / 3.0
        rows.append(BenchRow(
            pid=pid, nid=nid_v, teds=teds_v, mhs=mhs_v,
            overall=overall, reading_order=bm.reading_order,
        ))
```

**Answer:** yes, `overall` is a **plain flat mean** of `nid`, `teds`, and `mhs` with equal weight ⅓ each.

`reading_order` is advisory only: stored on `BenchRow`, never folded into `overall` (`bench.py:18-20`, `BenchRow.reading_order` default).

### 1.2 No-table papers: `teds = 1.0`

```124:129:packages/whisker/src/whisker/bench.py
def _table_score(candidate_md: str, reference_md: str) -> float:
    """Mean TEDS over order-matched tables. 1.0 if neither side has tables."""
    cand = _extract_md_tables(candidate_md)
    ref = _extract_md_tables(reference_md)
    if not cand and not ref:
        return 1.0
```

When **GT has tables but candidate drops them**, pairing continues: missing tables become empty `<table></table>` placeholders and TEDS tanks (`test_bench.py:57-60`). Real table **loss** is caught.

When **neither side has pipe tables**, TEDS is **1.0**, not null/omitted. Guard stores and diffs that 1.0 as a real score.

### 1.3 No-heading papers: `mhs = 1.0` (same pattern)

```669:682:packages/whisker/src/whisker/metrics.py
def mhs(md_a: str, md_b: str, *, structure_only: bool = False) -> float:
    ...
    no headings score 1.0.
    ...
    if denom <= 1:
        return 1.0
```

Two documents whose heading trees are empty (synthetic root only) score MHS **1.0**, same benign-for-loss / inflate-for-aggregation semantics as TEDS.

### 1.4 Worked example: no-table, no-heading paper

Assume `nid = 0.90` (typical floor-adjacent text score):

| Axis | Value | Eligible? |
|------|-------|-----------|
| `nid` | 0.90 | always |
| `teds` | 1.0 | GT has no tables → **not applicable**, scored as perfect |
| `mhs` | 1.0 | GT has no headings → **not applicable**, scored as perfect |
| `overall` | **(0.90 + 1.0 + 1.0) / 3 = 0.967** | inflated vs text-only signal 0.90 |

Corpus `aggregate()` then averages per-paper values with the same flat-mean logic:

```181:186:packages/whisker/src/whisker/bench.py
    n = len(rows)
    mean_nid = sum(r.nid for r in rows) / n
    mean_teds = sum(r.teds for r in rows) / n
    mean_mhs = sum(r.mhs for r in rows) / n
    mean_overall = sum(r.overall for r in rows) / n
```

Corpus `mean_teds` and `mean_mhs` include synthetic 1.0s from ineligible papers. `below_floor` checks `nid`, `teds`, `mhs` only (not `overall`):

```187:191:packages/whisker/src/whisker/bench.py
    below = sorted(
        r.pid
        for r in rows
        if r.nid < C.NID_FLOOR or r.teds < C.TEDS_FLOOR or r.mhs < C.MHS_FLOOR
    )
```

### 1.5 Guard today (`guard.py`)

Regression axes: `GUARD_REGRESSION_AXES = ("nid", "teds", "mhs", "overall")` (`constants.py:96-99`).

Guard diffs all four as finite floats from `BenchRow`. Non-finite values (NaN/inf) → `STATUS_INVALID` (`guard.py:272-278`). A baseline axis value of `None` skips regression for that axis only (`guard.py:296-299`), but `baseline_from_rows` always writes rounded floats — no eligibility bit today.

**Inflation impact on guard:** an ineligible `teds=1.0` baseline diffed against `teds=1.0` is a no-op; it also contributes ⅓ to `overall`, so cross-axis compensation (table collapse hidden by nid/mhs gains within slack) remains possible (`test_guard.py:109-114` pattern cited in `nougat.md`).

`constants.py` already documents the intended peer semantics: *"OpenDataloader nulls such axes"* (`constants.py:71-74`) — current bench does not implement that.

---

## 2. Per-repo evidence: eligibility and stratified aggregation

Repo paths below are from red-team reads (`research/redteam/*.md`). Clones were under `research/repos/<name>/` during that pass.

### 2.1 opendataloader-pdf — null eligibility + excluded means (direct peer)

**Pattern:** return `(None, None)` when GT lacks the modality; aggregate excludes nulls; publish counts.

| Location (pinned clone) | Behavior |
|-------------------------|----------|
| `evaluator_table.py:234-235` | No GT tables → TEDS **None**, not 1.0 |
| `evaluator_heading_level.py:138-139` | No GT headings → MHS **None** |
| `evaluator.py:131-162` | `_aggregate_document_scores` **excludes nulls** from means; emits `teds_count`, `mhs_count`, `nid_count` |

Red-team verdict (`opendataloader-pdf.md` §1.3): **[CRITICAL][ACTIONABLE-NOW]** — whisker's `teds=1.0` inflates corpus means opendataloader would not count.

Corpus-mean gate uses `score >= threshold - regression_tolerance` on eligible means only (`run.py:73-86`, `thresholds.json`).

### 2.2 nougat — per-stratum means, never one headline number

| Location | Behavior |
|----------|----------|
| `metrics.py:63-83` | `split_text` → Text / Math / Tables strata |
| `metrics.py:104-117` | Separate char-NED + set-F1 **per stratum**; printed independently |
| `metrics.py:27-30,93-96` | `minlen=4`: short samples return `{}`, **omitted from stratum averages** (not scored as zero or 1.0) |

Red-team (`nougat.md` §1.2, §1.5): never collapse Text+Math+Tables into one regression decision; empty stratum omitted, not perfect.

### 2.3 marker — stratified reporting by document type and block type

| Location | Behavior |
|----------|----------|
| `overall.py:37-38,67-71` | Scores recorded per `classification` and `gt_block["block_type"]` |
| `overall.py:69-71` | `averages_by_block_type` aggregated separately |
| `display/table.py:17-47` | Separate averages per stratum in reports |
| `overall.py:72-77` | Failed samples **dropped** from averages |

Table-block collapse can hide inside a healthy **within-stratum** mean if only a flat overall is watched (`marker.md` §1.1).

### 2.4 Others flagged for null-axis / synthetic 1.0

| Repo | Evidence | Issue |
|------|----------|-------|
| **PDF-Extract-Kit** | Demo drops table blocks (`pdf2markdown.py:320-321`); whisker `teds=1.0` when both lack tables (`PDF-Extract-Kit.md` §1.2) | Modality loss invisible when GT also table-free |
| **surya** | Empty both sides → `teds=1.0` (`surya.md` fooler table) | Degenerate conversion can look table-perfect |
| **img2table** | Explicit empty-input tests; recommends hard-fail on synthetic perfect (`img2table.md` §1.3) | 1.0 masks structural absence |
| **MinerU** | Table substring asserts when GT has tables; meaningless 1.0 when none (`MinerU.md` §1.1) | Same eligibility gap |

### 2.5 cross-repo synthesis

`notes/cross-repo-qa-research.md` §4: *"opendataloader: per-axis null eligibility (null when GT lacks that axis), excluded from means with published counts, so a table regression can't hide behind a strong reading-order score."*

`notes/redteam-synthesis.md` Tier 3: deferred but documented — real table **loss** already caught; inflation only when GT genuinely lacks tables → **lower urgency than CRITICAL**, but design debt remains.

---

## 3. Library check

**No applicable buy.** This is aggregation **semantics**, not a metric algorithm.

| Candidate | Why it does not apply |
|-----------|----------------------|
| numpy / scipy (already deps) | `numpy.nanmean` over a mask is ~3 lines; does not define *when* an axis is eligible |
| `pandas` | Not a dep; adds no semantics |
| ML metric libs (sklearn, torchmetrics) | Classification metrics with `labels`/`mask`; wrong domain; no bench contract |
| opendataloader / nougat code | Reference **patterns**, not pip packages; logic is ~20 lines in whisker |

**Conclusion:** build the eligibility mask and weighted mean locally. Minimalism ladder rung 2–3 (stdlib + existing numpy if needed).

---

## 4. Verdict: BUILD-IMPROVE (design)

**Recommendation:** introduce explicit **GT-driven eligibility** per axis; store `null` (JSON) / `None` (Python) for ineligible scores; compute `overall` as the mean over **eligible axes only**; exclude ineligible axes from corpus means and from guard floor/regression checks.

**Why not KEEP-AS-IS alone:**

1. **Corpus mean inflation is real:** table-less and heading-less papers contribute synthetic 1.0 to `mean_teds`, `mean_mhs`, and per-paper `overall`, diverging from opendataloader (whisker's cited peer for bench floors and tolerance).
2. **Constants already promise null semantics** (`constants.py:71-74`) but bench contradicts them.
3. **Guard cannot distinguish** earned 1.0 from ineligible 1.0; both baseline and diff treat them as full signal.
4. **Real table loss is already caught** — so this is not CRITICAL for detection, but it **is** CRITICAL for **interpretability**, corpus-mean gates, and baseline honesty.

**Why not defer forever:** the fix is small, deterministic, and aligns with Tier-3 consensus direction; deferral keeps baselines that encode misleading 1.0s.

### 4.1 Proposed design sketch (implementation deferred)

**Eligibility rule (GT/reference is authoritative):**

| Axis | Eligible when | Ineligible score |
|------|---------------|------------------|
| `teds` | `_extract_md_tables(reference_md)` non-empty | `None` (not 1.0) |
| `mhs` | heading tree in reference has more than synthetic root (`denom > 1`) | `None` |
| `nid` | always eligible (every paper has text blocks to match) | — |

Candidate-only absence when GT has modality still scores low TEDS/MHS (existing pairing logic) — eligibility gates **measurement**, not **failure to detect loss**.

**`BenchRow` shape (conceptual):**

```python
@dataclass(frozen=True)
class BenchRow:
    pid: str
    nid: float
    teds: float | None      # None = ineligible
    mhs: float | None
    overall: float          # mean of eligible axis values only
    teds_eligible: bool     # or derive from teds is not None
    mhs_eligible: bool
    reading_order: float = 0.0
```

**`overall` computation:**

```python
parts = [nid_v]
if teds_eligible:
    parts.append(teds_v)
if mhs_eligible:
    parts.append(mhs_v)
overall = sum(parts) / len(parts)  # minimum 1 (nid always)
```

Publish `eligible_counts: {teds: n, mhs: n, nid: n}` in `aggregate()` alongside means (opendataloader `teds_count` pattern).

**`aggregate()` corpus means:** use eligibility-weighted mean per axis — average `teds` only over rows where `teds is not None`; same for `mhs`. Report `teds_eligible_count` etc.

**Guard handling:**

| Case | Behavior |
|------|----------|
| Axis `None` in current row | Skip floor check and baseline regression for that axis |
| Axis `None` in baseline, finite in current | Treat as newly eligible paper/modality; compare if GT now has tables (or fail `fail_on_new` policy) |
| Axis finite in baseline, `None` in current | **Regression** if GT still has modality (score disappeared) — likely bug or `STATUS_INVALID` |
| `overall` | Recompute from eligible axes both sides; regress only if eligible set unchanged, or document mixed-eligibility diff policy |
| NaN/inf | Keep `STATUS_INVALID` (existing) |

Extend `GUARD_REGRESSION_AXES`: consider dropping `overall` from regression (nougat/marker: never let one modality cancel another) **or** keep `overall` but only when eligible-axis sets match between baseline and current.

**Baseline migration:**

1. Bump `WHISKER_SCHEMA_VERSION` (breaking baseline shape).
2. One-time `--update` regenerates baselines with `null` for ineligible axes and recomputed `overall`.
3. Document in CHANGELOG: expect corpus `mean_teds`/`mean_overall` to **drop** on table-sparse corpora (correction, not regression).
4. CI: require explicit `--update` commit when schema bumps.

**Backward compatibility:** old baselines with `teds: 1.0` on no-table papers will show artificial regressions or improvements after migration — **intentional one-shot refresh**, not silent compatibility.

### 4.2 Alternative considered: KEEP-AS-IS

**Argument for keep:** table **loss** when GT has tables already tanks TEDS; guard per-paper diffs catch large drops; Tier-3 marked lower urgency; changing baselines churns CI.

**Reject because:** corpus-mean `bench --baseline` overall check (`__main__.py:306-315`) and aggregate reports remain misleading; committed baselines encode fake perfect scores; opendataloader parity and `constants.py` comment remain violated.

---

## 5. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Baseline break** | HIGH | Schema version bump; single `--update` PR; note expected mean shifts in commit message |
| **Determinism** | LOW | Eligibility is pure function of reference markdown structure; no RNG; same inputs → same null pattern |
| **Guard false positives** | MEDIUM | Mixed-eligibility baseline vs current (GT edited to add/remove tables) needs explicit policy: treat as baseline refresh event |
| **Guard false negatives** | MEDIUM | If `overall` stays in `GUARD_REGRESSION_AXES`, cross-axis compensation persists when all three eligible; consider dropping `overall` from regression axes (separate decision) |
| **`None` → STATUS_INVALID today** | HIGH (if shipped without guard change) | Must skip checks for ineligible axes before `_finite` gate; do not treat eligibility null like NaN |
| **Floor on ineligible axis** | LOW | Skip `teds < TEDS_FLOOR` when `teds is None`; prevents vacuous floor hits |
| **JSON serialization** | LOW | `GuardFinding.to_dict` already maps non-finite to `null` (`guard.py:118-120`); extend to eligibility null with clear `"teds": null` semantics in docs |
| **Test corpus mix shift** | MEDIUM | Papers added with tables change eligible denominator; publish counts so reviewers see denominator changes |

---

## 6. Summary table

| Question | Answer |
|----------|--------|
| Is `overall` a flat mean? | **Yes:** `(nid + teds + mhs) / 3` always (`bench.py:161`) |
| No-table paper score? | `teds=1.0`, `mhs=1.0` if no headings; `overall` inflated above `nid` |
| Buy a library? | **No** — local eligibility mask + weighted mean |
| Verdict | **BUILD-IMPROVE:** GT-driven `None` eligibility, weighted `overall`, guard skip/regen, baseline migration |
