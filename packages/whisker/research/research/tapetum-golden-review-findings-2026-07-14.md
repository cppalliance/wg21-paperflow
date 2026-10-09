# tapetum_llm Golden-Review Findings (2026-07-14)

Three verified LLM-lane failure modes, diagnosed from the debug transcripts
of PR #282-#285 golden-ideal reviews. Every claim is grounded in the actual
LLM I/O logs (`*.debug.tapetum_llm.md`) and sidecar JSONs.

## F1: Fusion false-pass upgrade (p0957r8, PDF)

**What happened.** The PDF-text-layer judge received the full source text layer
AND the full converted markdown in one monolithic call. Page 13 content (Figure 1,
Figure 2, Table 2) was present in the RAW block but entirely absent from the
CONVERTED MARKDOWN block. The model said `pass, confidence 0.98,
missing_content: []`. The deterministic lane correctly flagged this as
`missing_region` on page 13 (coverage 0.9166, verdict `review`).

**The decisive failure.** Fusion rule `llm_clear_soft_review` (fusion.py L166-201)
upgraded the deterministic `review` to combined `pass`, because `missing_region`
produces only a soft flag (`"{N} misaligned region(s)"`), and fusion currently
does not consult `missing_region_count` or `coverage` from the whisker sidecar.

**Root cause classification.** Primarily architecture, not model:
- The monolithic prompt (~50k tokens, source + markdown side by side) rewards
  shallow scanning over systematic page-by-page verification.
- `content_recall` (0.9806) and `text_nid` (0.9178) were computed alongside but
  explicitly NOT wired to the verdict (pdf_judge.py L21-24).
- The fusion guardrail (`ref_nid >= 0.10`) is too coarse to block this.

**Fix direction.** Block `llm_clear_soft_review` when `missing_region_count > 0`
in the whisker sidecar. The sidecar already carries this field; fusion just does
not read it. Secondary: wire `content_recall`/`text_nid` as a pass->review floor
in the PDF judge itself. Neither fix requires a model change.

**Prior research alignment.** `research/hybrid-llm-scoring/19-false-pass-hunter.md`
explicitly listed misaligned-region reviews upgraded by LLM pass as a risk.
`research/hybrid-llm-scoring/20-false-fail-hunter.md` designed the
`llm_clear_soft_review` rule as an intentional 44% queue-shrink mechanism. The
fix narrows the rule (carve out missing_region reviews) rather than removing it.

## F2: Hallucinated reasoning (p3556r0, PDF)

**What happened.** The PDF-text-layer judge correctly passed the golden (all
wording edits properly converted from `<del>`/`<ins>` to `~~...~~`). But its
`reasoning` field stated: "wording markup (<ins>/<del>)" as if observed in the
file. Ground truth: 0 `<del>`, 0 `<ins>`, 0 `:::` in the reviewed markdown.

**Root cause.** Rubric-bleed: the SYSTEM PROMPT describes sanctioned wording
markup forms (`<ins>/<del> tags`, `:::wording` fences) at pdf_judge.py L101-110.
The model echoed this contract description as observed content. The `reasoning`
field is never grounded: grounding (pdf_judge.py L296-303) only verifies
`missing_content` quotes. A `pass` with empty `missing_content` triggers no
grounding check at all.

**Fix direction.** Two steps:
1. Mechanical tag-claim check: after `judge_pdf_extraction()`, grep `paper_md`
   for literal markup tokens mentioned in `reasoning` (`<ins>`, `<del>`, `:::`);
   annotate contradictions.
2. Label `reasoning` as "unverified narrative" in the inspect report
   (inspect_report.py L110-112) so operators know not to trust it.

## F3: Heading-level blind spot (p4020r0, HTML)

