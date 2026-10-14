# 03 - Bidirectional Entailment Designer

**Verdict:** usable-with-conditions — a minimal two-sided per-quote state machine can reuse `ground_spans` / `ground_page_quotes` for the candidate **presence** leg only; treating `dropped` as proven **absence** without an `ambiguous` band would repeat the 40% false-missing rate from `00-baseline.md`.
**Confidence:** high

## Findings

- [CRITICAL] **Current sidecar over-claims bidirectional entailment.** Evidence: `pdf_judge.py:513-520` grounds quotes only against `pdf_text`; `pdf_judge.py:401-404` labels every survivor `"present in PDF text layer, absent from markdown"` without a candidate check. Impact: 8/20 quotes were genuinely absent in the forced replay (`00-baseline.md:14-24`); 12/20 were false missing-content evidence driving inflated fail/review signals.

- [HIGH] **Minimal per-quote state machine (no new dependencies).** Evidence: olmOCR `TextPresenceTest` pattern (`05-web.md:14-18`); existing tiers in `grounding.py:171-241` and page-scoped variant `grounding.py:244-278`; tri-state routing from CRAG/LitRAG (`05-web.md:157-159`, `59-61`). Impact: one deterministic function per quote, two haystacks, explicit statuses — no NLI, no new packages.

  ```text
  LLM quote Q
      |
      v
  [S1] SOURCE_LOCATE(Q, pdf_text | page_text)
      |-- drop -------------------------> source_ungrounded  (discard; count in ungrounded_dropped)
      |-- exact / fuzzy ----------------> source_grounded
      v
  [S2] CANDIDATE_LOCATE(Q, tomd_md)     # only if source_grounded
      |-- exact / fuzzy substring -------> present_in_candidate  (demote missing claim)
      |-- partial_ratio in (hi, floor) --> ambiguous            (abstain; demote verdict)
      |-- below floor ------------------> verified_missing       (retain as evidence)
      v
  [S3] AGGREGATE (verdict policy below)
  ```

  **Statuses (per quote, persisted in sidecar):**

  | Status | Meaning | Counts as missing evidence? |
  | --- | --- | --- |
  | `source_ungrounded` | Not locatable in PDF text layer | No |
  | `present_in_candidate` | Source grounded; locatable in markdown | No (false LLM absence) |
  | `verified_missing` | Source grounded; candidate locate failed at floor | Yes |
  | `ambiguous` | Source grounded; weak fuzzy only (gray band) | No (abstain) |

  **Locate tiers (reuse existing code paths):**

  - Monolith quotes: call `ground_spans([EvidenceSpan(..., quote=Q)], haystack)` (`grounding.py:171-241`); map `GroundedSpan.status` ∈ `{exact, fuzzy}` → located; `dropped` → not located at tier bundle.
  - Page escalation quotes: call `ground_page_quotes([Q], page_text)` for source (`pdf_judge.py:572-574`); for candidate, same quote against **full** `tomd_md` (prompt contract: page content may appear anywhere, `pdf_judge.py:214-217`).

- [HIGH] **`ground_spans` reuse for candidate presence is safe; inverted `dropped` → `absent` is not.** Evidence: `ground_spans` is symmetric in API (`spans`, `markdown` at `grounding.py:171-174`) and already used on markdown in adjudicate (`adjudicate.py:285`). Asymmetry is in **haystack semantics**, not the function: PDF text is dehyphenated for screen/recall (`pdf_judge.py:96-108`, `299-300`) but monolith grounding uses raw `normalize_textlayer` output (`pdf_judge.py:464-519`); candidate uses `strip_binary_payloads` markdown (`pdf_judge.py:467-468`). `normalized_text` strips markup and punctuation (`metrics.py:118-126`, `00-baseline.md:52-53`) — fine for "is this prose anywhere?" but blind to sub-resolution defects (table cell swap, math collapse). Impact: **reuse call, do not reuse interpretation**: `grounded` on candidate ⇒ `present_in_candidate`; `dropped` ⇒ run ambiguous probe before `verified_missing`.

  **Ambiguous probe (stdlib + existing constants only):** when `ground_spans` drops on candidate, compute `partial_ratio(normalized_text(Q), normalized_text(tomd_md))` (`grounding.py:232-236`, `rapidfuzz` already imported). If ratio ∈ `[EVIDENCE_FUZZY_FLOOR - AMBIGUOUS_BAND, EVIDENCE_FUZZY_FLOOR)` → `ambiguous` (new named constant, e.g. `CANDIDATE_AMBIGUOUS_BAND = 0.05`, in `constants.py`); if ≥ floor → treat as `present_in_candidate` (catches cases fuzzy tier missed due to `EVIDENCE_MIN_FUZZY_CHARS`, `constants.py:69-73`); if below band low → `verified_missing`. Page quotes: reuse length-relative threshold from `ground_page_quotes` (`constants.py:181`, `grounding.py:272-273`) for both legs; gray band = ratio within `1/max(1,len)` of threshold.

