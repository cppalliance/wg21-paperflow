# Experiment 1: readback negative control (audit check L16)

Date: 2026-08-03. Operator: Auditv3 runtime agent.

## Corpus

- Directory: `packages/whisker/corpus/` (repo-relative: `c:\Users\sabo2\Desktop\cppalliance\packages\whisker\corpus`)
- `dev-replay/`: 0 `*.facts.jsonl` files (contains `labels.json` only)
- `holdout/`: 0 `*.facts.jsonl` files (contains anchor JSONL + manifest)
- Root corpus: **6** `*.facts.jsonl` files: `EXAMPLE.facts.jsonl`, `N5040` (`n5040.facts.jsonl`), `P0876R23` (`p0876r23.facts.jsonl`), `P4182R0`, `P4185R0`, `P4234R0`
- Papers executed: 5 (`EXAMPLE` skipped: no converted markdown in workspace)

## Workspace / write targets

Markdown was read from `c:\Users\sabo2\Desktop\cppalliance\data` (read-only for paperstore). Artifacts written only to temp:

- `C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\readback-out\clean`
- `C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\readback-out\corrupt`

Data-dir `whisker/` file count before and after: **772** (unchanged). No repo source files modified.

## Commands

### Clean pass

```powershell
$env:PYTHONIOENCODING="utf-8"
uv run --package whisker -- whisker-readback 
  --corpus packages\whisker\corpus 
  --workspace c:\Users\sabo2\Desktop\cppalliance\data 
  --out C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\readback-out\clean 
  -v
```

**Exit code:** 0

### Corrupt pass

```powershell
$env:PYTHONIOENCODING="utf-8"
uv run --package whisker -- whisker-readback 
  --corpus packages\whisker\corpus 
  --workspace c:\Users\sabo2\Desktop\cppalliance\data 
  --out C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\readback-out\corrupt 
  --corrupt -v
```

**Exit code:** 0

## Comparison table

Paper-level **pass** = all verified facts pass (`fail_count=0`, `error_count=0`).

| PID | Clean score | Clean paper pass? | Corrupt score | Corrupt paper pass? | Δ pass |
|-----|-------------|-------------------|---------------|---------------------|--------|
| N5040 | 6/6 | yes | 4/6 | no | −2 |
| P0876R23 | 6/8 | no | 6/8 | no | 0 |
| P4182R0 | 8/8 | yes | 8/8 | yes | 0 |
| P4185R0 | 8/9 | no | 8/9 | no | 0 |
| P4234R0 | 6/6 | yes | 6/6 | yes | 0 |

**Fact-level pass rate:** clean **34/37** (91.9%); corrupt **32/37** (86.5%).

**Paper-level pass rate:** clean **3/5** (60%); corrupt **2/5** (40%).

**Papers still passing all facts under `--corrupt`:** P4182R0 (8/8), P4234R0 (6/6) — **2 papers**.

Corrupt-only new failures vs clean: N5040 `table-pipe-wd`, `table-pipe-kona`; P4185R0 `table-text-output-point-no` (clean had `table-anchored-true-zero` fail in both modes).

## Pass/fail and corruption logic (`readback.py`)

Corruption prefix + transform:

```python
_CORRUPT_PREFIX = (
    "--- CORRUPTION BLOCK: all tables, formulas, and references below have "
    "been scrambled for adversarial testing. Do not trust any data. ---\n\n"
)

def _corrupt_markdown(md: str) -> str:
    lines = md.split("\n")
    result = []
    for line in lines:
        if "|" in line and not line.strip().startswith("`"):
            cells = line.split("|")
            cells = list(reversed(cells))
            line = "|".join(cells)
        line = re.sub(r">=", "<=", line)
        line = re.sub(r"\^(\d+)", lambda m: f"^{int(m.group(1)) + 1}", line)
        result.append(line)
    return "\n".join(result)
