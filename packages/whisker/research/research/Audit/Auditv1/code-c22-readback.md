# C22 - Readback Proxy Auditor

**Mandate:** Verify clean/corrupt readback, scoring methodology, non-CI contract.
**Focus dimensions:** D4 (no parallel_tool_calls), D5 (no per-call temperature override).

---

## 1. Anti-Sycophantic Scoring (`readback.py`)

### 1.1 Bare YES Never Passes

| Severity | **PASS** |
|----------|----------|
| Claim | A bare "YES" without a grounded quote of the fact's needle fails for `present`, `code`, `xref`, and `image_ref` types. |
| Evidence | `readback.py:244-247`: `FACT_PRESENT` requires `answer_lower.startswith("yes")` AND `_grounded_quote(fact, answer)`. `readback.py:197-219`: `_grounded_quote` checks that the fact text (fuzzy within `max_diffs`) appears in the answer. For `image_ref`, requires `_IMAGE_REF_RE.search(answer)` (actual `![...](...)` syntax). `test_readback.py:44-47`: `test_present_bare_yes_fails` asserts `not passed` for "YES." without a quote. `test_readback.py:50-55`: `test_present_yes_with_quote_passes` confirms quote grants pass. `test_readback.py:58-62`: `test_present_yes_with_unrelated_quote_fails` confirms wrong quote fails. |
| Affected gate | D4 |
| Confidence | 0.99 |
| False-pass hypothesis | A sycophantic model saying "YES" with a paraphrase but not the exact needle text. Mitigated: `_present_within` uses the fact's own `max_diffs` fuzzy budget (same as Lane 3). |
| False-fail hypothesis | A model quoting the needle with minor formatting differences. Mitigated: `normalized_text` folding and `max_diffs` budget. |

### 1.2 Code/Xref Require Raw-Surface Quote

| Severity | **PASS** |
|----------|----------|
| Claim | `code` and `xref` facts require the raw-surface needle in the answer, not the normalized form. |
| Evidence | `readback.py:213-215`: `FACT_CODE` and `FACT_XREF` use `_raw_surface` for both needle and haystack. `test_readback.py:65-75`: `test_code_requires_raw_quote` and `test_xref_requires_quote` confirm bare YES fails and quoted content passes. |
| Affected gate | D4 |
| Confidence | 0.98 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

### 1.3 Image_ref Requires Image Syntax Quote

| Severity | **PASS** |
|----------|----------|
| Claim | `image_ref` facts require either `![...](...)` regex match or the fact's text as a raw-surface substring in the answer. |
| Evidence | `readback.py:205-212`: checks `_IMAGE_REF_RE.search(answer)` first, then falls back to `_present_within` if `fact.text` is non-empty. `test_readback.py:78-83`: `test_image_ref_requires_image_syntax_quote` asserts bare "YES" fails and quoted image syntax passes. |
| Affected gate | D4 |
| Confidence | 0.98 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

### 1.4 Absent: Weak Pass

| Severity | **PASS** |
|----------|----------|
| Claim | `absent` facts pass on "NO" but are flagged `weak` (a correct NO cites nothing). |
| Evidence | `readback.py:248-250`: returns `(ok, ok)` where `ok = answer_lower.startswith("no")`. The second `ok` sets `weak=True` on pass. `test_readback.py:86-90`: `test_absent_no_is_weak_pass` asserts `passed=True, weak=True`. |
| Affected gate | D4 |
| Confidence | 0.99 |
| False-pass hypothesis | A model saying "NO" to a present fact. This is a model quality issue, not a scoring bug. The adversarial `--corrupt` mode is the control for this. |
| False-fail hypothesis | None. |

---

## 2. Word-Boundary Table Scoring

| Severity | **PASS** |
|----------|----------|
| Claim | Expected cell value "8" does not match "18" in the answer (word-boundary matching prevents substring exploits). |
| Evidence | `readback.py:222-234`: `_cell_value_in_answer` uses regex `(?<![0-9a-z]){}(?![0-9a-z])` on `_norm_cell`-normalized values. `test_readback.py:104-122`: `test_cell_value_8_does_not_match_18`, `test_cell_value_boundary_with_punctuation`, `test_table_answer_substring_exploit_fails` exhaustively test boundary behavior. |
| Affected gate | D5 |
| Confidence | 0.99 |
| False-pass hypothesis | None: the regex explicitly rejects digit-adjacent matches. |
| False-fail hypothesis | None: punctuation-wrapped values like "(8)" correctly match. |

---

## 3. `--corrupt` Adversarial Control (`readback.py`)

