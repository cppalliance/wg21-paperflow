# Meta-reviewer A - Load-bearing code claim re-verification

Date: 2026-07-22. All claims re-checked against the working tree at
`C:\Users\sabo2\Desktop\cppalliance` (HEAD `51cb704`, dirty; matches the baseline's
recorded state). Method: direct file reads plus `rg` cross-checks; no code executed,
no files modified outside this report.

**Tally: 10/12 CONFIRMED, 2 PARTIAL (claims 3 and 5), 0 REFUTED.**

---

## Claim 1: `route_pdf_units` never reads `PageUnit.has_tables`

**VERDICT: CONFIRMED.**

- `route_pdf_units` spans `packages/whisker/src/whisker/tapetum_llm/source_router.py:149-233`.
  It reads exactly five `PageUnit` attributes: `unit.text` (lines 163-165, 174-176),
  `unit.page` (182, 192), `unit.content_tokens` (193), `unit.caption_lines` (206-208),
  `unit.heading_candidates` (218-220). `has_tables` never appears.
- Workspace-wide `rg has_tables` over `packages/whisker/src`: the only occurrences are
  the field definition and assignment sites. PDF: `textlayer.py:94` (dataclass field),
  `textlayer.py:272` (assignment). HTML: `html_outline.py:53, 105, 120, 127, 148`.
  Zero read sites anywhere in the lane. `route_html_units`
  (source_router.py:236-317) likewise never reads `SectionUnit.has_tables`.
- Where it IS computed (`textlayer.py`): `_block_looks_tabular` at lines 160-170
  (>= `_TABLE_MIN_COLUMNS`=2 nonempty spans per line on >= `_TABLE_MIN_ROWS`=2 lines,
  constants at lines 77-78); `has_table_structure` accumulated at lines 220-224;
  `has_table_caption` at lines 253-255; OR-combined into page metadata at line 260;
  assigned to `PageUnit.has_tables` at line 272.

The signal is computed, stored, and dies unread. No `signal_type` for tables exists in
the router (only `token_delta`, `low_recall`, `missing_captions`, `heading_drift` on
the PDF path).

## Claim 2: severity-then-LEXICAL unit_id sort, cap at MAX_UNIT_CHECKS=5

**VERDICT: CONFIRMED.**

- Exact sort key, `unit_judge.py:225-234`:

```python
severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
sorted_signals = sorted(
    risk_signals,
    key=lambda s: (
        severity_rank.get(s.severity, 3),
        s.unit_id,
        s.signal_type,
        s.detail,
    ),
)
```

  `s.unit_id` is a plain string (`"page:13"`), so within a severity tier the sort is
  lexicographic: `"page:13" < "page:2"` because `"1" < "2"`. The baseline's
  displacement mechanism is real.
- Cap: `selected_unit_ids = risky_unit_ids[:MAX_UNIT_CHECKS]` at `unit_judge.py:239`,
  overflow to `unchecked_unit_ids` at line 240. Unit order comes from
  first-signal insertion into `signals_by_unit` (lines 235-238), i.e. inherits the
  lexical signal sort.
- Constant: `constants.py:223` reads `MAX_UNIT_CHECKS = 5`, docstring at lines 224-227.

## Claim 3: html_outline collects ALL heading descendant text incl. span.secno; no normalization between extraction and comparison

**VERDICT: PARTIAL** (collection claim exact; "no normalization exists" is overstated,
but no normalization strips the secno label, so the miss mechanism holds).

- Collection, `_HeadingExtractor` (`html_outline.py:57-81`): `handle_data` at lines
  79-81 appends every text node while `self._in_heading` is set, with no attribute or
  class filtering; `handle_starttag` (66-69) never inspects child-element classes, so
  text inside `<span class="secno">1.</span>` is captured. Join at lines 71-77.
  Same pattern in `_SectionExtractor.handle_data` at lines 168-172 (heading text
  branch 169-170).
