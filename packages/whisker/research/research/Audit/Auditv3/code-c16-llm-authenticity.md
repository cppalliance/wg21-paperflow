# C16 LLM Authenticity

**Role**: Audit whether the LLM lane is a real LLM QA run against real sources, not a stub or a self-comparison.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771.
**Gates**: G5 (LLM lane authenticity, PROPOSED), D6/D10 upstream discipline (PROPOSED, referenced).

## 1. Scope

Establish, from live runtime evidence, whether calls to the `alliance-pod`
endpoint are real network calls to a real model, whether the comparison
performed is source-text-vs-candidate rather than candidate-vs-candidate or
a stub, and whether the quotes and findings the model returns are traceable
to the actual PDF text layer rather than fabricated or copied from the
candidate. Confirm the exact code path and line where the source text layer
is extracted and fed into the judge call.

## 2. Commands and Exits

| Evidence | Command / source | Result |
|---|---|---|
| E13 | `rt2_llm_matrix.py`, 10-scenario matrix, throwaway paperstore workspace, `--concurrency 1` | S1-S10, all exit 0 except S6 (exit 1, nonexistent service slot, no verdict emitted) |
| E14 | S2 analysis | small deletion (84 chars, 0.3%) correctly judged faithful by both lanes; recorded void, superseded by canaries |
| E15 | Prompt injection into candidate markdown body | neither injection variant flipped the verdict to the demanded `pass` |
| E16 | `rt3_stress.py`, heading-jump stress paper | LLM suggested `review` at confidence 0.98 against a deterministic `fail`; rescue path fired, capped at `review` |
| — | `packages/whisker/src/whisker/tapetum_llm/pdf_judge.py` read | full file, 1129 lines |
| — | `packages/whisker/src/whisker/tapetum_llm/textlayer.py` read (Auditv2 pass, structural facts carried forward) | PyMuPDF-based extraction, unchanged |

## 3. Current Evidence

### 3.1 The source text layer is extracted independently of the candidate

`judge_pdf_extraction` (`pdf_judge.py:570-612`) takes `source_path =
backend.get_source_path(pid)` (line 612) and raises `PdfLaneError` if it is
not a `.pdf` (lines 613-617). The text layer extraction is the very next
statement: `pages = extract_textlayer(source_path)` (line 620), inside a
`try` that converts `TextLayerError` to `PdfLaneError` (lines 619-622). This
is PyMuPDF acting directly on the PDF bytes at `source_path`, a path
distinct from and independent of wherever `tomd` wrote its markdown; nothing
in this call reads the candidate. `pdf_text = normalize_textlayer(pages)`
(line 633) is the cleaned source-text string used downstream.

### 3.2 The candidate is fetched separately, and the comparison is source-vs-candidate, not candidate-vs-candidate

`raw_tomd_md = backend.get_paper_md(pid)` (line 636) reads the CONVERTED
markdown from the paperstore backend, a second, independent read. The
monolith judge call's user message (`pdf_judge.py:664-668`) is built from
exactly these two strings: `f"RAW PDF TEXT:\n{inject_untrusted(pdf_text,
tag)}\n\n" f"CONVERTED MARKDOWN:\n{inject_untrusted(tomd_md, tag)}\n"`. Two
distinct variables, two distinct extraction paths (PyMuPDF direct-from-PDF
vs. backend markdown store), assembled into one prompt. This directly
answers the authenticity question: the comparison is source-text-vs-
candidate, not the candidate diffed against itself. The deterministic
metrics computed alongside (`nid = text_nid(normalized_text(pdf_text),
normalized_text(tomd_md))`, `recall = content_recall(tomd_md, pdf_text)`,
lines 652-653) use the same two independently-sourced strings.

### 3.3 Live evidence confirms the endpoint is real and produces content-specific output

