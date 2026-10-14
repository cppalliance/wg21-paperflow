# 40 - tapetum_llm/cli.py full read (C3 scope)
**Claims tested:** C3 (a, c only; b out of file scope)
**Exhaustive:** yes (1331 lines read top-to-bottom; user note said ~1182, file is 1331 at read time)

## Method
- Read in full: `packages/whisker/src/whisker/tapetum_llm/cli.py` (lines 1–1331).
- Read for timeout constants: `packages/whisker/src/whisker/tapetum_llm/constants.py` (lines 191–197, 223–227, 241–242).
- rg patterns: `exhaustive_units`, `args\.inspect`, `coverage`, `exhaustive`, `inspect`, `judge_pdf_extraction`, `_compute_fingerprint`, `_LANE_VERSION`, `fingerprint` in cli.py.
- Signature cross-check: `judge_pdf_extraction` in `pdf_judge.py:567–573`.

## Inventory

### File metadata
| Item | Location | Role |
|---|---|---|
| Module docstring / exit contract | cli.py:8–16 | Advisory lane CLI; exit 0 on verdicts, 1 on errors |
| `_LANE_VERSION` | cli.py:111 | Integer `8`; bumped on lane logic changes; included in fingerprint |
| `_PAPER_TIMEOUT_SECONDS` | cli.py:132 | `900.0` |
| `_IDEAL_MAX_TOKENS` | cli.py:136 | `2048` |
| `_DEFAULT_CONCURRENCY` | cli.py:121 | `32` |
| `_MAX_TESTED_CONCURRENCY` | cli.py:126 | `32` |
| `_HEALTH_PROBE_TIMEOUT_SECONDS` | cli.py:161 | `30.0` |

### `--exhaustive-units` (definition + every consumption)
| Item | Location | Role |
|---|---|---|
| Arg definition | cli.py:257–262 | `--exhaustive-units` store_true; help says caps at MAX_UNIT_CHECKS unless set; "Implied by --inspect" |
| **Only consumption** | cli.py:1186–1187 | Passed to `adjudicate_paper(..., exhaustive=getattr(args, "exhaustive_units", False) or getattr(args, "inspect", False), ...)` on **text lane only** |
| Not passed elsewhere | cli.py (entire file) | Zero other references to `exhaustive_units` or `args.exhaustive_units` |

### `--inspect` (definition + every consumption)
| Item | Location | Role |
|---|---|---|
| Arg definition | cli.py:251–255 | `--inspect` store_true; writes `tapetum-inspect.md` |
| `_fuse_only` entry | cli.py:888 | `_fuse_only(backend, inspect=args.inspect)` |
| `_fuse_only` pair collect | cli.py:797–798 | `if inspect: inspect_pairs.append(...)` |
| `_fuse_only` persist | cli.py:808–811 | `if inspect and inspect_pairs: _persist_inspect(...)` |
| PDF lane per-paper pair | cli.py:1174–1178 | `if args.inspect:` builds `inspect_pair` from whisker + pdf sidecar |
| Text lane exhaustive alias | cli.py:1186–1187 | `or getattr(args, "inspect", False)` forces exhaustive on text lane |
| Text lane per-paper pair | cli.py:1250–1254 | `if args.inspect:` builds `inspect_pair` from whisker + text result |
| Error path pair | cli.py:1265–1266 | `if args.inspect:` pair with `None` tapetum sidecar |
| Batch persist report | cli.py:1304–1306 | `if args.inspect and inspect_pairs: _persist_inspect(...)` |
| Import / helper (not args) | cli.py:59, 701–713, 760, 774, 1037, 1116, 1270, 1279–1287 | `inspect_report`, `_persist_inspect`, local `inspect` param, `inspect_pair` locals |

### PDF branch `judge_pdf_extraction` call
| Item | Location | Role |
|---|---|---|
| Lane gate | cli.py:1040–1042 | `use_pdf_judge = kind == "pdf" and judge_agent is not None` |
| Call site | cli.py:1121–1126 | `judge_pdf_extraction(pid, backend, judge_agent, debug_log=judge_debug)` inside `asyncio.wait_for(..., timeout=_pdf_judge_timeout_seconds())` |
| Parameters passed | cli.py:1122–1125 | `pid`, `backend`, `judge_agent`, `debug_log` only |
| No coverage/exhaustive arg | cli.py:1121–1126 | No `exhaustive`, `coverage`, `all_pages`, or similar keyword |
| Function signature (external) | pdf_judge.py:567–573 | `async def judge_pdf_extraction(pid, backend, agent, *, debug_log=None) -> PdfJudgeResult` — no coverage parameter |

