# 20 - Payload-Scoping-Auditor

**Verdict:** usable-with-conditions — unit checks and page escalations waste the most prefill by re-embedding full candidate markdown (~66% of fleet calls); scoped page-local excerpts can cut prefill only if paired with a mechanical ANYWHERE oracle, but savings cap near ~7–14% wall and are secondary to prefix-cache reorder plus call elimination.
**Confidence:** high (payload shapes and token ceilings are file:line anchored at HEAD); medium (scoped-window false-fail rate without holdout A/B)

## Call-type payload matrix (measured from code)

| Call type | Count (cold fleet) | Source payload | Candidate payload | Scoped? | Agent / max_tokens | thinking_budget |
|-----------|-------------------:|----------------|-------------------|:-------:|-------------------|-----------------|
| PDF monolith | 180 | **Full** normalized PDF text layer (`normalize_textlayer`, all pages concatenated) | **Full** md after `strip_binary_payloads` | No | `judge` / **1536** (`cli.py:1110-1112`) | **Omitted** — pod ignores (`cli.py:1109`, `tapetum_llm.md:307`) |
| HTML tier-1 triage | 201 | Optional HTML heading outline only (deterministic, best-effort) | **Full** md, or one **H2 chunk** if `len(md) > MAX_PAPER_MD_CHARS` (500k) | Chunk only when oversized | `fast` / **1024** (`adjudicate.py:90-93`, `tapetum_llm.md:247`) | Documented **1024** in prompt; **not forwarded** to backend |
| HTML tier-2 adjudicate | ~23 | Tier-1 reasoning/concern (wrapped, small) | **Full** md (always whole doc, even if tier-1 was chunked) | No | `deep` / **2048** (`adjudicate.py:90-93`, `tapetum_llm.md:268`) | Documented **4096**; **not forwarded** |
| Metadata / outline | 377 | Bounded: PDF page-1 text + heading candidates; HTML first 4000 chars metadata + outline list | **Front matter + ATX heading list only** — not full md (`unit_judge.py:220-261`) | Yes | PDF: `judge` / 1536; HTML: `fast` / 1024 | Omitted / not forwarded |
| Unit check | **~1510** | **One page or section** text slice (`unit_text_map[unit_id]`) | **Full** candidate md every call (`unit_judge.py:791-798`) | Source only | PDF: `judge` / 1536; HTML: `fast` / 1024 | Omitted / not forwarded |
| Page escalation | ~16 | **One page** raw PDF text (dehyphenated) | **Full** converted md (`pdf_judge.py:397-403`) | Source only | `judge` / 1536 | Omitted |
| Ideal verification | ~1 | N/A | **Full** candidate md **+ full** ideal md (`ideal_verify.py:53-57`) | No | `ideal` / **2048** (`cli.py:148`, `1089`) | Not set on AgentBackend |

**Within-paper message layout (prefix-cache relevant):**

- Unit checks already lead with shared content: `[CANDIDATE MARKDOWN][Paper/Unit/Risk/SOURCE TEXT]` (`unit_judge.py:791-798`), with paper-stable HMAC guard tag via `_paper_guard_tag` (`cli.py:467-479`, `unit_judge.py:345-349`).
- Page escalations mirror that: `[CONVERTED MARKDOWN][Paper/Page][RAW PDF TEXT page N]` (`pdf_judge.py:397-403`).
- PDF monolith is symmetric full-doc: `[RAW PDF TEXT][CONVERTED MARKDOWN]` (`pdf_judge.py:662-665`).
- Metadata is inherently small and not repeated at scale.

**Prefill vs decode (settled baseline):** mean decode **5.91 s** vs prefill **0.46 s** per call (`research/tapetum-llm-speedup/00-baseline.md`, P146). Fleet wall is still dominated by **call count × ~20 s/call / 16 slots**, not raw prefill seconds — but duplicated full-md prefills on 1510 unit calls are the largest *repeatable* input waste.

## Findings

- [CRITICAL] **Unit checks are the prefill waste class: 66% of calls, full candidate md each time.** Evidence: `_check_one_unit` injects entire `candidate_md` (`unit_judge.py:791-793`); fleet census **1510 / 2284** unit calls (`research/tapetum-llm-speedup/10-call-graph-accountant.md:8`, `research/cold-run-10min/00-baseline.md:21`). Median paper runs monolith + metadata + up to **5** unit checks, each re-prefilling the same md. Impact: even at ~0.46 s mean prefill/call, **~695 s aggregate prefill** on unit class alone; duplicated md tokens also block APC reuse when layout/tag is wrong. Quality risk: none from duplication; waste is latency-only.

- [CRITICAL] **Page escalations repeat the same pattern on a smaller denominator.** Evidence: `_escalate_page` sends full `tomd_md` plus one page's source (`pdf_judge.py:397-403`); only **~16** fleet calls (`10-call-graph-accountant.md:24`). Impact: negligible wall (~20 s class total) but identical semantic design as unit checks. Quality risk: none.

