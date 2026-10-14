# Auditv3 Preconditions

Recorded before any scoring or claim work. Auditv2 was capped because its
target state was not pinned and its live lane was unavailable. This file pins
the target and records the lane status honestly, whatever it says.

**Date:** 2026-08-03
**Auditor:** agent-run, PlannerExecutor orchestration
**Method:** every statement below is a recorded command result, not an assumption.

## 1. Target freeze

Git HEAD alone is not a usable audit anchor for this run. The working tree
carries 7205 uncommitted insertions across `packages/whisker` and
`packages/tomd`, plus whole untracked modules that the audit explicitly
targets (`ideal_verify.py`, `metadata_compare.py`, `payload_scope.py`,
`table_compare.py`, `survey/`, `compare/`, `branding/`). Auditing HEAD would
audit code that no longer exists in the form the operator runs.

The audit target is therefore the **working tree**, pinned by content hash.

| Anchor | Value |
|---|---|
| Git HEAD (base) | `0d18a65b0cb000f24408af819ae118528b4a9a96` |
| HEAD subject | `Merge remote-tracking branch 'upstream/main'` (2026-08-02 02:02:59 +0200) |
| Branch | `main` |
| Uncommitted diff (whisker + tomd) | 44 files changed, 7205 insertions, 539 deletions |
| Untracked modules in target | 4 `tapetum_llm/*.py`, 3 packages (`survey/`, `compare/`, `branding/`), 18 test files |
| Stashes | none |
| **Target manifest aggregate** | **`b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771`** |
| Manifest file count | 157 |

The per-file SHA-256 manifest is `raw/w0-target-manifest.txt`. Any reader can
recompute it and confirm they are looking at the same code this audit judged.
If the aggregate differs, the findings below do not apply to their tree.

**Command:**

```
git rev-parse HEAD; git status --short; git diff --stat -- packages/whisker packages/tomd; git stash list
```

**Precondition verdict:** PINNED (by content manifest, not by clean tree).
The v2 finding "audited at a dirty tree" is **not** resolved. It is replaced by
a stronger anchor. Reproducibility from a clean clone remains impossible for
this run; that limitation is carried into the synthesis and must not be scored
as if the tree were clean.

## 2. LLM lane availability

**Status: GREEN. `alliance-pod` is live and serving.**

Reaching this answer took two rounds, and the first round was wrong in a way
worth recording, because the same mistake would make any future health check
report a false outage.

### 2.1 Round 1 (wrong): every endpoint returned 403

A probe using `urllib.request` with its default user-agent returned HTTP 403
from `alliance-pod`, `h200x8-deepseek-v4-pro`, `b300-qwen36-27b`, **and** from
a deliberately nonexistent control subdomain. The identical control result
looked like proof that 403 was RunPod's "no pod behind this subdomain"
response, i.e. an outage.

Capturing the response **body** refuted that:

```
alliance root      403 server=cloudflare b'error code: 1010\n'
alliance health    403 server=cloudflare b'error code: 1010\n'
bogus control      403 server=cloudflare b'error code: 1010\n'
```

Cloudflare error 1010 means the client was banned by browser signature. The
RunPod proxy sits behind Cloudflare, which rejected the `python-urllib/3.x`
user-agent **before routing**. That is why the control returned the same
status: nothing was ever routed, so the control proved nothing.

### 2.2 Round 2 (correct): browser user-agent and the real SDK stack

| Probe | Client | Result |
|---|---|---|
| `/health` | urllib + browser UA | **200** (0.37s) |
| `/v1/models` | urllib + browser UA | **200**, `deepseek-v4-pro`, `max_model_len=393216` |
| `/health` | httpx | **200** (0.30s) |
| `/v1/models` | httpx | **200** |
| `/v1/chat/completions` | openai SDK | **OK** (0.97s), `content='ok'`, 13 total tokens |
| control: `zzzznotarealpod99-8000` | urllib + browser UA / httpx | **404** |

The control now returns 404, which is the genuine "no such pod" signal and is
cleanly distinguishable from a served response. The method is sound and the
conclusion is positive: the pod is up, the credential in `.env` is valid, and
an end-to-end chat completion succeeds.

Command: `uv run --package whisker --extra tapetum-llm python probe2.py`
(probe script retained outside the repo, output reproduced above verbatim).

**Consequence:** the runtime phases are unblocked. L10 through L14, L16, L25
and the live half of L26/L32 are executable against a real model. Auditv2's
central cap does not apply to v3.

### 2.3 Finding carried into the audit

The tapetum lane reaches the pod through the `openai` SDK (httpx), which sends
its own user-agent and passes Cloudflare. Any auxiliary reachability check
written with `urllib` or with a stripped user-agent would report a live pod as
down. Whether such a check exists in whisker is examined under L32
(Advisory Fail-Closed) and L26 (Exit-Code Contracts): a false "endpoint
unreachable" would degrade the lane for an infrastructure reason that is not
real. This audit's own round-1 error is the existence proof that the failure
mode is easy to hit.

## 3. Incidental observation carried into L30

The pod probe surfaced something the secrets check must examine: `SERVICES.toml`
is a tracked file and its header states "API keys are NEVER stored here", yet
six services carry literal `api_key = "sk-..."` values in the committed file.
Only `alliance-pod` and `anthropic-opus` use the `$ENV_VAR` indirection the
header describes.

Recorded here because it was observed during preconditions. It is adjudicated
in L30 (Secrets and Debug Redaction), not here.

## 4. Environment

| Item | Value |
|---|---|
| OS | Windows 10.0.26200, PowerShell |
| `WG21_DATA_DIR` | recorded in `shared-evidence-ledger.md` |
| Python / uv | recorded in `raw/w3-deps-packaging.md` |
| `ALLIANCE_POD_KEY` | present via `.env` + `load_dotenv()`, not exported in the ambient shell |

## 5. Gate on proceeding

| Precondition | Status |
|---|---|
| Target pinned | PASS (content manifest `b9ad8ab0...8f771`, 157 files) |
| Working tree clean | **FAIL** (7205 uncommitted insertions; mitigated by the manifest, not resolved) |
| Live LLM lane reachable | PASS (chat completion succeeded, 0.97s) |
| Credential present | PASS (`.env` via `load_dotenv`) |

One precondition remains red. The tree is not clean, so a reader cannot
reproduce these findings from a fresh clone; they can only verify they hold
the same bytes via the manifest. That limitation carries into the synthesis
and must cap any claim of external reproducibility. It does **not** cap the
runtime dimensions, which are now provable.

The audit proceeds with all phases executable.
