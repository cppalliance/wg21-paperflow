# C24 Optional/VLM Boundary and the OCR Question

**Role**: Audit the dormant VLM lane's boundary safety, re-verify the documented absence of OCR, and determine live whether the deterministic lane fails closed when a source PDF's text layer is effectively empty.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771
**Gates**: D7 (API contract + packaging: dormant-code boundary), G2 (Fail-not-partial: scanned-source behavior)

## 1. Scope

Two questions Auditv2 answered by code inspection only, now with live
evidence: whether OCR's absence is a documented decision or an
undocumented gap, and, the sharper question this run adds, whether ANY
lane in the system fails closed when handed a source PDF with a
near-empty text layer. The VLM boundary-safety re-verification (import
isolation, guard test, dormancy documentation) is unchanged in method
from Auditv2 and is re-confirmed rather than re-derived from scratch.

## 2. Commands and Exits

```
E1: uv run --package whisker pytest packages/whisker/tests -q --tb=line -> 3 failed, 1784 passed (exit 1)
Experiment 2 (raw/w6-readback-scan.md): synthetic 3-page image-only PDF, 0 extractable characters
  extract_textlayer(scan0r0.pdf)                                    -> TextLayerError, exit 1
  tomd.api.convert_paper_full(SCAN0R0, scan0r0.pdf)                  -> ConvertedPaper(skipped=True, skip_reason=UNREADABLE, markdown=''), no exception
  whisker SCAN0R0 --workspace scan-ws --json      (plausible md)     -> exit 0, verdict "review"
  whisker SCAN0R0 --workspace scan-ws-empty --json (empty md)        -> exit 5, verdict "fail"
  whisker-tapetum-llm SCAN0R0 ...  (plausible md)                    -> exit 1, PdfLaneError
  whisker-tapetum-llm SCAN0R0 ...  (empty md)                        -> exit 1, PdfLaneError
```

## 3. Current Evidence

### 3.1 OCR absence in the production conversion path (`raw/w5-ocr-boundary.md` §1-2)

A scoped `rg` sweep for `ocr|tesseract|surya|paddleocr|easyocr|rapidocr|
nougat|olmocr` returns **zero hits** in `packages/tomd/src` and
`packages/cli/src` (w5 §1a). tomd's PDF text extraction uses only two
PyMuPDF paths, `extract_mupdf` (`extract.py:23-29`, `page.get_text
("dict")`) and `extract_spatial` (`extract.py:69-81`, `page.get_text
("rawdict")`); no rasterize-and-recognize step exists anywhere in
`packages/tomd/src/tomd/lib/pdf/` (w5 §2a). Docling's table-structure
enrichment explicitly sets `do_ocr=False` (`docling_backend.py:168-171`,
w5 §2b): OCR capability exists in a third-party dependency and is turned
off in this project's own integration of it, on purpose.

### 3.2 OCR absence is a documented decision, not a silent gap

`tomd/README.md:99`: "**No OCR.** Scanned or image-only PDFs are not
supported." (w5 §6.) `tomd/CLAUDE.md:104-105`: "Scanned-page PDFs whose
body is one image per page trip the 20-image cap and produce image-free
markdown... No vision LLM." `whisker/CLAUDE.md:944`: "raster extraction,
pixel inspection, VLM coverage, and image fidelity are outside the audit
scope." No capability claim anywhere in whisker/tomd `src/` markdown
states or implies that scanned or image-only PDFs ARE supported (w5 §6,
exhaustive sweep, zero contradicting hits). Beyond documentation, the
decision was actively evaluated and rejected with reasons, not merely
never considered: `research/marker-v2/50-steelman-decision.md:63` (w5
§5d) records "VLM path conflicts with convert determinism and Lane-1
goldens; disable_ocr path conflicts with quality claims... no Marker mode
simultaneously satisfies (stable goldens) and (76% quality)," a
determinism-vs-quality trade-off this project weighed and declined to
accept, citing a competitor's own OCR-on (76.0%) vs OCR-off (43.6%)
benchmark spread (w5 §5d, §5h) as the concrete cost of the alternative.
**The absence of OCR is a documented, reasoned decision, confirmed again
this run, not an undocumented gap.**

### 3.3 tomd's own readability guard is separate from whisker's text-layer guard, and neither is OCR

