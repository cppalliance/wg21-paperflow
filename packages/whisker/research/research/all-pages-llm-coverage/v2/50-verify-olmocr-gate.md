# 50 - olmocr-bench gate + BaselineTest (C4a)
**Claims tested:** C4a
**Exhaustive:** yes

## Method
Files read in full (no truncation):
- `packages/whisker/research/repos/olmocr/olmocr/bench/benchmark.py` (464 lines)
- `packages/whisker/research/repos/olmocr/olmocr/bench/tests.py` (881 lines)

No `rg` searches run; both files were read end-to-end.

## Inventory

### (a) Gate: refuse scoring when (pdf, page) has no test

| file:line | role |
|---|---|
| `benchmark.py:246-251` | After loading tests and BaselineTest injection, iterates every PDF page; if no test covers `(pdf, page)` and `--force` is not set, prints error and `sys.exit(1)` before any candidate scoring. |
| `benchmark.py:253-254` | `--skip_baseline` removes injected baseline tests after the gate (gate already ran). |
| `benchmark.py:69-77` | Separate pre-scoring check: missing MD repeats for a PDF (not the dataset-entry gate). |
| `benchmark.py:95-101` | Per-test missing page MD files during scoring (records failure, does not abort whole bench). |

**Verbatim condition and error message (`benchmark.py:246-251`):**

```python
    for pdf in pdf_basenames:
        pdf_doc = PdfReader(os.path.join(pdf_folder, pdf))
        for page in range(1, len(pdf_doc.pages) + 1):
            if not any(test for test in all_tests if test.pdf == pdf and test.page == page) and not args.force:
                print(f"No dataset entry found for pdf {pdf} page {page}")
                sys.exit(1)
```

- Condition: `not any(test for test in all_tests if test.pdf == pdf and test.page == page) and not args.force`
- Error message: `No dataset entry found for pdf {pdf} page {page}` (printed to stdout; process exits with code 1)

### (b) BaselineTest auto-injection: when it fires and what it checks

| file:line | role |
|---|---|
| `benchmark.py:241-244` | Auto-injection site (runs after JSONL load, before the per-page gate). |
| `benchmark.py:175` | `--skip_baseline` CLI flag documents baseline purpose. |
| `tests.py:483-545` | `BaselineTest` class and `run()` checks. |

**When injection fires (`benchmark.py:241-244`):**

```python
    for pdf in pdf_basenames:
        if not any(t.type == "baseline" for t in all_tests if t.pdf == pdf):
            all_tests.append(BaselineTest(id=f"{pdf}_baseline", pdf=pdf, page=1, type="baseline"))
            test_to_jsonl[all_tests[-1].id] = "baseline"
```

- Fires once per PDF in `pdf_basenames` when **no existing test with `type == "baseline"`** for that PDF is already in `all_tests`.
- Injected test is always **`page=1`** (not one BaselineTest per page).
- Runs **before** the gate at `benchmark.py:246-251`; the gate still requires an explicit test entry for every page (BaselineTest on page 1 only satisfies page 1).

**BaselineTest checks quoted from `tests.py` (`BaselineTest.run`, lines 499-545):**

Blank-page short-circuit (`max_length` set):

```python
        if self.max_length is not None:
            if self.max_length_skips_image_alt_tags:
                # Remove markdown image tags like ![alt text](image.png) from the text length count
                content_for_length_check = re.sub(r"!\[.*?\]\(.*?\)", "", content)
                base_content_len = len("".join(c for c in content_for_length_check if c.isalnum()).strip())

            if base_content_len > self.max_length:
                return False, f"{base_content_len} characters were output for a page we expected to be blank"
            else:
                return True, ""
```

Non-blank baseline checks (default path when `max_length is None`):

```python
        if base_content_len == 0:
            return False, "The text contains no alpha numeric characters"
```

Repeat detection:

```python
        d = RepeatDetector(max_ngram_size=5)
        d.add_letters(content)
        repeats = d.ngram_repeats()

        for index, count in enumerate(repeats):
            if count > self.max_repeats:
                return False, f"Text ends with {count} repeating {index+1}-grams, invalid"
```

Disallowed character sets (when `check_disallowed_characters` is True, default):

```python
        pattern = re.compile(
            r"["
            r"\u4e00-\u9FFF"  # CJK Unified Ideographs (Chinese characters)
            r"\u3040-\u309F"  # Hiragana (Japanese)
            r"\u30A0-\u30FF"  # Katakana (Japanese)
            r"\U0001F600-\U0001F64F"  # Emoticons (Emoji)
            r"\U0001F300-\U0001F5FF"  # Miscellaneous Symbols and Pictographs (Emoji)
            r"\U0001F680-\U0001F6FF"  # Transport and Map Symbols (Emoji)
            r"\U0001F1E0-\U0001F1FF"  # Regional Indicator Symbols (flags, Emoji)
            r"]",
            flags=re.UNICODE,
        )

        matches = pattern.findall(content)
        if self.check_disallowed_characters and matches:
            return False, f"Text contains disallowed characters {matches}"

        return True, ""
```

Class docstring intent (`tests.py:485-489`):

```python
    """
    This test makes sure that several baseline quality checks pass for the output generation.

    Namely, the output is not blank, not endlessly repeating, and contains characters of the proper
    character sets.

    """
```

