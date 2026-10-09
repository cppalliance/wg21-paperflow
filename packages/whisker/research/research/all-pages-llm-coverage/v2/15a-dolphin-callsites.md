# 15a - Dolphin (ByteDance/Dolphin @ befa5da)
**Claims tested:** C1, C2
**Exhaustive:** yes

## Method
Clone: `packages/whisker/research/repos/Dolphin` @ `befa5dad986f86396b73cbd8c37e557b5770c902` (matches baseline pin `befa5da`).

Exact search commands run:
```bash
git -C packages/whisker/research/repos/Dolphin ls-tree -r HEAD --name-only
git -C packages/whisker/research/repos/Dolphin rev-parse HEAD
```
`rg` against the clone returned no matches (clone is gitignored from workspace indexers); all `.py` files were read in full via direct file read.

Files read in full (complete tracked Python corpus at this SHA):
- `demo_page.py` (396 lines)
- `demo_layout.py` (275 lines)
- `demo_element.py` (234 lines)
- `utils/utils.py` (537 lines)
- `utils/markdown_utils.py` (359 lines)

Also read: `README.md` (first 120 lines) for external eval references. No other tracked source files contain Python or model code at this SHA (`git ls-tree` lists 32 tracked files; no `tests/`, no `deployment/`, no eval harness).

Charter search-floor patterns checked manually in the five Python files: `model.chat`, `model.generate`, `from_pretrained`, `Qwen2_5_VL`, `transformers`, `openai`, `anthropic`, `litellm`, `vllm`, `ollama`, `LLM`, `VLM`, `pipeline(`, `predict`, `invoke`, `prompt`, `system_prompt`.

## Inventory

### VLM inference primitives (duplicate `DOLPHIN` class, one per demo script)

| file:line | function | input | output | role (C2) |
|---|---|---|---|---|
| `demo_page.py:103` | `DOLPHIN.chat` → `self.model.generate` | Resized PIL image(s) + text prompt(s) via Qwen2.5-VL processor | Decoded text string(s) | **extraction** (low-level VLM generate; all page/element calls funnel here) |
| `demo_layout.py:103` | `DOLPHIN.chat` → `self.model.generate` | Same | Same | **extraction** |
| `demo_element.py:100` | `DOLPHIN.chat` → `self.model.generate` | Same | Same | **extraction** |

### Page-level layout parsing (Stage 1)

| file:line | function | input | output | role (C2) |
|---|---|---|---|---|
| `demo_page.py:186` | `process_single_image` | Full **page image** (PIL); prompt `"Parse the reading order of this document."` | Layout string (bbox/label/tags reading-order sequence) | **extraction** (production page pipeline) |
| `demo_layout.py:173` | `process_single_layout` | Full **page image** (PIL); same layout prompt | Layout string | **extraction** (**demo script**: layout-only; no Stage 2 element parsing) |

### Element-level recognition (Stage 2)

| file:line | function | input | output | role (C2) |
|---|---|---|---|---|
| `demo_page.py:307` | `process_element_batch` | **Element crop** PIL image(s) batched (tables/equations/code/text); prompt per label type | Stripped text per element (table HTML, formula LaTeX, code, paragraph text) | **extraction** (production page pipeline; called from lines 269/273/277/281) |
| `demo_page.py:269` | `process_elements` → `process_element_batch` | Tab element crops; prompt `"Parse the table in the image."` | Table text appended to `recognition_results` | **extraction** (call path into 307) |
| `demo_page.py:273` | `process_elements` → `process_element_batch` | Equation crops; prompt `"Read formula in the image."` | Formula text | **extraction** (call path into 307) |
| `demo_page.py:277` | `process_elements` → `process_element_batch` | Code crops; prompt `"Read code in the image."` | Code text | **extraction** (call path into 307) |
| `demo_page.py:281` | `process_elements` → `process_element_batch` | Text/para crops (includes `distorted_page` full-page fallback at `demo_page.py:205-209`); prompt `"Read text in the image."` | Paragraph text | **extraction** (call path into 307) |
| `demo_element.py:152` | `process_element` | Single **element crop** image; prompt selected by `--element_type` (table/formula/code/text) | Parsed element text | **extraction** (**demo script**: element-only) |

### Non-LLM paths examined (not invocation sites)

| file:line | function | finding |
|---|---|---|
| `utils/markdown_utils.py:308-354` | `MarkdownConverter.convert` | Deterministic markdown assembly from recognition JSON; optional `post_process` applies regex/LaTeX/table normalization (`truncate_repeated_tail`, etc.). **No model call.** C2: **other** (deterministic output formatting, not LLM refinement). |
| `utils/utils.py:489-533` | `check_bbox_overlap` | Deterministic IoU heuristic routing photographed pages to `distorted_page` mode. **No model call.** |
| `utils/utils.py:55-91` | `convert_pdf_to_images` | PDF → PIL rasterization only. **No model call.** |
| `README.md:60-104` | (documentation) | OmniDocBench scores cited; eval is **external**, no in-repo benchmark harness at this SHA. |

### Model loading (not inference)

| file:line | function | note |
|---|---|---|
| `demo_page.py:26-27` | `DOLPHIN.__init__` | `AutoProcessor.from_pretrained`, `Qwen2_5_VLForConditionalGeneration.from_pretrained` — weight load only |
| `demo_layout.py:26-27` | `DOLPHIN.__init__` | Same |
| `demo_element.py:27-28` | `DOLPHIN.__init__` | Same |

**Call-site count (VLM inference via `model.chat`, distinct invocation lines): 4**
1. `demo_page.py:186` (page layout)
2. `demo_page.py:307` (element batch — sole generate site for tab/equ/code/text paths at 269/273/277/281)
3. `demo_layout.py:173` (layout demo)
4. `demo_element.py:152` (element demo)

**Low-level `model.generate` sites: 3** (one per duplicate `DOLPHIN.chat` in each demo file).

## Verdict on the claim(s)

**C1 (negative existential — no LLM judges already-produced output against source): CONFIRMED**

At SHA `befa5da`, every VLM invocation takes a **page image or element crop** as visual input and **produces** layout or recognition text. No code path accepts an already-produced markdown/JSON conversion output together with the source document and asks a model to verify, score, or judge fidelity. `MarkdownConverter` post-processing (`utils/markdown_utils.py`) is deterministic string normalization applied after extraction, not an LLM judge. README OmniDocBench numbers (`README.md:60-104`) reference external evaluation; no in-repo eval harness exists at this SHA.

**C2 (positive classification): CONFIRMED**

All four `model.chat` invocation lines classify as **extraction**. No **refinement** (LLM fixing its own pipeline output), **eval-harness** (offline LLM scoring), or other LLM roles found. Deterministic post-processing is **other** (non-LLM).

## Coverage gaps

None for source code at pinned SHA. `rg`/workspace glob could not index the gitignored clone; coverage was completed via `git ls-tree -r HEAD --name-only` (32 files) and full read of all five tracked `.py` files. README references `deployment/vllm/` and `deployment/tensorrt_llm/` but those directories are **not present** in the tracked tree at `befa5da`.

## What could still hide a counterexample

- Untracked or submodule content outside the pinned commit (not applicable: working tree clean at `befa5da`).
- External eval scripts or deployment wrappers referenced in README but not committed at this SHA.
- Runtime dynamic imports or notebook code not in the repository.