### 3.1 Corruption Mechanics

| Severity | **PASS** |
|----------|----------|
| Claim | `--corrupt` deterministically scrambles table rows (reverses pipe-delimited cells), flips relational operators (`>=` to `<=`), and shifts formula exponents (`^N` to `^(N+1)`). |
| Evidence | `readback.py:371-387`: `_corrupt_markdown` reverses cells in pipe-containing lines, `re.sub(r">=", "<=")` flips operators, and `re.sub(r"\^(\d+)", ...)` increments exponents. `readback.py:330-333`: `readback_paper` prepends `_CORRUPT_PREFIX` and applies `_corrupt_markdown` when `corrupt=True`. |
| Affected gate | D5 |
| Confidence | 0.95 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

### 3.2 Corruption Limitations

| Severity | **LOW** |
|----------|---------|
| Claim | The corruption function has known limitations: (1) it flips ALL `>=` to `<=`, including in code blocks and non-math contexts; (2) it does not flip `<=` to `>=` (asymmetric); (3) it reverses entire lines containing pipes, including non-table lines. |
| Evidence | `readback.py:383-385`: no fence-awareness for operator flipping. Line 380: `"|" in line` is broad. |
| Affected gate | D5 |
| Confidence | 0.85 |
| False-pass hypothesis | Over-corruption might make EVERY question fail, including those not targeting corrupted content, making the control less informative (proves sensitivity but not specificity). |
| False-fail hypothesis | Under-corruption on `<=` or code blocks means some facts targeting those constructs might still pass under corruption. |

---

## 4. D1 Exemption: Raw httpx

| Severity | **PASS** |
|----------|----------|
| Claim | `readback.py` calls the pod via raw `httpx`, not `pipeline.run_agent`, as a documented D1 exemption. |
| Evidence | `readback.py:1-24` (module docstring): "D1 exemption: this module calls the LLM via raw httpx (not pipeline's run_agent), because the read-back is a zero-shot Q&A task with no pipeline prompt, no steps, no structured output." `readback.py:35`: `import httpx`. `readback.py:273-317`: `_ask_pod` uses `client.post(f"{base_url}/chat/completions", ...)`. No imports from `pipeline`. |
| Affected gate | D4, D5 |
| Confidence | 0.99 |
| False-pass hypothesis | None: the exemption is documented and justified. |
| False-fail hypothesis | None. |

### 4.1 Temperature Pinning (D5 Compliance)

| Severity | **PASS** |
|----------|----------|
| Claim | The readback call uses `temperature: 0.0` (pinned, not overridden per-call). |
| Evidence | `readback.py:306`: `"temperature": 0.0` in the request JSON. This is hardcoded, not parameterized. |
| Affected gate | D5 |
| Confidence | 0.99 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

---

## 5. Windows UTF-8 Fix

| Severity | **PASS** |
|----------|----------|
| Claim | `readback_cli.py` reconfigures stdout to UTF-8 with `errors="replace"` to handle Windows cp1252 consoles. |
| Evidence | `readback_cli.py:132-133`: `if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")`. The `hasattr` guard handles environments where `reconfigure` is unavailable (e.g., redirected pipes, some test runners). |
| Affected gate | D5 |
| Confidence | 0.98 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

---

## 6. Transport Failures as ERROR State

| Severity | **PASS** |
|----------|----------|
| Claim | Transport failures (timeouts, connection resets) are marked as `error=True` on the check, excluded from pass/fail counts. |
| Evidence | `readback.py:344-349`: `except (httpx.HTTPError, KeyError)` sets `error = True`, `passed = False`, `weak = False`. `readback.py:109-118`: `pass_count` filters `c.passed and not c.error`; `fail_count` filters `not c.passed and not c.error`; `error_count` filters `c.error`. `test_readback.py:129-147`: `test_transport_error_marked_error_not_fail` asserts `check.error=True`, `result.error_count==1`, `result.fail_count==0`, `result.pass_count==0`. |
| Affected gate | D4 |
| Confidence | 0.99 |
| False-pass hypothesis | None: structurally enforced by the `not c.error` filter. |
| False-fail hypothesis | None. |

### 6.1 Error Rendering

| Severity | **PASS** |
|----------|----------|
| Claim | ERROR state is visually distinct in both terminal and markdown renders. |
| Evidence | `readback.py:401-408`: error checks render with `[!] ERROR` marker. `readback.py:441-443`: markdown renders as `**ERROR** (transport, rerun)`. `test_readback.py:150-166`: `test_render_shows_error_and_weak_states` asserts "ERROR" and "weak" appear in both formats. |
| Affected gate | D5 |
| Confidence | 0.98 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

