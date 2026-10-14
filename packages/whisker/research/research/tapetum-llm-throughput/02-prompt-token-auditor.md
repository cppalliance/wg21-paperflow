# 02 - Prompt-Token-Auditor

**Verdict:** usable — system-prompt growth is real but tiny (~22% on the monolith, ~112% on unit-check instructions); the 4.2× fleet regression is explained by new serial call types (metadata + up to five unit checks), not by prompt bloat inflating prefill.
**Confidence:** high (system-prompt char counts measured from git snapshots and live imports); medium (user-payload medians extrapolated from code structure and `17-latency-decomposer.md` corpus P50s, not re-sampled from tonight's sidecars)

## Findings

- [CRITICAL] **Call-count multiplication dominates the 4.2× wall regression; prompt growth does not.** Evidence: `00-baseline.md:13-14` (692.3 s → 2883 s, 4.2×); `00-baseline.md:41-42` (1.8 s/paper → 7.6 s/paper); `00-baseline.md:103-109` (back-of-envelope ~1 + ~3–5 unit + metadata calls vs ~1 call at 07-09); `pdf_judge.py:646-888` (monolith → metadata → unit_checks serial cascade). Impact: pricing the regression as token bloat mis-targets the lever; fleet cost is ~5× more decode-bound round-trips per PDF paper, not ~5× longer prefill on one call.

- [HIGH] **Monolith system prompt grew modestly: 3072 → 3751 chars (+22%, +679 chars) between 07-09 and 07-17; unchanged 07-17 → HEAD.** Evidence: `git show 58a978c:…/pdf_judge.py` (`JUDGE_SYSTEM_PROMPT` measured 3072 chars via exec); `git show c59139c:…/pdf_judge.py` and HEAD import (`JUDGE_SYSTEM_PROMPT` 3751 chars); growth is contract refactor (TOC-leak inverse, figure-text rule) extracted to `_CONVERSION_CONTRACT` / `CONVERSION_CONTRACT` (`00-baseline.md:66-72`). At chars/4 and ~4000 tok/s prefill (`00-baseline.md:59-60`, `17-latency-decomposer.md:12`): +679/4 ≈ **+170 tok → +0.04 s prefill** per monolith call. Impact: negligible vs ~25–28 s decode per call.

- [HIGH] **07-22 contract work bloated unit-check instructions, not the monolith.** Evidence: c59139c `UNIT_CHECK_SYSTEM_PROMPT` 1745 chars (embeds short `_UNIT_CONVERSION_CONTRACT` 511 chars); HEAD `UNIT_CHECK_SYSTEM_PROMPT` 3696 chars (embeds full `CONVERSION_CONTRACT` 2096 chars, `unit_judge.py:129-159`, `00-baseline.md:74-77`). Delta **+1951 chars (+112%)** ≈ **+488 tok** ≈ **+0.12 s prefill** per unit call. Impact: even ×5 unit calls adds **<1 s** prefill total; still noise vs decode.

- [HIGH] **New call types at c59139c add entire prompts absent at 07-09.** Evidence: `00-baseline.md:66-73` (`unit_judge.py` absent at `58a978c`); measured c59139c/HEAD: `METADATA_CHECK_SYSTEM_PROMPT` 738 chars; `PAGE_JUDGE_SYSTEM_PROMPT` 3833 chars; `UNIT_CHECK_SYSTEM_PROMPT` 1745–3696 chars; `58a978c` has no `PAGE_JUDGE` or unit lane. Runtime HEAD system+guard (`pipeline/tools.py:55-62`, 192 chars): monolith 3944, page 4026, metadata 931, unit 3889 chars. Impact: each new call pays full prefill **and** full decode (~25–28 s, `00-baseline.md:59-60`), not just a longer shared prefix.

- [HIGH] **User payload architecture repeats full candidate markdown on every unit check — far larger than system-prompt deltas.** Evidence: `unit_judge.py:744-751` (`CANDIDATE MARKDOWN: inject_untrusted(candidate_md, tag)` on every `_check_one_unit`); `unit_judge.py:355` (`MAX_UNIT_CHECKS = 5`, `constants.py:223`); monolith sends full PDF text + full md once (`pdf_judge.py:640-643`). Median payload model (P50 md ≈ 22–34K chars post-strip from `17-latency-decomposer.md:18`; typical page ≈ 2.5K chars): unit user ≈ **48K chars (~12K tok)** per call; three routed units ≈ **144K chars (~36K tok)** of duplicated md alone. Impact: user-payload duplication drives prefill on unit calls (~12K tok each), but each call still adds **~27 s decode** — the regression term is call count × decode, not +488 tok on the system block.

- [MED] **HTML text-lane system prompt grew slowly and is irrelevant to tonight's PDF fleet.** Evidence: `tapetum_llm.md` System Prompt section measured 8855 chars (`58a978c`) → 9232 (`c59139c`) → 9257 chars (HEAD); `00-baseline.md:35-36` (fleet default routed mode, `all_pages=False`). Impact: adjudicate text-lane prompt inflation is **+402 chars (+1.1%)** over the period; PDF papers never hit it in the bare fleet run.

- [MED] **Prefill remains ~7% of per-call wall at P50 even after lane expansion; decode stays ~93%.** Evidence: `00-baseline.md:59-60` (~25–28 s of ~30 s mean decode-dominated); `17-latency-decomposer.md:12-30` (P50 input ≈ 8538 tok → 2.1 s prefill @ 4000 tok/s). Scaling to HEAD PDF paper (serial ~5 calls, median payloads): total input ≈ 23K + 1.4K + 3×13K ≈ **65K tok prefill ≈ 16 s** vs **5 × 27 s ≈ 135 s decode** serial (~4% prefill share). Impact: shrinking system prompts saves sub-second per paper; removing or capping unit calls saves tens of seconds.

- [LOW] **`guard_instruction` adds 192 chars (~48 tok) per call, unchanged across commits.** Evidence: `pipeline/tools.py:55-62`; appended in `pdf_judge.py:639`, `unit_judge.py:743`. Impact: 5 calls × 48 tok = 240 tok ≈ 0.06 s — immaterial.

## Arithmetic summary (median PDF paper, routed fleet)

| State | Serial LLM calls (typical) | System+guard chars (sum) | Est. prefill (chars/4 @ 4K tok/s) | Est. decode (5×27 s routed) | Serial wall |
|-------|---------------------------|--------------------------|-----------------------------------|----------------------------|-------------|
| `58a978c` | 1 monolith | ~3,456 | ~2 s | ~27 s | ~29 s |
| `c59139c` | 1 + 1 metadata + ~3 units | ~15,543 | ~8 s | ~135 s | ~143 s |
| HEAD | same call shape; unit system +1951 chars | ~17,494 | ~9 s | ~135 s | ~144 s |

HEAD vs `58a978c` on prompts alone: **~+6 s prefill** (+4×) but **+108 s decode** (+4×) from new calls. HEAD vs `c59139c` from 07-22 contract move: **~+1 s prefill**, **0 s decode** (same call count).

Fleet wall check: 381 papers × ~144 s serial / 32 effective slots ≈ **1717 s** theoretical floor vs observed **2883 s** (`00-baseline.md:27-28`) — gap is retries (54), errors (4), variable unit counts, page escalations (16 logged), and pod variance (`00-baseline.md:54-56`), not prompt length.

## False-pass hypothesis

Shrinking `UNIT_CHECK_SYSTEM_PROMPT` back to the c59139c short `_UNIT_CONVERSION_CONTRACT` (~511 chars) would save ~0.4 s prefill per paper and might let the model miss TOC-leak / figure-text sanctioned rules, increasing false-clear unit passes without moving fleet wall meaningfully.

## False-fail hypothesis

Leaving the full `CONVERSION_CONTRACT` in every unit-check system prompt adds ~0.36 s prefill per paper (three units) but reduces TOC/page-1 false flags; removing it would not recover the 4.2× regression because decode time is unchanged.

## What would change my mind

A `--debug` replay of tonight's fleet logging per-call `prompt_tokens` / wall times from the pod (or sidecar-enriched timings) showing prefill grew ≥2× per call while call counts stayed ~1× — that would flip the call-count story and elevate prompt bloat to primary cause.
