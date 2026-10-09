# W7 Mechanical Probes (Auditv3)

Temp audit root enumerated 2026-08-03. Present: `ws/`, `ws-canary/`, `rt1/`-`rt4/`, `rt7/`, assorted scripts. **Missing:** `ws2/`, `ws3/`, `ws4/`, `ws5/`. No `*.log` files directly under `C:\Users\sabo2\AppData\Local\Temp\auditv3\`; many `*.txt` stderr/stdout captures under `rt*`.

## PROBE 1 - Secrets redaction (L30)

### Commands

```powershell
$env:PYTHONIOENCODING="utf-8"
cd c:\Users\sabo2\Desktop\cppalliance
$line = Get-Content .env | Where-Object { $_ -match '^ALLIANCE_POD_KEY=' }
if ($line -match '^ALLIANCE_POD_KEY=(.+)$') { $key = $Matches[1].Trim('"').Trim("'") }
"LENGTH=$($key.Length)"
"PREFIX4=$($key.Substring(0,[Math]::Min(4,$key.Length)))"
```

```
LENGTH=18
PREFIX4=zQtp
```

```powershell
@'...'@ | Set-Content C:\Users\sabo2\AppData\Local\Temp\auditv3\probe1_secrets.py -Encoding utf8
$env:PYTHONIOENCODING="utf-8"
python C:\Users\sabo2\AppData\Local\Temp\auditv3\probe1_secrets.py
```

### Scan scope

- All `*.json` under `C:\Users\sabo2\AppData\Local\Temp\auditv3\` (recursive)
- `*.debug.*.md` / `*.trace.*.md` (none found under audit temp)
- `*.log` / selected `*.txt` under audit temp (65 files scanned)

### Output (exit code 0)

```
KEY_META length=18 prefix4=zQtp
SCAN_FILES 65
C:\Users\sabo2\AppData\Local\Temp\auditv3\rt2\rt2-results.json {'hex32+': 37, 'b64run32+': 40}
C:\Users\sabo2\AppData\Local\Temp\auditv3\ws\whisker\llm\p4182r0.whisker.tapetum.json {'hex32+': 7, 'b64run32+': 7}
C:\Users\sabo2\AppData\Local\Temp\auditv3\ws\whisker\llm\p4182r0adv.whisker.tapetum.json {'hex32+': 4, 'b64run32+': 4}
C:\Users\sabo2\AppData\Local\Temp\auditv3\ws\whisker\llm\p4182r0defect.whisker.tapetum.json {'hex32+': 4, 'b64run32+': 4}
C:\Users\sabo2\AppData\Local\Temp\auditv3\ws\whisker\llm\p4182r0forge.whisker.tapetum.json {'hex32+': 4, 'b64run32+': 5}
C:\Users\sabo2\AppData\Local\Temp\auditv3\ws\whisker\llm\p4182r0head.whisker.tapetum.json {'hex32+': 4, 'b64run32+': 4}
C:\Users\sabo2\AppData\Local\Temp\auditv3\ws\whisker\llm\p4182r0inject.whisker.tapetum.json {'hex32+': 4, 'b64run32+': 5}
C:\Users\sabo2\AppData\Local\Temp\auditv3\ws-canary\whisker\llm\p4182r0c1defect.whisker.tapetum.json {'hex32+': 4, 'b64run32+': 4}
C:\Users\sabo2\AppData\Local\Temp\auditv3\ws-canary\whisker\llm\p4182r0c2permute.whisker.tapetum.json {'hex32+': 4, 'b64run32+': 4}
C:\Users\sabo2\AppData\Local\Temp\auditv3\ws-canary\whisker\llm\p4182r0c3tableswap.whisker.tapetum.json {'hex32+': 4, 'b64run32+': 5}
C:\Users\sabo2\AppData\Local\Temp\auditv3\ws-canary\whisker\llm\p4182r0c4mathflip.whisker.tapetum.json {'hex32+': 4, 'b64run32+': 4}
C:\Users\sabo2\AppData\Local\Temp\auditv3\ws-canary\whisker\llm\p4182r0control.whisker.tapetum.json {'hex32+': 4, 'b64run32+': 4}
```

No file reported `literal_ALLIANCE_POD_KEY_value`. No hits for `sk-`, `Bearer `, `api_key`, or `ALLIANCE_POD_KEY` string patterns in scanned files.

**ANSWER:** Real key value (length 18, prefix `zQtp`) did not appear in scanned audit artifacts; only SHA-like `hex32+` / `b64run32+` matches in LLM sidecars and `rt2-results.json`.

## PROBE 2 - Model and prompt attribution (L31)

### Representative sidecar

`C:\Users\sabo2\AppData\Local\Temp\auditv3\ws\whisker\llm\p4182r0adv.whisker.tapetum.json`

### Command

```powershell
$env:PYTHONIOENCODING="utf-8"
python -c "import json; ..."
```

### Top-level JSON keys

```
['advisory', 'all_pages_requested', 'axis_findings', 'confidence', 'defect_groups', 'duration_seconds', 'escalated', 'escalation_signals', 'evidence_dispositions', 'evidence_summary', 'fingerprint', 'fusion', 'grounded_evidence', 'lane', 'metadata_outline_check', 'page_count', 'page_escalations', 'page_screen', 'pid', 'primary_concern', 'reasoning', 'risk_signals', 'schema_version', 'source_kind', 'status', 'suggested_verdict', 'textlayer_diff', 'tier1_model', 'tier2_model', 'ungrounded_dropped', 'unit_checks', 'unit_coverage', 'unit_selection', 'whisker_verdict']
```

### Attribution-like fields (values truncated in sidecar dump)

| Field | Value (summary) |
|-------|-----------------|
| `schema_version` | `8` |
| `tier1_model` | `"alliance-pod"` |
| `tier2_model` | `null` |
| `duration_seconds` | `5.8` |
| `fingerprint.lane_version` | `11` |
| `fingerprint.lane` | `"pdf_textlayer_judge"` |
| `fingerprint.prompt_sha256` | hex digest |
| `fingerprint.schema_sha256` | hex digest |
| `fingerprint.model` | JSON string listing `services.alliance-pod` (`backend`, `base_url`, `model`: `deepseek-v4-pro`, slots) |

No top-level `prompt_hash`, `service`, `endpoint`, or `timestamp` keys. `rg prompt_hash packages/whisker/src/whisker/tapetum_llm/` returned no matches.

### Code references (`path:line`)

| Symbol | Defined | Written into sidecar |
|--------|---------|----------------------|
| `_LANE_VERSION` | `packages/whisker/src/whisker/tapetum_llm/cli.py:123` | via `_compute_fingerprint` → `lane_version` in `fingerprint` (`cli.py:630`, attached `cli.py:738-739`, `766-767`, `827-828`) |
| `fingerprint` dict | `_compute_fingerprint` `cli.py:595-651` | `_persist_lane_result` / tombstone writers `cli.py:738-739`, `766-767`, `827-828` |
| `prompt_sha256` (not `prompt_hash`) | `_compute_fingerprint` `cli.py:628` | inside `fingerprint` block on write |
| `schema_version` | sidecar model e.g. `tapetum_llm/models.py:466`, `pdf_judge.py:559` | emitted in `to_sidecar_dict()` payloads |

**ANSWER:** **Yes** - tuple attributable via `tier1_model` / `tier2_model`, top-level `schema_version`, and `fingerprint` (`model`, `prompt_sha256`, `schema_sha256`, `lane_version`, `lane`, content hashes); there is no field named `prompt_hash` or top-level `endpoint` (endpoint appears inside `fingerprint.model` JSON).

## PROBE 3 - Workspace isolation (L34)

### Workspace

`C:\Users\sabo2\AppData\Local\Temp\auditv3\ws`

### Command

```powershell
Get-ChildItem C:\Users\sabo2\AppData\Local\Temp\auditv3\ws -Recurse -File | ForEach-Object { ... }
```

### Recursive listing (size, class, relative path)

```
237568	paperstore body	paperstore.db
25568	paperstore body	paperstore\p4182r0.md
98070	paperstore body	paperstore\p4182r0.pdf
214	paperstore body	paperstore\p4182r0adv.md
98070	paperstore body	paperstore\p4182r0adv.pdf
25478	paperstore body	paperstore\p4182r0defect.md
98070	paperstore body	paperstore\p4182r0defect.pdf
25747	paperstore body	paperstore\p4182r0forge.md
98070	paperstore body	paperstore\p4182r0forge.pdf
25570	paperstore body	paperstore\p4182r0head.md
98070	paperstore body	paperstore\p4182r0head.pdf
25846	paperstore body	paperstore\p4182r0inject.md
98070	paperstore body	paperstore\p4182r0inject.pdf
1642	whisker det sidecar	whisker\det\p4182r0.whisker.json
2248	whisker det sidecar	whisker\det\p4182r0adv.whisker.json
1652	whisker det sidecar	whisker\det\p4182r0defect.whisker.json
1651	whisker det sidecar	whisker\det\p4182r0forge.whisker.json
1732	whisker det sidecar	whisker\det\p4182r0head.whisker.json
1653	whisker det sidecar	whisker\det\p4182r0inject.whisker.json
2192	report	whisker\det\report.json
625	report	whisker\det\report.md
408614	whisker llm sidecar	whisker\llm\p4182r0.whisker.tapetum.json
9448	whisker llm sidecar	whisker\llm\p4182r0adv.whisker.tapetum.json
6239	whisker llm sidecar	whisker\llm\p4182r0defect.whisker.tapetum.json
8441	whisker llm sidecar	whisker\llm\p4182r0forge.whisker.tapetum.json
8794	whisker llm sidecar	whisker\llm\p4182r0head.whisker.tapetum.json
8365	whisker llm sidecar	whisker\llm\p4182r0inject.whisker.tapetum.json
2088	report	whisker\llm\report-merged.json
1262	report	whisker\llm\report-merged.md
3672	report	whisker\llm\tapetum-inspect.md
```

No `other` class under `ws`. **Writes outside `whisker/det/`, `whisker/llm/`, and report files:** `paperstore/` tree and `paperstore.db` at workspace root (expected paperstore layout).

### `rg 'open\(|\.write_text\(|\.write_bytes\(|mkdir\(' packages/whisker/src/whisker --glob '*.py'` (excerpt)

Deterministic lane (`__main__.py:245-264`): `out_dir = whisker_output_dir(...)` → `sidecar_path(pid, backend)` → `sidecar.write_text(...)`, `(out_dir / "report.json").write_text(...)`, `report.md.write_text(...)`.

`whisker_output_dir` (`score.py:374-388`): `backend.get_paper_md_path(pid).parent.parent / "whisker" / "det"` (not raw `backend.workspace_dir`).

LLM lane (`tapetum_llm/cli.py:729-743`): `out_dir = _llm_output_dir(pid, backend)` → `out_path.write_text(...)`.

Other packages modules (`survey/`, `compare/`, `corpus_tools/`, `__main__.py` `--out` flags) write to caller-supplied or derived paths, not audit `ws` layout.

**ANSWER:** Under `ws`, audit outputs stay in `whisker/det/`, `whisker/llm/`, and report artifacts; **paperstore bodies and `paperstore.db` also occupy the workspace root**; whisker det/llm paths derive from `backend.get_paper_md_path`, not direct `workspace_dir` string concatenation.

## PROBE 4 - CI hermeticity and pin discipline (L38)

### Workflow files

| File | Whisker tests | Network / pod | `WHISKER_LLM_EVAL` | `WHISKER_PIN_UPDATE` |
|------|---------------|---------------|--------------------|----------------------|
| `.github/workflows/tests.yml` | Yes (`matrix.package` includes `whisker`; `uv run pytest packages/whisker/tests`) | Not declared; no pod secrets | Not set or referenced | Not set or referenced |
| `.github/workflows/notify-superproject-vendor-pin.yml` | No | Dispatches external workflow on release | No | No |

### Repo grep (`WHISKER_PIN_UPDATE`, `WHISKER_LLM_EVAL`)

Excluding `packages/whisker/research/**`, `research/**`, `.worktrees/**`:

```
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_tapetum_llm_eval.py-13-
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_tapetum_llm_eval.py-14-Execution requirements:
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_tapetum_llm_eval.py:15:- Set WHISKER_LLM_EVAL=1 to enable (skipped otherwise).
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_tapetum_llm_eval.py-16-- ALLIANCE_POD_KEY must be available (loaded from .env).
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_tapetum_llm_eval.py-17-- The Alliance pod is billed per hour (24/7), not per token, so running this
--
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_tapetum_llm_eval.py-32-
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_tapetum_llm_eval.py-33-pytestmark = pytest.mark.skipif(
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_tapetum_llm_eval.py:34:    not os.environ.get("WHISKER_LLM_EVAL"),
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_tapetum_llm_eval.py:35:    reason="opt-in pod-gated eval; set WHISKER_LLM_EVAL=1 to run",
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_tapetum_llm_eval.py-36-)
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_tapetum_llm_eval.py-37-
--
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py-17-Update the baseline with::
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py-18-
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py:19:    WHISKER_PIN_UPDATE=1 uv run --package whisker pytest packages/whisker/tests/test_score_pinning.py -x
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py-20-
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py-21-The test is hermetic: no backend, no source PDF extraction at runtime,
--
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py-123-        pytest.fail(
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py-124-            f"Baseline not found at {_BASELINE_PATH}. "
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py:125:            "Generate it with: WHISKER_PIN_UPDATE=1 uv run --package whisker "
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py-126-            "pytest packages/whisker/tests/test_score_pinning.py -x"
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py-127-        )
--
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py-131-@pytest.fixture(scope="module")
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py-132-def baseline():
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py:133:    if os.environ.get("WHISKER_PIN_UPDATE") == "1":
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py-134-        if os.environ.get("CI"):
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py-135-            pytest.fail(
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py:136:                "WHISKER_PIN_UPDATE=1 is forbidden in CI. "
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py-137-                "Refresh the baseline locally, review the diff, then commit."
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py-138-            )
--
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py-143-            encoding="utf-8",
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py-144-        )
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py:145:        pytest.skip("Baseline updated; re-run without WHISKER_PIN_UPDATE to test.")
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py-146-    return _load_baseline()
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py-147-
--
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\CLAUDE.md-878-   heading-only fails) is the current escape valve.
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\CLAUDE.md-879-3. **Pinning baseline has no CI guard against silent gate additions.** Fixed
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\CLAUDE.md:880:   in this batch (A2): `WHISKER_PIN_UPDATE=1` is blocked when `CI=true`, and
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\CLAUDE.md-881-   unannotated `false` gates in the baseline now fail a meta-test.
c:\Users\sabo2\Desktop\cppalliance\packages\whisker\src\whisker\CLAUDE.md-882-

```

(Full-repo `rg -c` reports additional matches under audit/research markdown copies.)

**ANSWER:** **`WHISKER_PIN_UPDATE=1` fails in CI** (`packages/whisker/tests/test_score_pinning.py:133-138` when `CI` set); workflows do not set pin-update. **LLM eval is opt-in** (`test_tapetum_llm_eval.py:33-35`, skipped without `WHISKER_LLM_EVAL=1`) and is **not** a merge gate in `.github/workflows/tests.yml`.

## PROBE 5 - tomd interop contract (L39)

### Source path

`packages/tomd/src/tomd/lib/golden_qa.py`

### `_call_whisker_score_file` (lines 484-514)

- **argv:** `["whisker", "score-file", "--json", "--md", str(md_file)]` plus optional `["--ref", str(ref_file)]`, `["--source", str(source_path)]`
- **Accepted exit codes:** `{0, 3, 5}` else returns `None`
- **JSON read:** full `json.loads(result.stdout)` returned to callers
- **Callers read:** `gates` (`name`, `passed`, `detail`), `missing_regions`, `extra_regions`, `verdict` (see `golden_qa.py:443-446`, `625-628`, `681-682`)
- **Error handling:** `except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError, OSError): return None` (`506-512`)

### `_call_whisker_check_facts` (lines 519-548)

- **argv:** `["whisker", "check-facts", "--json", "--md", str(md_file)]` plus optional `--facts`, `--anchors`
- **Accepted exit codes:** `{0, 5}` else `None`
- **JSON read:** entire parsed object stored as `comprehension` (`572-573`); no sub-key reads in this module
- **Error handling:** same `except` → `None` (`546-547`)

### Live whisker JSON (commands, exit 0)

```powershell
$env:PYTHONIOENCODING="utf-8"
cd c:\Users\sabo2\Desktop\cppalliance
uv run whisker score-file --json --md C:\Users\sabo2\AppData\Local\Temp\auditv3\ws\paperstore\p4182r0.md --ref ... --source ...
uv run whisker check-facts --json --md ... --facts packages\whisker\corpus\P4182R0.facts.jsonl
```

**score-file top-level keys emitted:** `content_recall`, `coverage`, `drift`, `extra_regions`, `gates`, `hard_flags`, `missing_regions`, `pid`, `ref_mhs`, `ref_nid`, `ref_overall`, `ref_teds`, `soft_flags`, `source_format`, `unigram_coverage`, `unigram_drift`, `verdict`

**Bridge top-level keys read:** `gates`, `missing_regions`, `extra_regions`, `verdict` (plus gate objects: `name`, `passed`, `detail`)

- **Read but always emitted:** none at top level
- **Emitted, not read by bridge:** `content_recall`, `coverage`, `drift`, `hard_flags`, `pid`, `ref_*`, `soft_flags`, `source_format`, `unigram_*`

**check-facts top-level keys emitted:** `anchors`, `facts`, `pid`, `verdict`

**Bridge:** stores full dict; no top-level key subset beyond whole object

### Fatality

Whisker subprocess failures return `None` (non-fatal): `score_result` still returns structural axes (`571-573`); `bless_stem` skips gate enforcement when `whisker_data is None` (`623-628`); only when whisker returns data do failed gates raise `ValueError` (`624-628`).

**ANSWER:** Bridge reads a **subset** of `score-file` output; **`check-facts` response is passed through whole**; whisker unavailability is **non-fatal** (`golden_qa.py:506-512`, `546-547`); failed gates when whisker data exists are **fatal to bless** (`624-628`).

## PROBE 6 - UTF-8 machine-readable output (L28)

Corpus: no paper with non-ASCII in `title`/`reply-to` in first 1500 chars scan; `n5034.md` has non-ASCII en-dashes in body. **Staged paper:** copied `ws` → `probe6_ws`, set title to `Plattformüberblick - Compilerübersicht` in `paperstore/p4182r0.md`.

### Commands

```powershell
cd c:\Users\sabo2\Desktop\cppalliance
$ws="C:\Users\sabo2\AppData\Local\Temp\auditv3\probe6_ws"
Remove-Item Env:PYTHONIOENCODING -ErrorAction SilentlyContinue
uv run whisker p4182r0 --workspace $ws --json --no-write  # UNSET_EXIT=0
$env:PYTHONIOENCODING="utf-8"
uv run whisker p4182r0 --workspace $ws --json --no-write  # SET_EXIT=0
```

Captures: `probe6_unset.txt` (1824 bytes), `probe6_set.txt` (1822 bytes).

### Parse check

```
json_equal True (parsed structures identical)
nonascii_in_stdout False (both captures)
bytes_identical False (line-ending / capture wrapper only)
```

No `Ü`, `Ã`, or `` in either capture. JSON does not include paper title text; non-ASCII title exists only in staged markdown.

**ANSWER:** **Both captures parse as JSON**; **no mojibake in stdout**; **no non-ASCII code points in emitted JSON** for this run (Unicode title not serialized into CLI JSON payload).
