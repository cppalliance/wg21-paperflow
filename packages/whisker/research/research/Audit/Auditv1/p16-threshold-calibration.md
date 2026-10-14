# P16 — Threshold-Calibration & Operating-Point Researcher

**Persona:** 16 (Cluster D — Audit frameworks, scoring & calibration)  
**Date:** 2026-07-18  
**Stage:** 0 evidence framing (internet research only; no whisker code inspection)

---

## 1. Question restated

How should a **QA gate threshold** be set from labeled data so the operating point is defensible: chosen at a stated false-positive / true-positive (or precision / recall) constraint, supported by ROC or precision–recall analysis, preceded by score calibration when scores are not well-calibrated probabilities, and **committed with recorded TPR/FPR (and precision/recall) at the chosen point**? What audit criteria distinguish a professionally calibrated gate from a borrowed, default, or hand-waved threshold?

This persona delivers the **calibration method and audit bar** to run later on real labels. It does not score whisker, pick libraries, or audit existing threshold constants.

---

## 2. Proposed audit criteria

Each criterion lists: **how to measure**, **audit method** (from `00-FRAME.md` §5), **scoring-design hook** (§6), **gaming vector + anti-gaming guard**, **evidence grade**, and **Tier 1–2 sources**.

### Criterion 2.1 — Documented operating policy before any numeric threshold

**Statement:** The project publishes, before calibration runs, which error type is intolerable (e.g., maximum FPR / minimum precision on bad conversions) and which metric is secondary (e.g., maximize TPR subject to FPR cap, or maximize recall subject to precision floor).

**How to measure:** Written operating policy names: (a) primary constraint (FPR ceiling, precision floor, or explicit cost ratio C_FP:C_FN), (b) secondary objective when multiple thresholds satisfy the constraint, (c) fallback when the constraint is infeasible on the calibration set.