- What normalization DOES exist between extraction and comparison: the router's
  `_text_key` (`source_router.py:57-58`) = `normalized_text(text).casefold()`, where
  `normalized_text` (`whisker/metrics.py:342-344`) is OmniDocBench unicode cleanup +
  whitespace collapse. That is case/whitespace/unicode normalization only. `rg -i secno`
  over `packages/whisker/src`: zero matches. No code anywhere strips section-number
  labels, so source `1. Abstract` and candidate `1. Abstract` produce identical keys at
  the comparison site (`route_html_units`, `source_router.py:249-262`) and no
  `heading_drift` signal fires.
- The metadata/outline LLM check receives the raw collected outline verbatim via
  `format_outline` (`html_outline.py:187-208`) and the prompt
  (`unit_judge.py:79-91`) contains no secno-stripping rule.

Truth: normalization exists (whitespace/case/unicode) but none of it encodes the golden
contract's label-stripping rule; the substantive claim (the comparison structurally
cannot see the retained label) is correct.

## Claim 4: PDF unit packets are flat get_text text; no span x-coordinates reach any LLM prompt

**VERDICT: CONFIRMED.**

- Unit packets: `pdf_judge.py:837-839` builds
  `unit_text_map = {f"page:{unit.page}": unit.text for unit in page_units}`.
  `PageUnit.text` is the cleaned flat text: `extract_page_units` captures
  `page.get_text("text", sort=True).strip()` at `textlayer.py:197`, runs it through
  `clean_pages` at line 265, and assigns it at lines 267-269. The unit-check prompt
  injects only this string (`unit_judge.py:581-589`).
- Geometry usage in `textlayer.py` is extraction-internal only: block `bbox` used as a
  sort key at lines 204-213; span dicts are read for `text` (227-229) and `size`
  (232-237). No x-coordinate is ever stored on `PageUnit` (fields at lines 86-98).
- Monolith judge prompt: `pdf_text = normalize_textlayer(pages)` (`pdf_judge.py:603`),
  injected at lines 633-637. Page escalation prompt: dehyphenated cleaned page text
  (`pdf_judge.py:742, 403-410`). Metadata check: `source_metadata = page_units[0].text`
  and an outline of `"page {n}, font {size:.2f}: {text}"` strings
  (`pdf_judge.py:661-666`), i.e. font SIZE reaches the prompt but never x-positions.

So the wrapped-cell geometry evidence (`S` at x=77.25 vs `F` at x=100.5, baseline PR
#286) is invisible to every prompt in the lane. In `get_text` flat output the model
sees only the linearized token stream.

## Claim 5: unit-check taxonomy cannot express "table cell content wrong" or "heading label not stripped"

**VERDICT: PARTIAL** (heading-label half fully confirmed; table-cell half is
correct-in-spirit but overstated as "cannot express").

- The actual taxonomy, quoted from `UNIT_CHECK_SYSTEM_PROMPT`
  (`unit_judge.py:102-107`):

  > "Defect types: qualifier_omission (missing keywords like constexpr),
  > heading_drift (wrong heading level), content_omission (text/figures missing),
  > table_corruption (table structure broken), punctuation_loss (periods/operators
  > dropped), entity_artifact (HTML entities in output), toc_leak (TOC content in
  > body), code_loss (code block missing/broken)."

  Mirrored in the `DefectFinding.defect_type` field description at
  `models.py:234-237`.
- "Heading label not stripped": CONFIRMED inexpressible. `heading_drift` is defined as
  wrong heading LEVEL only. Worse, the entire framework's polarity is
  "candidate must preserve source text": a candidate heading that verbatim matches the
  source heading (label included) is the definition of fidelity under every prompt in
  the lane (`unit_judge.py:99-100` "faithfully preserves the source content"). A rule
  requiring the candidate to DIFFER from the source has no expressible defect type and
  contradicts the check's core framing.
- "Table cell content wrong": the enumerated definitions do not name cell-content
  transcription errors ("structure broken" is the only table wording). However,
  `defect_type` is a free `str` field, not a `Literal` (`models.py:234`), so the schema
  would not reject a model that stretched `table_corruption` or `content_omission` to
  cover a wrong cell value. "Cannot express" is therefore too strong; "never prompted
  to look for it, and no adjacent category names it" is the defensible version. (Note
  the routing gap of claim 1 means such a unit usually never reaches this prompt
  anyway.)