`is_readable` (`tomd/lib/pdf/types.py:355-371`, thresholds
`_READABLE_MIN_LENGTH=100`, `_READABLE_MIN_RATIO=0.3`,
`_READABLE_MAX_SLASH_RATIO=0.1`) is a heuristic on the CANDIDATE'S OWN
extracted text quality (rejects garbage/CID-encoded output), checked at
`pipeline.py:1605-1613`: `if not is_readable(mupdf_text): ... return
_enforce_skip_contract(PipelineResult.for_skip(SkipReason.UNREADABLE,
...))`. This is tomd's CONVERT-time guard. Whisker's `MIN_TEXTLAYER_CHARS
= 200` (`textlayer.py:56-59`, w5 §3a) is a SEPARATE, later guard inside
the advisory `tapetum_llm` package only, enforced in `extract_textlayer`
(`textlayer.py:148-154`): `if total_chars < MIN_TEXTLAYER_CHARS: raise
TextLayerError(...)`. **No `textlayer.py` equivalent exists under
`packages/tomd/src`** (w5 §3d): tomd's own package has no separate
text-layer-richness floor distinct from `is_readable`'s garbage-detection
heuristic.

### 3.4 The fail-loud contract on `skipped` is caller-enforced, at two independent call sites, not callee-enforced

`convert_paper_full` (the low-level function `pipeline.py:1605-1613`
returns from) returns `ConvertedPaper(skipped=True, skip_reason=
SkipReason.UNREADABLE, markdown='')` and does **not** raise (confirmed
live, Experiment 2, `raw/w6-readback-scan.md:1564-1575`: direct Python
call to `convert_paper_full` on the synthetic scanned PDF returns this
tuple with `skipped= True`, `skip_reason= unreadable`, `markdown_len= 0`,
no exception). The raise happens one layer up, and it happens
independently at TWO separate call sites:

```482:486:packages/tomd/src/tomd/api.py
    if r.skipped:
        raise RuntimeError(
            f"tomd produced empty markdown for {paper_id} "
            f"({r.skip_reason.value if r.skip_reason else 'slide deck, standards draft, or unreadable source'})."
        )
```

```456:461:packages/cli/src/cli/process.py
    if result.skipped:
        # The convert stage cannot make this paper into markdown.
        # Raise so process_paper records the failure and does not
        # advance status past download. ``skip_reason`` distinguishes
        # this from a genuine conversion error.
        raise RuntimeError(f"convert skipped ({result.skip_reason})")
```

