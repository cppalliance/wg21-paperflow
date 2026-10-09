# MEASUREMENT-PROTOCOL — Honest cold A/B on `alliance-pod`

**Sources:** `28-shared-pod-noise.md`, `19-quality-gate-1pod.md`, `PLANNING-HANDOFF.md` §5/§11, `SYNTHESIS.md`.

**Variance default:** HIGH. Shared Alliance multi-tenant pod; API key ≠ slot isolation.

---

## 1. Purpose

Produce wall-time and quality comparisons that can be attributed to **code levers**, not to:

- Foreign vLLM occupancy on `alliance-pod`
- Warm fingerprint skip
- Mixed `_LANE_VERSION` / workspace sidecars
- Console encoding corruption on Windows log capture

---

## 2. Off-hours / quiet window

| Rule | Detail |
|------|--------|
| Prefer off-hours / announced maintenance | Informal mitigation; no enforcement on shared pod |
| Before gather | Confirm no other large Alliance fleets on `alliance-pod` |
| During run | Scrape `/metrics` (every ~10 s): `num_requests_running`, `num_requests_waiting`, `request_queue_time_seconds` |
| Occupancy match | A1, A2, and B must run under **comparable** external load; log occupancy beside wall |
| Downgrade variance claim | Only if external_in_flight ≈ 0 for the full run **and** double-A `flip_AA ≤ 5%` on the four-component vector (neither evidenced today) |

**Modeled failure mode:** 8/16 slots stolen ≈ **2×** wall on that shard. Do not treat single A/B as ground truth without matched occupancy.

---

## 3. Metrics to capture (every cold fleet)

| Metric | Where |
|--------|--------|
| Wall seconds (end-to-end) | Client timer |
| Call counts by class / pod | Sidecar `call_timings[]` or equivalent |
| `num_requests_running` / `waiting` time series | Pod `/metrics` |
| Queue p95 if available | `/metrics` |
| `_LANE_VERSION`, git SHA, `SERVICES.toml` pin | Run manifest |
| Config flags (`--force`, concurrency, service overrides) | Run manifest |
| Equivalence artifacts | `_scratch/equiv/...` (see quality protocol) |

Never enable `VLLM_BATCH_INVARIANT` for speed-path measurement (~50% throughput tax).

---

## 4. Double-A (noise floor) before lever claims

1. **A1** then **A2**: identical MODERATE single-pod config, full 381, `--force`.
2. Compute four-component `flip_AA` + discordant PID list.
3. Only then run **B** and require `flip_AB ≤ flip_AA + margin`.
4. Weekly cached A2 is allowed **only** if same `_LANE_VERSION`, alliance-pod image, dense contract, and `SERVICES.toml`.

Without load-matched double-A, do not attribute verdict drift to a lever (`28`, `19`).

---

## 5. Cold-run invariants

| Do | Do not |
|----|--------|
| Full 381 with `--force` for equivalence | Warm fingerprint skip for A/A or A/B |
| Client c=32 (production) unless measuring isolation baselines | Raise c>32 or MoE S>16 |
| Serial in-paper calls (already default) | In-paper parallel |
| Remeasure after v11 before claiming further wins | Compare B against v10 3003 s as if it were MODERATE A |

---

## 6. Workspace isolation

| Rule | Why |
|------|-----|
| Dedicated `WG21_DATA_DIR` (or clearly named workspace) for measurement fleets | Avoid mixing production advisory sidecars with experiment `_LANE_VERSION` bumps |
| One workspace per config regime (A vs B) or hard wipe between regimes | Fingerprint / sidecar pollution invalidates incremental and equivalence |
| Write gate artifacts under a run-specific scratch path | e.g. `research/tapetum-llm-speedup/_scratch/equiv/aggressive-1pod-v<N>/` |
| Do not mutate golden expected labels during a gate run | Holdout anchors are locked (SHA-256) |
| Dense and MoE probes use keys from `.env`; do not share scratch DBs across machines mid-gate | Path/HMAC and skip state diverge |

---

## 7. PYTHONIOENCODING (Windows)

Not called out in the 1-pod research cards, but **relevant on Windows** operator hosts when capturing fleet logs / JSON sidecars with non-ASCII paper titles:

```powershell
$env:PYTHONIOENCODING = "utf-8"
# optional belt-and-suspenders for the console:
chcp 65001 | Out-Null
```

Set this for the shell that launches `uv run` / tapetum cold fleets so progress lines and artifact dumps do not mojibake and poison post-hoc parsers. Prefer writing metrics to UTF-8 files over trusting the console alone.

---

## 8. Pre-flight checklist (copy)

- [ ] Off-hours or confirmed quiet window
- [ ] `/metrics` scraper ready
- [ ] Isolated measurement workspace + empty or version-pinned sidecars
- [ ] `--force` cold; fingerprint skip off
- [ ] `PYTHONIOENCODING=utf-8` on Windows shells
- [ ] Dense pod `GET /v1/models` → 200 if measuring Option B
- [ ] Manifest: lane version, SHA, services pin, start time
- [ ] Double-A complete (or valid cached A2) before B claims