- [HIGH] **Demotion policy (verdict-level, advisory-only preserved).** Evidence: existing pass demotions in `pdf_judge.py:525-538` and `adjudicate.py:298-323`; fusion guardrail that LLM cannot clear whisker missing regions (`fusion.py:129-133`, `175-176`); LitRAG short-circuit (`05-web.md:59-61`). Impact: evidence precision improves without touching `whisker --gate`.

  | Condition | Action |
  | --- | --- |
  | Quote → `present_in_candidate` | Remove from `missing_content`; increment `candidate_false_missing` counter |
  | Quote → `ambiguous` | Remove from `missing_content`; increment `ambiguous_quotes`; append reason |
  | Quote → `source_ungrounded` | Drop (existing `ungrounded_dropped`) |
  | Verdict `fail`/`review` and **zero** `verified_missing` after S2 | Demote toward `pass` if monolith confidence ≥ `CONFIDENCE_DECISION_FLOOR` (`constants.py:45`) and no confirmed page escalation (`pdf_judge.py:576-592`); else cap at `review` |
  | Verdict `fail` and deciding quotes all `ambiguous`/`present_in_candidate` | Force `review` (never `fail` on quotes alone) |
  | Page escalation `content_missing=true` but all quotes `present_in_candidate` | Set `content_missing=false` for that page entry |
  | Any surviving `verified_missing` with source `fuzzy` only | Cap axis/verdict at `review` (mirror fuzzy-only pass demotion, `adjudicate.py:313-321`) |
  | Sub-floor confidence | Existing demotion to `review` (`pdf_judge.py:525-526`, `adjudicate.py:322-323`) |

  Sidecar `grounded_evidence` entries must split axes: `source_status`, `candidate_status`, `entailment` (`verified_missing` | `false_missing` | `ambiguous` | `ungrounded`), replacing the false combined reason at `pdf_judge.py:401-404`.

- [MED] **Failure semantics (lane vs quote).** Evidence: `PdfLaneError` fail-closed policy (`pdf_judge.py:424-425`, `449-450`); tapetum `status: error` vs `ok` (`models.py:157-160`, `fusion.py:86-94`). Impact: bidirectional verifier must not widen lane failures.

  - **Lane failures (unchanged):** text-layer extract error, context budget exceeded, judge/escalation transport failure → `PdfLaneError`; no partial sidecar (`pdf_judge.py:449-450`, `567-570`).
  - **Quote failures (soft):** `source_ungrounded`, `ambiguous`, `present_in_candidate` never raise; they demote or drop evidence.
  - **Never fail-closed on ambiguous:** ambiguous quotes abstain (`05-web.md:157-159`); they do not count toward missing-content evidence or major-axis escalation.
  - **Determinism:** fixed tier order in `grounding.py:216-239`; sorted sidecar keys (`models.py:177-180`); no LLM in S1/S2.

- [MED] **Do not use inverted monolith `ground_spans` alone for page quotes on candidate.** Evidence: page source check uses `ground_page_quotes` with `PAGE_QUOTE_MAX_DIFFS` (`grounding.py:244-278`); monolith uses document-wide `EVIDENCE_FUZZY_FLOOR` (`constants.py:67-73`). Impact: mixing tiers across legs inflates false `verified_missing` on short page quotes or false `present_in_candidate` on long quotes.

- [LOW] **Optional later: facts.py windowed edit distance for code/math quotes.** Evidence: `_best_match` + `_substring_edit_distance` in `facts.py:282-326` gives localized edit count vs document-wide `partial_ratio`. Impact: not required for v1 prose missing-content quotes; justified only if replay shows code-token false positives in the ambiguous band.

## False-pass hypothesis

A PDF quote `"The constexpr function template shall be"` normalizes to a substring already present inside a markdown code fence with different whitespace. `ground_spans` candidate tier-2 substring match on `normalized_text` returns `present_in_candidate` (`grounding.py:230-231`) while the **declaration** is actually dropped — a genuine miss masked as present because normalization erases fence boundaries and `constexpr` spacing. v1 accepts this in exchange for killing the 12/20 false-missing rate; code-heavy quotes should route through raw-surface locate (`facts.py:324-326`, `SURFACE_RAW`) in a follow-up.

## False-fail hypothesis

A legitimately missing `constexpr` block (PR #293, 5/5 genuine in `00-baseline.md:19`) survives as `verified_missing` because neither PDF nor markdown contains the text — wait, if missing from markdown but in PDF, candidate locate correctly drops. **Real false-fail:** PDF text layer garbles a symbol (`α` → `a`) so source grounds fuzzy (`grounding.py:230-237`) while markdown has the correct Unicode; candidate exact fails, monolith fuzzy fails, ratio lands in ambiguous band → quote abstains and a real defect is demoted from `fail` to `review`. Mitigation: keep `verified_missing` when source is `exact` and candidate is strictly below floor; demote only when source is `fuzzy`-only (policy row above).

## What would change my mind

A labeled replay of the 20-quote holdout from `00-baseline.md` showing that the tri-state candidate probe (with `CANDIDATE_AMBIGUOUS_BAND`) achieves ≥90% evidence precision **and** retains all 8 genuine absences (zero false demotions from `verified_missing` to abstain), measured at `pdf_judge.py:513-520` call sites — would flip verdict to **usable** without conditions.
