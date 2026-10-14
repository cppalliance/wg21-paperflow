# Opus-E - Meta-Review: Security, Determinism, API Contracts, Docs, Error-Handling, Downstream-Consumer

**Cluster:** 01-security-reviewer.md, 02-determinism-auditor.md, 03-api-contract-design.md,
05-documentation-claims.md, 06-error-handling-robustness.md, 10-downstream-consumer.md.

**Method:** every CRITICAL/HIGH claim in the assigned list re-read at the cited `file:line`
against the live tree (not the gitignored `research/repos/` clones, which this cluster's
claims do not depend on). No production code modified.

---

## Verdict on cluster

**Usable-with-conditions.** All six persona reports converge on the same shape: the
deterministic-gates-decide + advisory-LLM split is real and holds at the one boundary that
matters for the architecture question — `whisker --gate` never reads fusion, tapetum, or any
LLM signal (confirmed: `fusion.py`/`fuse_verdicts` is not imported by `__main__.py`; tapetum's
own CLI hard-codes exit 0). Every CRITICAL/HIGH claim I re-verified is CONFIRMED as coded, but
on inspection every one of them lives either (a) inside the *opt-in advisory lane's own
plumbing* (stale sidecar, unwrapped outline/readback prompts) or (b) inside the *deterministic
lane's internal soft-flag folding* (`score.py`'s region matcher) or (c) is a *documented,
working-as-designed default* (`--gate review`). None of them is evidence that LLM output can
flip a CI verdict. That is the correct scope for "architecture-relevant" in this research
question, and I score accordingly below — several personas' CRITICAL severity ratings are
defensible for artifact trustworthiness but overstated for the specific architecture question.

## Findings table

| # | Claim | Status | Evidence |
|---|---|---|---|
| P01a | HTML heading outline injected outside `wrap_source`/`inject_untrusted` envelope | **CONFIRMED** | `adjudicate.py:400-419`: `outline_block` from `format_outline(extract_heading_outline(html_source))` is concatenated into `header` at line 415, and `wrapped_md = ctx.inject_untrusted(md)` only happens at line 418 for the markdown, not the outline. `html_outline.py:65-86` `format_outline` emits raw `- h2: {display}` with zero escaping/delimiting. An attacker-controlled WG21 HTML `<h2>` can therefore sit in the tier-1/tier-2 user message as unescaped plain text, ahead of the wrapped block. |
| P01b | `readback.py:297-302` sends raw markdown with no injection guard | **CONFIRMED** | `_ask_pod` (`readback.py:273-317`) builds the user message as a bare f-string (`f"DOCUMENT:\n{paper_md}\n\nQUESTION:\n{question}"`) via raw `httpx`, never through `pipeline.run_agent`/`StepContext.inject_untrusted` (module docstring documents the D1 exemption: no pipeline steps, no structured output — by design, this module cannot call `inject_untrusted` because it never has a `ctx`). |
| P06 | Rerun adjudication failure leaves yesterday's pass sidecar with no tombstone | **CONFIRMED** | `cli.py:865-873`: the `except Exception as exc:` branch only logs (`logger.error`/`logger.exception`) and optionally sets `inspect_pair`; it never calls `_persist_result`/`_persist_lane_result` (those run only inside the preceding `try:`, lines 812-814/850-852) and never deletes/tombstones the prior sidecar path. Confirmed no other write path exists on this branch. |
| P03 | Fusion/`select_candidates` still parse `hard_flags`/`soft_flags` prose | **PARTIALLY CONFIRMED - class not fully closed** | See enumeration below. |
| P10 | `--gate review` exits 0 for a review verdict | **CONFIRMED (as-designed)** | `__main__.py:88-92` `_GATE_ACCEPTS["review"] = {"pass", "review"}`; default `--gate` is `"review"` (`__main__.py:175-178`); `_verdict_exit_code` (`:130-136`) returns `C.EXIT_OK` whenever the worst verdict present is in the accepted set. With the documented default, a batch that is entirely `review` exits 0. |
| P05 | `CLAUDE.md:526-528` cascade-trigger prose is stale | **CONFIRMED**, plus 4 more stale-doc items found in the same sweep | See doc-fix list below. |

### P03 - full enumeration of flag-string parse sites (`rg` over `hard_flags\|soft_flags`)