---

## 7. Service Resolution (`readback_cli.py`)

| Severity | **PASS** |
|----------|----------|
| Claim | `readback_cli.py` resolves the service endpoint by parsing `SERVICES.toml` directly with stdlib `tomllib`, not by importing `pipeline.services.load_services()`. |
| Evidence | `readback_cli.py:43-82`: `_find_services_toml` walks up from cwd, `_resolve_service` parses with `tomllib`, extracts `base_url`, `api_key` (expanding `$ENV_VAR`), and `model`. Docstring (lines 47-52) explains why: `pipeline.services.load_services` returns `ModelBackend` instances with private attributes. |
| Affected gate | D4 |
| Confidence | 0.97 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

### 7.1 API Key Environment Variable Expansion

| Severity | **PASS** |
|----------|----------|
| Claim | API keys starting with `$` are expanded from environment variables. |
| Evidence | `readback_cli.py:76-78`: `if api_key_raw.startswith("$"): api_key = os.environ.get(api_key_raw[1:], "")`. Line 151-152: empty key after expansion is caught as an error. |
| Affected gate | D5 |
| Confidence | 0.95 |
| False-pass hypothesis | A `$$` prefix is not handled (double-dollar escaping). Low risk: SERVICES.toml keys are not user-facing input. |
| False-fail hypothesis | None. |

---

## 8. Question Generation (Persona 22 Critique)

| Severity | **PASS** |
|----------|----------|
| Claim | Questions are generated from fact metadata without embedding answer lexemes (the blind-readback methodology critique). |
| Evidence | `readback.py:121-194`: `_generate_question` uses type-specific phrasing. For `table` facts (lines 160-173): asks for "the cell immediately {direction} of {cell}" without embedding the expected neighbor value. For `present`/`code`/`xref`: asks YES/NO + quote without embedding the needle. `test_readback.py:93-98`: `test_xref_and_image_ref_questions_request_quotes` asserts "quote" appears in the question (grounding is only fair if the question asks for it). |
| Affected gate | D4 |
| Confidence | 0.95 |
| False-pass hypothesis | The `math` question (line 140-145) includes the symbols from the fact text, which could be considered leaking. Mitigated: the question asks the model to "quote the exact formula", not confirm a value, so the symbols are a search hint, not an answer. |
| False-fail hypothesis | None. |

---

## 9. Test Coverage (`test_readback.py`)

| Severity | **PASS** |
|----------|----------|
| Claim | The test suite covers anti-sycophancy (6 tests), word-boundary scoring (4 tests), transport errors (1 test), and rendering (1 test). |
| Evidence | `test_readback.py`: 12 tests total. No LLM calls (all mocked or pure-function tests). |
| Affected gate | D4, D5 |
| Confidence | 0.93 |
| False-pass hypothesis | No test for `_corrupt_markdown` behavior. The corruption function is simple enough for code inspection, but a test would strengthen confidence. |
| False-fail hypothesis | None. |

**Finding (LOW):**

| Severity | LOW |
|----------|-----|
| Claim | `_corrupt_markdown` has no dedicated unit test. |
| Evidence | `test_readback.py`: no test class or function name matching "corrupt". |
| Affected gate | D5 |
| Confidence | 0.90 |
| False-pass hypothesis | A regression in corruption logic would go undetected by the offline test suite. |
| False-fail hypothesis | None. |

---

## Summary

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | Bare YES never passes (anti-sycophancy enforced) | CRITICAL | PASS |
| 2 | Grounded quotes required for all YES/NO types | HIGH | PASS |
| 3 | Word-boundary table scoring prevents substring exploits | HIGH | PASS |
| 4 | `--corrupt` scrambles tables, operators, exponents | MEDIUM | PASS |
| 5 | Corruption function has no fence-awareness (minor) | LOW | NOTED |
| 6 | D1 exemption documented and justified | HIGH | PASS |
| 7 | Temperature pinned at 0.0 (D5 compliant) | HIGH | PASS |
| 8 | Windows UTF-8 fix with graceful degradation | MEDIUM | PASS |
| 9 | Transport errors are ERROR, excluded from pass/fail | HIGH | PASS |
| 10 | No unit test for `_corrupt_markdown` | LOW | NOTED |
| 11 | Question generation avoids answer-lexeme leakage | MEDIUM | PASS |

**Auditor verdict: The readback subsystem is sound.** Anti-sycophantic scoring is structurally enforced with six targeted tests. The D1 exemption is documented and justified. Two low-severity findings noted (corruption fence-awareness and test gap).
