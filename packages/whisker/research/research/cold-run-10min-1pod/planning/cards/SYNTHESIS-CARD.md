# CARD: SYNTHESIS — ≤10 min on one MoE pod

## Bottom line (3 sentences max)
≤10 min on one V4-Pro replica alone is below the quality-preserving physics floor; the only arithmetic path under the twin ban is **`wall = max(T_moe, T_dense)`** on an already-running dense Alliance endpoint. Heterogeneous Package C centers ~**511 s** (planning **~510–710 s**) if scoping + parity land; MoE-only AGGRESSIVE realistic stays ~**715–910 s**. **Live blocker:** all four dense pods **404** today — Package C infra-blocked until `h200-qwen3-32b` restarts; honest SLA without dense is **~15–20 min**.

## Numbers that matter
- v10 baseline: **3003 s**; v11-only expected: ~**1260–1493 s** (~21–25 min)
- Packages @ S=16: CONSERVATIVE ~**2163**; MODERATE ~**1366**; AGGRESSIVE realistic ~**715**; bare optimistic ~**585** (hairline)
- Heterogeneous split: MoE ~**428** calls / dense ~**1879**; MoE-bound ~**511 s** if 2× scoped dense decode
- Front-end floor: **948 s** (758×20/16) already >600 s before units
- v11 short-circuit already: **−1059 to −1341 s**

## Architecture implication
Execute MoE package first (det-metadata → verdict-first → router/quota → server Tier-1); ask Alliance to restart dense; then payload scoping → cascade (units dense, escalate ≤15%) → 381 quality gate. Prefer Qwen3-32B primary; avoid Gemma-4 / R1 as unit primary. Distill only if scoped dense + short pass tokens fail the gate.

## Cite / do not re-open
- Skip monolith; default `--det-skip`; twin / S=32 / c>32
- P/D on one 8×H200; `VLLM_BATCH_INVARIANT`; bank MTP seconds
- Flash without new deploy; server `guided_grammar`; same-pod MoE→MoE cascade
- Claiming ≤10 min executable while dense pods are 404

## Links to related reports
- `research/cold-run-10min-1pod/SYNTHESIS.md` (this source)
- `00-baseline.md`, `12-dense-offload-architecture.md`, `17-physics-floor-skeptic.md`, `18-packages-1pod.md`, `26-dense-pod-liveness.md`
- `PLANNING-HANDOFF.md`, `05*.md` forage set