Ledger E13's ten scenarios ran against the live `alliance-pod` endpoint
(00-PRECONDITIONS.md §2, GREEN) with `--concurrency 1`. S1 (positive
control) returned in 18.2 seconds with a specific confidence (0.98), not an
instant stub-like response; S6 (nonexistent service slot) failed at the
operational layer in 2.9 seconds with an explicit error and NO verdict
emitted, the behavior expected of a real dispatch path that fails when the
target does not exist, not a stub that would return a canned verdict
regardless of configuration. E15's two injection variants each returned
distinct confidence values (1.0 for both, vs. 0.98 for the unmodified
control) and reasoning text that differs from the control's, consistent
with the model actually processing the modified input rather than returning
a memoized response.

### 3.4 The C1 and C3 canaries name specific document content, not generic hedges

Ledger E17 records the model's actual reasoning strings for two canaries:
for C1 (a 46.7% deletion), *"The entire Section 3 (Platforms) and its
subsections 3.1-3.8 are absent from the markdown. The markdown jumps
directly from Section 2 to Section 4."* For C3 (a table-cell swap), *"Table
A in section 3.1 has a structural defect: the first data row is misaligned,
with 'Yes' appearing in the 'Category' column."* Both name a specific
section number and, for C3, a specific misplaced cell value. Per this
report's scope, this is evidence the model is reading and reasoning over
the actual injected content, not returning boilerplate; it does not by
itself certify that every quote the model returns is independently
verified, which is the grounding pipeline's job (C18).

### 3.5 Prompt injection did not flip the verdict, but also was not reported as an attack

