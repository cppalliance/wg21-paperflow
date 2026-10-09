# 05b - Web Forager: vLLM Batch REST API vs Offline CLI

**Question:** Does vLLM 0.24 expose provider-style `/v1/batches` and `/v1/files` over HTTP, or is batching offline-only (`vllm run-batch`)? Do proxies emulate this?

**Search seeds:** `vllm openai compatible batch API /v1/batches run-batch online endpoint 2026`, refined against vLLM stable/v0.24 docs, GitHub issues #8567/#8631, LiteLLM docs and #18188/#17996, vLLM production-stack PR #109.

**Verdict (one line):** Stock vLLM 0.24 has **no** OpenAI Batch/Files REST API; `run-batch` is an offline CLI that boots its own engine; the only native online batch primitive is the synchronous `/v1/chat/completions/batch` endpoint (not async job semantics).

---

## Finding Cards

### 1. vLLM official docs: OpenAI batch *file format*, not Batch REST API

**URL:** https://docs.vllm.ai/en/stable/examples/features/openai_batch/

**Summary:** The stable docs open with an explicit disclaimer: this guide covers batch inference using the OpenAI batch **JSONL file format**, "**not** the complete Batch (REST) API." Batch work is invoked from the **command line** via `python -m vllm.entrypoints.openai.run_batch` or `vllm run-batch -i … -o … --model …`, which reads/writes local or remote HTTP(S) files but does not expose `/v1/batches` or `/v1/files` on the running server. Supported line-item endpoints inside the JSONL are `/v1/chat/completions`, `/v1/embeddings`, and `/v1/score`.

**Relevance:** **HIGH** — primary upstream source; directly answers the baseline question that provider-style async batch is not part of the online server contract.

---

### 2. GitHub #8567 / maintainer reply: `/v1/batches` returns 404 on online server

**URL:** https://github.com/vllm-project/vllm/issues/8567

**Summary:** A user pointed the OpenAI Python SDK at a running `vllm serve` container and got `404 Not Found` on both `client.files.create` and `client.batches.create`. vLLM maintainer @DarkLight1337 confirmed: batch via the OpenAI client against the **online** server is wrong; use `vllm/entrypoints/openai/run_batch.py` for **offline** inference instead. The reporter noted `run_batch` starts a **new model instance** and does not reuse the existing `api_server`, and the maintainer replied that is why it is called offline inference — "Feel free to open an issue to request for online support."

**Relevance:** **HIGH** — empirical 404 behavior matches our API-only pod access pattern; clarifies that `run-batch` is host-side, not an HTTP surface on the live server.

---

### 3. GitHub #8631: online OpenAI Batch API feature request closed `not_planned`

**URL:** https://github.com/vllm-project/vllm/issues/8631

**Summary:** Follow-up feature request (Sep 2024) for full OpenAI SDK batch workflow (`files.create` + `batches.create`) against a local vLLM HTTP server. Core maintainer @wuisawesome explained the original batch file work avoided a **stateful** job-management endpoint because of foot-gun risk. Discussion pointed to vLLM **production-stack** issue #47 / router PR #109 as a sibling effort, and to third-party `parasail-ai/openai-batch`. Issue auto-closed as **`not_planned`** (Jul 2025) with no merged in-core `/v1/batches` implementation.

**Relevance:** **HIGH** — best evidence that as of mid-2025 there is no upstream plan to add provider-style batch endpoints to core vLLM; any solution lives in external gateways.

---

### 4. vLLM 0.24 docs: `/v1/chat/completions/batch` (online, synchronous, not provider batch)

**URL:** https://docs.vllm.ai/en/v0.24.0/examples/generate/batched_chat_completions_online/

**Summary:** vLLM 0.24 documents a **different** online endpoint: `POST /v1/chat/completions/batch`, where `messages` is a **list of conversations** and the response returns one choice per conversation in a **single synchronous HTTP round-trip**. Limitations vs `/v1/chat/completions`: no streaming, no tool use, no beam search. This is real server-side multi-request batching over HTTP, but it is **not** the OpenAI/Anthropic async batch job model (no file upload, no job ID, no poll-for-completion, no 24h completion window).

**Relevance:** **MED** — usable only if the pod exposes this route and our client can adopt its payload shape; does **not** satisfy "provider-style batch processing" as defined in `00-baseline.md`, and may conflict with tapetum's streaming/thinking path.

---

### 5. LiteLLM #18188 / #17996: proxy `/v1/batches` docs do not work against standard vLLM upstream

**URL:** https://github.com/BerriAI/litellm/issues/18188 (duplicate of #17996)

**Summary:** After LiteLLM PR #15823 added "vLLM batch+files" routing, users hit `404` because LiteLLM **forwards** `POST /v1/files` to the upstream vLLM server, which does not implement that route. Reporter and maintainers agree: standard vLLM online serving lacks `/v1/files` and `/v1/batches`; making LiteLLM work would require the **proxy** to store files locally, parse JSONL, fan out concurrent `/v1/chat/completions` calls, and assemble output — i.e. orchestration at the gateway, not passthrough. LiteLLM's public vLLM batch doc page still lists `/v1/files` and `/v1/batches` as supported, but that assumes a working proxy layer, not a bare RunPod vLLM endpoint.

**Relevance:** **HIGH** — directly falsifies "point LiteLLM at our pod and use OpenAI batch SDK" without deploying a separate LiteLLM+Postgres managed-batch stack in front.

---

### 6. vLLM production-stack router PR #109: batch API as optional gateway add-on

**URL:** https://github.com/vllm-project/production-stack/pull/109

**Summary:** The vLLM **production-stack** (not core `vllm serve`) adds a `BatchProcessor` / `LocalBatchProcessor` with SQLite-backed state and OpenAI-shaped batch routes behind an `enable-batch-api` flag on the **router**. At merge time, core routing logic to backend inference was still incomplete; follow-on PRs were expected. This is an adjacent Kubernetes/router project, not something present on a default RunPod `vllm serve` 0.24 deployment.

**Relevance:** **MED** — shows where OpenAI-compatible `/v1/batches` *could* live (gateway in front of vLLM), reinforcing that it is not in core vLLM HTTP server as shipped.

---

## Cross-cut for `00-baseline.md`

| Surface | On stock vLLM 0.24 HTTP server? | API-only client usable? |
| --- | --- | --- |
| `POST /v1/batches`, `/v1/files` | **No** (404; docs say not REST batch API) | **No** |
| `vllm run-batch` / `run_batch.py` | Offline CLI; separate engine process | **No** (requires shell on pod host) |
| `POST /v1/chat/completions/batch` | **Maybe** (documented in 0.24; pod exposure unverified) | **Partial** — sync multi-convo, not async jobs |
| LiteLLM `/v1/batches` over `hosted_vllm` | Emulated at proxy only; upstream passthrough **broken** (#18188) | **No** unless CTO deploys LiteLLM managed-batch infra |
| Third-party gateways (production-stack router, efficient-vllm-batch-server, llm-d) | Separate deployment | **No** on current RunPod URL unless infra added |

**Practical levers unchanged for whisker:** raise client concurrency on `/v1/chat/completions`, optional probe of `/v1/chat/completions/batch`, dual-pod sharding — not OpenAI Batch SDK against the existing pod URL alone.
