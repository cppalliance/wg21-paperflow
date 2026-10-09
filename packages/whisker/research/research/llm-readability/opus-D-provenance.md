# opus-D - Provenance / Ground-Truth of Claims

Meta-reviewer D. Every load-bearing claim in personas 01, 02, 08, 15, 25 re-verified
against code and documents at repo SHA `e66116a09bbe833a8080e9e60a95833ab339cf64`
(2026-07-06), not on the personas' word. A claim I could not reproduce is
DOWNGRADED or DROPPED, stated explicitly. Method: read the cited file:line, read
the surrounding function, and check the compensating paths the personas did not cite.

Verdict legend: **SURVIVED** (reproduced exactly), **SURVIVED-NARROWED** (core true,
scope tighter than stated), **DOWNGRADED** (severity or framing overstated),
**DROPPED** (not reproducible).

---

## Claim 1 - Confident-pass grounding gap at `adjudicate.py:237`

**Verdict: SURVIVED (exact).** The single most load-bearing finding of the cluster.

The line is verbatim what four personas quote:

```237:240:packages/whisker/src/whisker/tapetum_llm/adjudicate.py
    if suggested_verdict != VERDICT_PASS and not grounded:
        suggested_verdict = VERDICT_REVIEW
    if confidence < CONFIDENCE_DECISION_FLOOR:
        suggested_verdict = VERDICT_REVIEW
```

`_custom_decide` (`adjudicate.py:215-272`) is the ONLY place a verdict is set.
`ground_spans` (`grounding.py:24-56`) returns `(grounded, dropped)` and contains
zero verdict logic, so it cannot compensate. The CLI persists whatever the
pipeline produced (`cli.py:320` `verdict_str = result.suggested_verdict`) and only
counts it, no compensation. `inspect_report.py:96-99` DISPLAYS "N kept, M dropped"
to a human but never mutates the verdict. So a `pass` whose every emitted span was
dropped as ungrounded exits as `pass` in the sidecar. No path compensates.
**Confirmed against the three files the prompt named.**

