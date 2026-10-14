# 24 - The False-Positive Hunter

**Verdict:** usable-with-conditions — the unigram hard floor catches real content loss (3/382), but 64% of hard fails and ~21–25% of the corpus are false alarms (heading pedantry + benign misaligned-region review).
**Confidence:** high

## Findings

- [CRITICAL] **Heading-monotone hard-fails are the dominant false-fail class: 9/14 hard fails (64%), all with uni ≥ 0.947, on conversions that read cleanly.** Evidence: ref-free run `14 failed, 205 review, 163 passed (382 scored)` (`00` §3a); live re-run 2026-06-25 confirms same 9 papers — `n5035`, `n5037`, `n5043`, `p3161r5`, `p3647r1`, `p3941r2`, `p3941r3`, `p3941r4`, `p4160r0` — with `uni` 0.947–0.999 and sole hard flag `gate:heading_monotone` (`gates.py:105-109`, `score.py:152-154`). Impact: QA equates “broken, not shippable” with PDF-faithful heading depth skips; triage treats good papers as hard fails.

- [HIGH] **P3941R2/R3/R4 are confirmed false hard-fails: near-perfect metrics, fail only on H2→H4.** Evidence: `P3941R2 uni=0.999 drift=0.002 qa=95`; `P3941R3 uni=0.999 drift=0.001 qa=95`; `P3941R4 uni=0.998 drift=0.003 qa=95` (runtime); `p3941r2.md` shows `## 4 Wording Changes` immediately followed by `#### 4.0.1 execution::get_start_scheduler` (WG21 wording section numbering skips H3, matching the PDF). Impact: 3 revisions of the same paper hard-fail for typography, not comprehension or content loss.

- [HIGH] **Review tier is majority noise: 205/382 (53.7%) sent to human, driven by flags the spec declares benign.** Evidence: `186 soft misaligned region(s)` vs `163 pass` (`00` §3a); `constants.py:43-47` (“tomd deliberately strips furniture… expected on clean papers”); `CLAUDE.md:231-236` (“Misaligned regions are soft only… expected on clean papers”). **70 papers (18.3% of corpus, 34.1% of review tier)** have *only* a misaligned-region flag with `uni ≥ 0.95` — no review-band, drift, qa, or uncertain signal (runtime Python API sweep). Impact: more than half the corpus needs human eyes; ~1/3 of review queue is furniture-stripping alone.

- [HIGH] **Combined cry-wolf rate ≈ 21–25% of corpus on ref-free path.** Evidence: conservative false burden = 9 heading false-fails + 70 pure-misaligned reviews = **79/382 (20.7%)**; aggressive upper bound adds 87 review papers with `uni ≥ 0.95`, `drift ≤ 0.10`, no review-band flag = **96/382 (25.1%)** (runtime). Impact: a QA tool that flags ~1 in 4 good conversions erodes trust in both fail and review tiers.

- [MED] **Pass tier requires zero misaligned regions — all 163 passes have `missing+extra == 0`; any furniture strip guarantees review.** Evidence: runtime sweep — lowest passing `uni` is ~0.9505 (`p4136r0`) but every pass has 0 region count; `score.py:164-166` fires at `REGION_SOFT_COUNT = 1`. Impact: structural asymmetry — you cannot pass with the single-region mismatch the spec calls expected; triage ceiling is 42.7% auto-pass regardless of content quality.

- [MED] **Meeting-minute headings (n5035/n5037/n5043) false-fail on H1→H3 with uni 0.947–0.953.** Evidence: `n5035.md` opens `# 2026-03 WG21 admin telecon` then `### Teleconference information` (H1→H3); runtime `n5035 uni=0.953 gate:heading_monotone:heading level jumps H1 -> H3`. Impact: non-paper artifacts use title-as-H1 conventions; monotone gate treats them like broken WG21 papers.

- [MED] **`no_empty_table` hard-fails (2/14) are debatable, not clear false-fails.** Evidence: `p3290r4 uni=0.982` and `p4012r1 uni=0.909` fail on `table separator with no data row` (`gates.py:147-149`); `p3290r4.md` has straw-poll tables with separator then `|  |  |  |  |  |` empty row. Impact: may be PDF-faithful spacer rows or tomd artifacts — without labeled GT, treat as MED false-fail risk, not confirmed good.

- [LOW] **True hard-fails exist and are rare: 3/382 (0.8%) on unigram floor.** Evidence: `p3978r0 uni=0.811`, `p4167r0 uni=0.837`, `p4231r0 uni=0.843` (`00` §3a; runtime); `P3978R0` shows missing front-matter/contents tokens in region detail. Impact: content gate works when words are actually gone; false-positive problem is not total instrument failure.

## False-pass hypothesis

**Borderline pass at the 0.95 review edge:** `p4136r0` passes with `uni=0.9505`, zero regions, no soft flags (runtime), sitting 0.0005 above `UNIGRAM_COVERAGE_REVIEW_EDGE` (`constants.py:38`). Without labeled GT or Lane 3 facts, cannot prove content loss, but the pass band is a knife-edge — a paper losing ~5% of vocabulary still auto-passes if furniture aligns perfectly. No confirmed broken conversion found in the 382-paper corpus that whisker passes.

## False-fail hypothesis

**P3941R2** (and R3/R4): `uni=0.999`, `drift=0.002`, `qa=95`, full prose and code intact; hard-fail solely because `## 4 Wording Changes` jumps to `#### 4.0.1` (`gates.py:105-109`, `p3941r2.md`). A human would ship this; whisker hard-fails it.

**Secondary:** 70 papers (e.g. high-`uni` passes’ neighbors) sit in review with only `1 misaligned region(s)` — furniture stripping the spec calls expected (`constants.py:43-47`) — e.g. any paper matching the P3941 metrics but with a single header/footer region mismatch.

## What would change my mind

A labeled corpus (30–50 papers, `whisker calibrate --labels`) showing measured FPR ≤ 10% at the chosen operating point **after** demoting `heading_monotone` to soft/review (or PDF-aware level normalization) and raising `REGION_SOFT_COUNT` above 1 — with TPR/FPR/precision recorded per flag class, not just unigram coverage.