### (c) LLM calls in scoring path — imports and external calls

**Scoring path definition:** `main()` from test load through gate, then `evaluate_candidate()` → `process_test()` → `test.run(md_content)` (`benchmark.py:287-288`, `benchmark.py:116`).

#### `benchmark.py` imports (all lines 16-30)

| import | LLM-capable? |
|---|---|
| `argparse` | no |
| `glob` | no |
| `os` | no |
| `random` | no |
| `re` | no |
| `sys` | no |
| `concurrent.futures.ThreadPoolExecutor, as_completed` | no |
| `typing.Dict, List, Tuple` | no |
| `pypdf.PdfReader` | no |
| `tqdm.tqdm` | no |
| `.report.generate_html_report` | not in core scoring loop; report-only (`benchmark.py:417-418`) |
| `.tests.BaselineTest, BasePDFTest, load_tests, save_tests` | see tests.py |
| `.utils.calculate_bootstrap_ci` | post-score statistics only (`benchmark.py:330`); not LLM |

#### `benchmark.py` external calls on scoring path

| file:line | call | LLM-capable? |
|---|---|---|
| `benchmark.py:227` | `load_tests(jsonl_path)` | no |
| `benchmark.py:247` | `PdfReader(...)` | no |
| `benchmark.py:249-251` | gate `any(...)`, `print(...)`, `sys.exit(1)` | no |
| `benchmark.py:62` | `glob.glob(...)` | no |
| `benchmark.py:109-110` | `open(md_path)`, `f.read()` | no |
| `benchmark.py:116` | `test.run(md_content)` | dispatches to tests.py (below) |
| `benchmark.py:142-145` | `ThreadPoolExecutor`, `executor.submit`, `tqdm`, `future.result()` | no |
| `benchmark.py:330` | `calculate_bootstrap_ci(...)` | no |

#### `tests.py` imports (all lines 1-17)

| import | LLM-capable? |
|---|---|
| `json` | no |
| `os` | no |
| `re` | no |
| `unicodedata` | no |
| `concurrent.futures.ThreadPoolExecutor, as_completed` | no (load_tests only) |
| `dataclasses.asdict, dataclass` | no |
| `enum.Enum` | no |
| `typing.Dict, List, Optional, Tuple, Union` | no |
| `fuzzysearch.find_near_matches` | no |
| `rapidfuzz.fuzz` | no |
| `tqdm.tqdm` | no |
| `olmocr.repeatdetect.RepeatDetector` | no |
| `.katex.render.compare_rendered_equations, render_equation` | no (KaTeX/LaTeX render) |
| `.table_parsing.parse_html_tables, parse_markdown_tables` | no |

#### `tests.py` external calls reachable from `test.run()` on scoring path

| test class | file:line | external call | LLM-capable? |
|---|---|---|---|
| `TextPresenceTest.run` | `tests.py:169` | `fuzz.partial_ratio(...)` | no |
| `TextOrderTest.run` | `tests.py:214-215` | `find_near_matches(...)` | no |
| `FormatTest.run` | `tests.py:324` | `fuzz.partial_ratio(...)` | no |
| `TableTest.run` | `tests.py:400-404` | `parse_markdown_tables`, `parse_html_tables` | no |
| `TableTest.run` | `tests.py:415,437` | `fuzz.ratio(...)` | no |
| `BaselineTest.run` | `tests.py:520-522` | `RepeatDetector(...)`, `.add_letters`, `.ngram_repeats()` | no |
| `MathTest.run` | `tests.py:561` | `render_equation(self.math)` (init) | no |
| `MathTest.run` | `tests.py:600-607` | `fuzz.ratio`, `render_equation`, `compare_rendered_equations` | no |
| `FootnoteTest.run` | `tests.py:722,748` | `fuzz.partial_ratio(...)` | no |
| `load_tests` | `tests.py:846-858` | `open`, `ThreadPoolExecutor`, `load_single_test` | no (not on per-candidate scoring path after initial load) |

**LLM/VLM API patterns in both files:** none (`openai`, `anthropic`, `chat.completions`, `generate_content`, `litellm`, `vllm`, `ollama`, `transformers`, etc. absent).

## Verdict on the claim(s)

**PARTIALLY CONFIRMED**

- **CONFIRMED:** olmocr-bench refuses to run scoring when any `(pdf, page)` pair lacks a test entry, unless `--force` (`benchmark.py:249-251`).
- **REFUTED (wording in C4a):** auto-injection is **not per-page**. It adds at most one `BaselineTest` per PDF at **`page=1` only** when no baseline test exists for that PDF (`benchmark.py:241-244`). Pages 2+ still require explicit dataset entries or the gate aborts.
- **CONFIRMED:** no LLM/VLM call anywhere in the scoring path through `benchmark.py` + `tests.py`.

## Coverage gaps

None. Both assigned files read in full.

## What could still hide a counterexample

- LLM usage in other bench modules imported at runtime but not referenced by `benchmark.py` or `tests.py` (e.g. `.report.generate_html_report`, `.utils.calculate_bootstrap_ci`, `.katex.render`, `.table_parsing`) was not read; not on the scoring path enumerated above.
- Indirect LLM inside `RepeatDetector`, `rapidfuzz`, or `pypdf` would be third-party library internals, not present in these two files.