## Claim 6: `UnitCheck.verdict_matches_defects` accepts pass-with-empty-defects; no external-correctness validator

**VERDICT: CONFIRMED.**

- `models.py:315-320`:

```python
@model_validator(mode="after")
def verdict_matches_defects(self) -> UnitCheck:
    """Reject pass-with-defects and non-pass-without-defects."""
    if (self.verdict == "pass") != (not self.defects):
        raise ValueError("unit verdict must be pass exactly when defects are empty")
    return self
```

  `verdict="pass"` + `defects=[]` satisfies the biconditional; it is the canonical
  accepted shape. The validator enforces internal consistency only.
- No validator on `UnitCheck` or `DefectFinding` (`models.py:231-259, 298-320`)
  grounds quotes or checks anything against source/candidate. External verification
  happens post-hoc in `verify_unit_evidence` (`unit_judge.py:493-565`) and
  `verify_defect_counts` (416-472), both of which can only act on defects the model
  chose to emit: a pass-with-empty-defects sails through untouched
  (`unit_judge.py:280-289` iterates `result.get("defects", [])`, which is empty).

## Claim 7: inspect_report prints unit coverage counts but not unchecked unit IDs

**VERDICT: CONFIRMED.**

- `inspect_report.py:180-196`: the unit-coverage block extracts `checked_unit_ids`,
  `unchecked_unit_ids`, `failed_unit_ids` (lines 184-189) and then renders only their
  LENGTHS:

```python
lines += [
    "**Unit coverage:** "
    f"complete={unit_coverage.get('coverage_complete', False)}, "
    f"checked={len(checked)}, unchecked={len(unchecked)}, "
    f"failed={len(failed)}",
    "",
]
```

  (lines 190-196). No other line in the file renders the ID lists; an operator reading
  the report cannot see that pages 8/9 were the displaced units. (The IDs ARE in the
  raw sidecar JSON, `unit_judge.py:332` / `pdf_judge.py:851-857`, so this is a
  rendering gap, not a data-loss gap.)

## Claim 8: no defect group without a model-generated claim; source_aware_review_cap fires on coverage alone

**VERDICT: CONFIRMED.**

- Defect-group provenance: groups are created exactly once, in
  `_aggregate_defects(verified_defects)` (`unit_judge.py:291`). `verified_defects` is
  populated only from `result.get("defects", [])` of unit results
  (`unit_judge.py:279-289`), and unit results are the LLM's `UnitCheck.defects`
  (`unit_judge.py:600-606`). `grounding.py` creates no defects (rg for `defect|group`
  in it matches only regex `.group()` calls, lines 111, 237, 239, 555); it can only
  classify/refute spans handed to it. `fusion.py` only reads `defect_groups`
  (lines 200-214). Zero generated claims => zero groups, deterministically.
- Coverage-alone cap: `fusion.py:391-404` applies `FUSION_RULE_SOURCE_AWARE_REVIEW_CAP`
  whenever `_source_aware_requires_review` is true. That function
  (`fusion.py:183-216`) returns True on metadata verdict != pass (188-190) or on
  `coverage_complete is not True` / any `unchecked_unit_ids` / `failed_unit_ids`
  (192-196) BEFORE any defect-group inspection (the group loop starts at line 200).
  So both PR #286 and PR #295 "review" outcomes are reachable with zero accepted
  defect groups, exactly as the baseline records ("coverage caution, not detection").

