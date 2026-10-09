# opus-C — MC5 / LLM-Lane Meta-Review

**Reviewer:** Meta-Reviewer C, Golden-QA Gap Research Swarm
**Date:** 2026-07-15
**Assigned personas:** 17 (LLM-Calibration-Skeptic), 25 (Steelman), 02 (marker-hybrid), 05 (surya-nougat), 12 (langextract)
**Method:** every claim re-verified against the ACTUAL modified source in
`packages/whisker/src/whisker/tapetum_llm/` (adjudicate, pdf_judge, fusion,
constants, grounding, html_outline) plus `metrics.py`, the authority doc
`tapetum_llm.md`, and prior research. Code line numbers cite the files as read
2026-07-15.

## Scoreboard

| # | Persona | Rating | One-line |
|---|---|---|---|
| 17 | LLM-Calibration-Skeptic | **CONFIRMED** | 4/5 sub-claims land verbatim in code; 1 needs a carve-out |
| 25 | Steelman | **PARTIALLY_CONFIRMED** | mechanisms real; the "72 review→pass clears" number is **untraceable** |
| 12 | langextract | **CONFIRMED** | monotonic-DP + char-interval reject are literally ported |
| 02 | marker-hybrid | **PARTIALLY_CONFIRMED** | whisker-side implications hold; repo-internal file:lines out of scope |
| 05 | surya-nougat | **PARTIALLY_CONFIRMED** | page-level pattern adopted; "no heading oracle" holds |

**Findings tally:** 9 CONFIRMED, 3 PARTIALLY_CONFIRMED, 1 REFUTED (the "72"
number, with evidence), plus repo-internal citations for 02/05 left
UNVERIFIABLE (no clone inspected in this pass).

---

## Persona 17 — LLM-Calibration-Skeptic → CONFIRMED

### 17.1 "empty-evidence passes still sanctioned" → **CONFIRMED**

The exact code path is `_custom_decide` in `adjudicate.py:300-305`:

```300:305:packages/whisker/src/whisker/tapetum_llm/adjudicate.py
    if (
        suggested_verdict == VERDICT_PASS
        and working.evidence_spans
        and not grounded
    ):
        suggested_verdict = VERDICT_REVIEW
```

The demotion requires `working.evidence_spans` to be **truthy**. A `pass` that
emitted **zero** evidence quotes has `evidence_spans == []`, so the guard is
`False` and the pass is **not** demoted. The comment above it (`:296-299`) states
this deliberately: *"Do NOT demote passes with no evidence at all (sanctioned
empty-evidence passes where working.evidence_spans is empty/falsy)."*

So there are two ways to reach 0 grounded quotes and they are treated
oppositely:

- emitted-then-all-dropped (`evidence_spans` truthy, `grounded == []`) → demoted
  to review (the #277 rule).
- emitted-nothing (`evidence_spans == []`) → **stays pass** (sanctioned).

Persona 17's RULERS-style proposal — `pass` + 0 grounded quotes + source
outline present → demote — is **not** implemented for the empty-emission case.
The half-built gate the persona describes is exactly the code above. **CONFIRMED.**

### 17.2 "`SIGNAL_AXIS_CONFLICT` works only for pass+fail contradictions" → **CONFIRMED**

`_escalation_signals` in `adjudicate.py:236-238`:

```236:238:packages/whisker/src/whisker/tapetum_llm/adjudicate.py
    verdicts = {af.verdict for af in tier1.axis_findings}
    if VERDICT_PASS in verdicts and VERDICT_FAIL in verdicts:
        signals.add(SIGNAL_AXIS_CONFLICT)
```

The signal fires **only** when the per-axis verdict set contains BOTH a `pass`
and a `fail`. Consequences, all verified against this literal boolean:

- all-axes-`pass` (the uniformly-wrong false-clear, MC5 #290): **no conflict**,
  signal never fires.
- `pass`+`review` or `review`+`fail` mixes: **no conflict** (only pass∧fail).

The constants.py comment (`:32-34`) corroborates: *"tier-1 per-axis verdicts
contain both a pass and a fail (internal contradiction)."* Persona 17's
"uniformly-wrong passes have no internal conflict" is precisely the escape
hatch this predicate leaves open. **CONFIRMED.**

### 17.3 "Remove front-matter truth from LLM scope" → **CONFIRMED (persona wording), with a mandatory carve-out**

The persona's exact wording is *"front-matter **truth**"* — the LLM only sees
the markdown, so it structurally cannot verify the title VALUE against the
source. That diagnosis is correct: MC5 #290's failure was the LLM asserting
"front-matter correctly captures the title block" for an objectively wrong
title.

BUT — and this is the sharpest finding of this review — the authority doc
**deliberately keeps front matter in LLM scope** and says so explicitly:

> `tapetum_llm.md:129`: *"Front matter is kept intact: its key order and the
> `document` id are themselves judged rules … so blanking it would hide a real
> defect class."*

So the front-matter judgment splits into two classes:

- **Markdown-internal defects** (key order, invented fields, corrupted
  `document` revision letter): visible in the markdown alone, the LLM legitimately
  judges these (`tapetum_llm.md:45`, `models.py:110-119`). Removing them from
  scope would REGRESS a live defect class.
- **Truth-vs-source defects** (wrong title value, missing `date` the source
  had): NOT verifiable from markdown, this is where the LLM false-clears. This
  belongs in a deterministic YAML-vs-source gate (MC1, persona 13, `gates.py`).

**Verdict:** persona 17's finding as written ("front-matter *truth*") is
CONFIRMED. The **task's broader paraphrase** ("remove front-matter from LLM
scope") is only safe with the carve-out above; stripping the whole YAML block
before injection would blind the LLM to the order/document-id class that
`tapetum_llm.md:129` intentionally assigns to it. See "MC5 fix feasibility"
below.

### 17.4 "Heading-level NOT fixable by LLM even with outline injection" → **CONFIRMED**

The outline IS injected today — `_build_triage_message` in `adjudicate.py:395-406`:

```395:406:packages/whisker/src/whisker/tapetum_llm/adjudicate.py
    outline_block = ""
    try:
        source_path = ctx.backend.get_source_path(ctx.pid)
        if str(source_path).lower().endswith((".html", ".htm")):
            html_source = source_path.read_text(encoding="utf-8", errors="replace")
            outline = format_outline(extract_heading_outline(html_source))
            if outline:
                outline_block = f"\n{outline}\n\n"
    except Exception:
        pass
```

This is a text HINT handed to the model — no deterministic comparison happens.
Baseline `00-baseline.md:63,65` records that WITH this exact injection the LLM
still false-cleared (#282: claimed "outline matches exactly" when
`### References` ≠ source `h2`) AND false-positived (#295: flagged a genuine
`h2→h3` source jump). Injecting the oracle and asking the LLM to reason over it
demonstrably does not work. The persona's prescription — a **deterministic**
source-vs-markdown outline diff — is the correct replacement. **CONFIRMED.**

### 17.5 "Bias-adjusted calibration requires labeled holdout first" → **CONFIRMED**

Consistent with `constants.py:16-28,75-78` which stamps the escalation band and
selection thresholds as *"PROVISIONAL … must be refit on the labeled review
set"*. No labeled holdout exists in-repo, so any Platt/VERDI recalibration is
premature. **CONFIRMED** as a methodological gate.

---

## Persona 25 — Steelman → PARTIALLY_CONFIRMED

### 25.x "72 review→pass clears in sighting run" → **REFUTED (untraceable)**

I grepped `72` across `research/` and `packages/whisker/` (all sidecars,
reports, prior research). The string **"72 review→pass"** appears in **exactly
one place: the persona-findings doc itself** (`10-persona-findings.md:145`). It
is in no sidecar, no report, no prior synthesis.

The traceable figure is different. The 2026-07-14 golden-review findings say:

> `tapetum-golden-review-findings-2026-07-14.md:35-37`: *"`20-false-fail-hunter.md`
> designed the `llm_clear_soft_review` rule as an intentional **44% queue-shrink**
> mechanism."*

And the reproduced cross-tabs in prior research report *"3/74 pass→review"* and
*"9/9 review"* RESCUE outcomes over **197** sidecars
(`llm-stack/11-false-positive-hunter.md:12`, `opus-B-gates-logic.md:30`), never
"72 review→pass clears." The **mechanism** persona 25 defends — that narrowing
`llm_clear_soft_review` (fusion.py:187-202) would undo a real queue-shrink — is
CONFIRMED and the rule is live. But the specific **number 72 is fabricated or
mis-transcribed**; the defensible figure is "44% queue-shrink." Rated
**REFUTED** as to the number, **CONFIRMED** as to the mechanism.

### 25.other — the rest of the steelman → **CONFIRMED**

Every other "what works" claim traces to code:

- `clear_blocked_missing_region` prevents unsafe LLM upgrade →
  `fusion.py:171-184` (`FUSION_RULE_CLEAR_BLOCKED_MISSING_REGION`),
  demonstrated on P0957R8 (`golden-findings:128,144`). **CONFIRMED.**
- ungrounded quotes dropped → `grounding.py:238-239` + `adjudicate.py:294-295`.
  **CONFIRMED.**
- rubric-bleed annotated → `pdf_judge.py:111-126` (`_annotate_reasoning`,
  `_MARKUP_CLAIM_TOKENS`). **CONFIRMED.**
- `screen_pages` closed p0957r8 end-to-end → `pdf_judge.py:279-304`; calibration
  cites p0957r8 page-13 recall 0.8810 (`constants.py:149-154`). **CONFIRMED.**
- PR #293 LLM found 31 dropped `constexpr`; PR #286 three-lane agreement →
  traceable to `00-baseline.md:66` (runtime PR evidence, not code). **CONFIRMED**
  as documented.

Overall persona 25 verdict: **PARTIALLY_CONFIRMED** (one refuted number inside
an otherwise accurate steelman).

---

## Persona 12 — langextract → CONFIRMED

Both load-bearing claims verify literally:

- "Monotonic exact-DP already in whisker's grounding.py" → `grounding.py:102-168`
  is a named port of langextract's `_select_monotonic_matches` (docstring
  `:14-21` credits `resolver.py`, Apache-2.0). **CONFIRMED.**
- "`char_interval is None` drop / anti-hallucination" → the post-alignment guard
  `grounding.py:224-228` refuses any interval whose raw slice does not normalize
  back to the quote, and `:238-239` drops it. langextract's looser LCS fuzzy
  tier is explicitly **not** ported (`:18-21`). **CONFIRMED.**
- "No MC1-MC4 fix; only tightens MC5 evidence" → correct; grounding touches only
  evidence spans, never metadata/TOC/golden. **CONFIRMED.**

Rating: **CONFIRMED.** (The optional plural-stemming suggestion is a feasible
~7 LOC add, not a claim to verify.)

---

## Persona 02 — marker-hybrid → PARTIALLY_CONFIRMED

The whisker-side implications verify; the marker repo internals were not
re-cloned this pass.

- "lane separation, Pydantic validation, block-scoped sanity gates are portable"
  → whisker already embodies all three: det vs LLM lanes are separate
  (`whisker/CLAUDE.md`), structured output is Pydantic (`PdfJudgment` at
  `pdf_judge.py:236-252`, `Adjudication` via `output_type` at
  `adjudicate.py:356-357`), and reject-and-keep floors exist
  (`pdf_judge.py:517-530` demote pass→review on recall/nid floors). **CONFIRMED
  (whisker side).**
- "marker has no title/author/date validation; does not close MC1" → aligns with
  the fact that whisker's LLM lane also cannot validate front-matter truth
  (17.3). **Plausible / consistent**, but marker's own `metadata = TOC +
  page_stats` file:lines are **UNVERIFIABLE** here (no clone read).

Rating: **PARTIALLY_CONFIRMED.**

## Persona 05 — surya-nougat → PARTIALLY_CONFIRMED

- "Both scope QA to page level" → whisker adopted exactly this: the deterministic
  per-page recall screen `screen_pages` (`pdf_judge.py:279-304`) + scoped page
  escalation (`:307-340`). Pattern is live. **CONFIRMED (whisker side).**
- "no heading-level oracle, no front-matter plausibility" (in surya/nougat) →
  mirrors whisker's own gap: the LLM lane injects an HTML outline but never
  diffs it deterministically (17.4), and has no deterministic heading oracle for
  PDFs at all (PDF path skips outline injection — `adjudicate.py:398` gates on
  `.html`/`.htm` only). **CONFIRMED as a gap that applies to us too.**
- Surya `_detect_repeat_loop`, nougat `[MISSING_PAGE_FAIL:n]`, `varvar<0.045`
  file:lines → **UNVERIFIABLE** here (no clone read).

Rating: **PARTIALLY_CONFIRMED.**

---

## MC5 fix feasibility — "remove front-matter from LLM scope + deterministic heading-outline diff"

Assessed against the actual prompt construction. Two halves, different verdicts.

### Half A — deterministic heading-outline diff → **FEASIBLE, clean, highest impact**

All building blocks already exist in-repo:

- source HTML outline: `html_outline.extract_heading_outline()` →
  `[(tag, text)]`, already computed for the prompt (`adjudicate.py:400`).
- markdown outline: `metrics._parse_headings(md) -> list[tuple[int, str]]`
  (`metrics.py:583`) + `_build_heading_tree` (`:653`), the same mistune AST
  whisker's `mhs` uses.

A deterministic comparator (map `h1..h6`→levels `1..6`, compare the level
sequence markdown-vs-source, emit a structural flag on divergence) needs **no
LLM** and reuses two existing functions. It **replaces** the failed inject-and-
ask approach (17.4) that produced both #282 (false-clear) and #295 (false-
positive). This is the single most impactful MC5 move: it converts a
provably-unreliable LLM judgment into a pure-Python diff. **FEASIBLE.**

### Half B — "remove front-matter from LLM scope" → **FEASIBLE mechanically, but REQUIRES a carve-out**

Mechanically trivial: strip the leading `---…---` YAML block from `md` before
`ctx.inject_untrusted(md)` in `_build_triage_message` (`adjudicate.py:413`).

**But it conflicts with a deliberate design decision.** `tapetum_llm.md:129`
keeps front matter in scope on purpose so the LLM judges **key order** and a
**corrupted `document` revision id** — a real defect class the model CAN see in
the markdown alone. Blanket removal regresses that.

The correct, minimal MC5 fix is therefore:

1. **Keep** the YAML block in the LLM prompt (order / document-id defects stay
   in scope).
2. **Add a deterministic YAML-vs-source check** in `gates.py` (this is MC1,
   persona 13) so the truth question (wrong title VALUE, missing `date`) is
   answered where the source is actually available. The LLM stops being the
   authority on front-matter truth without being blinded to front-matter
   structure.
3. **Add the deterministic heading-outline diff** from Half A.

Net: the truth-validation the LLM cannot do moves to a deterministic gate; the
structural checks it can do stay; heading levels leave the LLM entirely. No LLM
prompt/model change is required for the parts that matter (Half A + the MC1
gate); Half B's safe version is a *no-op on the prompt* plus a new deterministic
gate.

---

## False-pass hypothesis

A clean-looking HTML paper whose tomd output has a wrong front-matter title
(first body heading leaked into `title:`) and a single `h2→h3` heading collapse.
Today: the LLM sees the YAML, asserts the title "looks correct" (it cannot check
the source), emits **zero evidence** (nothing looks wrong to it), returns
`pass`. `_custom_decide` does not demote a zero-evidence pass (17.1), no
`SIGNAL_AXIS_CONFLICT` fires because all axes are `pass` (17.2), fusion sees
det=pass + llm=pass → `agree`. Combined: **pass**. Both MC1 and MC5 slip
through. The Half-A diff + MC1 gate close it deterministically.

## False-fail hypothesis

A paper with a legitimate `h2: References → h3: Informative References` source
nesting (PR #295's real structure). A naive heading-diff that flags any
level-increase would REJECT it. The deterministic comparator MUST diff against
the **source** outline (`extract_heading_outline`), not against an abstract
"levels must be flat" rule — otherwise Half A trades the LLM false-positive for
a deterministic one. The building blocks support source-anchored diffing, so
this is avoidable, but it is the trap to test first.

## What would change my mind

For 17.1: a test or code path showing an empty-`evidence_spans` `pass` being
demoted somewhere downstream (fusion, CLI) that I missed — I found none. For the
"72" number (25): any sidecar, report, or sighting-run transcript in-repo
containing "72 review→pass clears" — the string exists only in the persona doc.

---

## Returns

**(a) Findings confirmed / refuted:** 9 CONFIRMED, 3 PARTIALLY_CONFIRMED, **1
REFUTED** (persona 25's "72 review→pass clears"). Repo-internal file:line
citations for personas 02 and 05 left UNVERIFIABLE (no clone inspected this
pass); their whisker-side implications are confirmed.

**(b) Single most impactful MC5 adoption:** the **deterministic
source-vs-markdown heading-outline diff** (persona 17.4). Both building blocks
already exist (`html_outline.extract_heading_outline` + `metrics._parse_headings`),
it needs **no LLM change**, and it directly kills the two documented MC5 heading
failures (#282 false-clear, #295 false-positive) that outline *injection* could
not. Pair it with a deterministic YAML-vs-source front-matter gate for MC1;
leave the LLM prompt otherwise untouched.

**(c) Refuted with evidence:** persona 25's *"72 review→pass clears in sighting
run."* The number appears nowhere except `10-persona-findings.md:145` — not in
any sidecar, report, or prior synthesis. The defensible, traceable figure is the
*"44% queue-shrink"* the `llm_clear_soft_review` rule was designed to produce
(`tapetum-golden-review-findings-2026-07-14.md:35-37`), with reproduced counts
of "3/74 pass→review" over 197 sidecars. The mechanism is real; the "72" is not.
