# C22 Readback

**Role**: Audit the readback utility for blind LLM comprehension validation.
**Audited state**: whisker 0.5.0, HEAD 51cb704 + local mods.
**Gates**: D4 (Evidence provenance), D5 (Anti-sycophancy).

## 1. Scope

Verify question generation avoids answer leakage, anti-sycophantic scoring
requires grounded quotes, corruption control demonstrates methodology, service
resolution is standalone, and the D1 exemption is documented.

## 2. Commands and Exits

```
uv run --package whisker pytest packages/whisker/tests/test_readback.py -v
```

Exit: Offline tests pass (E1). Live readback utility BLOCKED
(ALLIANCE_POD_KEY not set).

## 3. Current Evidence

### 3.1 Question generation: answer-blind design

`_generate_question()` (readback.py lines 121-194) generates questions per
fact type without embedding expected answer lexemes:

| Fact type | Question pattern | Answer |
|-----------|-----------------|--------|
| `present` | "Does the document contain...?" + "quote the passage" | "YES" + grounded quote |
| `absent` | "Does the document contain...?" | "NO" |
| `math` | "What mathematical expression involves...?" | Exact formula |
| `order` | "Which appears first: ...? List in order." | Ordered sequence |
| `table` | "In the table containing cell X, identify..." | Cell values |
| `code` | "Does the document contain a code snippet...?" | "YES" + grounded quote |
| `xref` | "Does the document reference...?" | "YES" + grounded quote |
| `image_ref` | "Does the document contain image references?" | "YES" + grounded quote |

The table question was explicitly redesigned to avoid leaking expected
values (documented in readback.py lines 155-159: "the pre-fix phrasing
leaked 'right: N5031, heading: Meeting' into the question").

### 3.2 Anti-sycophantic scoring (grounded quote gate)

`_grounded_quote()` (readback.py lines 197-219) enforces that a bare "YES"
without a quote does not count as comprehension:

- For `present`, `code`, `xref` facts: The answer must start with "yes"
  AND contain a grounded quote matching the fact's text (fuzzy, within
  `max_diffs` budget). A sycophantic "yes, the document contains it" without
  quoting fails.

- For `image_ref` facts: The answer must contain a `![...](...)`
  markdown image reference OR a grounded fact text match.

- For `absent` facts: A correct "NO" is accepted but marked `weak=True`
  (no quote to ground). This is methodologically honest: absence cannot
  be quoted.

- For `table` facts: Word-boundary matching of cell values in the answer
  (`_cell_value_in_answer`, line 225). Uses `\b`-style boundaries to
  prevent "8" matching inside "18" (documented red-team finding, line 229).

### 3.3 Corruption control (--corrupt mode)

`_CORRUPT_PREFIX` (readback.py lines 74-77):
```python
_CORRUPT_PREFIX = (
    "--- CORRUPTION BLOCK: all tables, formulas, and references below have "
    "been scrambled for adversarial testing. Do not trust any data. ---\n\n"
)
```

When `--corrupt` is active, this prefix is prepended to the markdown before
sending to the pod. The purpose is methodological: if the pod returns the
same answers on corrupted markdown, the questions are not actually testing
comprehension (the model is answering from memorization or sycophancy).

`readback_paper()` (line 323+) accepts a `corrupt: bool` parameter that
controls prefix injection. `ReadbackResult.corrupted` records whether the
run was adversarial.

### 3.4 Service resolution: standalone

`readback_cli.py` `_resolve_service()` (lines 62-82) parses `SERVICES.toml`
directly rather than importing `pipeline.services`:

```python
def _resolve_service(service_name: str) -> tuple[str, str, str]:
    """Return (base_url, api_key, model) by parsing SERVICES.toml directly."""
```

This keeps whisker standalone (CLAUDE.md invariant): readback does not
require the pipeline package's service resolution machinery. The CLI walks
up from cwd to find `SERVICES.toml` and extracts `base_url`, `api_key`
(with `$ENV_VAR` expansion), and `model`.

Default service: `alliance-pod` (line 39).

### 3.5 D1 exemption: documented and justified