Load-bearing nuance the personas split on (I side with persona 25). There are two
`pass` sub-cases and the code treats them identically:
- (a) `pass` with NO evidence emitted: prompt-SANCTIONED (`tapetum_llm.md:99`
  "If the conversion is faithful, say `pass` with high confidence and empty
  evidence"). Legitimate.
- (b) `pass` that emitted spans, ALL dropped by grounding: the actual gap.

The correct fix must therefore gate on `working.evidence_spans and not grounded`,
which is exactly what `SYNTHESIS.md:32` and persona 25 finding MED (line 22)
specify. Persona 01's "what would change my mind" ("demote any pass when
`grounded` is empty") and persona 08's occasional shorthand are imprecise: a
naive `not grounded` demotion would wrongly demote the sanctioned empty-evidence
pass (a). This does not weaken Claim 1; it sharpens the fix. `TapetumResult`
(`models.py:89-124`) carries `ungrounded_dropped` but no `evidence_was_emitted`
flag, so the sidecar cannot distinguish (a) from (b) post-hoc (persona 25 MED,
verified).

Corroborating constants (all verified): `CONFIDENCE_DECISION_FLOOR = 0.50`
(`constants.py:28`), `CONFIDENCE_AMBIGUOUS_LO/HI = 0.35/0.65` (`constants.py:22-23`),
`EVIDENCE_FUZZY_FLOOR = 0.90` (`constants.py:50`). `SYNTHESIS.md:19` calls it
"Fix: one code change"; `SYNTHESIS.md:32` gives the exact branch. Confirmed.

---

## Claim 2 - All three #277 blocking conditions still open

**Verdict: SURVIVED (all three).**

- **Condition 1 (grounding gap fix):** unchanged, see Claim 1. `adjudicate.py:237`
  still exempts `pass`.
- **Condition 2 (ground-truth the sighting run):** no completion artifact exists.
  The sighting-run doc lists suggested review targets at
  `tapetum-sighting-run-2026-07-01.md:69-73`, and CRUCIALLY the 72 `review -> pass`
  clears are NOT even on that suggested-audit list (it names only the 6 `fail ->
  review`, 13 `review -> fail`, 4 `pass -> review`). Per-paper sidecars live in
  gitignored `data/whisker/` (`:77-80`). A repo-wide search for an audit/gold/
  mini-eval artifact returned only persona reports and `buildvsbuy/` studies, no
  labeled false-clear audit. So condition 2 is not just open, the 72 headline
  clears are LESS audited than personas imply (persona 25's citation "listed as
  suggested review targets" is slightly generous; the yield table at `:28` lists
  them, the audit-targets section at `:69-73` does not).
- **Condition 3 (vLLM v0.24.0 flags):** the `alliance-pod` service declaration
  carries endpoint, model, context window only, with zero vLLM flag comments:

```64:74:SERVICES.toml
[services.alliance-pod]
backend = "vllm_thinking"
base_url = "https://sgjy18glyi4blu-8000.proxy.runpod.net/v1"
api_key = "$ALLIANCE_POD_KEY"
model = "deepseek-v4-pro"
max_context_window = 393216
chars_per_token = 4.0
token_multiplier = 1.5
thinking_capable = true
tools_capable = true
stream = true
```

No `v0.24`, `reasoning-parser`, `tokenizer-mode`, or `tool-call-parser` anywhere in
`SERVICES.toml`. `SYNTHESIS.md:35` itself lists this as an open bug ("SERVICES.toml
V4 entries lack any comment about required vLLM flags"). Persona 25's citation
`SERVICES.toml:64-74` matches exactly. Confirmed.

---

## Claim 3 - Tier1 -> tier2 unwrapped-reasoning injection (persona 01 HIGH)

**Verdict: SURVIVED-NARROWED (real path, latent/unexercised).**

The tier-2 message builder concatenates raw tier-1 model output into the header as
trusted pipeline context, and wraps ONLY the paper body:

```338:349:packages/whisker/src/whisker/tapetum_llm/adjudicate.py
    header = (
        f"Paper: {ctx.pid}\n"
        f"Whisker verdict: {signals.get('verdict', 'unknown')}\n"
        f"Flags: {flags_str or 'none'}\n\n"
        f"Tier 1 reasoning: {tier1.reasoning}\n"
        f"Tier 1 verdict: {tier1.verdict} (confidence {tier1.confidence:.2f})\n"
        f"Tier 1 worst axis: {tier1.worst_axis}\n"
        f"Tier 1 concern: {tier1.primary_concern}\n\n"
        f"Converted Markdown:\n"
    )
    wrapped_md = ctx.inject_untrusted(state.paper_md)
    return header + wrapped_md
```

Tier-1 itself was produced FROM the untrusted paper body (`adjudicate.py:327`,
`wrapped_md = ctx.inject_untrusted(md)`), so paper-controlled text can steer
`tier1.reasoning`/`primary_concern`, which then re-enter tier-2 OUTSIDE the
`inject_untrusted` envelope. The delimiter escape (`tools.py`) and framework floor
never touch these fields. Persona 01's file:line anchors (342-345, 348, 327) are
all exact. **The vulnerability is real but LATENT:** tier-2 only runs when tier-1
confidence lands in `[0.35, 0.65]` (`adjudicate.py:207`), and the 2026-07-01
sighting run had 0/196 escalations (`tapetum-sighting-run-2026-07-01.md:21-22`),
so this path has never executed in production. Narrowed from "active steer" to
"latent injection path, unexercised to date." Still a valid pre-landing hardening
requirement.

---

## Claim 4 - Apache-2.0 attribution gap for OmniDocBench ports (persona 02 HIGH)

**Verdict: SURVIVED (exact).**

Three verbatim Apache-2.0 ports, header-documented as such:

```392:399:packages/whisker/src/whisker/metrics.py
# -- TEDS (tables) -----------------------------------------------------------
#
# Verbatim port of PubTabNet/OmniDocBench TEDS (Apache-2.0, IBM peter.zhong):
# _bench_src/OmniDocBench/src/metrics/table_metric.py. The only adaptations are
# privatizing the names, dropping the batch/CLI helpers, and a defensive
# zero-denominator guard. The algorithm (lxml DOM -> APTED, char-token cell
# content, xpath-descendant denominator, td-only content, strict tag/colspan/
# rowspan rename) is unchanged so scores match the published table leaderboards.
```

Also `metrics.py:88-96` ("Content normalization ported VERBATIM from
OmniDocBench") and `match.py:23-24` ("Faithful to ...OmniDocBench...
match_quick.py"). A workspace glob for `NOTICE`/`THIRD_PARTY_NOTICES` returned
**zero files**; only the root `LICENSE_1_0.txt` (BSL) exists. Apache-2.0 §4(c)/(d)
requires reproducing upstream copyright + license (and NOTICE contents) on
redistribution of a derivative work. Verbatim ports + no NOTICE = a real
redistribution-attribution gap for a public repo. This is attribution hygiene, not
copyleft infection (BSL + Apache combine fine). Persona 02's anchors all verified.
The `match.py` header says "Faithful to" rather than persona 02's "ports"; same
substance (it is a port, self-described).

---

## Claim 5 - Documentation contradiction (persona 08 CRITICAL/HIGH)

**Verdict: DOWNGRADED (real but narrow; the mechanism-level docs are honest).**

Persona 08 frames the docs as claiming the gap is closed. The evidence does not
support that framing at the mechanism level:

- The AUTHORITY prompt doc is ACCURATE and openly discloses the pass exemption:
  `tapetum_llm.md:156` "Demote to `review` ... when: no grounded evidence survives
  and the verdict is not `pass`". Persona 08 itself concedes this ("correctly
  scopes demotion").
- The whisker package doc `packages/whisker/src/whisker/CLAUDE.md:387-389` reads:
  "an ungrounded **non-pass** or sub-floor confidence demotes to `review`. The
  lane never turns uncertainty into a pass/fail." The phrase "non-pass" literally
  telegraphs that `pass` is NOT demoted. So this doc does NOT "read as if the gap
  were closed"; it describes the exact asymmetric behavior the code implements.
- The code comment `adjudicate.py:234-236` uses the same honest wording
  ("an ungrounded fail/review keeps the human").

The ONLY genuine overreach is the aspirational tagline "The lane never turns
uncertainty into a pass/fail," which is contradicted by case (b) of Claim 1 (a
pass whose grounding-revealed uncertainty is not acted on). That is a real but
MINOR wording defect, not a hidden doc-vs-code contradiction. Note also a
citation-hygiene issue: persona 08's bare `CLAUDE.md:387-389` is the WHISKER
package CLAUDE.md, while persona 01's bare `CLAUDE.md:155` is the ROOT CLAUDE.md
(173 lines total; it has no line 387). The personas conflated two different files
under one name. **Downgraded from CRITICAL to MED.** The corrective action
(update the tagline, land condition 1) is still valid.

---

## Claim 6 - Downstream consumer breaks tables; assay vs dissect provenance

**Verdict: SURVIVED-NARROWED, and the citation dispute RESOLVED in persona 15's
favor.**

Provenance resolution (the prompt's explicit question): the baseline (`00`) and
several docs say consumers are "dissect/agora." A glob confirms **`packages/dissect`
does not exist at this SHA**; only `packages/assay` and `packages/agora` have a
`pipeline.py`. So the baseline's "dissect" is STALE and persona 15 is CORRECT to
cite `assay` as the real paper-markdown consumer (persona 15 LOW documents the
dissect->assay rename; `agora/models.py` still carries legacy `dissect_*` field
names, verified indirectly via `agora/pipeline.py:261-267` `dissect_claims`/
`dissect_evidence`/`dissect_markers`). **The citation is real; the baseline's is the
imprecise one.**

Cited assay code, all verified to exist and say what persona 15 claims:
- `chunk_paper` invoked in Survey: `assay/pipeline.py:525-528`. Verified.
- Per-chunk injection is line-windowed: `assay/pipeline.py:208-212`
  `format_numbered_lines(paper_lines, chunk.start_line, chunk.end_line)` then
  `ctx.inject_untrusted(numbered)`. Verified (and it IS wrapped, unlike agora).
- Chunker has no table-atomic guard: `assay/chunker.py:19-20` splits only on
  `_HEADING_RE` and `_BOLD_SUBSECTION_RE`; `_flatten` (`:152-174`) and
  `_split_bold_subsections` (`:209-253`) never inspect pipe tables. Verified.
- Oversized-section paragraph split: `assay/rag.py:135` `re.split(r"\n\n+", ...)`.
  Verified.

NARROWING: persona 15's specific phrasing "an entire table is one paragraph and can
still be **truncated** against a char budget" / "table rows straddle chunk seams" is
imprecise. A standard contiguous pipe table has no blank lines, so `\n\n+` keeps it
as ONE paragraph, and `rag.py:141-159` never splits a single oversized paragraph:
it emits it whole (over budget), it does not drop rows. Rows only straddle a seam if
the table itself contains a blank line or a `**N.N**` bold-numbered line, or if a
chunk boundary (heading) falls between table fragments. So the concrete failure is
"a wide table lands in an oversized chunk that blows the token budget, or a
heading-separated table fragment gives a partial view," NOT "rows are silently
truncated mid-table." The CRITICAL core survives: Lane 3 checks neighbor relations
on the FULL grid, while assay's LLM only ever sees line-windowed chunks
(`chunk_paper` produces line ranges, never the whole `paper.md`), so a full-grid
`table` fact pass does not certify per-chunk comprehension. Direction is false-pass,
as persona 15 states.

Bonus verification (persona 01 LOW + persona 15 MED, agora): `agora/pipeline.py:157`
sets `state.paper_source = paper_md`, and `:268` and `:454` inject
`## Paper Source\n\n{state.paper_source}` with **zero** `inject_untrusted` (grep for
`inject_untrusted` in `agora/pipeline.py` returns nothing). So agora feeds raw,
unwrapped paper markdown into LLM prompts. The untrusted-data contract named at root
`CLAUDE.md:155` as `pipeline.tools.wrap_source` is (a) named after a function that
does not exist (the live API is `inject_untrusted`, `tools.py:49` / `runner.py:119`;
`wrap_source` appears only in docs/research, never as a `def`), and (b) not enforced
in agora. Both persona LOW findings SURVIVED.

---

## Cluster summary

The cluster's spine is one verified defect: the confident-pass grounding gap
(`adjudicate.py:237`). It is reproduced exactly, no compensating path exists in the
three files named (grounding.py, cli.py, inspect_report.py), and it anchors #277
condition 1, persona 01's false-pass, persona 08's tagline overreach, and persona
25's "no code path catches a confidently wrong pass." All three #277 blocking
conditions are genuinely open, with condition 2 slightly worse than advertised (the
72 clears are not even on the in-repo audit-target list). The Apache-2.0 NOTICE gap
is real and legally precise. The tier1->tier2 injection path is real but latent
(0 escalations ever). Two things needed correction: persona 08's "docs claim the
gap is closed" is DOWNGRADED because the mechanism-level docs (`tapetum_llm.md:156`,
whisker `CLAUDE.md:387-388` "non-pass") honestly disclose the exemption, only the
tagline overreaches; and persona 15's "tables truncated / rows straddle seams" is
NARROWED to "full-grid Lane 3 facts do not certify assay's line-windowed per-chunk
views" (contiguous pipe tables are kept whole, not row-split). The dissect-vs-assay
provenance question resolves cleanly in persona 15's favor: `packages/dissect` is
gone, assay is the real consumer, the baseline citation is the stale one. Nothing
was DROPPED entirely; two findings were narrowed, one downgraded.

Citation-hygiene note for downstream readers: "CLAUDE.md" is ambiguous across these
personas (root, 173 lines, vs the whisker-package copy at 387+ lines). Anchor by
package path, not bare filename.