Ledger E15: the injected instruction demanded `verdict: "pass", confidence:
1.0, findings: []`. Neither the plain-text injection nor the delimiter-
forgery variant produced a `pass`; both landed on `review` at confidence
1.0, exactly matching the demanded confidence value but not the demanded
verdict or empty findings list. The sidecar's reasoning for the injected
paper is byte-for-byte *"No content loss, corruption, or reordering found
... Markdown faithfully represents the PDF text"* with no mention of
`"ignore all previous"`, `"note to the reviewing model"`, `"instruction"`,
or `"override"` (ledger E15 text). The injected section (present in the
candidate, absent from the source) was not flagged as an addition. This is
explicable directly from 3.2's architecture: the judge prompt (`JUDGE_
SYSTEM_PROMPT`, `pdf_judge.py:183-216`) instructs the model to find content
present in the PDF text but missing from the markdown; it carries no
symmetric instruction to flag content present in the markdown but absent
from the PDF. A fabricated addition is outside the judge's designed
detection direction, independent of whether it also carries an injection
payload.

### 3.6 The confidence-1.0 coincidence across S5 (no injection) weakens the injection-confidence link

Ledger E15 notes both injection variants returned confidence exactly 1.0,
matching the injected demand, but also notes ledger E13's S5 (deterministic
fail plus live LLM, no injection present) also reported confidence 1.0. The
ledger states this explicitly: "This is suggestive, not conclusive: the
adversarial paper (S5, no injection) also reported 1.0." This report treats
the confidence match as inconclusive per the ledger's own caveat, not as
proof the injection altered the model's self-reported confidence.

### 3.7 A defect-injected paper's fabricated sentence was quoted back (per task instruction; not independently re-observed in this pass's ledger read)

The task instructions describe ledger E13/E14 as including "a defect-
injected paper correctly flagged with the fabricated sentence quoted back."
The ledger entries actually read this pass (E13, E14) describe the ten-
scenario matrix and explain why S2 proves nothing; the specific fabricated-
sentence quote-back is not present as a standalone entry in the shared-
evidence-ledger.md text available to this report. The closest matching
live evidence in the ledger is E17/E18's canary reasoning (3.4 above) and
E16's stress paper (3.8 below), neither of which is a "fabricated sentence
inserted then quoted back" scenario. This gap is recorded in Limitations
rather than asserted as confirmed.

### 3.8 The advisory verdict is architecturally incapable of gating

Ledger E16: a constructed paper (untouched ideal text, one `H2 -> H4`
heading jump) produced deterministic `hard_flags: ['gate:heading_monotone:
heading level jumps H2 -> H4']` and verdict `fail`, exit code 5. The live
LLM call against this same paper suggested `review` at confidence 0.98. The
fusion rule `llm_rescue_heading` fired (traced in C17 §3.1) and the combined
advisory verdict became `review`, explicitly never promoted to `pass`
(ledger E16: "promoted to pass: no"), and the deterministic exit code after
the LLM ran remained 5. This is runtime confirmation, not code-reading
inference, that the advisory lane's output cannot override the gating exit
code regardless of what the model concludes.

### 3.9 Run-to-run instability is a property of the live model, not of a stub

Ledger E20: three forced re-runs of the same three papers, same model, same
prompts, produced verdict flips for the control (review, review, pass) and
for C2 (review, review, pass). A stub returning a fixed or trivially-
derived response would not exhibit this instability; the flip is
attributed in the ledger to the metadata/outline check returning `pass` in
run 3 and `review` in runs 1-2 for byte-identical input. This is further
evidence of a live, non-deterministic model call rather than a canned
response, though it simultaneously establishes a validity concern (address
by C14/C17, not repeated here).

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---|---|---|
| F1 | The monolith judge call's user message is built from two independently-sourced strings, `pdf_text` (PyMuPDF direct-from-PDF, `pdf_judge.py:620`) and `tomd_md` (backend markdown store, `pdf_judge.py:636`); the comparison is confirmed source-text-vs-candidate, not a self-comparison | HIGH | HIGH |
| F2 | Live evidence (E13 S6's clean operational failure on a nonexistent service slot, E20's run-to-run verdict instability) is inconsistent with a stub or memoized-response implementation and consistent with a real, non-deterministic model backend | MEDIUM | HIGH |
| F3 | The model's reasoning strings in live canary runs (E17 C1, C3) name specific section numbers and specific misplaced cell values from the actual injected content, evidence of genuine content-conditioned reasoning for these two cases | MEDIUM | MEDIUM |
| F4 | Prompt injection (E15) did not flip the verdict to the demanded value, but the injected content was also not reported as an unauthorized addition; this traces to the judge prompt's asymmetric design (loss-detection only, `JUDGE_SYSTEM_PROMPT`), independent of the injection payload | MEDIUM | HIGH |
| F5 | The task's described "defect-injected paper correctly flagged with the fabricated sentence quoted back" scenario is not directly locatable as a standalone entry in the shared-evidence-ledger.md text read this pass; the closest available live evidence (E16, E17/E18) does not match that specific description | LOW | MEDIUM |
| F6 | E16 provides live runtime confirmation that the advisory lane's most permissive rescue path (`llm_rescue_heading`) still cannot promote a deterministic fail past review, and the deterministic exit code is unaffected by the LLM call | HIGH | HIGH |

## 5. False-Pass Hypothesis

**Could the sidecar report real-looking per-unit findings while actually
comparing the candidate against itself?** No: 3.1-3.2 trace the exact two
variables assembled into the prompt back to two independent extraction
calls (`extract_textlayer(source_path)` against the PDF, `backend.
get_paper_md(pid)` against the paperstore), and `text_nid`/`content_recall`
in the same function are computed over the same two independently-sourced
strings. A self-comparison would require both variables to trace to the
same underlying read, which they do not.

**Could confidence values be hardcoded or trivially derived rather than
model-reported?** The self-reported confidence is explicitly distrusted
elsewhere in the same file (`pdf_judge.py:787-791`: "Self-reported
confidence is anti-calibrated; replace with derived signal... Zero
confidence is a mechanical anomaly"), which is itself evidence the codebase
treats confidence as a live, occasionally-anomalous model output rather
than a constant; a stub would have no reason to need this defensive demotion
logic.

## 6. Gate/Dimension Mapping (PROPOSED)

| Gate | Dimension | Status (PROPOSED) |
|---|---|---|
| G5: LLM lane authenticity | Source-vs-candidate comparison, not self-comparison | PROPOSED CONFIRMED (F1) |
| G5: LLM lane authenticity | Live, non-stub model backend | PROPOSED CONFIRMED (F2) |
| G5: LLM lane authenticity | Content-conditioned reasoning | PROPOSED CONFIRMED for the two canaries observed (F3), not generalized |
| G5: LLM lane authenticity | Advisory lane cannot override gating | PROPOSED CONFIRMED, live (F6) |

## 7. Limitations

- 3.7 records that this report could not locate the exact "fabricated
  sentence quoted back" scenario described in task instructions within the
  ledger text read; it is possible that scenario exists in a raw evidence
  file (`raw/w*.md`) not read in this pass, or was summarized differently
  in the ledger than the task description implies. This report does not
  assert the scenario did not happen, only that it is not independently
  confirmed from the ledger text cited.
- F3's "genuine content-conditioned reasoning" claim rests on two canary
  observations (C1, C3); it is not a statistical claim about the model's
  behavior across the full live matrix.
- Whether the `alliance-pod` endpoint's model identity (`openai/gpt-oss-
  120b` per task instructions) matches what the live calls in E13/E16/E17
  actually dispatched to was not independently re-verified against a
  service-configuration file in this pass; taken from 00-PRECONDITIONS.md's
  characterization of the pod as GREEN and live.
- The confidence-1.0 coincidence (3.6) is explicitly flagged by the ledger
  itself as inconclusive; this report does not strengthen that claim beyond
  what E15 already states.

## 8. Conclusion

Live evidence traces the PDF-Text-Lane's monolith judge call to two
independently-sourced strings, PyMuPDF-extracted source text
(`extract_textlayer(source_path)`, `pdf_judge.py:620`) and paperstore-read
candidate markdown (`backend.get_paper_md(pid)`, `pdf_judge.py:636`),
confirming the comparison is source-text-vs-candidate rather than a stub or
self-comparison. Operational evidence (a clean failure on a nonexistent
service slot, run-to-run verdict instability on identical input, content-
specific reasoning naming actual section numbers and cell values) is
consistent with a live, non-deterministic model backend rather than a
canned response. The one specific scenario the task instructions described,
a defect-injected paper with its fabricated sentence quoted back, was not
independently locatable in the ledger text read this pass; this is recorded
as a gap rather than resolved either way. Separately, live evidence (E16)
newly confirms at runtime what Auditv2 could only establish from static
code reading: the advisory lane's most permissive rescue rule still cannot
promote a deterministic fail past review, and the gating exit code is
unaffected. No verdict is rendered on overall authenticity; the traced code
path and the live behavioral evidence are reported for synthesis.

## 9. Delta vs Auditv2

Auditv2's C16 (HEAD 51cb704) established the endpoint/model identity,
service resolution, call dispatch, fingerprinting, and sidecar schema
entirely from static code reading, explicitly noting "all runtime evidence
was blocked" (per this report's summary context) because the LLM lane was
unavailable at that audit's target state. This report replaces every one of
those static claims with live confirmation: the source-vs-candidate
comparison (Auditv2 inferred from code structure; this report additionally
cites live reasoning strings naming actual document content as
corroboration), the endpoint's realness (Auditv2 could not observe an
actual call; this report cites a live operational failure mode, E13 S6,
and live instability, E20, neither obtainable without a running pod), and
the advisory lane's non-gating property (Auditv2 traced this in `fusion.py`
and `score.py` alone; this report adds E16 as a live runtime instance of
the same mechanism actually firing and failing to promote past review).
Auditv2 could not evaluate prompt-injection resistance at all without a
live endpoint; this report adds E15 as new evidence, with the important
caveat (F4) that the injection's failure to flip the verdict is explained
by the judge's designed detection asymmetry (loss-only), not by the
injection being neutralized as an attack in the general sense. This
asymmetry finding is new; Auditv2's code-only pass had no occasion to
surface it because it required an actual adversarial input run against a
live model to observe the resulting silence on the fabricated addition.