| Site | Match style | Status |
|---|---|---|
| `fusion.py:105-116` `_is_heading_only_fail` (hard_flags) | `f.startswith("gate:heading_monotone")` | **FIXED** (2026-07-16 prefix patch; `test_fusion.py:131-146` replays the PR #290 TOC-leak collision and asserts it stays locked) |
| `adjudicate.py:140-151` `_is_heading_only_fail` (hard_flags, candidate selection — a *second, independent* copy of the same function name) | `f.startswith("gate:heading_monotone")` | **FIXED**, same prefix pattern |
| `adjudicate.py:128-137` `_is_benign_region_only` (soft_flags, candidate selection) | `"misaligned region" in f.lower()` — **substring** | **STILL OPEN** |
| `score.py:234-238` `_is_benign_region_only` (soft_flags, inside the deterministic `_decide` itself) | `"misaligned region" in f` — **substring** | **STILL OPEN** |
| `fusion.py:119-121` `_has_only_soft_flags` | list truthiness only, no string content read | not a parse site, no risk |
| `score.py:128` `"gates": [asdict(g) for g in self.gates]` | structured `{name, passed, detail}` serialized | present on disk, but `rg` over the whole package found **zero** production reads of `.get("gates")` outside `__main__.py` display code and tests |

**Verdict on P03:** the 2026-07-16 fix closed the *heading* collision (both copies of
`_is_heading_only_fail`, in `fusion.py` and independently in `adjudicate.py`) but did **not**
close the underlying class. The *region* matcher, doing the identical substring-match, is open
in two places — one of which (`score.py:234-238`) is inside the **deterministic gate's own**
soft-flag folding, not the advisory lane. Practical risk is lower than the heading case was:
`no_toc_leak`'s `detail` embeds a quoted document heading (`"duplicate heading '1. introduction' ..."`), which is exactly what collided with the substring `"heading"`; the region soft-flag
strings are fixed literal templates with no document-text splice, so an accidental
`"misaligned region"` collision from an unrelated flag is unlikely today. But the *pattern* —
matching machine-generated prose by substring instead of the stable `GateResult.name` (or the
already-serialized `gates[]` field) — is unchanged, and it is now demonstrably able to hide
inside the deterministic lane, not only the LLM lane. This is the exact class API-Contract-
Design's "what would change my mind" asked for (a `failed_gate_names`/`gates[].name`-based
refactor); it has not happened for the region matcher.

### P05 - doc-fix list (exact edits for synthesis)

1. **`packages/whisker/src/whisker/CLAUDE.md:526-528`** — "Two-tier cascade... only a
   confidence inside the ambiguous band escalates to the deep model" is stale. Code
   (`adjudicate.py:230-253`, constants `SIGNAL_AXIS_CONFLICT`/`SIGNAL_UNGROUNDED_EVIDENCE`/
   `SIGNAL_CONFIDENCE_AMBIGUOUS` at `constants.py:38-40`) fires on three derived signals
   (axis conflict, ungrounded evidence, ambiguous confidence), only one of which is the
   legacy scalar band. **Fix:** name all three signals in the bullet, matching
   `tapetum_llm.md:12`'s mermaid label.
2. **`packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md:3`** — "only genuinely
   ambiguous calls escalate" is the same staleness, and self-contradicts the file's own
   mermaid diagram two lines later (`:12`, which correctly lists all three signals).
   **Fix:** reword the opening paragraph to match `:12`.
3. **`packages/whisker/src/whisker/CLAUDE.md:557-558`** — "every call is serial and
   deterministic" overstates reproducibility; `tapetum_llm.md:29` documents that hosted
   vLLM token output is not bit-stable under continuous batching/MoE routing. **Fix:**
   split the claim — "every call is serial (one in-flight request per paper); token-level
   output is not bit-stable on a hosted pod (see `tapetum_llm.md`)."
4. **`research/llm-qa-integration/00-baseline.md:60`** — "616 tests" is stale.
   **Verified live:** `uv run pytest packages/whisker/tests --collect-only -q` → **995
   tests collected** (2026-07-16, this session). **Fix:** update to 995 and date the
   number; reconcile against the file's own `:95` "986 tests green" (a different,
   earlier point-in-time count from the MC2 session) so the two numbers in the same doc
   stop disagreeing.
5. **`research/llm-qa-integration/00-baseline.md:85`** — "Dead two-tier cascade (0/198
   escalations)" overstates the current mechanism. Code now adds the three derived
   triggers (`constants.py:32-40`, `adjudicate.py:230-253`, tests
   `test_tapetum_llm.py:1254-1330`); the cascade is no longer structurally confined to the
   confidence band. The empirical `0/198` rate is stale pending a corpus re-run under the
   new triggers. **Fix:** reframe the row from "dead" to "mechanism widened 2026-07-16
   (derived signals added); empirical escalation rate not yet re-measured under the new
   triggers."

All five are documentation-only edits; none touches production code, and fixing them changes
no runtime behavior.

## Architecture-relevant vs hygiene split

**Architecture-relevant** (bear on "did we take the wrong path letting det gates decide"):