### `_compute_fingerprint` — fields hashed
| Field key | Location | Source |
|---|---|---|
| `md_sha256` | cli.py:544 | `_sha256_file(md_path)` |
| `source_sha256` | cli.py:545 | `_sha256_file(source_path)` |
| `prompt_sha256` | cli.py:546 | `_sha256_str(prompt_text)` |
| `model` | cli.py:547 | `model_name` argument (effective services JSON string) |
| `lane_version` | cli.py:548 | `_LANE_VERSION` (`8`) |
| `lane` | cli.py:549 | `"pdf_textlayer_judge"` or `"text"` |
| `schema_sha256` | cli.py:550 | `_sha256_str(schema_json)` |
| `ideal_sha256` | cli.py:551 | hash of ideal text or `None` |
| `ideal_prompt_sha256` | cli.py:552–555 | hash of `IDEAL_VERIFY_PROMPT_CONTRACT` or `None` |
| `ideal_schema_sha256` | cli.py:557–562 | hash of `IdealVerification` schema or `None` |
| `ideal_model` | cli.py:564 | `model_name` if ideal present else `None` |
| **No exhaustive/coverage field** | cli.py:515–565 | Docstring lists all keys (527–538); none encode `--exhaustive-units`, unit count, or all-pages mode |

### `_LANE_VERSION` and fingerprint-skip path
| Item | Location | Role |
|---|---|---|
| Constant | cli.py:111 | `_LANE_VERSION = 8` |
| v6 comment (unit coverage) | cli.py:105–106 | Comment only: "unit coverage is fail-closed"; not a fingerprint field |
| Incremental gate | cli.py:1011–1014 | `full_run` → incremental unless `--force`; explicit PIDs/`--review-all` → incremental only if `--incremental` |
| Skip attempt | cli.py:1091–1105 | If `incremental and ideal_read_error is None`: compute fp, `_fingerprint_matches` → return `"skipped"` |
| fp compute inputs | cli.py:1093–1097 | `fp_lane`, `fp_prompt`, `fp_model`, `fp_schema`, `ideal_text` — no exhaustive flag |
| Match semantics | cli.py:581–588 | `all(old.get(k) == v for k, v in new_fp.items())` — extra old keys ignored; exhaustive mode change would not differ |
| fp None paths | cli.py:1107–1109, 1152–1160, 1231–1239 | On skip failure, non-incremental, or post-run recompute |

### Timeout formulas (exact arithmetic)
| Formula | Location | Expression |
|---|---|---|
| `_pdf_judge_timeout_seconds` | cli.py:146–151 | `_PAPER_TIMEOUT_SECONDS + MAX_PAGE_ESCALATIONS * PAGE_ESCALATION_TIMEOUT_SECONDS + (1 + MAX_UNIT_CHECKS) * UNIT_CHECK_TIMEOUT_SECONDS` |
| `_text_lane_timeout_seconds` | cli.py:154–158 | `_PAPER_TIMEOUT_SECONDS + (1 + MAX_UNIT_CHECKS) * UNIT_CHECK_TIMEOUT_SECONDS` |
| `_PAPER_TIMEOUT_SECONDS` | cli.py:132 | `900.0` |
| `MAX_PAGE_ESCALATIONS` | constants.py:191 | `5` |
| `PAGE_ESCALATION_TIMEOUT_SECONDS` | constants.py:197 | `120.0` |
| `MAX_UNIT_CHECKS` | constants.py:223 | `5` |
| `UNIT_CHECK_TIMEOUT_SECONDS` | constants.py:241 | `120.0` |
| **PDF timeout numeric** | derived | `900.0 + 5*120.0 + (1+5)*120.0` = `900 + 600 + 720` = **`2220.0` s** |
| **Text timeout numeric** | derived | `900.0 + (1+5)*120.0` = `900 + 720` = **`1620.0` s** |
| Ideal attach timeout | cli.py:1070–1077 | Separate `asyncio.wait_for(..., timeout=_PAPER_TIMEOUT_SECONDS)` = **900.0 s** |
| Note | cli.py:146–151, constants.py:223–227 | Budget assumes at most `MAX_UNIT_CHECKS` unit calls; exhaustive/all-pages would exceed this budget |