**What happened.** The text lane (HTML paper, adjudicate.py `_build_triage_message`
L363-395) injected only the converted markdown. No HTML source, no heading list,
no h1-h6 outline. The structure axis (tapetum_llm.md L62) explicitly classifies
heading-level jumps as cosmetic ("severity minor, verdict review at most, never
fail"). The model correctly reported "Sections are complete and in correct order"
with confidence 1.00 and empty evidence.

**Root cause.** Architecture + prompt-spec:
- The HTML text lane never receives the source (by design: independence refactor).
- Even the conversion contract in the system prompt lists `References` as H2,
  but the structure axis explicitly tells the model heading-level deviations are
  cosmetic. The defect (`### References` vs source `<h2>References</h2>`) was
  architecturally undetectable.

**Fix direction.** Inject a deterministic HTML-heading outline (h1-h6 tags
extracted with stdlib `html.parser`) into the triage message for HTML papers.
This is not a det-verdict leak (no whisker signals/flags), it is deterministic
source metadata. Update the structure axis prompt: when a source outline is
present, heading LEVEL mismatches on known top-level sections (References,
Abstract, Acknowledgements, Motivation, Wording) are a finding at `review`, still
never `fail` (rescue mandate intact).

## Cross-cutting findings

- **Confidence is uncalibrated self-report.** In 204 production sidecars: min
  0.90, median 0.95, 18/18 fails at >= 0.95. The escalation band [0.35, 0.65]
  was hit 0/198 times. Escalation is effectively dead; tier 2 is the same model.
  (constants.py L23-26, research/hybrid-llm-scoring/14-confidence-calibration.md)
- **Empty-evidence pass is sanctioned.** tapetum_llm.md L108 explicitly allows a
  pass with no evidence at high confidence, which is the exact pattern in all
  three failures. (#277 condition 1 now implemented: adjudicate.py L293-306.)
- **Fusion is advisory.** CI gate = det only. The merged verdict lives in
  namespaced fields (`combined_verdict`, `advisory: true`). Fix stays advisory.
- **Reasoning is ungrounded everywhere.** Both PDF judge and text lane persist
  `reasoning` as a free-text narrative that passes through inspect_report.py
  and fusion_report.py without mechanical verification.

## v2 backlog (documented here, not in this fix batch)

- **Per-page/per-unit judging** (olmocr BasePDFTest per-page facts pattern,
  benchmark.py:94-101). Replaces the monolithic prompt with scoped checks.
  olmocr-Bench 82.4% on extraction, Apache-2.0. Decided as v1 target in
  `research/vlm-pdf-qa/SYNTHESIS.md`.
- **langextract monotonic-DP grounding** (resolver.py:1113-1185). Upgrade for
  `ground_spans`: maps each quote to successive non-overlapping source
  occurrences with `char_interval` provenance. MED priority.
- **Confidence calibration** (protocol drafted in
  research/hybrid-llm-scoring/14-confidence-calibration.md). Requires a labeled
  holdout set. Prerequisite for any confidence-weighted fusion.
- **docling computed per-page scores** (datamodel/base_models.py:539-674).
  `parse_score`, `layout_score`, `table_score`, `ocr_score` per page with
  aggregation via worst-10% pages. Non-LLM quality signal.
- **marker per-block LLM + reject-on-fail** (llm_table.py:208-237,
  llm_sectionheader.py:17-90). Schema + sanity gate on each LLM-refined block.

## Simulation results (2026-07-14, post-fix)

All four fixes implemented (Fix 0-4), whisker test suite green (941 passed).
Three-paper simulation: offline fusion replay + live re-runs on alliance-pod
(DeepSeek-V4-Pro).

### Offline fusion replay (no LLM, old sidecars + new `fuse_verdicts`)

| Paper | det | old LLM | old combined (old rule) | NEW combined (NEW rule) | Changed? |
|-------|-----|---------|------------------------|------------------------|----------|
| P4020R0 | pass | pass 1.00 | pass (agree) | pass (agree) | no |
| P0957R8 | review | pass 0.98 | pass (llm_clear_soft_review) | **review (clear_blocked_missing_region)** | **YES** |
| P3556R0 | pass | pass 0.95 | pass (agree) | pass (agree) | no |

Fix 1 deterministically blocks the false-pass upgrade for P0957R8 (missing_region_count=2).

### Live re-runs on alliance-pod (new code, --debug --inspect --force)

**P4020R0 (HTML, Fix 3: heading outline injection)**
- Outline injected: `Source HTML heading outline: h1: Concerns about contract assertions, h2: Contracts in general, ...`
- Model explicitly referenced it: `"Section order and nesting match the source HTML outline exactly."`
- Verdict: pass (conf=1.00), fusion: pass (agree). Correct: this paper has no heading-level mismatch.
- Note: p4020r0's det verdict is `pass` (no heading issue in this golden). The outline infrastructure is confirmed working; a paper with an actual h2->h3 drift would now surface it.

**P0957R8 (PDF, Fix 1+4: fusion guardrail + PDF judge floors)**
- LLM still says pass (conf=0.98, missing=0): the model remains blind to page-13 content absence in the monolithic prompt.
- `content_recall=0.9806`, `text_nid=0.9178`: both above the new floors (0.85/0.80), so Fix 4 does not demote here.
- Fix 1 fires: fusion combined_verdict = **review (clear_blocked_missing_region)**. The guardrail catches what the model missed.
- Correct outcome: the deterministic `review` (2 missing regions) is preserved.

**P3556R0 (PDF, Fix 2: reasoning annotation)**
- LLM says pass (conf=0.98), verdict correct (golden IS correct).
- Model hallucinated the same rubric-bleed: `"wording markup (<ins>/<del>)"`.
- Fix 2 annotated it: reasoning now ends with `[unverified: '<ins>' not present in markdown; '<del>' not present in markdown]`.
- Verdict unchanged (pass/agree): correct, since the golden IS faithful. The annotation surfaces the hallucination for operator awareness without changing the verdict.

### Summary

| Fix | Target paper | Mechanism | Result |
|-----|-------------|-----------|--------|
| Fix 1 (fusion guardrail) | P0957R8 | `missing_region_count > 0` blocks `llm_clear_soft_review` | false-pass eliminated |
| Fix 2 (reasoning hygiene) | P3556R0 | `_annotate_reasoning` flags `<ins>/<del>` claims absent from markdown | hallucination surfaced |
| Fix 3 (HTML outline) | P4020R0 | `extract_heading_outline` + injection in triage message | infrastructure confirmed, model references outline |
| Fix 4 (PDF judge floors) | P0957R8 | `content_recall < 0.85` or `text_nid < 0.80` demotes pass->review | did not fire (metrics above floor); backstop for future cases |

Fix 4 is a safety net for more extreme content-loss cases than P0957R8 (recall 0.98 is
above the 0.85 floor). It would fire on a paper where, e.g., half the pages are missing
from the markdown while the LLM still says pass.

## Fix v2: per-page recall screen + scoped escalation (2026-07-15, implemented)

The v2 backlog item ("the model is blind to localized absence even when the
content is in the prompt") is now closed by the hybrid design derived in
`research/per-page-judging/SYNTHESIS.md` (12-persona research swarm over 10
document-processing repos). The naive per-page LLM judge (one call per page,
worst-page-wins) was refuted there: at 33 pages a 1%/page false-flag rate
compounds to 28% document-level false review, and no surveyed repo runs an LLM
per page for verification. Instead:

- **Deterministic per-page recall screen** (`screen_pages` in `pdf_judge.py`):
  `content_recall(tomd_md, cleaned_page)` per dehyphenated page, computed
  lane-locally from source+markdown (never reads the det sidecar; same
  admissibility as the Fix 4 floors). Flag below `PAGE_RECALL_FLOOR=0.90`,
  skip below `PAGE_MIN_TOKENS=50`.
- **Calibration** (offline, before any code): defective p0957r8 ideal page 13
  recall 0.8810 vs >= 0.9404 on all other pages; negative control over all 8
  golden PDFs vs correct snapshots (107 non-trivial pages) has zero pages
  below 0.90 (worst healthy page 0.9129). Floor 0.90 sits in the gap: 1 true
  flag, 0 false flags.
- **Scoped escalation**: only flagged pages (cap `MAX_PAGE_ESCALATIONS=5`,
  above the cap the verdict is capped at review without calls) get one
  page-scoped LLM call (`PageJudgment`) whose prompt inherits the full
  conversion contract (YAML/TOC/figure-text/reflow sanctions). Quotes are
  grounded against the PAGE with length-relative tolerance
  (`PAGE_QUOTE_MAX_DIFFS=2`, olmocr pattern). Confirmed gap -> verdict capped
  at review with `[pN]`-attributed quotes; sanctioned -> monolith verdict
  stands, screen flag + escalation recorded in the sidecar. Escalation
  failure fails the paper (fidelity). Monolith call unchanged (global
  order/structure checks). Sidecar schema v3 (`page_screen`,
  `page_escalations`), `_LANE_VERSION=3`.

### Live simulation (2026-07-15, alliance-pod, fresh temp workspace)

**P0957R8 with the defective PR-284 ideal** (the original F1 false-pass case):
- Screen: 33 pages, exactly page 13 flagged (recall 0.881).
- Escalation `pdf-judge-page-13`: `content_missing=True`, conf 0.95, five
  grounded quotes: Figure 1 caption, Figure 2 caption, "Table 2 - Sample code
  to compile", the table header row, and a sample row.
- Lane verdict: **review** (was: pass 0.98 with `missing_content: []`). The
  lane now sees the page-13 hole ITSELF, independent of the Fix 1 fusion
  guardrail. Fusion: review/agree.
- `grounded_evidence` carries the `[p13]`-attributed quotes;
  `primary_concern` names the Figure 1 caption.

**P3556R0 with its correct golden** (negative control):
- Screen: 11 pages, zero flagged, zero escalation calls, no added cost.
- Lane verdict review (conf 0.85) comes from the unchanged monolith judgment,
  not from the screen; fusion resolves to pass (whisker_only). Pre-existing
  monolith conservatism, out of scope here.

**Regression:** full whisker suite 977 passed / 6 skipped / 3 xfailed
(baseline before v2: 941/6/3; delta is exactly the 36 new tests).

## Evidence artifacts

Debug transcripts and sidecars used for this analysis:
- `%TEMP%\pr282-review\ws\` (p4020r0, HTML)
- `%TEMP%\pr284-review\ws\` (p0957r8, PDF)
- `%TEMP%\pr285-review\ws\` (p3556r0, PDF)
- `%TEMP%\perpage-sim\ws\` (Fix v2 live simulation: p0957r8 defective ideal +
  p3556r0 golden; debug transcripts contain the `pdf-judge-page-13` call)