- [HIGH] **Monolith and HTML tier-1/2 must send full documents by role; they are not the waste target.** Evidence: PDF monolith compares whole PDF text layer to whole md (`pdf_judge.py:662-665`, docstring `584-586`); HTML triage injects full md or serial H2 chunks (`adjudicate.py:241-260`, `_build_triage_message` `702-708`); tier-2 re-injects full md after tier-1 (`adjudicate.py:736-738`). Impact: **381 + ~23 ≈ 404** calls where full-doc input is structurally required. Quality risk: **HIGH** if monolith is scoped without a whole-doc substitute.

- [HIGH] **Metadata is already scoped and cheap relative to unit checks.** Evidence: `_candidate_structure_packet` extracts front matter + heading outline only (`unit_judge.py:220-261`); PDF source side is page-1 text + heading candidates (`pdf_judge.py:694-699`). Impact: **377 calls** with **O(headings)** candidate payload, not O(paper). Not a 10 min lever. Quality risk: none.

- [HIGH] **Judge max_tokens are tight; thinking budgets are paper-only.** Evidence: PDF judge **1536** (`cli.py:1110-1112`); text lane **1024/2048** by slot (`adjudicate.py:90-93`); ideal **2048** (`cli.py:148`); `thinking_budget` explicitly omitted on judge agent with live-probe note (`cli.py:1109`); `tapetum_llm.md` documents fast=1024 / deep=4096 thinking intent but states pod ignores `thinking_token_budget` (`tapetum_llm.md:33`, `307`). Impact: decode is capped (~70 tok/s); latency lever is **shorter structured output**, not thinking tokens (`pdf_judge.py:27-28`, `research/tapetum-llm-speedup/68-marker-output-discipline.md:8-10`). Quality risk: **HIGH** if caps shrink below quote-grounding needs (marker anti-pattern, `68-marker-output-discipline.md:26-28`).

- [HIGH] **LangExtract speedup lesson: scoped Q: tail (~200–1000 chars) + shared static prefix beats our 6× full-doc prefill.** Evidence: default `max_char_buffer=1000` / Annotator **200** (`research/tapetum-llm-speedup/83-langextract-call-census.md:14`, `85-langextract-prompt-structure.md:20`); prompt order static→examples→chunk LAST (`85-langextract-prompt-structure.md:10-12`); contrast tapetum unit checks embed full `candidate_md` (`85-langextract-prompt-structure.md:20`). Impact: langextract trades **more calls** for **smaller variable prefill**; tapetum trades **fewer calls** for **massive repeated prefill** — inverted economics on 80k-char papers (~80–150 langextract calls vs 6 tapetum calls, `83-langextract-call-census.md:14`). Portable insight: **scope the variable tail, hoist the shared doc prefix** — not copy langextract's chunk count. Quality risk: **HIGH** if scoping drops ANYWHERE rule without substitute (`unit_judge.py:137-139`).

- [MED] **Marker speedup lesson: call topology dominates; unbounded output would slow us.** Evidence: marker defaults **no output cap** on most backends; table processors emit full HTML rewrites (`68-marker-output-discipline.md:8-12`); speed from **block-gated call count + in-doc parallelism**, not terse JSON (`68-marker-output-discipline.md:14-16`). Our judge already caps output and runs **6 serial calls/paper** vs marker's variable block inventory. Impact: copying marker-style large rewrite outputs would **increase** decode time; the relevant marker pattern for tapetum is **fewer gated calls**, not bigger payloads. Quality risk: N/A for comparison.

- [MED] **Portable scoped-payload design (hybrid, preserves ANYWHERE):** (1) LLM sees **H2-bounded candidate window** for the unit's page ±1 neighbor (join tails, `packages/tomd/src/tomd/CLAUDE.md:231-232`); (2) add **compact presence index** (sorted normalized phrases / 5-gram sketch of full md); (3) prompt clause: treat index hits as document-wide present; (4) keep **`verify_unit_evidence` / `classify_candidate_evidence` on full `raw_tomd_md`** unchanged (`unit_judge.py:439`, `742-744`). Prior art: `research/tapetum-llm-speedup/13-payload-scoper.md:18`; unstructured soft/hard window pattern (`123-unstructured-chunking-strategy.md:10-18`). Estimated fleet wall savings **~198 s (~7% of 3003 s)** at P50 sizes — insufficient alone for ≤600 s (`13-payload-scoper.md:14-15`, `00-baseline.md:24-28`). Quality risk: **MEDIUM** (index normalization vs dehyphenation / wording markup).

