# 51 - langextract suppress_parse_errors (C4b)
**Claims tested:** C4b
**Exhaustive:** yes

## Method
Search commands run:
- `rg -n "suppress_parse_errors|suppressed|suppress" packages/whisker/research/repos/langextract/langextract --glob "*.py"`
- `rg -n "InferenceOutputError" packages/whisker/research/repos/langextract --glob "*.py"`
- `rg -n "class (AnnotatedDocument|Document|Extraction)" packages/whisker/research/repos/langextract --glob "*.py"`

Files read in full or in targeted sections:
- `langextract/__init__.py`
- `langextract/extraction.py` (lines 45-427)
- `langextract/annotation.py` (lines 163-445, 532-598)
- `langextract/resolver.py` (lines 77-325)
- `langextract/core/data.py`
- `langextract/core/types.py`
- `langextract/core/exceptions.py` (lines 125-130)
- `langextract/chunking.py` (TextChunk dataclass, lines 39-58)
- `langextract/data_lib.py`
- `langextract/exceptions.py`

## Inventory

### (a) `suppress_parse_errors` parameter default in every public entry point signature

| file:line | entry point | signature exposure | default |
|---|---|---|---|
| `langextract/__init__.py:53-55` | `extract()` (top-level wrapper) | passthrough `*args, **kwargs`; no `suppress_parse_errors` in signature | effective default from `extraction.py:365` |
| `langextract/extraction.py:45-75` | `extract()` | not a direct parameter; exposed via `resolver_params: dict \| None = None` at line 60 | effective `True` at `extraction.py:365` |
| `langextract/extraction.py:136-138` | `extract()` docstring | documents resolver_params key | `"Default is True in extract()."` |
| `langextract/resolver.py:276-279` | `Resolver.resolve()` | explicit parameter | `suppress_parse_errors: bool = False` |
| `langextract/annotation.py:209-220` | `Annotator.annotate_documents()` | `**kwargs` only; no explicit `suppress_parse_errors` in signature | routed to `_annotate_documents_single_pass`; see below |
| `langextract/annotation.py:532-544` | `Annotator.annotate_text()` | `**kwargs` only; no explicit `suppress_parse_errors` in signature | routed via `annotate_documents(**kwargs)` |
| `langextract/annotation.py:285-296` | `_annotate_documents_single_pass()` (internal callee, not public API) | explicit parameter | `suppress_parse_errors: bool = False` |

**Verbatim signatures and defaults:**

`langextract/__init__.py:53-55`:
```python
def extract(*args: Any, **kwargs: Any):
  """Top-level API: lx.extract(...)."""
  return extract_func(*args, **kwargs)
```

`langextract/extraction.py:60`:
```python
    resolver_params: dict | None = None,
```

`langextract/extraction.py:136-138`:
```python
        'suppress_parse_errors' (bool): Suppresses chunk-level parse
        errors so one malformed chunk does not fail the entire document.
        Default is True in extract().
```

`langextract/extraction.py:365`:
```python
  alignment_kwargs.setdefault("suppress_parse_errors", True)
```

`langextract/resolver.py:276-279`:
```python
  def resolve(
      self,
      input_text: str,
      suppress_parse_errors: bool = False,
```

`langextract/annotation.py:209-220` (`annotate_documents`; no explicit param):
```python
  def annotate_documents(
      self,
      documents: Iterable[data.Document],
      resolver: resolver_lib.AbstractResolver | None = None,
      max_char_buffer: int = 200,
      batch_length: int = 1,
      debug: bool = True,
      extraction_passes: int = 1,
      context_window_chars: int | None = None,
      show_progress: bool = True,
      tokenizer: tokenizer_lib.Tokenizer | None = None,
      **kwargs,
  ) -> Iterator[data.AnnotatedDocument]:
```

`langextract/annotation.py:532-544` (`annotate_text`; no explicit param):
```python
  def annotate_text(
      self,
      text: str,
      resolver: resolver_lib.AbstractResolver | None = None,
      max_char_buffer: int = 200,
      batch_length: int = 1,
      additional_context: str | None = None,
      debug: bool = True,
      extraction_passes: int = 1,
      context_window_chars: int | None = None,
      show_progress: bool = True,
      tokenizer: tokenizer_lib.Tokenizer | None = None,
      **kwargs,
  ) -> data.AnnotatedDocument:
```