### Other complications for planned `--all-pages` design
| Item | Location | Complication |
|---|---|---|
| Batch mode | cli.py:984–1006, 1272–1302 | Quiets loggers, progress bar, retry counting; behavior differs from single-paper |
| Service overrides | cli.py:891, 925, 942–955, 976–980, 1188 | `--service SLOT=NAME` affects ideal agent, PDF judge agent, and text lane via `service_overrides=overrides` |
| Error tombstone | cli.py:674–698, 1264 | On failure writes minimal `{"status":"error",...}` sidecar; no fingerprint; inspect pair gets `None` tapetum (1265–1266) |
| `--text-only` | cli.py:943–964, 293–297 | Forces text lane; `judge_agent = None`; PDF papers never hit `judge_pdf_extraction` |
| `--fuse-only` | cli.py:887–889, 760–811 | No LLM adjudication; only refusion + optional inspect |
| `--review-all` | cli.py:895–898 | Subset via `select_candidates`; not full corpus |
| Auto-incremental full run | cli.py:902–906, 1011–1012, 304–305 | Bare invocation skips papers on fingerprint match; `--force` only in full-run mode |
| Lane routing | cli.py:1040–1042, 1080–1089 | PDF vs text chosen by source suffix + judge agent availability; separate fingerprint lanes |
| Judge service missing | cli.py:959–964 | PDF service not in registry → warning + text lane fallback |
| Concurrency | cli.py:1016–1031, 1274–1276 | Up to 32 papers parallel; independent sidecars |
| Ideal read error | cli.py:1050–1054, 1091 | Skips fingerprint incremental check when `ideal_read_error is not None` |
| Health probe gate | cli.py:918, 829–870 | Batch aborts before fan-out if endpoint unhealthy |
| Merged report | cli.py:1308–1309, 716–757 | Full run builds merged report after adjudication |
| Debug/trace asymmetry | cli.py:1119, 1184–1185 | PDF lane: debug only on judge path; text lane gets both `debug` and `trace` |
| Timeout vs exhaustive | cli.py:146–151, 1186–1191 | Text exhaustive can run >5 unit checks but timeout capped at `(1+MAX_UNIT_CHECKS)` unit slots |

## Verdict on the claim(s)

### C3a — `exhaustive` passed only on text lane; PDF branch never receives it
**CONFIRMED**

- `--exhaustive-units` is consumed only at cli.py:1186–1187 inside the `else` (text) branch of `if use_pdf_judge` (cli.py:1118–1179 vs 1179–1254).
- PDF branch calls `judge_pdf_extraction` at cli.py:1121–1125 with four arguments only; no coverage/exhaustive parameter.
- External signature `pdf_judge.py:567–573` corroborates: no such parameter exists on the callee.

### C3b — empty risk router → `coverage_complete=True` with zero checked units; fusion trusts it
**NOT VERIFIED from this file** (out of scope)

- `cli.py` contains no symbol `coverage_complete`, no risk-router logic, and no `fuse_verdicts` consumption of coverage fields beyond passing sidecars through persist paths (cli.py:621, 646, 1177, 1253).
- C3b lives in `adjudicate.py`, `unit_judge.py`, `fusion.py` (rg hits elsewhere); cannot CONFIRM or REFUTE from cli.py alone.

### C3c — `_compute_fingerprint` encodes no coverage mode; `--exhaustive-units` changes behavior without cache-key change
**CONFIRMED**

- Fingerprint dict keys are exactly ten fields listed above (cli.py:543–565); none encode exhaustive mode, unit cap, or all-pages scope.
- `_LANE_VERSION` (cli.py:111) is a global lane bump, not per-run mode.
- Incremental skip (cli.py:1091–1105) compares fingerprints without exhaustive; toggling `--exhaustive-units` alone would match prior sidecar and skip re-adjudication when incremental is active.

## Coverage gaps
None for `cli.py` (full file read). C3b requires reading `adjudicate.py`, `unit_judge.py`, `fusion.py` (not in this agent's scope).

## What could still hide a counterexample
- `judge_pdf_extraction` / `adjudicate_paper` internals may read env vars or defaults not visible in cli.py.
- Library callers of `_compute_fingerprint` or `_adjudicate_one` logic duplicated outside this file.
- Fingerprint "match" ignores extra keys in old sidecar (cli.py:588) — stale fields would not force re-run.
- Timeout firewall may kill exhaustive runs before all units complete, masking behavioral intent (cli.py:1190–1191 vs 1186–1187).