- [MED] **Prefix-cache reorder may match scoping savings with lower semantic risk.** Evidence: paper-stable `_paper_guard_tag` + candidate-first user layout (`cli.py:467-479`, `unit_judge.py:791-798`); prior per-call random tags broke APC (`research/tapetum-llm-speedup/102-vllm-anti-steelman.md:8-10`); DeepSeek-V4 APC **74% hits / 4.5× throughput** when prefix aligns (`research/tapetum-llm-speedup/05-web.md`, cited in `85-langextract-prompt-structure.md:8`). Impact: est. **~236 s wall** from redundant md prefills on calls 2–6 without shrinking payload (`13-payload-scoper.md:16-17`). Quality risk: **LOW** if guard tags stay per-paper and `inject_untrusted` wraps all blocks.

- [LOW] **Ideal verify doubles full-doc prefill but is ~0.04% of calls.** Evidence: two full documents in one prompt (`ideal_verify.py:53-57`); fleet **~1** call (`10-call-graph-accountant.md:24`). Impact: irrelevant to cold-run 10 min target.

## Which call types waste prefill (ranked)

1. **Unit check** — full md × ~1510 calls; largest repeatable waste; 70% zero-defect (`00-baseline.md:26-27`).
2. **Page escalation** — same full-md pattern; tiny call share.
3. **PDF monolith / HTML tier-1/2** — full doc necessary; not waste in the sense of eliminable duplication without changing role.
4. **Metadata** — already scoped; minimal waste.
5. **Ideal verify** — negligible call volume.

**Not prefill waste but larger wall levers (already ranked in `00-baseline.md`):** metadata-fail short-circuit (**~1341 s**, 44.6% fusion-dead unit calls), call elimination, dual-pod shard, APC — all dominate scoped-payload prefill math.

## Portable scoping idea (with risk)

**Proposal:** For unit checks and page escalations only, replace full `candidate_md` in the LLM prompt with:

```
[system + CONVERSION_CONTRACT + paper-stable guard tag]
[CANDIDATE WINDOW: H2-aligned slice for unit page ±1 neighbor, soft/hard char caps ~8K/12K]
[PRESENCE INDEX: sorted normalized key phrases from full md — mechanical ANYWHERE oracle]
[unique tail: unit_id, risk signal, SOURCE TEXT slice]
```

Post-process unchanged: `verify_unit_evidence(..., candidate_md=full raw)`, `verify_defect_counts` on full doc (`unit_judge.py:648`).

| Risk | Severity | Mitigation |
|------|----------|------------|
| Cross-page join false-fail (content lives under prior page's heading) | HIGH | ±1 H2 neighbor window; presence index; keep ANYWHERE prompt clause |
| Cross-page join false-pass (scoped window hides defect, model passes without quote) | MEDIUM | Fail-closed: ambiguous window → `review`; grounding still on full doc when model emits defects |
| Index too strict (dehyphenation, wording divs, fuzzy match) | MEDIUM | Index uses same normalization as `grounding.py` / `normalized_text` |
| APC + scoping both needed; scoping alone misses 10 min target | HIGH | Stack with metadata short-circuit, reorder, sharding — do not treat scoping as primary lever |
| Batching multiple units per prompt (langextract `batch_length` analog) | HIGH | RuVerBench-style rubric degradation (`83-langextract-call-census.md:34`) — forbidden without holdout proof |

## False-pass hypothesis

Section-window scoping **without** a full-doc presence index: a table cell transposition on page 10 survives because the LLM sees only a local window, returns `pass` with empty defects, and post-hoc grounding never runs — reproducing the monolith-only blind spot that motivated unit checks (`research/tapetum-llm-speedup/11-router-precision-auditor.md`, PR #286 class).

## False-fail hypothesis

Strict alnum-only presence index: dehyphenated join text (`implementa-` / `tion`) or wording-markup-wrapped prose appears absent in the index but exists in full md; model reports `content_omission`, verified grounding refutes — wasted decode on good papers, verdict capped at `review` via evidence uncertainty (`unit_judge.py:479-487`).

## What would change my mind

`--debug` logging of vLLM `prompt_tokens` and APC block hit rate **per call type** on a 20-paper replay showing **≥50% of unit-check wall time is uncached prefill** (not decode) **after** paper-stable tags and candidate-first layout — would elevate scoped payloads above metadata short-circuit in the ≤600 s stack.

## Code anchors (absolute paths)

- `c:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\tapetum_llm\unit_judge.py` — unit/metadata payloads, ANYWHERE rule
- `c:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\tapetum_llm\pdf_judge.py` — monolith, page escalation, metadata orchestration
- `c:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\tapetum_llm\adjudicate.py` — HTML tier-1/2 full-md messages, agent max_tokens
- `c:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\tapetum_llm\cli.py` — judge 1536, ideal 2048, `_paper_guard_tag`
- `c:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\tapetum_llm\constants.py` — `MAX_UNIT_CHECKS`, `MAX_PAPER_MD_CHARS`, timeouts
- `c:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\tapetum_llm\tapetum_llm.md` — documented thinking budgets (not forwarded)