**Audit method:** Conformance checklist (#1) + Calibration / operating-point audit (#5).

**Scoring hook:** §6.1 (scored dimension: calibration maturity); §6.2 (candidate hard gate if policy absent while thresholds gate CI).

**Gaming vector:** Declare a vague “high quality” policy with no FPR/precision bound so any threshold passes.  
**Anti-gaming guard:** Require a numeric constraint traceable to domain harm (e.g., “≤5% false pass on labeled holdout” or “precision ≥0.95 on positives flagged bad”), plus a named fallback rule.

**Evidence grade:** A (multiple Tier-1 converging: ROC cost framing, NIST FMR-first calibration, PR constraint selection).

**Sources:** Fawcett (2006) iso-performance / expected-cost framing; Provost & Fawcett (2001) ROCCH; NIST SP 800-76-2 §10.3; scikit-learn `precision_recall_curve` constraint pattern.

---

### Criterion 2.2 — Labeled calibration corpus independent of threshold tuning on the holdout

**Statement:** Thresholds are fit only on a **dedicated labeled calibration split** (or nested CV producing out-of-sample scores for calibration). The final reported operating point is evaluated once on a **held-out test split** that was not used to pick the threshold.

**How to measure:** Data-flow diagram or run log showing three roles: train/fit scores (if any), **calibration split** (threshold + optional probability calibration fit), **holdout test** (single-shot report of TPR/FPR/precision/recall at committed τ). Flag leakage if the same labeled items both select τ and report final metrics.

**Audit method:** Calibration / operating-point audit (#5) + Reproducibility replay (#8) for split integrity.

**Scoring hook:** §6.1; §6.2 hard gate if holdout was used to pick τ.

**Gaming vector:** Report stellar metrics on the same N items used to sweep τ (optimistic operating point).  
**Anti-gaming guard:** Require frozen split IDs or hash of label file + explicit “τ selected on split A; metrics below on split B only.”

**Evidence grade:** A (Fawcett 2006 on ROC generation; Niculescu-Mizil & Caruana 2005 on independent calibration set; sklearn calibration module).

**Sources:** Fawcett (2006); Niculescu-Mizil & Caruana (2005); scikit-learn probability calibration §1.16.2.

---

### Criterion 2.3 — Minimum labeled N and class balance declared

**Statement:** Calibration documents labeled **N**, positive/negative counts, and acknowledges imprecision when N is small (especially for isotonic calibration or rare failure modes).

**How to measure:** Calibration artifact records `n_pos`, `n_neg`, date, label provenance tier (links P11). Fail or downgrade if N below method-specific floor (e.g., isotonic regression with ≪1000 samples per sklearn guidance) without justification for simpler calibration (sigmoid/Platt) or wider uncertainty band (P17).

**Audit method:** Calibration / operating-point audit (#5) + Metric construct-validity audit (#4) for label adequacy.

**Scoring hook:** §6.1; §6.3 confidence (low N → lower confidence on τ).

**Gaming vector:** Calibrate on 15 hand-picked “obvious” failures and positives.  
**Anti-gaming guard:** Minimum N threshold per gate axis; stratified sampling requirement; report confidence interval or bootstrap band on TPR/FPR at τ (even wide).

**Evidence grade:** B (Niculescu-Mizil sample-size guidance + sklearn isotonic warning; NIST Annex A calibration programs for scale precedent).

**Sources:** Niculescu-Mizil & Caruana (2005); scikit-learn calibration §1.16.3.2; NIST SP 800-76-2 Table 17 / Annex A.

---

### Criterion 2.4 — Score calibration validated before threshold commit (when scores are not interval-calibrated)

**Statement:** If gate scores are treated as probabilities or compared to fixed numeric τ across releases, **reliability (calibration) is checked** on the calibration split. If predicted scores are miscalibrated (reliability diagram departs from diagonal), a post-hoc calibrator (sigmoid/Platt or isotonic) is fit on calibration data only, then thresholds are chosen on **calibrated** scores.

**How to measure:** Reliability diagram or Brier/log-loss report on calibration split; record whether raw scores were used or `CalibratedClassifierCV`-style mapping applied; document calibrator type and fit split.

**Audit method:** Calibration / operating-point audit (#5) + Metric construct-validity audit (#4).

**Scoring hook:** §6.1; §6.2 candidate hard gate if miscalibrated scores gate production without calibration step.

**Gaming vector:** Pick τ=0.5 or a “looks reasonable” constant while scores are rank-only or sigmoid-distorted (Fawcett: default 0.5 threshold can mis-rank operating point vs ROC-optimal point).  
**Anti-gaming guard:** Mandatory reliability check when documentation claims “probability” or cross-release comparability of τ; allow rank-only thresholds only if policy states “ROC-relative scores, τ not portable across score definitions.”

**Evidence grade:** A (Niculescu-Mizil & Caruana 2005; sklearn calibration; Fawcett 2006 on miscalibrated scores vs ROC ranking).

**Sources:** Niculescu-Mizil & Caruana (2005); scikit-learn §1.16; Fawcett (2006) §3–4.

**Contradiction surfaced:** Fawcett notes a classifier can have **perfect ROC ranking** yet wrong accuracy at a fixed 0.5 threshold; Niculescu-Mizil shows **good AUC does not imply good calibration**. Audit requires both ranking (ROC/PR) and calibration when τ is interpreted as a probability or fixed literal.

---

### Criterion 2.5 — Operating point selected via ROC or PR curve, not accuracy alone

**Statement:** Threshold τ is chosen by sweeping score-ordered thresholds and computing **TPR/FPR** (ROC) and/or **precision/recall** (PR) at each candidate. Single-number accuracy is not the primary selector when class skew or asymmetric costs apply.

**How to measure:** Published curve or table of (τ, TPR, FPR, precision, recall) for all candidate thresholds (or complete ROC/PR polyline). Selection rule applied in traceable code/spec: e.g., argmax TPR s.t. FPR ≤ α; or argmax recall s.t. precision ≥ β; tie-break documented.

**Audit method:** Calibration / operating-point audit (#5).

**Scoring hook:** §6.1; feeds §6.6 sensitivity (“if FPR cap relaxed 1 point, does verdict flip?”).

**Gaming vector:** Optimize accuracy on skewed corpus (hidden FN tolerance).  
**Anti-gaming guard:** Require reporting **both** TPR and FPR (or precision and recall) at chosen τ; disallow accuracy-only calibration reports for gate metrics.

**Evidence grade:** A (Fawcett 2006; Provost & Fawcett 2001; sklearn model evaluation).

**Sources:** Fawcett (2006); Provost & Fawcett (2001); scikit-learn §3.4 metrics.

**Contradiction surfaced:** For **heavy class imbalance**, PR curve constraint selection is often more informative than ROC (Fawcett: ROC can be optimistic under skew; PR constraint workflows standard in imbalanced gate design). Audit should accept either **FPR-capped ROC selection** or **precision-capped PR selection** if policy matches domain asymmetry.

---

### Criterion 2.6 — Constrained optimum with explicit fallback (Youden or declared infeasibility)

**Statement:** When the primary constraint (e.g., FPR ≤ α) yields **no feasible** threshold on the calibration split, the project uses a **pre-declared fallback** (commonly maximize Youden J = TPR − FPR = sensitivity + specificity − 1, or cost-weighted iso-performance point on ROC convex hull) or **declares calibration failed** and does not ship a borrowed τ.

**How to measure:** Calibration log field `method`: e.g., `max_tpr_at_fpr` vs `youden_j_fallback` vs `failed_infeasible`. If fallback used, record that primary constraint was not met on calibration data.

**Audit method:** Calibration / operating-point audit (#5).

**Scoring hook:** §6.2 hard gate: silent fallback to arbitrary τ without recording infeasibility fails.

**Gaming vector:** Quietly use Youden or 0.5 when FPR cap impossible, then claim “meets 5% FPR on holdout” by luck.  
**Anti-gaming guard:** Fallback must appear in committed artifact; holdout metrics must not claim primary constraint unless holdout confirms it.

**Evidence grade:** A (Youden 1950; Fawcett 2006; Provost & Fawcett 2001 iso-performance / ROCCH).

**Sources:** Youden (1950); Fawcett (2006); Provost & Fawcett (2001).

**Contradiction surfaced:** Youden assumes **equal cost** for FP and FN. FPR-ceiling / precision-floor policies assume **asymmetric costs**. Using Youden as fallback is acceptable only if documented as “equal-cost secondary”; otherwise use cost slope m = (P(pos)·C_FP)/(P(neg)·C_FN) from Fawcett Eq. 8 / Provost iso-performance line.

---

### Criterion 2.7 — Committed threshold artifact with frozen operating-point metrics

**Statement:** Shipping a gate threshold requires a **versioned calibration record** containing: τ, selection rule, calibration dataset reference, **TPR, FPR, precision, recall at τ** on holdout, class counts, timestamp, and calibrator version (if any). Constants promoted to code must trace to this record.

**How to measure:** File such as `thresholds.json` / calibration report with fields above; CI or docs link constant → calibration record hash.

**Audit method:** Conformance checklist (#1) + Calibration / operating-point audit (#5) + Documentation completeness (#9).

**Scoring hook:** §6.1; §6.2 **hard gate** — gate thresholds in production without committed calibration record fail audit regardless of weighted score.

**Gaming vector:** Copy τ from another project or prior release notes without refit.  
**Anti-gaming guard:** Record must include dataset hash and selection rule; diff on τ change requires new calibration run id.

**Evidence grade:** A (NIST SP 800-76-2 threshold calibration programs; FISWG/OSAC operational threshold alignment).

**Sources:** NIST SP 800-76-2 §10.3–10.4; FISWG FR Scoring Thresholds v1.1 (2022); NIST OSAC Passive LFR Framework (2024) §2.5.

---

### Criterion 2.8 — No borrowed thresholds without refit on representative labels

**Statement:** Thresholds from benchmarks, other corpora, vendor defaults, or “industry typical” floors are **hypotheses only** until refit on a project-specific labeled set with the protocol above.

**How to measure:** For each production τ, trace to calibration record (2.7) or mark `UNCALIBRATED_BORROWED` with explicit risk acceptance (downgrades confidence; cannot satisfy hard gate 2.7).

**Audit method:** Calibration / operating-point audit (#5) + Anti-gaming / Goodhart (#7).

**Scoring hook:** §6.1; §6.3 evidence grade C or D for borrowed τ; §6.4 anti-gaming.

**Gaming vector:** Import Docling/Marker floor values or red-team anecdotal cutoffs as production gates.  
**Anti-gaming guard:** `UNCALIBRATED_BORROWED` cannot be used for hard-fail CI gates; only shadow monitoring until calibrated.

**Evidence grade:** B (external QA practice survey in prior whisker research notes “almost nobody calibrates”; NIST/OSAC require scenario-specific threshold evaluation vs vendor default).

**Sources:** NIST OSAC (2024) §2.5 vendor default as starting point only; Fawcett (2006) on incomparable scores across model classes at common τ.

---

### Criterion 2.9 — Recalibration triggers and drift monitoring

**Statement:** Policy defines when τ must be recomputed: label schema change, metric definition change, score function change, material shift in document mix, or holdout FPR/TPR beyond tolerance vs committed record.

**How to measure:** Documented triggers + optional periodic holdout replay comparing live metrics to committed TPR/FPR band.

**Audit method:** Calibration / operating-point audit (#5) + Observability (#11) for drift alerts.

**Scoring hook:** §6.1; §6.6 flip conditions when drift unreported.

**Gaming vector:** Never revisit τ after one 2024 calibration while converters and metrics evolve.  
**Anti-gaming guard:** Tie recalibration triggers to semver or metric version constants; failed drift check blocks “calibrated” status in docs.

**Evidence grade:** B (NIST calibration test programs; Provost & Fawcett on changing operating conditions).

**Sources:** NIST SP 800-76-2 §10.4; Provost & Fawcett (2001).

---

### Criterion 2.10 — Full candidate sweep or equivalent ROC envelope

**Statement:** Threshold selection considers **every score-induced partition** on the calibration set (or an algorithmically equivalent ROC/PR envelope), not a sparse manual grid (0.7, 0.8, 0.9).

**How to measure:** Candidate count equals distinct scores (plus sentinel) or documented equivalence to sklearn `roc_curve` / `precision_recall_curve` exhaustive thresholds; tie-break rules applied on enumerated points.

**Audit method:** Calibration / operating-point audit (#5).

**Scoring hook:** §6.1.

**Gaming vector:** Manual grid that misses better operating point between grid points.  
**Anti-gaming guard:** Require proof of exhaustive sweep or library curve with `drop_intermediate` justified if tie-break does not depend on intermediate points.

**Evidence grade:** A (Fawcett Algorithm 1 monotonic sweep; sklearn curve definitions).

**Sources:** Fawcett (2006); scikit-learn `roc_curve` / `precision_recall_curve` docs.

---

## 3. External benchmark / exemplar bar

**Professional bar (synthesis from Tier 1–2):**

| Practice | Exemplar / standard | Bar |
|----------|---------------------|-----|
| FMR/FAR-first threshold calibration | NIST SP 800-76-2 PIV biometric specs | Set τ to achieve **false match rate at or below tabulated FMR** on conformance calibration data; verify on independent test; document DET/ROC tradeoff |
| Scenario-aligned operating point | FISWG FR Scoring Thresholds (2022), NIST OSAC LFR (2024) | Do not adopt vendor default without operational evaluation; high-security ConOps → low FPR even at higher FRR |
| ML gate calibration | Fawcett (2006), Provost & Fawcett (2001) | ROC/PR curves decouple from skew; pick point on ROCCH or iso-performance line for stated costs; never compare τ across incomparable score scales |
| Probability gates | Niculescu-Mizil & Caruana (2005), sklearn 1.16 | Reliability diagram before trusting τ as probability; isotonic needs O(1000+) calibration samples |
| Constraint-first selection | sklearn PR workflow, screening-test literature | Primary: max TPR at FPR≤α **or** max recall at precision≥β; fallback: Youden only if pre-declared |

**Field reality (contextual, not lowering bar):** Prior whisker build-vs-buy research found most document converters use **hand-set floors**, not labeled ROC fit. The audit bar above is **stricter than typical OSS extraction tools** and matches biometric/NIST and ML evaluation norms for **high-stakes gating**.

**Wrong to cargo-cult:** Vendor default τ; single global τ across metrics with different score scales; accuracy at 0.5 cut; AUC alone without operating point; calibrating and testing on the same labels.

---

## 4. Recommended weight & hard-gate rationale

**Weighted composite (§6.1):** Assign **medium–high weight** to a “Threshold calibration & operating-point maturity” sub-dimension under the scoring/calibration cluster (alongside P15 weighting design and P17 uncertainty). Suggested relative emphasis within that cluster: **calibration protocol ≈ 35–40%**, metric construct validity (P09) and benchmarking integrity (P12) share the remainder. Exact numeric weights deferred to Opus synthesis with P15 evidence.

**Hard gates (§6.2) — recommend YES for:**

1. **Criterion 2.7** — Production gate τ without versioned calibration record (holdout TPR/FPR/precision/recall, dataset ref, rule) → **fail** (conjunctive gate; mirrors “uncalibrated threshold used as hard gate” risk in frame §6.2).
2. **Criterion 2.2** — Holdout used to **select** τ → **fail** (leakage).
3. **Criterion 2.8** — `UNCALIBRATED_BORROWED` τ driving CI hard-fail → **fail** unless explicit time-bounded waiver with risk acceptance (otherwise confidence propagation §6.3 breaks).

**Not hard gates (scored maturity instead):** Reliability diagram polish, bootstrap CIs, recalibration automation — these raise confidence (P17) but need not block alpha if core protocol satisfied.

**Anti-gaming (§6.4):** Any “calibrated” claim must mean **labeled refit + committed metrics**, not “we picked a named constant.” Canary: holdout FPR must match recorded band within stated tolerance on replay.

---

## 5. Sources

### Tier 1 — Authoritative / primary

| ID | Citation | URL | Date/ver |
|----|----------|-----|----------|
| S1 | Fawcett, T. "An introduction to ROC analysis." *Pattern Recognition Letters* 27(8):861–874. DOI 10.1016/j.patrec.2005.10.010 | https://doi.org/10.1016/j.patrec.2005.10.010 | 2006 |
| S2 | Provost, F. J.; Fawcett, T. "Robust Classification for Imprecise Environments." *Machine Learning* 42:203–231. DOI 10.1023/A:1007601015854 | https://mlanthology.org/mlj/2001/provost2001mlj-robust/ | 2001 |
| S3 | Niculescu-Mizil, A.; Caruana, R. "Predicting Good Probabilities With Supervised Learning." *ICML* 2005. DOI 10.1145/1102351.1102430 | https://mlanthology.org/icml/2005/niculescumizil2005icml-predicting/ | 2005 |
| S4 | Youden, W. J. "Index for rating diagnostic tests." *Cancer* 3(1):32–35. DOI 10.1002/1097-0142(1950)3:1<32::AID-CNCR2820030106>3.0.CO;2-3 | https://doi.org/10.1002/1097-0142(1950)3:1%3C32::AID-CNCR2820030106%3E3.0.CO;2-3 | 1950 |
| S5 | NIST SP 800-76-2: *Biometric Specifications for Personal Identity Verification* (operating threshold specification §10.3–10.4) | https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-76-2.pdf | 2013 |
| S6 | scikit-learn 1.9.0 — Probability calibration & metrics (`calibration.html`, `model_evaluation.html`, `precision_recall_curve`) | https://scikit-learn.org/stable/modules/calibration.html | 2026 (doc v1.9.0) |

### Tier 2 — Strong secondary

| ID | Citation | URL | Date/ver |
|----|----------|-----|----------|
| S7 | FISWG. *Facial Recognition Systems Operation Assurance: Scoring Thresholds* v1.1 | https://fiswg.org/fiswg_fr_sys_oper_assur_scoring_thresholds_v1.1_2022.11.04.pdf | 2022-11-04 |
| S8 | NIST OSAC. *Framework for Implementing Passive Live Facial Recognition* (decision threshold §2.5) | https://www.nist.gov/system/files/documents/2024/01/23/OSAC-Technical-Guidance-Document-Framework-for-Implementing-Passive-Live-Facial-Recognition-Jan-2024.pdf | 2024-01-23 |

**Tier 1–2 distinct sources used for criteria:** 8 (S1–S8).  
**Tier 3 (context only, not load-bearing):** Practitioner PR-threshold interview patterns; LinkedIn/educational Youden summaries — used to locate S4/S1, not as sole basis.

**Key contradictions recorded:**

- **Youden (equal FP/FN cost) vs FPR-cap / precision-floor (asymmetric cost):** Audit requires primary policy to match asymmetry; Youden only as declared fallback (Criterion 2.6).
- **ROC vs PR for threshold pick under imbalance:** Both allowed if aligned to policy; PR constraint often matches “precision gate” products (Criterion 2.5).
- **Rank-only scores vs calibrated probabilities:** ROC ranking works without calibration (Fawcett); probability interpretation requires reliability step (Niculescu-Mizil; Criterion 2.4).

---

## 6. Overlap statement

This persona researched **external threshold-calibration and operating-point methodology only**. It did **not**:

- Open, inspect, or score whisker production code (no `file:line` citations).
- Re-litigate **`packages/whisker/research/buildvsbuy/calibration-roc.md`** (stdlib vs sklearn **library choice** and whisker-specific inverted-gate implementation details).
- Duplicate **P12** (benchmark leaderboard methodology) or **P17** (evidence grading / score uncertainty bands), except where calibration confidence defers to P17.
- Repeat **`persona/`** or **`llm-stack/`** code-level calibration findings.

**Overlap boundary confirmed:** Avoided `buildvsbuy/calibration-roc.md` library verdict scope; avoided whisker threshold audit; delivered **method + audit criteria** for later labeled execution per `00-FRAME.md` §10.

---

## Appendix — Reference calibration protocol (for later execution)

Minimal protocol satisfying criteria 2.1–2.10 (method design only):

1. **Policy:** Declare FPR ceiling α (or precision floor β) and tie-break (e.g., max TPR then max precision then higher τ).
2. **Labels:** Collect N labeled items; split → calibration (fit) / holdout (report once).
3. **Scores:** Run deterministic scorer on calibration split; if treating scores as probabilities, fit calibrator on calibration split only; check reliability diagram.
4. **Curve:** Sweep all score thresholds; compute (TPR, FPR, precision, recall) per candidate.
5. **Select τ:** Apply primary constraint on calibration split; if empty, apply declared fallback (Youden or fail).
6. **Commit:** Write versioned record with τ, rule, calibration N, holdout metrics at τ, timestamp.
7. **Promote:** Copy τ to production constants only from committed record; set recalibration triggers (2.9).

This appendix is operational guidance for a future stage, not a whisker implementation mandate.