Both `tomd.api.convert_paper` (the package's own public wrapper) and
`cli.process`'s pipeline step independently re-check `.skipped` and raise.
This means the fail-loud property is a CONVENTION replicated at each of
these two call sites, not a property the low-level `convert_paper_full`
function itself enforces. A THIRD caller that invokes
`convert_paper_full` directly, as this audit's own Experiment 2 script
did to construct the canary, receives the skipped tuple silently, with no
exception, and must remember to check `.skipped` itself. This audit found
exactly two production call sites that perform this check (`tomd/api.py`,
`cli/process.py`); no third production call site invoking
`convert_paper_full` directly without going through one of those two
wrappers was found, but this file did not exhaustively enumerate every
caller of `convert_paper_full` across the workspace to guarantee none
exists.

### 3.5 Live result: the LLM lane fails closed correctly; the deterministic lane does not, and its `review` outcome was an accident of unrelated soft flags

Experiment 2 staged a plausible-looking candidate markdown directly
against the scanned-PDF source (bypassing `convert_paper_full`'s skip, to
isolate what each SCORING lane does when handed this pairing). Results
(`raw/w6-readback-scan.md`, scanned-PDF exit-code table):

| Lane | Command | Exit | Result |
|---|---|---|---|
| LLM (plausible md) | `whisker-tapetum-llm SCAN0R0 ...` | 1 | `PdfLaneError` |
| LLM (empty md) | `whisker-tapetum-llm SCAN0R0 ...` | 1 | `PdfLaneError` |
| Deterministic (plausible md) | `whisker SCAN0R0 --json` | 0 | `verdict: "review"` |
| Deterministic (empty md) | `whisker SCAN0R0 --json` | 5 | `verdict: "fail"` |

The LLM lane fails closed in BOTH cases, correctly and by design:
`judge_pdf_extraction` calls `extract_textlayer`, which raises
`TextLayerError` on the same 0-character text layer regardless of what
the candidate markdown contains (`pdf_judge.py:620-622`, w5 §3c); the
candidate's content is irrelevant to this guard because it fires on the
SOURCE side before the candidate is ever compared.

The deterministic lane's plausible-markdown result is the live proof
requested for this file. The full sidecar
(`raw/w6-readback-scan.md:1602-1677`):

```
"coverage": 1.0, "drift": 1.0, "unigram_coverage": 1.0, "unigram_drift": 1.0,
"missing_region_count": 0, "extra_region_count": 1, "qa_score": 100,
"ref_nid": 0.0, "ref_teds": 1.0, "ref_mhs": 0.5,
"hard_flags": [],
"soft_flags": [
  "1 misaligned region(s)",
  "reference text agreement 0.000 low (advisory)",
  "unigram drift 1.000 > 0.1"
],
"verdict": "review"
```

`unigram_coverage: 1.0` against a source with zero extractable tokens is
vacuous: coverage of nothing by anything is complete by construction, and
the deterministic hard gate (`score.py:181-186`, the ONLY unconditional
fail trigger tied to text similarity, per C02 §3.2) can therefore never
fire on this input regardless of what the candidate contains. **This
confirms directly: the deterministic lane does not fail closed on an
empty text layer.** There is no equivalent of `MIN_TEXTLAYER_CHARS`
anywhere in `score.py`, `gates.py`, or tomd's own `qa.py`
path (w5 §3d, no `textlayer.py` equivalent under `packages/tomd/src`).

The `review` verdict this specific run landed on was not the deterministic
lane recognizing the empty source; it was an accident of the OTHER two
soft flags also firing. `_is_benign_region_only` (`score.py:237-241`)
would fold a lone region-mismatch flag at `unigram_coverage >= 0.95` into
a benign `pass`, and `unigram_coverage` here is 1.0, comfortably above
that floor:

```237:241:packages/whisker/src/whisker/score.py
def _is_benign_region_only(soft: list[str], unigram_coverage: float) -> bool:
    """True when all soft flags are region flags and coverage is high enough."""
    if unigram_coverage < C.REGION_BENIGN_UNIGRAM_FLOOR:
        return False
    return all(f.endswith(_REGION_FLAG_SUFFIX) for f in soft)
```

The fold does not apply here ONLY because two OTHER, unrelated soft flags
also fired in this specific instance (`ref_nid` 0.000 low, `unigram_drift`
1.000): `all(...)` over the three flags is `False` since two do not end
with "misaligned region(s)". Had this synthetic candidate not also
tripped the reference-agreement and drift floors, for instance a shorter
or differently-shaped plausible markdown, the same `unigram_coverage: 1.0`
would have folded to `VERDICT_PASS` (benign) via this exact code path.
**The `review` outcome on the scanned-PDF canary was reached by accident,
via two coincidental secondary soft flags, not by design: no code path in
`score.py` treats an empty or near-empty source text layer as a condition
requiring review or fail in its own right.**

The empty-markdown case (exit 5, `fail`) does not contradict this: an
empty CANDIDATE trips the `non_empty` structural gate directly
(`score.py:179`'s gate-loop hard trigger), a check on the candidate's own
content, unrelated to whether the source's text layer was readable. A
scanned PDF paired with a non-empty, plausible-looking candidate, exactly
the scenario a real conversion bug or a stale/mismatched artifact could
produce, has no equivalent structural safety net.

### 3.6 VLM boundary safety, re-verified (unchanged from Auditv2)

Import-chain sweep (`raw/w5-ocr-boundary.md` §4c, this run's own `rg`, not
merely re-cited from Auditv2): zero matches for `vlm|vision|transcribe|
rasterize` in `__main__.py`, `menu.py`, or the import block of
`tapetum_llm/cli.py`. `tapetum_llm/__init__.py:30-44` re-exports no VLM
symbols. The guard test `test_pipeline_stays_text_only`
(`tests/test_vlm_lane.py:215-224`) still asserts `pipeline`'s `Model
Backend.run`/`AgentBackend.run`/`run_task` signatures carry no
`user_media` parameter and `BACKEND_REGISTRY` carries no `vllm_vision`
entry. All dormancy docstrings (`vision.py:15-16`, `vision_task.py:23-26`,
`vlm_diff.py:21-22`, `vlm_pipeline.py:14-15`) are present and consistent
with Auditv2's citations, confirmed at re-counted line numbers this run.

### 3.7 The LOC/file-count doctrine claim is stale, confirmed with exact current counts

`CLAUDE.md:885-886`: "VLM lane is unwired. 788 LOC across 5 files
(`tapetum_llm/vlm_*.py`, `vision_task.py`)." Live physical line counts
this run (w5 §4a): `vision.py` 126, `vision_task.py` 211, `vlm_diff.py`
221, `vlm_pipeline.py` 100 (658 across the four explicitly named files),
plus `transcribe.py` 154 (the implied 5th file, imported by
`vlm_pipeline.py`, not individually named in the doctrine sentence's file
list despite the sentence claiming "5 files"). Total: **812 lines across
5 files**, 24 more than the documented 788. This is the same stale-figure
finding C01 recorded (F20: "doctrine text claim (dormancy) verified;
doctrine text figure (LOC/file count) refuted by the live count"),
independently re-derived here from the raw line-count evidence rather
than taken on that file's word.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | OCR's absence from the production conversion path is confirmed, again, by a zero-hit sweep plus explicit documentation in three independent locations (`tomd/README.md`, `tomd/CLAUDE.md`, `whisker/CLAUDE.md`) and a recorded, reasoned rejection of a competitor's OCR mode on determinism/quality trade-off grounds | Informational (confirms documented decision) | HIGH |
| F2 | The fail-loud contract on `convert_paper_full`'s `skipped` result is enforced independently at two call sites (`tomd/api.py`, `cli/process.py`), not by the low-level function itself; a third caller invoking it directly receives a silent skip with no exception | MEDIUM | HIGH |
| F3 | The LLM (advisory) lane fails closed correctly and deterministically on an empty text layer, independent of candidate content, via `MIN_TEXTLAYER_CHARS`/`extract_textlayer` | Informational (confirms design intent) | HIGH |
| F4 | The deterministic (gating) lane has no equivalent floor; `unigram_coverage` against an empty source is vacuously 1.0, so the hard gate cannot fire on this input class regardless of candidate content | HIGH | HIGH |
| F5 | The live `review` verdict on the scanned-PDF canary was produced by two coincidental secondary soft flags (`ref_nid` low, `unigram_drift` high), not by any source-text-layer-awareness in `score.py`; the same `unigram_coverage: 1.0` would fold to a benign `pass` via `_is_benign_region_only` if those two flags had not also fired | HIGH | HIGH |
| F6 | The empty-markdown case correctly hard-fails (exit 5), but via the unrelated `non_empty` structural gate on the CANDIDATE, not via any check of the source's text-layer richness | MEDIUM | HIGH |
| F7 | VLM boundary safety (import isolation, guard test, dormancy documentation) is unchanged and reconfirmed by this run's own independent sweep, not merely re-cited from Auditv2 | Informational | HIGH |
| F8 | The doctrine's "788 LOC across 5 files" VLM figure is stale; the live count is 812 across the same 5 files, a 24-line drift, independently re-derived this run | LOW | HIGH |

## 5. False-Pass Hypothesis

**Could a real (non-synthetic) scanned or badly-degraded PDF reach a
deterministic `pass` today?** This file establishes the mechanism (F4-F5)
but not a live `pass` outcome: the one live observation (Experiment 2)
landed on `review`, not `pass`, because of the two coincidental soft
flags in F5. Whether a DIFFERENTLY-SHAPED plausible candidate (one that
does not trip `ref_nid`/`unigram_drift`, for instance if no reference
engine ran, or if the candidate's token distribution happened to overlap
enough with the reference converter's own equally-degenerate output on
the same source) would fold to a benign `pass` via `_is_benign_region_
only` is a direct, mechanical consequence of the code traced in 3.5, but
this audit did not construct that second variant to confirm it live. This
is flagged as the load-bearing next experiment, not claimed as already
observed.

**Does this finding contradict F1's "OCR absence is documented"?** No,
and this is worth stating precisely because the two claims sound related
but are distinct. OCR's absence is a decision about CAPABILITY (this
system will not attempt to read text out of a scanned image). The gap in
F4-F5 is a decision about FAIL-CLOSED BEHAVIOR when that documented
capability limit is reached: the LLM lane fails closed on it (F3, by
design); the deterministic gate does not (F4, no code path checks for it
at all, benign or otherwise). A system can correctly decline to support
OCR and simultaneously lack a floor that detects "this source has
essentially no text to compare against" in its PRIMARY gating lane. Both
things are true here.

**Is this a realistic production risk given the corpus?** The 189-PDF
production workspace sampled this run has a minimum text-layer length of
2,121 characters (w5 §7c), roughly 10x `MIN_TEXTLAYER_CHARS`; zero
in-workspace PDFs are near this threshold. This finding is a demonstrated
mechanism on a synthetic canary, not an observed production incident.

## 6. Gate/Dimension Mapping (PROPOSED)

| Gate | Dimension | Proposed status |
|------|-----------|------------------|
| D7 API contract + packaging | VLM dormant-code boundary safety | PROPOSED PASS (F7, reconfirmed) |
| D7 API contract + packaging | Doctrine accuracy (LOC/file-count claim) | PROPOSED minor FAIL: stale figure (F8), not a boundary-safety defect |
| G2 Fail-not-partial | Advisory (LLM) lane fail-closed behavior on empty text layer | PROPOSED PASS (F3) |
| G2 Fail-not-partial | Deterministic (gating) lane fail-closed behavior on empty text layer | PROPOSED gap: no floor exists (F4); the one live observation avoided a false `pass` only by coincidence (F5) |
| G2 Fail-not-partial | Fail-loud contract on `convert_paper_full`'s skip result | PROPOSED PASS at the two known call sites, PROPOSED gap for any undiscovered third caller (F2) |

## 7. Limitations

- This audit did not exhaustively enumerate every caller of
  `convert_paper_full` across the workspace to confirm no production call
  site exists that bypasses both `tomd.api.convert_paper` and
  `cli/process.py`'s checks (F2's residual risk).
- The "accident, not design" claim in F5 is demonstrated mechanically
  (the exact code path and the exact flag set that avoided the fold) but
  the second experiment that would show a `pass` outcome live (a
  differently-shaped plausible candidate that does not trip `ref_nid`/
  `unigram_drift`) was not run this pass; this is flagged as the natural
  next step, not claimed as already-observed evidence.
- The corpus-risk framing in Section 5's third paragraph is based on one
  189-PDF snapshot of the current workspace, not a claim about the full
  WG21 mailing or any future corpus.
- The suite is RED (E1); neither `test_pdf_judge.py`'s specific pass/fail
  status nor any test targeting `_is_benign_region_only` was
  independently re-checked against the 3 named failures; per the batch's
  hard rule this file does not cite passing-test counts as evidence for
  the live findings above, which stand on the runtime evidence in 3.5
  alone.

## 8. Conclusion

OCR's absence remains, on this run's independent re-sweep, a documented
and reasoned decision, not a gap: zero OCR code in the production path,
explicit limitation statements in three separate documents, and a
recorded rejection of a competitor's OCR mode on determinism and quality
grounds. Separately and more consequentially, this run's live canary
answers the sharper question directly: **the deterministic lane does not
fail closed on an empty text layer.** `unigram_coverage`'s hard-gate role
is vacuously satisfied when the source contributes zero tokens, and the
one live observation that avoided a false `pass` did so only because two
unrelated soft flags happened to co-occur with the region-mismatch flag,
not because any code in `score.py` recognizes an empty or near-empty
source as a condition worth flagging in its own right. The advisory LLM
lane, by contrast, fails closed correctly and unconditionally on the same
input, because its guard checks the source text layer directly and before
any candidate comparison happens. The fail-loud contract on
`convert_paper_full`'s skip result is real but is enforced by convention
at two independent call sites rather than by the function itself, a
narrower and more precise claim than "the callee fails loud."

## 9. Delta vs Auditv2

Auditv2's C24 scoped VLM boundary safety only (import isolation, guard
test, dormancy documentation) and concluded a flat "Gate verdict: PASS,"
citing "1406 passed" with no OCR-boundary or scanned-PDF live evidence in
its scope at all; the OCR claim in this file's F1 was covered, in
Auditv2's batch, only indirectly via C01-adjacent doctrine citations, not
as this file's own live-tested claim. This run's boundary-safety
re-verification (3.6) reconfirms every one of Auditv2's five findings
(F1-F5 in that file: production isolation, import isolation, guard-test
load-bearing, truthful dormancy documentation, disciplined D1 exception)
unchanged, via this audit's own independent sweep rather than by citation
alone, and additionally catches a stale doctrine figure (F8, 788 vs 812
LOC) Auditv2 did not surface.

The substantial new material is Section 3.4-3.5, which did not exist in
Auditv2's scope at all: a live scanned-PDF canary showing the LLM lane
fails closed correctly while the deterministic lane's hard gate is
structurally incapable of failing closed on this input class, and that
the one live `review` outcome observed was a coincidence of two unrelated
soft flags rather than evidence of an intentional floor. Auditv2 had no
occasion to test this because it had no live pod access and no canary
construction in its C24 scope; this file supplies that missing evidence
and reaches a materially more qualified verdict on the "fail-not-partial"
dimension for the deterministic lane specifically, while leaving the VLM
boundary-safety verdict itself unchanged from Auditv2's PASS.
