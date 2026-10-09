# 18 - Evidence-Provenance Designer

**Verdict:** usable-with-conditions — whisker already has the right primitives (char intervals, fingerprints, page regions, `checked` status) but PDF-lane sidecars over-label one-sided source grounding as bidirectional absence; a minimal per-quote provenance record can be assembled from existing fields without new dependencies once candidate-side locate is split out.
**Confidence:** high

## Findings

- [CRITICAL] **Current `grounded_evidence` reason string is dishonest provenance.** Evidence: `pdf_judge.py:401-404` emits `"present in PDF text layer, absent from markdown"` for every quote that survives source-only `ground_spans` (`pdf_judge.py:513-520`); no candidate haystack is consulted. Impact: 12/20 replay quotes were false missing-content (`00-baseline.md:14-24`); operators cannot reproduce or audit the absence leg from the sidecar alone.

- [HIGH] **Minimum reproducible quote record (v1 schema).** Evidence: langextract `char_interval` + `alignment_status` (`langextract/tests/annotation_test.py:64-77`); whisker text-lane `grounded_evidence` shape (`adjudicate.py:340-343`, `models.py:137-139`); bidirectional entailment statuses (`03-bidirectional-design.md:28-35`); firecrawl/markitdown document-level only (`entities.ts:64-67`, `_base_converter.py:5-25`). Impact: every retained quote claim must persist these fields (names stable across lanes):

  | Field | Purpose | Source today |
  | --- | --- | --- |
  | `claim_id` | Stable sort key within a run | *(new)* hash of `(pid, lane, quote, page?)` |
  | `quote` | Verbatim model emission | `EvidenceSpan.quote` / `missing_content[]` |
  | `axis` | Which fidelity axis cites it | `EvidenceSpan.axis` / `"structure"` |
  | `claim_kind` | What is being asserted | `missing_from_markdown` \| `defect_in_markdown` \| `support_for_pass` |
  | `source_surface` | Haystack searched on source leg | `pdf_textlayer` \| `pdf_page_text` \| `markdown` |
  | `source_page` | 1-based page when scoped | `page_escalations[].page` (`pdf_judge.py:577-582`) or `null` |
  | `source_status` | Source locate outcome | `exact` \| `fuzzy` \| `ungrounded` (from `GroundedSpan.status`, `grounding.py:46-60`) |
  | `source_start` / `source_end` | Char interval in source haystack | `GroundedSpan.start/end` when exact; `null` for fuzzy/page quotes today |
  | `source_slice` | Raw substring at interval | `haystack[start:end]` when exact; else `null` |
  | `candidate_surface` | Haystack for absence/presence leg | `tomd_markdown` (post `strip_binary_payloads`, `pdf_judge.py:467-468`) |
  | `candidate_status` | Candidate locate outcome | `present` \| `absent` \| `ambiguous` \| `not_checked` |
  | `candidate_start` / `candidate_end` | Char interval in markdown | text-lane already (`adjudicate.py:340-343`); PDF lane missing |
  | `entailment` | Honest combined label | `verified_missing` \| `false_missing` \| `ambiguous` \| `ungrounded` \| `present_defect` |
  | `locate_tier` | Which matcher decided | `monolith_ground_spans` \| `page_ground_quotes` \| `partial_ratio_band` |
  | `threshold` | Floor used (named constant value) | `EVIDENCE_FUZZY_FLOOR`, `PAGE_QUOTE_MAX_DIFFS` (`constants.py`) |
  | `reason_code` | Machine demotion/abstain code | e.g. `source_fuzzy_only`, `candidate_present`, `ambiguous_band` |
  | `llm_reason` | Model narrative (unverified) | `EvidenceSpan.reason` / sidecar `reasoning` — never folded into `entailment` |

  **Run-level envelope** (already partially present; must wrap every quote list):

  | Field | Purpose | Source today |
  | --- | --- | --- |
  | `pid` | Paper id | sidecar root |
  | `lane` | `pdf_textlayer_judge` \| `text` | `pdf_judge.py:392`, tapetum `to_dict` |
  | `schema_version` | Sidecar contract version | `pdf_judge.py:420`, `models.py` |
  | `fingerprint` | Reproduce inputs | `cli.py:322-352` (`md_sha256`, `source_sha256`, `prompt_sha256`, `model`, `lane_version`, `schema_sha256`) |
  | `judge_model` / `tier1_model` / `tier2_model` | Model sovereignty audit | `pdf_judge.py:398-399`, `TapetumResult` |
  | `advisory` | Never gates CI | `pdf_judge.py:412`, `models.py:184` |
  | `ungrounded_dropped` | Quotes discarded at source | `pdf_judge.py:406`, `adjudicate.py` |
  | `status` | Lane ok vs error tombstone | `models.py:157-160` |