## Claim 9: confidence branches into escalation/demotion/fusion despite documented anti-calibration

**VERDICT: CONFIRMED.**

Confidence is consumed at four decision sites:

1. Escalation: `adjudicate.py:272-273`,
   `if CONFIDENCE_AMBIGUOUS_LO <= tier1.confidence <= CONFIDENCE_AMBIGUOUS_HI:
   signals.add(SIGNAL_CONFIDENCE_AMBIGUOUS)` (band 0.35-0.65,
   `constants.py:28-29`).
2. Text-lane demotion: `adjudicate.py:342-343`,
   `if confidence < CONFIDENCE_DECISION_FLOOR: suggested_verdict = VERDICT_REVIEW`
   (floor 0.50, `constants.py:45`).
3. PDF-lane demotion: `pdf_judge.py:706-707`,
   `if verdict == "pass" and judgment.confidence < CONFIDENCE_DECISION_FLOOR:
   verdict = "review"`.
4. Fusion: `fusion.py:459-465` and `479-483`, the `llm_clear_soft_review` upgrade
   requires `conf >= CONFIDENCE_DECISION_FLOOR`; plus the usability gate
   `fusion.py:163` treats `confidence == 0.0` (with no axis findings) as an unusable
   stub.

The anti-calibration is documented in the same files: `constants.py:23-26` ("The band
alone proved dead in production (0/198 escalations; DeepSeek's self-reported
confidence never left [0.85, 1.00])") and `adjudicate.py:255-256` ("Self-reported
confidence is anti-calibrated (production: 18/18 fails at >= 0.95, band never hit in
198 runs)"). The code keeps the scalar as a live input to all four branches anyway.
Mitigating nuance: the code comments show the design already distrusts it (derived
signals added, band retained "as one trigger among three"), and the v6 review cap
deliberately bypasses confidence (`fusion.py:24-26` "without consulting confidence").
The claim as stated is nonetheless accurate.

## Claim 10: labels.json marks p3953r0 expected pass and p1068r11 without the SF table defect

**VERDICT: CONFIRMED.**

- `packages/whisker/corpus/dev-replay/labels.json` lines 183-190 (p3953r0):

```json
"p3953r0": {
  "pr": 295,
  "source_type": "html",
  "human_verdict": "merge",
  "defect_groups": [],
  "expected_llm_verdict": "pass",
  "expected_det_verdict": "pass"
}
```

  This contradicts the baseline's human-verified PR #295 blocker (4 retained secno
  labels). The label file (verified 2026-07-17, line 4) predates that finding and
  records the paper as clean.
- Lines 82-106 (p1068r11): `defect_groups` contains exactly two entries,
  `"type": "heading_hierarchy"` (lines 87-94) and `"type": "html_entities"`
  (lines 95-102). No entry mentions SF, poll tables, or table-cell transcription;
  the human-verified 6-table `SF`->`S` blocker from PR #286 is absent. Schema is
  `"$schema": "dev-replay-labels-v1"` (line 2), matching the baseline's "stale v1"
  note. Ground truth used for replay scoring is itself missing the defect the lane
  is being faulted for missing.

## Claim 11: LLM test stubs default to pass-with-empty-defects; zero end-to-end assertions that a known golden defect is detected

**VERDICT: CONFIRMED** (with one boundary note).

- Stub fixtures: `tests/test_pdf_judge.py:670-705`, `_StubAgent.run` returns
  `MetadataOutlineCheck(... heading_drift=[], missing_sections=[], verdict="pass")`
  (687-696) and `UnitCheck(reasoning="unit matches", unit_id="page:1", defects=[],
  verdict="pass", confidence=0.95)` (697-704) by default. Same pattern in
  `tests/test_source_aware_integration.py:62-97`: metadata check hardcoded pass
  (83-92), fallback `PdfJudgment(verdict="pass", missing_content=[], confidence=0.95)`
  (95-97). A second `_PagedStubAgent` in test_pdf_judge.py:1225-1261 repeats it.