```

When `--corrupt`: `md = _CORRUPT_PREFIX + _corrupt_markdown(md)`.

Per-fact evaluation (no aggregate score threshold; each fact is pass/fail via `_evaluate_answer`):

- `present`/`code`/`xref`/`image_ref`: answer must start with `yes` **and** `_grounded_quote` must find the fact needle in the answer (fuzzy within `max_diffs`).
- `absent`: answer must start with `no` (marked `weak`).
- `math`: `_present_within` on math surface.
- `order`: each sequence item found in order by position.
- `table`: every neighbor cell value must match on alphanumeric word boundaries via `_cell_value_in_answer`.
- Transport errors are `ERROR`, excluded from pass/fail counts.
- CLI exit code is **0** unless no papers run; it does **not** fail on comprehension failures.

## Clean pass terminal output (stdout; includes preceding DEBUG from `-v`)

```WARNING whisker.tapetum_llm.readback_cli: skipping EXAMPLE: No converted markdown for 'EXAMPLE'. Run 'paperflow convert EXAMPLE' first.
INFO whisker.tapetum_llm.readback_cli: readback N5040: 6 verified facts
DEBUG httpcore.connection: connect_tcp.started host='sgjy18glyi4blu-8000.proxy.runpod.net' port=443 local_address=None timeout=120.0 socket_options=None
DEBUG httpcore.connection: connect_tcp.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001CD243CD7F0>
DEBUG httpcore.connection: start_tls.started ssl_context=<ssl.SSLContext object at 0x000001CD24DB93D0> server_hostname='sgjy18glyi4blu-8000.proxy.runpod.net' timeout=120.0
DEBUG httpcore.connection: start_tls.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001CD2480F620>
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:20 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258246b7c0478c0-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:21 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258247f080f78c0-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:21 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25824830df778c0-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:22 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25824869a7f78c0-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:23 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258248ddb2a78c0-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:25 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25824951d2d78c0-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.connection: close.started
DEBUG httpcore.connection: close.complete
INFO whisker.tapetum_llm.readback_cli: wrote C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\readback-out\clean\n5040.readback.md
INFO whisker.tapetum_llm.readback_cli: readback P0876R23: 8 verified facts
DEBUG httpcore.connection: connect_tcp.started host='sgjy18glyi4blu-8000.proxy.runpod.net' port=443 local_address=None timeout=120.0 socket_options=None
DEBUG httpcore.connection: connect_tcp.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001CD24DF70E0>
DEBUG httpcore.connection: start_tls.started ssl_context=<ssl.SSLContext object at 0x000001CD24C48250> server_hostname='sgjy18glyi4blu-8000.proxy.runpod.net' timeout=120.0
DEBUG httpcore.connection: start_tls.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001CD24DF6FF0>
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:29 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258249c8ba1d9cf-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:29 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25824b46c50d9cf-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:31 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25824b8acd6d9cf-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:32 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25824c57bbfd9cf-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:33 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25824c9dc0fd9cf-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:33 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25824ceacfed9cf-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:36 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25824d36f9ad9cf-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:36 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25824e08c4bd9cf-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.connection: close.started
DEBUG httpcore.connection: close.complete
INFO whisker.tapetum_llm.readback_cli: wrote C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\readback-out\clean\p0876r23.readback.md
INFO whisker.tapetum_llm.readback_cli: readback P4182R0: 8 verified facts
DEBUG httpcore.connection: connect_tcp.started host='sgjy18glyi4blu-8000.proxy.runpod.net' port=443 local_address=None timeout=120.0 socket_options=None
DEBUG httpcore.connection: connect_tcp.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001CD24DC3530>
DEBUG httpcore.connection: start_tls.started ssl_context=<ssl.SSLContext object at 0x000001CD24DBABD0> server_hostname='sgjy18glyi4blu-8000.proxy.runpod.net' timeout=120.0
DEBUG httpcore.connection: start_tls.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001CD24DC30E0>
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:38 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25824e56cfc590f-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:38 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25824ed6f71590f-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:41 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25824f1dc75590f-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:41 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25825000bd8590f-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:42 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25825050b42590f-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:43 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258250719da590f-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:44 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25825102d55590f-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:45 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a2582516995a590f-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.connection: close.started
DEBUG httpcore.connection: close.complete
============================================================
READBACK: N5040 (NORMAL, model=deepseek-v4-pro)
============================================================
  [+] PASS order-headings (order)
      Q: In the document, which of these items appears first: '1. Opening and introductions', '1.1. Opening comments, welcome fro
      Expected: 1. Opening and introductions -> 1.1. Opening comments, welcome from host -> 1.2.
      Answer:   1. Opening and introductions 1.1. Opening comments, welcome from host 1.2. Meeting guidelines
      Latency:  3235ms

  [+] PASS present-opening (present)
      Q: Does the document contain the following text or concept: 'Nina Ranns opens the meeting at 9:02'? Answer YES or NO, then 
      Expected: YES
      Answer:   YES  "Nina Ranns opens the meeting at 9:02 UTC+0."
      Latency:  639ms

  [+] PASS present-host-welcome (present)
      Q: Does the document contain the following text or concept: 'Guy Davidson welcomes the group'? Answer YES or NO, then quote
      Expected: YES
      Answer:   YES  "Guy Davidson welcomes the group. Welcome from the host."
      Latency:  563ms

  [+] PASS table-pipe-wd (table)
      Q: In the table containing cell 'C++26 Working Draft', identify: the cell immediately right of 'C++26 Working Draft'; the c
      Expected: cell=C++26 Working Draft, right: [N5033](https://www.open-std.org/jtc1/sc22/wg21
      Answer:   The cell immediately right of 'C++26 Working Draft' is: [N5033](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2025
      Latency:  1155ms

  [+] PASS table-pipe-kona (table)
      Q: In the table containing cell 'WG21 Kona', identify: the cell immediately right of 'WG21 Kona'; the column heading of the
      Expected: cell=WG21 Kona, right: [N5031](https://www.open-std.org/jtc1/sc22/wg21/docs/pape
      Answer:   The cell immediately right of 'WG21 Kona' is: [N5031](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2025/n5031.pdf
      Latency:  1155ms

  [+] PASS table-html-nb1 (table)
      Q: In the table containing cell '1', identify: the cell immediately right of '1'; the column heading of the column containi
      Expected: cell=1, right: US 70-126 17.12.7 [compare.type] Allow incomplete types in type_o
      Answer:   The cell immediately right of '1' is: `US 70-126 17.12.7 [compare.type] Allow incomplete types in type_order`  The colum
      Latency:  1016ms

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
  Total: 6 | Pass: 6 | Fail: 0 | Error: 0
============================================================
============================================================
READBACK: P0876R23 (NORMAL, model=deepseek-v4-pro)
============================================================
  [+] PASS order-toc (order)
      Q: In the document, which of these items appears first: 'abstract', 'Recent WG21 History', 'Revision History'? List them in
      Expected: abstract -> Recent WG21 History -> Revision History
      Answer:   abstract, Recent WG21 History, Revision History
      Latency:  3859ms

  [+] PASS present-subtitle (present)
      Q: Does the document contain the following text or concept: 'fibers without scheduler'? Answer YES or NO, then quote the re
      Expected: YES
      Answer:   YES  The document's title is "fiber_context - fibers without scheduler".
      Latency:  672ms

  [+] PASS present-exception-state (present)
      Q: Does the document contain the following text or concept: 'per-fiber exception state'? Answer YES or NO, then quote the r
      Expected: YES
      Answer:   YES  The document contains the concept of "per-fiber exception state". Relevant passages include:  *   "CWG finished ini
      Latency:  2061ms

  [+] PASS absent-audience-label (absent) (weak: no groundable quote)
      Q: Does the document contain the following text or concept: 'Audience:'? Answer YES or NO.
      Expected: NO
      Answer:   NO
      Latency:  688ms

  [X] FAIL table-poll-stlouis (table)
      Q: In the table containing cell '6', identify: the cell immediately right of '6'; the column heading of the column containi
      Expected: cell=6, right: 8, heading: SF
      Answer:   The cell immediately right of '6' is '8'.   The column heading of the column containing '6' is 'F'.
      Latency:  780ms

  [+] PASS table-poll-sofia (table)
      Q: In the table containing cell '10', identify: the cell immediately right of '10'; the column heading of the column contai
      Expected: cell=10, right: 14, heading: SF
      Answer:   The cell immediately right of '10' is '14'.   The column heading of the column containing '10' is 'SF'.
      Latency:  766ms

  [+] PASS code-fiber-example (code)
      Q: Does the document contain a code snippet including: '1  fiber_context* pf1; 2  fiber_context f4{[&pf1]{ 3      pf1->resu
      Expected: YES
      Answer:   YES  ```cpp  1  fiber_context* pf1;  2  fiber_context f4{[&pf1]{  3      pf1->resume();  4  }};  5  fiber_context f3{[&f
      Latency:  2093ms

  [X] FAIL xref-p3472 (xref)
      Q: Does the document reference the paper/section: '[P3472R1]'? Answer YES or NO, then quote the reference exactly as it app
      Expected: YES
      Answer:   YES  "P3472R1"
      Latency:  562ms

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
  Total: 8 | Pass: 6 | Fail: 2 | Error: 0
============================================================
============================================================
READBACK: P4182R0 (NORMAL, model=deepseek-v4-pro)
============================================================
  [+] PASS title-survives (present)
      Q: Does the document contain the following text or concept: 'A Citable Inventory of Platforms, Operating Systems, and Compi
      Expected: YES
      Answer:   YES  The document's title is: "A Citable Inventory of Platforms, Operating Systems, and Compiler Toolchains".
      Latency:  1327ms

  [+] PASS edg-frontend (present)
      Q: Does the document contain the following text or concept: 'Edison Design Group supplies a commercial C++'? Answer YES or 
      Expected: YES
      Answer:   YES  "Edison Design Group supplies a commercial C++ **front end** (parser and semantic analysis) that compiler vendors e
      Latency:  735ms

  [+] PASS pmr-term (present)
      Q: Does the document contain the following text or concept: 'polymorphic memory resources'? Answer YES or NO, then quote th
      Expected: YES
      Answer:   YES  The document contains the concept of "polymorphic memory resources" in multiple places. One relevant passage is:  "
      Latency:  2264ms

  [+] PASS pigweed-coro (present)
      Q: Does the document contain the following text or concept: 'Pigweed provides C++20 coroutines'? Answer YES or NO, then quo
      Expected: YES
      Answer:   YES  "Pigweed provides C++20 coroutines with an allocator passed per coroutine (`CoroContext`) because PMR is not availa
      Latency:  797ms

  [+] PASS docnumber-label-consumed (absent) (weak: no groundable quote)
      Q: Does the document contain the following text or concept: 'Document Number'? Answer YES or NO.
      Expected: NO
      Answer:   NO
      Latency:  327ms

  [+] PASS section-flow (order)
      Q: In the document, which of these items appears first: 'Every mailing repeats the same deployment background', 'consolidat
      Expected: Every mailing repeats the same deployment background -> consolidates a single, c
      Answer:   1. "Every mailing repeats the same deployment background" (in the Abstract) 2. "consolidates a single, citeable inventor
      Latency:  1453ms

  [+] PASS tableA-gpu-coro-no (table)
      Q: In the table containing cell 'GPU device code (CUDA, SYCL)', identify: the cell immediately right of 'GPU device code (C
      Expected: cell=GPU device code (CUDA, SYCL), right: No, heading: Category
      Answer:   The cell immediately right of "GPU device code (CUDA, SYCL)" is **No**.   The column heading of the column containing "G
      Latency:  1031ms

  [+] PASS tableB-console-alloc (table)
      Q: In the table containing cell 'Arenas common', identify: the cell immediately left of 'Arenas common'; the column heading
      Expected: cell=Arenas common, left: Often off, heading: Alloc
      Answer:   The cell immediately left of "Arenas common" is "Often off".   The column heading of the column containing "Arenas commo
      Latency:  750ms

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
  Total: 8 | Pass: 8 | Fail: 0 | Error: 0
INFO whisker.tapetum_llm.readback_cli: wrote C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\readback-out\clean\p4182r0.readback.md
INFO whisker.tapetum_llm.readback_cli: readback P4185R0: 9 verified facts
DEBUG httpcore.connection: connect_tcp.started host='sgjy18glyi4blu-8000.proxy.runpod.net' port=443 local_address=None timeout=120.0 socket_options=None
DEBUG httpcore.connection: connect_tcp.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001CD24E1DDC0>
DEBUG httpcore.connection: start_tls.started ssl_context=<ssl.SSLContext object at 0x000001CD24DBB0D0> server_hostname='sgjy18glyi4blu-8000.proxy.runpod.net' timeout=120.0
DEBUG httpcore.connection: start_tls.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001CD24E1DCA0>
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:50 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258251c887fd2db-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:52 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258253badbdd2db-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:53 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25825485b7cd2db-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:54 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258254f6e01d2db-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:55 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25825545815d2db-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:56 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258255a6e15d2db-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:58 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25825609cb6d2db-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:41:59 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258256efaf4d2db-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:00 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a2582572ea11d2db-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.connection: close.started
DEBUG httpcore.connection: close.complete
INFO whisker.tapetum_llm.readback_cli: wrote C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\readback-out\clean\p4185r0.readback.md
INFO whisker.tapetum_llm.readback_cli: readback P4234R0: 6 verified facts
DEBUG httpcore.connection: connect_tcp.started host='sgjy18glyi4blu-8000.proxy.runpod.net' port=443 local_address=None timeout=120.0 socket_options=None
DEBUG httpcore.connection: connect_tcp.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001CD26180E00>
DEBUG httpcore.connection: start_tls.started ssl_context=<ssl.SSLContext object at 0x000001CD24DBA650> server_hostname='sgjy18glyi4blu-8000.proxy.runpod.net' timeout=120.0
DEBUG httpcore.connection: start_tls.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001CD24E5C650>
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:01 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a2582579e989d298-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:02 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25825800928d298-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:02 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25825833929d298-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:05 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25825886d95d298-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:05 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25825974aecd298-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:06 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258259b3cadd298-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.connection: close.started
DEBUG httpcore.connection: close.complete
INFO whisker.tapetum_llm.readback_cli: wrote C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\readback-out\clean\p4234r0.readback.md
============================================================
============================================================
READBACK: P4185R0 (NORMAL, model=deepseek-v4-pro)
============================================================
  [+] PASS math-even-power-nonneg (math)
      Q: What mathematical expression appears in the document that involves the symbols/variables in: '\\(x^{2k} \\geq 0\\)'? Quo
      Expected: \(x^{2k} \geq 0\)
      Answer:   The exact formula is:  \(x^{2k} \geq 0\)
      Latency:  5031ms

  [+] PASS math-gravitational-pe (math)
      Q: What mathematical expression appears in the document that involves the symbols/variables in: '\\(U = -G \\cdot m_1 \\cdo
      Expected: \(U = -G \cdot m_1 \cdot m_2 / r\)
      Answer:   The exact formula is:  \\(U = -G \cdot m_1 \cdot m_2 / r\\)
      Latency:  2015ms

  [+] PASS math-reactive-power (math)
      Q: What mathematical expression appears in the document that involves the symbols/variables in: '\\(Q = U_\\text{rms} \\cdo
      Expected: \(Q = U_\text{rms} \cdot I_\text{rms} \cdot \sin\varphi\)
      Answer:   The exact formula is:  \\(Q = U_\\text{rms} \\cdot I_\\text{rms} \\cdot \\sin\\varphi\\)
      Latency:  1125ms

  [+] PASS math-helmholtz (math)
      Q: What mathematical expression appears in the document that involves the symbols/variables in: '\\(A = U - T{\\cdot}S\\)'?
      Expected: \(A = U - T{\cdot}S\)
      Answer:   The exact formula is:  \\(A = U - T{\cdot}S\\)
      Latency:  781ms

  [X] FAIL table-anchored-true-zero (table)
      Q: In the table containing cell 'Anchored at true zero', identify: the cell immediately left of 'Anchored at true zero'; th
      Expected: cell=Anchored at true zero, left: Point origin (explicit or implicit), right: N/
      Answer:   Left: "N/A" Right: "Ô£ô" Column heading: "Delta"
      Latency:  968ms

  [+] PASS table-text-output-point-no (table)
      Q: In the table containing cell 'Text output', identify: the cell immediately right of 'Text output'; the column heading of
      Expected: cell=Text output, right: Ô£ù, heading: Feature
      Answer:   The cell immediately right of "Text output" is "Ô£ù".   The column heading of the column containing "Text output" is "Feat
      Latency:  984ms

  [+] PASS present-temperature-trap (present)
      Q: Does the document contain the following text or concept: 'temperature trap'? Answer YES or NO, then quote the relevant p
      Expected: YES
      Answer:   YES  The document contains the concept of the "temperature trap" in section 3.1:  > "By far the most frequently reported
      Latency:  2297ms

  [+] PASS absent-audience-label (absent) (weak: no groundable quote)
      Q: Does the document contain the following text or concept: 'Audience:'? Answer YES or NO.
      Expected: NO
      Answer:   NO
      Latency:  639ms

  [+] PASS section-flow (order)
      Q: In the document, which of these items appears first: '1 Abstract', '3 Motivation and scope', '4 Non-negative quantities'
      Expected: 1 Abstract -> 3 Motivation and scope -> 4 Non-negative quantities -> 5 Absolute 
      Answer:   1 Abstract, 3 Motivation and scope, 4 Non-negative quantities, 5 Absolute quantities, 14 Acknowledgments
      Latency:  938ms

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
  Total: 9 | Pass: 8 | Fail: 1 | Error: 0
============================================================
============================================================
READBACK: P4234R0 (NORMAL, model=deepseek-v4-pro)
============================================================
  [+] PASS order-sections (order)
      Q: In the document, which of these items appears first: '1. Introduction', '2. Proposed change', '3. Additional Motivation'
      Expected: 1. Introduction -> 2. Proposed change -> 3. Additional Motivation -> 4. Wording 
      Answer:   1. Introduction 2. Proposed change 3. Additional Motivation 4. Wording 5. Acknowledgements
      Latency:  1015ms

  [+] PASS abstract-claim (present)
      Q: Does the document contain the following text or concept: 'conditionally-supported'? Answer YES or NO, then quote the rel
      Expected: YES
      Answer:   YES  > This paper proposes making the use of `$` in identifiers conditionally-supported.
      Latency:  516ms

  [+] PASS dollar-dollar-survives (present)
      Q: Does the document contain the following text or concept: 'extern int Image$$ER_ZI$$Base;'? Answer YES or NO, then quote 
      Expected: YES
      Answer:   YES  > ```cpp > // oops, none of these are valid identifiers > extern int Image$$ER_ZI$$Base; > ```
      Latency:  827ms

  [+] PASS code-oops-comment (code)
      Q: Does the document contain a code snippet including: '// oops, none of these are valid identifiers'? Answer YES or NO, th
      Expected: YES
      Answer:   YES  ```cpp // oops, none of these are valid identifiers extern int Image$$ER_ZI$$Base; extern int Image$$ER_ZI$$Limit; 
      Latency:  2375ms

  [+] PASS code-asm-alias (code)
      Q: Does the document contain a code snippet including: 'extern int Image_ER_ZI_Base asm("Image$$ER_ZI$$Base");'? Answer YES
      Expected: YES
      Answer:   YES  ```cpp extern int Image_ER_ZI_Base asm("Image$$ER_ZI$$Base"); ```
      Latency:  640ms

  [+] PASS xref-lexname (xref)
      Q: Does the document reference the paper/section: '[lex.name]'? Answer YES or NO, then quote the reference exactly as it ap
      Expected: YES
      Answer:   YES  > ### [lex.name] Identifiers
      Latency:  406ms

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
  Total: 6 | Pass: 6 | Fail: 0 | Error: 0
============================================================

============================================================
READBACK SUMMARY: 5 paper(s), 34 pass, 3 fail, 0 error
============================================================
```

## Corrupt pass terminal output

```WARNING whisker.tapetum_llm.readback_cli: skipping EXAMPLE: No converted markdown for 'EXAMPLE'. Run 'paperflow convert EXAMPLE' first.
INFO whisker.tapetum_llm.readback_cli: readback N5040: 6 verified facts
DEBUG httpcore.connection: connect_tcp.started host='sgjy18glyi4blu-8000.proxy.runpod.net' port=443 local_address=None timeout=120.0 socket_options=None
DEBUG httpcore.connection: connect_tcp.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001C3EAC0FFE0>
DEBUG httpcore.connection: start_tls.started ssl_context=<ssl.SSLContext object at 0x000001C3EACD94D0> server_hostname='sgjy18glyi4blu-8000.proxy.runpod.net' timeout=120.0
DEBUG httpcore.connection: start_tls.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001C3E7005280>
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:31 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25826265acfdb02-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:32 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258263aed55db02-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:32 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258263eeb93db02-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:33 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25826421f2edb02-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:35 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a2582649a870db02-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:36 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a2582652aeaadb02-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.connection: close.started
DEBUG httpcore.connection: close.complete
INFO whisker.tapetum_llm.readback_cli: wrote C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\readback-out\corrupt\n5040.readback-corrupt.md
INFO whisker.tapetum_llm.readback_cli: readback P0876R23: 8 verified facts
DEBUG httpcore.connection: connect_tcp.started host='sgjy18glyi4blu-8000.proxy.runpod.net' port=443 local_address=None timeout=120.0 socket_options=None
DEBUG httpcore.connection: connect_tcp.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001C3EAD15DC0>
DEBUG httpcore.connection: start_tls.started ssl_context=<ssl.SSLContext object at 0x000001C3EAB6DC50> server_hostname='sgjy18glyi4blu-8000.proxy.runpod.net' timeout=120.0
DEBUG httpcore.connection: start_tls.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001C3EAD15C70>
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:40 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258265a1a8f7e59-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:40 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25826724d827e59-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:41 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25826765b8b7e59-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:42 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258267c1f6c7e59-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:43 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258267ee9477e59-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:43 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a2582683a8e97e59-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:45 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258268869637e59-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:46 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25826959d557e59-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.connection: close.started
DEBUG httpcore.connection: close.complete
INFO whisker.tapetum_llm.readback_cli: wrote C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\readback-out\corrupt\p0876r23.readback-corrupt.md
INFO whisker.tapetum_llm.readback_cli: readback P4182R0: 8 verified facts
DEBUG httpcore.connection: connect_tcp.started host='sgjy18glyi4blu-8000.proxy.runpod.net' port=443 local_address=None timeout=120.0 socket_options=None
DEBUG httpcore.connection: connect_tcp.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001C3EAD16240>
DEBUG httpcore.connection: start_tls.started ssl_context=<ssl.SSLContext object at 0x000001C3EACDBC50> server_hostname='sgjy18glyi4blu-8000.proxy.runpod.net' timeout=120.0
DEBUG httpcore.connection: start_tls.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001C3EAD15F10>
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:48 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258269c8b6de282-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:49 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25826a4c960e282-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:50 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25826a929f4e282-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:51 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25826b15848e282-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:51 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25826b639a3e282-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:52 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25826b80860e282-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:53 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25826c01c93e282-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:42:54 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25826c5c815e282-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.connection: close.started
DEBUG httpcore.connection: close.complete
============================================================
READBACK: N5040 (CORRUPT, model=deepseek-v4-pro)
============================================================
  [+] PASS order-headings (order)
      Q: In the document, which of these items appears first: '1. Opening and introductions', '1.1. Opening comments, welcome fro
      Expected: 1. Opening and introductions -> 1.1. Opening comments, welcome from host -> 1.2.
      Answer:   1. Opening and introductions 1.1. Opening comments, welcome from host 1.2. Meeting guidelines
      Latency:  3358ms

  [+] PASS present-opening (present)
      Q: Does the document contain the following text or concept: 'Nina Ranns opens the meeting at 9:02'? Answer YES or NO, then 
      Expected: YES
      Answer:   YES  "Nina Ranns opens the meeting at 9:02 UTC+0."
      Latency:  641ms

  [+] PASS present-host-welcome (present)
      Q: Does the document contain the following text or concept: 'Guy Davidson welcomes the group'? Answer YES or NO, then quote
      Expected: YES
      Answer:   YES  "Guy Davidson welcomes the group."
      Latency:  500ms

  [X] FAIL table-pipe-wd (table)
      Q: In the table containing cell 'C++26 Working Draft', identify: the cell immediately right of 'C++26 Working Draft'; the c
      Expected: cell=C++26 Working Draft, right: [N5033](https://www.open-std.org/jtc1/sc22/wg21
      Answer:   The cell immediately right of 'C++26 Working Draft' is:   [N5033](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/20
      Latency:  1219ms

  [X] FAIL table-pipe-kona (table)
      Q: In the table containing cell 'WG21 Kona', identify: the cell immediately right of 'WG21 Kona'; the column heading of the
      Expected: cell=WG21 Kona, right: [N5031](https://www.open-std.org/jtc1/sc22/wg21/docs/pape
      Answer:   The cell immediately right of 'WG21 Kona' is `[N5031](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2025/n5031.pdf
      Latency:  1436ms

  [+] PASS table-html-nb1 (table)
      Q: In the table containing cell '1', identify: the cell immediately right of '1'; the column heading of the column containi
      Expected: cell=1, right: US 70-126 17.12.7 [compare.type] Allow incomplete types in type_o
      Answer:   The cell immediately right of '1' is: `US 70-126 17.12.7 [compare.type] Allow incomplete types in type_order`  The colum
      Latency:  1016ms

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
  Total: 6 | Pass: 4 | Fail: 2 | Error: 0
============================================================
============================================================
READBACK: P0876R23 (CORRUPT, model=deepseek-v4-pro)
============================================================
  [+] PASS order-toc (order)
      Q: In the document, which of these items appears first: 'abstract', 'Recent WG21 History', 'Revision History'? List them in
      Expected: abstract -> Recent WG21 History -> Revision History
      Answer:   abstract, Recent WG21 History, Revision History
      Latency:  3906ms

  [+] PASS present-subtitle (present)
      Q: Does the document contain the following text or concept: 'fibers without scheduler'? Answer YES or NO, then quote the re
      Expected: YES
      Answer:   YES  "title: "fiber_context - fibers without scheduler""
      Latency:  639ms

  [+] PASS present-exception-state (present)
      Q: Does the document contain the following text or concept: 'per-fiber exception state'? Answer YES or NO, then quote the r
      Expected: YES
      Answer:   YES  "in Tokyo in March 2024, CWG finished initial P0876 Core wording review, with one requested change: that P0876 mand
      Latency:  922ms

  [+] PASS absent-audience-label (absent) (weak: no groundable quote)
      Q: Does the document contain the following text or concept: 'Audience:'? Answer YES or NO.
      Expected: NO
      Answer:   NO
      Latency:  452ms

  [X] FAIL table-poll-stlouis (table)
      Q: In the table containing cell '6', identify: the cell immediately right of '6'; the column heading of the column containi
      Expected: cell=6, right: 8, heading: SF
      Answer:   The cell immediately right of '6' is '0'.   The column heading of the column containing '6' is 'SF'.
      Latency:  766ms

  [X] FAIL table-poll-sofia (table)
      Q: In the table containing cell '10', identify: the cell immediately right of '10'; the column heading of the column contai
      Expected: cell=10, right: 14, heading: SF
      Answer:   The cell immediately right of '10' is `14`.   The column heading of the column containing '10' is `F`.
      Latency:  750ms

  [+] PASS code-fiber-example (code)
      Q: Does the document contain a code snippet including: '1  fiber_context* pf1; 2  fiber_context f4{[&pf1]{ 3      pf1->resu
      Expected: YES
      Answer:   YES  ```cpp  1  fiber_context* pf1;  2  fiber_context f4{[&pf1]{  3      pf1->resume();  4  }};  5  fiber_context f3{[&f
      Latency:  2108ms

  [+] PASS xref-p3472 (xref)
      Q: Does the document reference the paper/section: '[P3472R1]'? Answer YES or NO, then quote the reference exactly as it app
      Expected: YES
      Answer:   YES  "[P3472R1](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2025/p3472r1.html)"
      Latency:  938ms

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
  Total: 8 | Pass: 6 | Fail: 2 | Error: 0
============================================================
============================================================
READBACK: P4182R0 (CORRUPT, model=deepseek-v4-pro)
============================================================
  [+] PASS title-survives (present)
      Q: Does the document contain the following text or concept: 'A Citable Inventory of Platforms, Operating Systems, and Compi
      Expected: YES
      Answer:   YES  The document contains this exact text in its title: "A Citable Inventory of Platforms, Operating Systems, and Compi
      Latency:  1375ms

  [+] PASS edg-frontend (present)
      Q: Does the document contain the following text or concept: 'Edison Design Group supplies a commercial C++'? Answer YES or 
      Expected: YES
      Answer:   YES  "Edison Design Group supplies a commercial C++ **front end** (parser and semantic analysis) that compiler vendors e
      Latency:  702ms

  [+] PASS pmr-term (present)
      Q: Does the document contain the following text or concept: 'polymorphic memory resources'? Answer YES or NO, then quote th
      Expected: YES
      Answer:   YES  The document contains the concept "polymorphic memory resources" in the following passage:  "For **libc++,** polymo
      Latency:  1297ms

  [+] PASS pigweed-coro (present)
      Q: Does the document contain the following text or concept: 'Pigweed provides C++20 coroutines'? Answer YES or NO, then quo
      Expected: YES
      Answer:   YES  "Pigweed provides C++20 coroutines with an allocator passed per coroutine (`CoroContext`) because PMR is not availa
      Latency:  780ms

  [+] PASS docnumber-label-consumed (absent) (weak: no groundable quote)
      Q: Does the document contain the following text or concept: 'Document Number'? Answer YES or NO.
      Expected: NO
      Answer:   NO
      Latency:  297ms

  [+] PASS section-flow (order)
      Q: In the document, which of these items appears first: 'Every mailing repeats the same deployment background', 'consolidat
      Expected: Every mailing repeats the same deployment background -> consolidates a single, c
      Answer:   1. "Every mailing repeats the same deployment background" (Abstract) 2. "consolidates a single, citeable inventory" (Abs
      Latency:  1297ms

  [+] PASS tableA-gpu-coro-no (table)
      Q: In the table containing cell 'GPU device code (CUDA, SYCL)', identify: the cell immediately right of 'GPU device code (C
      Expected: cell=GPU device code (CUDA, SYCL), right: No, heading: Category
      Answer:   The cell immediately right of "GPU device code (CUDA, SYCL)" is "No".   The column heading of the column containing "GPU
      Latency:  905ms

  [+] PASS tableB-console-alloc (table)
      Q: In the table containing cell 'Arenas common', identify: the cell immediately left of 'Arenas common'; the column heading
      Expected: cell=Arenas common, left: Often off, heading: Alloc
      Answer:   The cell immediately left of "Arenas common" is "Often off".   The column heading of the column containing "Arenas commo
      Latency:  719ms

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
  Total: 8 | Pass: 8 | Fail: 0 | Error: 0
INFO whisker.tapetum_llm.readback_cli: wrote C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\readback-out\corrupt\p4182r0.readback-corrupt.md
INFO whisker.tapetum_llm.readback_cli: readback P4185R0: 9 verified facts
DEBUG httpcore.connection: connect_tcp.started host='sgjy18glyi4blu-8000.proxy.runpod.net' port=443 local_address=None timeout=120.0 socket_options=None
DEBUG httpcore.connection: connect_tcp.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001C3EAB3EBD0>
DEBUG httpcore.connection: start_tls.started ssl_context=<ssl.SSLContext object at 0x000001C3EACDA0D0> server_hostname='sgjy18glyi4blu-8000.proxy.runpod.net' timeout=120.0
DEBUG httpcore.connection: start_tls.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001C3EAD16210>
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:43:00 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25826cb7df08ed7-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:43:01 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25826f23aab8ed7-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:43:02 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25826f7ea598ed7-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:43:03 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25826fdaa578ed7-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:43:04 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25827017f4a8ed7-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:43:04 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25827067e038ed7-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:43:06 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258270c3d4e8ed7-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:43:07 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a25827169c8c8ed7-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:43:07 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a2582719c8548ed7-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.connection: close.started
DEBUG httpcore.connection: close.complete
INFO whisker.tapetum_llm.readback_cli: wrote C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\readback-out\corrupt\p4185r0.readback-corrupt.md
INFO whisker.tapetum_llm.readback_cli: readback P4234R0: 6 verified facts
DEBUG httpcore.connection: connect_tcp.started host='sgjy18glyi4blu-8000.proxy.runpod.net' port=443 local_address=None timeout=120.0 socket_options=None
DEBUG httpcore.connection: connect_tcp.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001C3EAD8A510>
DEBUG httpcore.connection: start_tls.started ssl_context=<ssl.SSLContext object at 0x000001C3EAB6DE50> server_hostname='sgjy18glyi4blu-8000.proxy.runpod.net' timeout=120.0
DEBUG httpcore.connection: start_tls.complete return_value=<httpcore._backends.sync.SyncStream object at 0x000001C3EAD8A3F0>
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:43:08 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258271fdaccd282-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:43:09 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a2582724ece6d282-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:43:10 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a2582727cf15d282-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:43:12 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a2582730ce3fd282-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:43:12 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a2582738a92dd282-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.http11: send_request_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_headers.complete
DEBUG httpcore.http11: send_request_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: send_request_body.complete
DEBUG httpcore.http11: receive_response_headers.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 03 Aug 2026 20:43:13 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Server', b'cloudflare'), (b'Strict-Transport-Security', b'max-age=63072000; includeSubDomains'), (b'cf-cache-status', b'DYNAMIC'), (b'Content-Encoding', b'gzip'), (b'CF-RAY', b'a258273c6d94d282-FRA')])
INFO httpx: HTTP Request: POST https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions "HTTP/1.1 200 OK"
DEBUG httpcore.http11: receive_response_body.started request=<Request [b'POST']>
DEBUG httpcore.http11: receive_response_body.complete
DEBUG httpcore.http11: response_closed.started
DEBUG httpcore.http11: response_closed.complete
DEBUG httpcore.connection: close.started
DEBUG httpcore.connection: close.complete
INFO whisker.tapetum_llm.readback_cli: wrote C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\readback-out\corrupt\p4234r0.readback-corrupt.md
============================================================
============================================================
READBACK: P4185R0 (CORRUPT, model=deepseek-v4-pro)
============================================================
  [+] PASS math-even-power-nonneg (math)
      Q: What mathematical expression appears in the document that involves the symbols/variables in: '\\(x^{2k} \\geq 0\\)'? Quo
      Expected: \(x^{2k} \geq 0\)
      Answer:   The exact formula is:  \[ x^{2k} \geq 0 \]  It appears in the document under ┬º4.4.1 "Inference from named spec definitio
      Latency:  6219ms

  [+] PASS math-gravitational-pe (math)
      Q: What mathematical expression appears in the document that involves the symbols/variables in: '\\(U = -G \\cdot m_1 \\cdo
      Expected: \(U = -G \cdot m_1 \cdot m_2 / r\)
      Answer:   The exact formula is:  \(U = -G \cdot m_1 \cdot m_2 / r\)
      Latency:  906ms

  [+] PASS math-reactive-power (math)
      Q: What mathematical expression appears in the document that involves the symbols/variables in: '\\(Q = U_\\text{rms} \\cdo
      Expected: \(Q = U_\text{rms} \cdot I_\text{rms} \cdot \sin\varphi\)
      Answer:   The exact formula is:  \\(Q = U_\text{rms} \cdot I_\text{rms} \cdot \sin\varphi\\)
      Latency:  921ms

  [+] PASS math-helmholtz (math)
      Q: What mathematical expression appears in the document that involves the symbols/variables in: '\\(A = U - T{\\cdot}S\\)'?
      Expected: \(A = U - T{\cdot}S\)
      Answer:   The exact formula is:  \(A = U - T{\cdot}S\)
      Latency:  609ms

  [+] PASS table-anchored-true-zero (table)
      Q: In the table containing cell 'Anchored at true zero', identify: the cell immediately left of 'Anchored at true zero'; th
      Expected: cell=Anchored at true zero, left: Point origin (explicit or implicit), right: N/
      Answer:   Left: "N/A" Right: "Point origin (explicit or implicit)" Column heading: "Absolute"
      Latency:  797ms

  [X] FAIL table-text-output-point-no (table)
      Q: In the table containing cell 'Text output', identify: the cell immediately right of 'Text output'; the column heading of
      Expected: cell=Text output, right: Ô£ù, heading: Feature
      Answer:   The cell immediately right of "Text output" is "Ô£ô".   The column heading of the column containing "Text output" is "Feat
      Latency:  922ms

  [+] PASS present-temperature-trap (present)
      Q: Does the document contain the following text or concept: 'temperature trap'? Answer YES or NO, then quote the relevant p
      Expected: YES
      Answer:   YES  The document contains the concept of the "temperature trap" in section 3.1, which is explicitly titled "The tempera
      Latency:  1655ms

  [+] PASS absent-audience-label (absent) (weak: no groundable quote)
      Q: Does the document contain the following text or concept: 'Audience:'? Answer YES or NO.
      Expected: NO
      Answer:   NO
      Latency:  515ms

  [+] PASS section-flow (order)
      Q: In the document, which of these items appears first: '1 Abstract', '3 Motivation and scope', '4 Non-negative quantities'
      Expected: 1 Abstract -> 3 Motivation and scope -> 4 Non-negative quantities -> 5 Absolute 
      Answer:   1 Abstract, 3 Motivation and scope, 4 Non-negative quantities, 5 Absolute quantities, 14 Acknowledgments
      Latency:  797ms

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
  Total: 9 | Pass: 8 | Fail: 1 | Error: 0
============================================================
============================================================
READBACK: P4234R0 (CORRUPT, model=deepseek-v4-pro)
============================================================
  [+] PASS order-sections (order)
      Q: In the document, which of these items appears first: '1. Introduction', '2. Proposed change', '3. Additional Motivation'
      Expected: 1. Introduction -> 2. Proposed change -> 3. Additional Motivation -> 4. Wording 
      Answer:   1. Introduction 2. Proposed change 3. Additional Motivation 4. Wording 5. Acknowledgements
      Latency:  859ms

  [+] PASS abstract-claim (present)
      Q: Does the document contain the following text or concept: 'conditionally-supported'? Answer YES or NO, then quote the rel
      Expected: YES
      Answer:   YES  "The inclusion of `$` in nondigit is conditionally-supported."
      Latency:  452ms

  [+] PASS dollar-dollar-survives (present)
      Q: Does the document contain the following text or concept: 'extern int Image$$ER_ZI$$Base;'? Answer YES or NO, then quote 
      Expected: YES
      Answer:   YES  "Unfortunately the examples given in armlink's documentation are not valid C++.  ```cpp // oops, none of these are 
      Latency:  1452ms

  [+] PASS code-oops-comment (code)
      Q: Does the document contain a code snippet including: '// oops, none of these are valid identifiers'? Answer YES or NO, th
      Expected: YES
      Answer:   YES  ```cpp // oops, none of these are valid identifiers extern int Image$$ER_ZI$$Base; extern int Image$$ER_ZI$$Limit; 
      Latency:  1250ms

  [+] PASS code-asm-alias (code)
      Q: Does the document contain a code snippet including: 'extern int Image_ER_ZI_Base asm("Image$$ER_ZI$$Base");'? Answer YES
      Expected: YES
      Answer:   YES  ```cpp extern int Image_ER_ZI_Base asm("Image$$ER_ZI$$Base"); ```
      Latency:  594ms

  [+] PASS xref-lexname (xref)
      Q: Does the document reference the paper/section: '[lex.name]'? Answer YES or NO, then quote the reference exactly as it ap
      Expected: YES
      Answer:   YES  "[lex.name] Identifiers"
      Latency:  390ms

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
  Total: 6 | Pass: 6 | Fail: 0 | Error: 0
============================================================

============================================================
READBACK SUMMARY: 5 paper(s), 32 pass, 5 fail, 0 error
  (CORRUPT mode: failures expected)
============================================================
```

# Experiment 2: scanned / empty-text-layer PDF canary (audit check L51)

## 1. Synthetic PDF

Built with PyMuPDF: 3 pages, text rendered to pixmaps and inserted as images only (no text objects). Path: `C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\scan0r0.pdf`.

Verification:

```
page 1 chars=0 text=''
page 2 chars=0 text=''
page 3 chars=0 text=''
TOTAL_CHARS=0
PAGES=3
```

## 2. `extract_textlayer` guard

Command:

```powershell
$env:PYTHONIOENCODING="utf-8"
uv run --package whisker python -c "from whisker.tapetum_llm.textlayer import extract_textlayer; extract_textlayer(r'C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\scan0r0.pdf')"
```

**Exit code:** 1

```
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "...\\textlayer.py", line 150, in extract_textlayer
    raise TextLayerError(
whisker.tapetum_llm.textlayer.TextLayerError: Text layer is effectively empty (0 chars across 3 pages); image-only PDF? This lane requires an intact text layer: C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\scan0r0.pdf
```

## 3. tomd `convert_paper_full`

Command:

```powershell
$env:PYTHONIOENCODING="utf-8"
uv run --package tomd python -c "from pathlib import Path; from tomd.api import convert_paper_full; r = convert_paper_full('SCAN0R0', Path(r'C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\scan0r0.pdf'), {}); print('skipped=', r.skipped); print('skip_reason=', r.skip_reason); print('markdown_len=', len(r.markdown)); print('repr=', repr(r))"
```

**Exit code:** 0 (no exception)

```
Consider using the pymupdf_layout package for a greatly improved page layout analysis.
Extracted text is not readable (encrypted/scanned PDF?)
skipped= True
skip_reason= unreadable
markdown_len= 0
repr= ConvertedPaper(markdown='', prompts=None, intent='', images=[], source_image_count=0, images_truncated=False, skipped=True, skip_reason=<SkipReason.UNREADABLE: 'unreadable'>, source_raster_count=0, source_vector_count=0)
```

## 4–5. End-to-end whisker lanes (staged in temp workspaces)

Staging used `SqliteBackend` temp dirs under `C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\`.

### Scanned-PDF exit-code / verdict table

| Scenario | Command | Exit | Verdict / result |
|----------|---------|------|------------------|
| Plausible markdown | `whisker SCAN0R0 --workspace ...\scan-ws --json` | **0** | `"verdict": "review"` (not pass) |
| Plausible markdown | `whisker-tapetum-llm SCAN0R0 --workspace ...\scan-ws --concurrency 1` | **1** | `PdfLaneError` / sidecar `status: "error"` |
| Empty markdown | `whisker SCAN0R0 --workspace ...\scan-ws-empty --json` | **5** | `"verdict": "fail"` |
| Empty markdown | `whisker-tapetum-llm SCAN0R0 --workspace ...\scan-ws-empty --concurrency 1` | **1** | `PdfLaneError` / sidecar `status: "error"` |

Tapetum sidecar (plausible-md): `{"pid": "SCAN0R0", "status": "error", "error": "PdfLaneError"}`

**No path produced a clean `pass` verdict or exit 0 on the LLM lane for the scanned PDF.** Deterministic lane exit 0 with plausible markdown is `review`, not `pass`.

## E2E verbatim log

```scan e2e log

===== plausible-md workspace: C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\scan-ws =====
whisker exit=0
INFO whisker: wrote report + 1 sidecar(s) to C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\scan-ws\whisker\det
[
  {
    "schema_version": 4,
    "pid": "SCAN0R0",
    "source_format": "pdf",
    "verdict": "review",
    "coverage": 1.0,
    "drift": 1.0,
    "unigram_coverage": 1.0,
    "unigram_drift": 1.0,
    "missing_region_count": 0,
    "extra_region_count": 1,
    "qa_score": 100,
    "uncertain_count": 0,
    "mojibake_count": 0,
    "table_parse_errors": 0,
    "lossy_table_count": 0,
    "ref_engine": "markitdown",
    "ref_nid": 0.0,
    "ref_teds": 1.0,
    "ref_mhs": 0.5,
    "ref_overall": 0.5,
    "ideal_nid": null,
    "ideal_teds": null,
    "ideal_mhs": null,
    "ideal_recall": null,
    "ideal_overall": null,
    "gates": [
      {
        "name": "non_empty",
        "passed": true,
        "detail": ""
      },
      {
        "name": "front_matter_valid",
        "passed": true,
        "detail": ""
      },
      {
        "name": "heading_monotone",
        "passed": true,
        "detail": ""
      },
      {
        "name": "no_empty_code",
        "passed": true,
        "detail": ""
      },
      {
        "name": "no_empty_table",
        "passed": true,
        "detail": ""
      },
      {
        "name": "no_toc_leak",
        "passed": true,
        "detail": ""
      }
    ],
    "hard_flags": [],
    "soft_flags": [
      "1 misaligned region(s)",
      "reference text agreement 0.000 low (advisory)",
      "unigram drift 1.000 > 0.1"
    ],
    "missing_regions": [],
    "extra_regions": [
      {
        "page": null,
        "token_start": 0,
        "token_end": 11,
        "sample": "abstract this markdown is staged for a scanned pdf negative..."
      }
    ]
  }
]

tapetum exit=1
INFO Service 'h200x8-deepseek-v4-pro': vllm_thinking  model=deepseek-v4-pro  endpoint=https://w80putgan2qou8-8000.proxy.runpod.net/v1
INFO Service 'alliance-pod': vllm_thinking  model=deepseek-v4-pro  endpoint=https://sgjy18glyi4blu-8000.proxy.runpod.net/v1
INFO Service 'b200-r1': vllm_thinking  model=deepseek-r1-distill-70b  endpoint=https://hdsfzi29n4xyup-8000.proxy.runpod.net/v1
INFO Service 'b200x2-gemma4': vllm_thinking  model=google/gemma-4-31B-it  endpoint=https://auzznfc1ourtrk-8000.proxy.runpod.net/v1
INFO Service 'b300-qwen36-27b': vllm_thinking  model=Qwen/Qwen3.6-27B  endpoint=https://5c9q67uhzngqc5-8000.proxy.runpod.net/v1
INFO Service 'b300-qwen3-235b': vllm_thinking  model=Qwen/Qwen3-235B-A22B-FP8  endpoint=https://8dqqdl9gaqme00-8000.proxy.runpod.net/v1
INFO Service 'h200-qwen3-32b': vllm_thinking  model=Qwen/Qwen3-32B  endpoint=https://d5htj97igzetl6-8000.proxy.runpod.net/v1
INFO Service 'anthropic-opus': anthropic  model=claude-opus-4-6  endpoint=
INFO HTTP Request: GET https://sgjy18glyi4blu-8000.proxy.runpod.net/health "HTTP/1.1 200 OK"
INFO LLM endpoint 'alliance-pod' healthy (https://sgjy18glyi4blu-8000.proxy.runpod.net/health)
INFO PDF-text-layer judge lane enabled: service=alliance-pod
INFO Adjudicating SCAN0R0 [pdf/pdf-judge] (1/1) ...
ERROR Failed to adjudicate SCAN0R0 [pdf-judge]
Traceback (most recent call last):
  File "C:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\tapetum_llm\pdf_judge.py", line 620, in judge_pdf_extraction
    pages = extract_textlayer(source_path)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\tapetum_llm\textlayer.py", line 150, in extract_textlayer
    raise TextLayerError(
whisker.tapetum_llm.textlayer.TextLayerError: Text layer is effectively empty (0 chars across 3 pages); image-only PDF? This lane requires an intact text layer: C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\scan-ws\paperstore\scan0r0.pdf

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "C:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\tapetum_llm\cli.py", line 1321, in _adjudicate_one
    judge_result = await asyncio.wait_for(
                   ^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\sabo2\AppData\Local\Programs\Python\Python312\Lib\asyncio\tasks.py", line 520, in wait_for
    return await fut
           ^^^^^^^^^
  File "C:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\tapetum_llm\pdf_judge.py", line 622, in judge_pdf_extraction
    raise PdfLaneError(f"{pid}: text-layer extraction failed: {exc}") from exc
whisker.tapetum_llm.pdf_judge.PdfLaneError: SCAN0R0: text-layer extraction failed: Text layer is effectively empty (0 chars across 3 pages); image-only PDF? This lane requires an intact text layer: C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\scan-ws\paperstore\scan0r0.pdf


===== empty-md workspace: C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\scan-ws-empty =====
whisker exit=5
INFO whisker: wrote report + 1 sidecar(s) to C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\scan-ws-empty\whisker\det
[
  {
    "schema_version": 4,
    "pid": "SCAN0R0",
    "source_format": "pdf",
    "verdict": "fail",
    "coverage": 1.0,
    "drift": 0.0,
    "unigram_coverage": 1.0,
    "unigram_drift": 0.0,
    "missing_region_count": 0,
    "extra_region_count": 0,
    "qa_score": 0,
    "uncertain_count": 0,
    "mojibake_count": 0,
    "table_parse_errors": 0,
    "lossy_table_count": 0,
    "ref_engine": "markitdown",
    "ref_nid": 1.0,
    "ref_teds": 1.0,
    "ref_mhs": 1.0,
    "ref_overall": 1.0,
    "ideal_nid": null,
    "ideal_teds": null,
    "ideal_mhs": null,
    "ideal_recall": null,
    "ideal_overall": null,
    "gates": [
      {
        "name": "non_empty",
        "passed": false,
        "detail": "body has no non-whitespace content"
      },
      {
        "name": "front_matter_valid",
        "passed": false,
        "detail": "missing or unterminated front matter"
      },
      {
        "name": "heading_monotone",
        "passed": true,
        "detail": ""
      },
      {
        "name": "no_empty_code",
        "passed": true,
        "detail": ""
      },
      {
        "name": "no_empty_table",
        "passed": true,
        "detail": ""
      },
      {
        "name": "no_toc_leak",
        "passed": true,
        "detail": ""
      }
    ],
    "hard_flags": [
      "gate:front_matter_valid:missing or unterminated front matter",
      "gate:non_empty:body has no non-whitespace content"
    ],
    "soft_flags": [
      "qa_score 0 < 70"
    ],
    "missing_regions": [],
    "extra_regions": []
  }
]

tapetum exit=1
INFO Service 'h200x8-deepseek-v4-pro': vllm_thinking  model=deepseek-v4-pro  endpoint=https://w80putgan2qou8-8000.proxy.runpod.net/v1
INFO Service 'alliance-pod': vllm_thinking  model=deepseek-v4-pro  endpoint=https://sgjy18glyi4blu-8000.proxy.runpod.net/v1
INFO Service 'b200-r1': vllm_thinking  model=deepseek-r1-distill-70b  endpoint=https://hdsfzi29n4xyup-8000.proxy.runpod.net/v1
INFO Service 'b200x2-gemma4': vllm_thinking  model=google/gemma-4-31B-it  endpoint=https://auzznfc1ourtrk-8000.proxy.runpod.net/v1
INFO Service 'b300-qwen36-27b': vllm_thinking  model=Qwen/Qwen3.6-27B  endpoint=https://5c9q67uhzngqc5-8000.proxy.runpod.net/v1
INFO Service 'b300-qwen3-235b': vllm_thinking  model=Qwen/Qwen3-235B-A22B-FP8  endpoint=https://8dqqdl9gaqme00-8000.proxy.runpod.net/v1
INFO Service 'h200-qwen3-32b': vllm_thinking  model=Qwen/Qwen3-32B  endpoint=https://d5htj97igzetl6-8000.proxy.runpod.net/v1
INFO Service 'anthropic-opus': anthropic  model=claude-opus-4-6  endpoint=
INFO HTTP Request: GET https://sgjy18glyi4blu-8000.proxy.runpod.net/health "HTTP/1.1 200 OK"
INFO LLM endpoint 'alliance-pod' healthy (https://sgjy18glyi4blu-8000.proxy.runpod.net/health)
INFO PDF-text-layer judge lane enabled: service=alliance-pod
INFO Adjudicating SCAN0R0 [pdf/pdf-judge] (1/1) ...
ERROR Failed to adjudicate SCAN0R0 [pdf-judge]
Traceback (most recent call last):
  File "C:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\tapetum_llm\pdf_judge.py", line 620, in judge_pdf_extraction
    pages = extract_textlayer(source_path)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\tapetum_llm\textlayer.py", line 150, in extract_textlayer
    raise TextLayerError(
whisker.tapetum_llm.textlayer.TextLayerError: Text layer is effectively empty (0 chars across 3 pages); image-only PDF? This lane requires an intact text layer: C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\scan-ws-empty\paperstore\scan0r0.pdf

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "C:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\tapetum_llm\cli.py", line 1321, in _adjudicate_one
    judge_result = await asyncio.wait_for(
                   ^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\sabo2\AppData\Local\Programs\Python\Python312\Lib\asyncio\tasks.py", line 520, in wait_for
    return await fut
           ^^^^^^^^^
  File "C:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\tapetum_llm\pdf_judge.py", line 622, in judge_pdf_extraction
    raise PdfLaneError(f"{pid}: text-layer extraction failed: {exc}") from exc
whisker.tapetum_llm.pdf_judge.PdfLaneError: SCAN0R0: text-layer extraction failed: Text layer is effectively empty (0 chars across 3 pages); image-only PDF? This lane requires an intact text layer: C:\Users\sabo2\AppData\Local\Temp\whisker-auditv3-w6\scan-ws-empty\paperstore\scan0r0.pdf

```