- **None of the six CRITICAL/HIGH claims in this cluster undermine the det-decides claim.**
  `whisker --gate`'s exit code is provably independent of fusion/tapetum (no import, hard-coded
  exit 0 in the tapetum CLI). Every failure mode found here is scoped to the advisory lane's
  own bookkeeping (P06, P01a/b) or to the deterministic lane's internal implementation detail
  (P03's region matcher, which happens to live in `score.py` itself). This is the strongest
  possible re-verification result for the architecture question: pressure-testing the exact
  boundary claim did not find a leak across it.
- **P03's discovery that the substring-match anti-pattern now provably lives inside the
  deterministic scorer (`score.py:234-238`), not only the advisory lane,** is the one item
  worth escalating to the synthesis as a general code-quality lesson: "flag prose as API" is
  not an LLM-lane-specific risk, it is a whisker-wide pattern that should be fixed at the
  `GateResult.name`/`gates[]` level everywhere, gate and lane both.

**Hygiene** (real bugs/gaps, but scoped to lane internals or documented defaults, not the
gate/LLM boundary):

- P06 stale sidecar — advisory-lane persistence idempotency bug. Downgraded from the
  persona's CRITICAL: it never touches CI, and the failure IS logged (an ERROR line per
  paper, correlatable with a missing/stale sidecar timestamp); the real gap is that
  correlation is manual, not automatic. **HIGH for advisory-lane trustworthiness, not
  CRITICAL for the architecture.**
- P01a/P01b unwrapped prompts — genuine, fixable defense-in-depth gaps, but both blast
  radii are already capped by the fusion asymmetry (LLM cannot hard-fail or override a det
  fail; readback never runs in CI and has no gating consumer at all). **MED**, matching the
  security-reviewer's own rating, not an escalation.
- P10 `--gate review` exits 0 — this is the CLI's documented, intentional default
  (`CLAUDE.md` "Exit codes (CI contract)" section states it verbatim), not a bug. The
  deterministic gate mechanism works exactly as specified; the risk is an integrator not
  reading the `--gate` flag docs. **Confirmed as coded; reclassified from the persona's
  CRITICAL to a documentation/onboarding hygiene item** — worth a louder callout (e.g. a
  one-line CLI startup warning when `--gate` is left at its default in a non-tty/CI-detected
  context), not a code fix.
- P05 stale docs — pure documentation drift, five concrete edits, zero runtime impact.

## Recommended actions ranked by cost

1. **(cheapest, do first) Fix the five stale-doc lines (P05 list above).** Pure text edits,
   no tests to run, no review risk. Closes the "docs oversell/undersell the architecture"
   gap outright.
2. **Add a tombstone/error-stub write on the `cli.py:865-873` exception path (P06).** One
   `try/except`-adjacent write: either delete the existing sidecar or write a minimal
   `{"status": "error", "error": type(exc).__name__}` stub before re-raising/continuing.
   `fusion.py:86-94` already handles `status="error"` correctly on read; this closes the
   write-side gap that makes the read-side handling meaningful. Low cost, single file,
   testable with one new case in the existing batch-worker test file.
3. **Extend the 2026-07-16 prefix-match fix to the region matcher, in both places (P03).**
   Change `adjudicate.py:128-137` and `score.py:234-238` from
   `"misaligned region" in f` to a name/prefix-based check (e.g.
   `f.startswith("region:")` if the region flag template is given a stable prefix, or
   reading `gates[]`/a new `soft_flag_kind` field instead of parsing `soft_flags` prose at
   all). Slightly higher cost than #2 because it touches the deterministic `score.py`
   `_decide` path directly and needs a regression test proving no verdict changes on the
   existing corpus — but it is the same fix shape already proven safe once this session.
4. **Wrap `format_outline`'s output through `inject_untrusted` before splicing into the
   triage/adjudicate header (P01a).** Contained change: `outline_block` in
   `adjudicate.py:400-419` should go through the same `ctx.inject_untrusted` call the
   markdown gets, or at minimum through the same forged-delimiter escaping
   `pipeline/tools.py:38-62` performs, before concatenation. Needs a new test asserting a
   heading containing `<<<SRC` (or the guard tag pattern) is escaped.
5. **(highest cost, lowest priority) Decide whether `readback.py` should get any wrapping
   at all (P01b).** Given the documented D1 exemption (no pipeline, no `ctx`, raw `httpx`),
   the only options are: (a) accept the current design and add an explicit warning in
   `readback_cli.py`'s help/README that `--corrupt`-style adversarial corpora must not be
   fed to readback without review, or (b) route readback through `pipeline.run_agent`
   after all, which reopens the D1 exemption rationale and is out of scope for this
   research pass. **Recommend (a)**: cheapest option that closes the "silent, undocumented"
   part of the gap without an architecture change nobody has asked for.