- Golden-corpus tests: the only tests touching the golden PRs are
  `tests/test_dev_replay_acceptance.py`, whose docstring says it explicitly
  ("hermetic, no LLM, no network", line 8; "LLM verdict accuracy is measured
  separately in runtime replays", line 19), plus schema checks
  (`test_dev_replay_schema.py`) and deterministic score pins
  (`test_score_pinning.py`). No test anywhere drives the LLM lane (even with a
  defect-emitting stub) against a golden paper and asserts the known defect lands in
  `defect_groups` or the verdict.
- Boundary note for precision: `test_dev_replay_acceptance.py:99-114`
  (`test_router_observes_full_151_token_delta`) DOES assert that a known golden defect
  (p0533r9's 151 missing `constexpr`) produces a router risk SIGNAL from the real PDF.
  That is router-level signal generation, not end-to-end detection (no unit check, no
  aggregation, no verdict), so the claim stands as written; but "zero coverage of
  golden defects in tests" would be too strong.

## Claim 12: SERVICES.toml alliance pod is hourly-billed, no per-token cost

**VERDICT: CONFIRMED.**

- `SERVICES.toml:59-74`. The comment block immediately above `[services.alliance-pod]`
  (lines 62-63):

```text
# Runs 24/7; billed per hour of uptime, NOT per token, so run size is not a
# cost question (used as the whisker tapetum_llm advisory lane endpoint).
```

  Section header at line 64, `backend = "vllm_thinking"` (65),
  `model = "deepseek-v4-pro"` (68), `max_context_window = 393216` (69). No per-token
  pricing field exists anywhere in the section. Marginal-cost-of-inference arguments
  (e.g. "MAX_UNIT_CHECKS=5 saves money") have no billing basis on this endpoint;
  the real budget constraints are wall-clock (`UNIT_CHECK_TIMEOUT_SECONDS`,
  `constants.py:228`) and determinism (serial in-flight requests).

---

## Summary

| # | Claim | Verdict |
|---|-------|---------|
| 1 | route_pdf_units never reads has_tables | CONFIRMED |
| 2 | severity-then-lexical sort, MAX_UNIT_CHECKS=5 | CONFIRMED |
| 3 | all heading descendant text collected, no normalization | PARTIAL |
| 4 | flat get_text packets, no x-coords in prompts | CONFIRMED |
| 5 | taxonomy cannot express cell-wrong / label-not-stripped | PARTIAL |
| 6 | UnitCheck validator internal-consistency only | CONFIRMED |
| 7 | inspect_report prints counts, not unchecked IDs | CONFIRMED |
| 8 | no group without model claim; cap fires on coverage | CONFIRMED |
| 9 | confidence consumed despite anti-calibration | CONFIRMED |
| 10 | labels.json: p3953r0 pass, p1068r11 no SF defect | CONFIRMED |
| 11 | stubs default pass-empty; no e2e golden-defect assert | CONFIRMED |
| 12 | alliance pod hourly-billed | CONFIRMED |

- **3 PARTIAL**: heading text collection and the secno miss mechanism are exactly as
  claimed (html_outline.py:79-81, rg finds zero secno handling), but normalization is
  not absent: `_text_key` (source_router.py:57-58) applies unicode/whitespace/casefold
  normalization. None of it strips section-number labels, which is what matters.
- **5 PARTIAL**: taxonomy quoted verbatim (unit_judge.py:102-107). "Heading label not
  stripped" is genuinely inexpressible (heading_drift is level-only, and the check's
  fidelity polarity treats a verbatim-matching heading as correct). "Table cell content
  wrong" is unnamed by the taxonomy but not schema-blocked: `defect_type` is a free
  `str` (models.py:234), so a model could stretch `table_corruption`; the prompt just
  never asks it to look.
