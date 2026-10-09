# 44 - Debug-IO-Auditor

**Verdict:** garbage (+ non-LLM I/O is ~1–2 s on the 3003 s cold fleet and ~1 s on the 64.8 s warm rerun; fingerprint hashing is not the warm-run bottleneck — the six error-tombstone re-cascades are)
**Confidence:** high

## Findings

- [CRITICAL] **Pure file hashing over the full 583-paper markdown corpus is sub-second.** Measured 2026-07-23 (`_scratch/research-tapetum-llm-speedup/time_io_overhead.py`, supplemental 583-md glob): **583 papers, 0.278 s total**, mean **0.48 ms/paper**, p95 **1.31 ms**, max **5.9 ms**, **149.9 MB** read (`cli.py:439-445`, `597-598`). Impact: even a full-corpus fingerprint pass saves **<1 s** vs the **3003 s** cold run; **quality risk: none** (measurement only).

- [CRITICAL] **Warm-run wall (64.8 s) decomposes to ~63 s LLM on six tombstone papers, not fingerprint I/O.** Baseline: **375/381 skipped**, **6 re-evaluated** (`00-baseline.md:19-20`). Measured full skip path on 381 converted papers: **0.529 s serial**, **0.037 s** simulated at c=32 wave max (`cli.py:1175-1202`, `_compute_fingerprint` at `566-619`, `_fingerprint_matches` at `638-661`). Startup without adjudication: **0.730 s** (health probe **0.716 s**, fingerprint precompute **0.009 s**, `cli.py:997-1061`, `910-951`). End `_build_merged_report`: **0.356 s** (`cli.py:797-835`, `1431-1432`). Residual **~63 s** matches **~42 LLM calls × ~20 s / 16 slots ≈ 52 s** plus probe/merge/footer (`00-baseline.md:24-25`; persona 37 ideal/tombstone accounting). Impact: incremental UX latency is **retry policy + LLM**, not `_sha256_file`; **quality risk: none** for I/O tuning.

- [HIGH] **`_build_merged_report` + whisker sidecar harvest are ~0.4–0.8 s combined, not >60 s.** Measured: `_build_merged_report` **0.356 s** on **381** tapetum sidecars; `_collect_sidecar_dicts` alone **0.078 s** (`cli.py:398-426`, `797-835`). Cold run adds **0.36 s** once at tail; warm rerun adds the same. Impact: **≤0.8 s** on **3003 s** (**<0.03%**); skip `--fuse-only`/merged rebuild is not a 5–10 min lever. **Quality risk: none.**

- [HIGH] **Per-paper persist I/O (read whisker sidecar + `fuse_verdicts` + JSON write) is ~2 ms/paper, hidden under LLM.** Measured on 381 pairs: fusion read+compute **0.447 s** (mean **1.17 ms/pair**, `cli.py:692-702`, `718-727`, `731-738`; `fusion.py:59` pure CPU); JSON serialize **0.215 s**; full read-fusion-write to disk **0.986 s** (mean **2.08 ms**, **5.9 MB**). Impact: **~1 s** total if serialized across 381 papers, **≪120 s** per-paper LLM depth (`00-baseline.md:38-39`); overlap with decode makes wall impact **≈0 s**. **Quality risk: none.**

- [MED] **Incremental skip reads one tapetum sidecar per paper for the stored fingerprint.** `_read_existing_fingerprint` alone: **0.177 s / 381 papers**, mean **0.46 ms** (`cli.py:622-632`). Dominated by `_sha256_file` on source+md inside `_compute_fingerprint`, not JSON parse. Impact: at c=32, **~0.04 s** wall for 375 skips; irrelevant vs **64.8 s** warm run. **Quality risk: none.**

- [MED] **Batch logging/progress bar overhead is architecturally bounded and unmeasured as seconds.** Batch mode quiets four loggers to WARNING (`cli.py:211-216`, `1069-1077`); `_BarAwareHandler` redraws stderr progress (`cli.py:245-263`, `1079-1087`, `1395-1396`). `_render_progress` is O(1) string write per completion. Impact: **≪1 s** on 381 updates; not a fleet lever. **Quality risk: none.**

- [LOW] **583 vs 381 corpus scope: fleet bare run adjudicates converted papers only.** Workspace has **583** `paperstore/*.md` files but `backend.list_all_paper_ids()` with existing `.md` yields **381** fleet papers (same count as cold baseline). Fingerprint extrapolation 583/381 × 0.529 s ≈ **0.81 s** serial full skip. Impact: numbering in the mandate does not change the verdict. **Quality risk: none.**

## False-pass hypothesis

Caching `_sha256_file` results in-process across the batch without invalidating on file mtime: a concurrent `paperflow convert` during `whisker-tapetum-llm` could skip a stale paper with a matching old sidecar fingerprint, silently reusing an outdated advisory verdict.

## False-fail hypothesis

Skipping `_build_merged_report` to save **~0.36 s** would not change per-paper verdicts but would leave `report-merged.md/json` stale after a full run, causing operators to read outdated fusion rollups while sidecars are fresh (`cli.py:797-802`, `whisker/CLAUDE.md` freshness contract).

## What would change my mind

A tracemalloc or `asyncio` loop-block profile of a live warm rerun showing **>60 s** cumulative time in `_sha256_file`, `_build_merged_report`, or sidecar `write_text` (not `classify_candidate_evidence` CPU already bounded separately in `tapetum-llm-throughput/10-evidence-verification-cost.md`) would flip the verdict to **usable-with-conditions** for I/O-specific work (e.g. mmap hashing, deferred merged report).