### (b) Code path: failed parse → empty result and continues

**Parse failure handler (`langextract/resolver.py:309-321`):**

```python
    except exceptions.FormatError as e:
      if suppress_parse_errors:
        logging.warning("Skipping chunk: parse error: %s", e)
        return []
      raise ResolverParsingError(str(e)) from e

    try:
      processed_extractions = self.extract_ordered_extractions(extraction_data)
    except ValueError as e:
      if suppress_parse_errors:
        logging.warning("Skipping chunk: schema error: %s", e)
        return []
      raise ResolverParsingError(str(e)) from e
```

**Caller continues after empty resolve (`langextract/annotation.py:404-432`):**

```python
          resolved_extractions = resolver.resolve(
              scored_outputs[0].output,
              debug=debug,
              suppress_parse_errors=suppress_parse_errors,
              **kwargs,
          )

          token_offset = (
              text_chunk.token_interval.start_index
              if text_chunk.token_interval
              else 0
          )
          char_offset = (
              text_chunk.char_interval.start_pos
              if text_chunk.char_interval
              else 0
          )

          aligned_extractions = resolver.align(
              resolved_extractions,
              text_chunk,
              token_offset=token_offset,
              char_offset=char_offset,
              **kwargs,
          )

          for extraction in aligned_extractions:
            per_doc[text_chunk.document_id].append(extraction)
```

When `resolve()` returns `[]`, the loop over `aligned_extractions` adds nothing and proceeds to the next chunk in the batch.

### (c) Code path: raises on empty inference output (`InferenceOutputError`)

**Definition (`langextract/core/exceptions.py:125-130`):**

```python
class InferenceOutputError(LangExtractError):
  """Exception raised when no scored outputs are available from the language model."""

  def __init__(self, message: str):
    self.message = message
    super().__init__(self.message)
```

**Raise site (`langextract/annotation.py:399-402`):**

```python
          if not scored_outputs:
            raise exceptions.InferenceOutputError(
                "No scored outputs from language model."
            )
```

### (d) Result/document models: field recording suppressed chunk?

**Models searched:** `Extraction`, `Document`, `AnnotatedDocument` (`langextract/core/data.py`); `CharInterval`, `AlignmentStatus`, `ExampleData`; `ScoredOutput` (`langextract/core/types.py`); `TextChunk` (`langextract/chunking.py`); `annotated_document_to_dict` output fields (`langextract/data_lib.py`).

**`Extraction` fields (`langextract/core/data.py:85-92`):**
```python
  extraction_class: str
  extraction_text: str
  char_interval: CharInterval | None = None
  alignment_status: AlignmentStatus | None = None
  extraction_index: int | None = None
  group_index: int | None = None
  description: str | None = None
  attributes: dict[str, str | list[str]] | None = None
```

**`AnnotatedDocument` fields (`langextract/core/data.py:217-218`):**
```python
  extractions: list[Extraction] | None = None
  text: str | None = None
```

**`Document` fields (`langextract/core/data.py:130-131`, property block):**
```python
class Document:
  """Document class for annotating a document."""
```

(document_id, text, additional_context, tokenized_text; no suppression field)

**`TextChunk` fields (`langextract/chunking.py:48-49`):**
```python
  token_interval: tokenizer_lib.TokenInterval
  document: data.Document | None = None
```

**`rg` over `langextract/core/*.py` for `suppress|suppressed|skipped|parse_error`:** no matches in result model modules.

**Verdict on (d):** no field in any result/document model records that a chunk was suppressed. Suppression is logging-only (`logging.warning("Skipping chunk: ...")` at `resolver.py:311,319`).

## Verdict on the claim(s)

**CONFIRMED**

C4b: `extract()` defaults to suppressing parse errors (`extraction.py:365` sets `suppress_parse_errors` to `True` unless overridden in `resolver_params`), failed chunk parses return `[]` (`resolver.py:309-321`), and annotation continues without recording suppression in result models.

## Coverage gaps

None for assigned scope. All production matches for `suppress_parse_errors` and `InferenceOutputError` in `langextract/` enumerated above (tests and `_compat` re-exports listed in inventory method; result models read exhaustively).

## What could still hide a counterexample

- A dynamically attached attribute on runtime objects not declared in dataclass fields (not found in code read).
- Provider-specific subclasses overriding `resolve()` or annotation flow (no overrides found in this search pass beyond listed files).