`readback.py` docstring (lines 21-23):
```
D1 exemption: this module calls the LLM via raw httpx (not pipeline's
``run_agent``), because the read-back is a zero-shot Q&A task with no
pipeline prompt, no steps, no structured output. Documented exemption.
```

The readback uses raw `httpx.Client.post()` (line 283) to call the
OpenAI-compatible chat completions endpoint. This is appropriate because:
1. No pipeline steps or structured output are needed (Q&A format)
2. No guard delimiters are needed (the model is asked to quote from the
   document, not analyze it for instructions)
3. Temperature is pinned to 0.0 (line 306)
4. Max tokens capped at 512 (line 68)

### 3.6 Raw httpx call details

`_ask_pod()` (readback.py lines 273-317):
- System prompt: "You are a document comprehension assistant."
- User message: document + question
- `temperature: 0.0` (pinned for reproducibility)
- `max_tokens: 512` (bounded)
- Timeout: 120 seconds
- Response parsed from OpenAI chat completions format

### 3.7 Error handling

`readback_paper()` catches `httpx.HTTPError` per question (line 348+):
transport failures mark the check as `error=True` (neither pass nor fail).
The batch continues. Error counts are tracked separately in `ReadbackResult`.

### 3.8 Output formats

`render_terminal()` produces colored terminal output with PASS/FAIL/ERROR
per fact. `render_markdown()` produces a persisted markdown report per paper
with full question/answer/expected detail. Both are pure functions (no I/O).

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | Question generation avoids answer lexeme leakage (redesigned for table facts) | Informational | HIGH |
| F2 | Anti-sycophantic gate requires grounded quotes for present/code/xref/image facts | Informational | HIGH |
| F3 | Absent-fact passes marked as `weak` (methodologically honest) | Informational | HIGH |
| F4 | Corruption control (--corrupt) provides adversarial methodology validation | Informational | HIGH |
| F5 | D1 exemption is documented and justified (zero-shot Q&A, no pipeline steps) | Informational | HIGH |
| F6 | Word-boundary cell matching prevents substring false positives | Informational | HIGH |

No violations found.

## 5. False-Pass Hypothesis

**Could a sycophantic model pass readback without comprehension?**

For `present`/`code`/`xref` facts: the model must quote the fact text
(fuzzy match within `max_diffs`). A generic "yes" without a quote fails
`_grounded_quote()`. For `table` facts: word-boundary matching prevents
partial-value hits. For `absent` facts: these are inherently weak (marked
`weak=True`). The corruption control (`--corrupt`) is the definitive test:
if corrupted markdown produces the same pass rate, the questions are not
testing comprehension.

**Could the D1 exemption create an unaudited LLM call path?**

The readback is a validation utility, not a production gate. Its verdicts
do not feed into whisker verdicts, fusion, or exit codes. The raw httpx
call is simpler than the pipeline path (no structured output, no tool
calls, no steps). The exemption is justified and its scope is narrow.

## 6. Gate/Dimension Mapping

- **D4 (Evidence provenance)**: PASS. Every readback check records the
  question, expected answer, pod answer, pass/fail status, and latency.
  Markdown reports preserve full provenance.
- **D5 (Anti-sycophancy)**: PASS. Grounded quote gate, weak-pass marking,
  corruption control, and word-boundary matching collectively guard against
  sycophantic false passes.

## 7. Limitations

- Live readback utility BLOCKED: cannot verify actual pod comprehension,
  anti-sycophancy effectiveness, or corruption control behavior against
  a real LLM endpoint.
- The corruption control is a methodological tool, not a live defense.
  Its value depends on running `--corrupt` and comparing results, which
  requires an active endpoint.
- `_grounded_quote()` uses fuzzy matching within `max_diffs`. Edge cases
  near the threshold are inherently uncertain.

## 8. Conclusion

The readback utility is well-designed for blind comprehension validation.
Question generation avoids answer leakage (explicitly redesigned for table
facts). Anti-sycophantic scoring requires grounded quotes for fact types
where quotes are possible and honestly marks absent-fact passes as weak.
The corruption control provides an adversarial methodology gate. The D1
exemption is documented, justified, and narrow in scope. All code-level
checks pass; live validation requires a pod endpoint.