- [HIGH] **Firecrawl and markitdown teach document provenance, not quote provenance.** Evidence: firecrawl `Document.metadata` carries `sourceURL`, `pageStatusCode`, `statusCode`, `numPages` (`entities.ts:64-67`; index persistence `scrapeURL/engines/index/index.ts:103-178`) — URL/page/status only, no span offsets. markitdown `DocumentConverterResult` returns `markdown` + optional `title` (`_base_converter.py:5-25`); input trace is `StreamInfo.url` / `local_path` (`_stream_info.py:11-18`); CI uses `must_include` / `must_not_include` substring vectors (`_test_vectors.py:11-12`) with zero coordinates. Impact: do not expect converters to emit char intervals; whisker must compute and persist locate results post-hoc (langextract/LitRAG pattern, `05-web.md:47-61`).

- [HIGH] **Whisker deterministic lane already models honest regional provenance.** Evidence: `missing_regions` entries carry `page`, `token_start`, `token_end`, `sample` (`score.py:282-287`); capped at `REGION_DETAIL_CAP`; inspect surfaces them in `report.py`. Impact: PDF-lane quote records should align with this shape for source legs (`page` + snippet) even when char intervals are unavailable (fuzzy/page tier). Candidate legs should mirror the same tuple on markdown token indices where exact DP succeeds.

- [HIGH] **Text-lane sidecar is the partial gold standard; PDF lane must converge.** Evidence: text adjudicate persists `quote`, `status`, `start`, `end` (`adjudicate.py:340-343`); `inspect_report.py:104-106` renders `exact at chars X-Y` vs `fuzzy`; PDF `to_sidecar_dict` omits intervals and mislabels reason (`pdf_judge.py:401-404`). Impact: port text-lane interval fields to PDF quotes on the source haystack; add parallel `candidate_*` fields when bidirectional locate lands (`03-bidirectional-design.md:59`).

- [MED] **Page escalation provenance is incomplete but salvageable.** Evidence: `page_escalations` records `page`, `content_missing`, `grounded_quotes`, `confidence` (`pdf_judge.py:577-582`); quotes prefixed `[pN]` in `missing_content` (`pdf_judge.py:592`); source grounding uses `ground_page_quotes` only (`pdf_judge.py:572-574`, `grounding.py:244-278`). Impact: each page quote needs `source_page` set, `locate_tier: page_ground_quotes`, and explicit `candidate_status: not_checked` until S2 exists; never inherit monolith's false combined reason.

- [MED] **Authorship and blessing provenance (facts corpus) is the honesty model for human-verified claims.** Evidence: corpus facts carry `checked: verified` \| `draft` (`corpus/p0876r23.facts.jsonl:1-5`); CLAUDE.md states only `verified` gates and blessing is manual. Impact: LLM quote claims are machine-generated and should carry `provenance_author: llm` plus `verification: deterministic_locate` \| `unverified_narrative` for `reasoning`; never promote to `verified` without a separate human/source pass (AuditRAG abstention pattern, `05-web.md:170-178`).

- [MED] **Debug/trace are mandatory siblings, not sidecar substitutes.** Evidence: project trace/debug contract (`CLAUDE.md` trace/debug section); tapetum `--debug` / `--trace` flags (`cli.py:182-189`); `debug_log` on judge calls (`pdf_judge.py:322-345`). Impact: sidecar quote records point to debug step ids (`pdf-judge-{pid}`, page escalation labels) but do not duplicate full prompts; reproducibility = fingerprint + debug artifact path, not reasoning text alone.

- [LOW] **Fusion fingerprint is verdict provenance, not quote provenance.** Evidence: `fusion.py:61-80` hashes whisker verdict/flags for merge audit. Impact: keep fusion block separate; quote records live under `grounded_evidence` / `quote_audit` array, not inside `fusion.whisker_fingerprint`.

## False-pass hypothesis

A quote grounds source-exact at PDF chars 1200-1240 (`grounding.py:221-228`) while the same prose exists in markdown inside a code fence at different chars. Sidecar copies today's reason (`pdf_judge.py:401-404`) and omits `candidate_status`; inspect shows a locatable source interval and the operator believes content is missing. Reproducing the claim requires re-running the lane, manually searching markdown, and discovering the false absence — the sidecar alone certifies a lie.

## False-fail hypothesis

A genuine missing `constexpr` block (PR #293, 5/5 genuine, `00-baseline.md:19`) is recorded with `source_status: fuzzy`, `candidate_status: absent`, `entailment: verified_missing`, but demotion policy caps at `review` because source fuzzy-only (`03-bidirectional-design.md:56`). Operator reads `verified_missing` in the quote record and expects a `fail` verdict; the honest label is correct, the verdict policy is conservative — looks like a false fail if `entailment` is confused with verdict authority.

## What would change my mind

A labeled holdout (≥30 papers, human-marked per-quote entailment) showing that persisting the full v1 schema without demotion policy changes does not improve evidence-precision auditability (measured as blind operator agreement with human labels when shown only sidecar + inspect, no re-run), or that candidate char intervals on normalized markdown disagree with human "present" labels more than 20% of the time — would flip the schema from **usable-with-conditions** to **garbage** and force document-level-only provenance like markitdown vectors.
