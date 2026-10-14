VERDICT: BUILD stdlib Counter — ~15 lines beats any new dep for bag recall/F1

# BUILD-vs-BUY: content-recall axis (set-F1 / %missing)

Deterministic NO-LLM complement to whisker's edit-distance text axis for labeled
bench + guard. Scope: research only; no whisker source changes in this pass.

**Constraints:** Python >=3.12, stdlib-first, permissive licenses only, lib funcs
return data, deterministic.

**Already-deps (buy is free):** `apted`, `levenshtein`, `lxml`, `markitdown[pdf]`,
`numpy`, `scipy`, `pylatexenc`, `paperstore`, `tomd` (`packages/whisker/pyproject.toml`).

---

## 1. Current gap (edit-only text axis)

| Location | What exists | What's missing |
|----------|-------------|----------------|
| `metrics.py:text_nid` | Full-string NED after `_normalize_text` (whitespace collapse on **raw** markdown strings); returns `1 - edit/max_len`. | No token-set precision/recall/F1; no multiset recall; no `%missing`. |
| `match.py:block_text_nid` / `block_metrics` | Block-matched NED on `normalized_text` (= `clean_string(textblock2unicode)`): order-robust **edit** sum over aligned blocks (`bench.py:157-158`). | Same: edit-only; dropped content inside a partially matched block can leave NID moderate. |
| `bench.py:BenchRow` | Fields: `nid`, `teds`, `mhs`, `overall`, `reading_order` (`bench.py:44-50`). | No `set_f1`, `content_recall`, or `percent_missing`. |
| `guard.py:_axes` | Regresses `nid`, `teds`, `mhs`, `overall` (`guard.py:79-86`, `constants.py:99`). | No content-recall axis on labeled path. |
| `score.py` / `check_content` | Reference-**free** `unigram_coverage` (multiset recall: PDF/HTML source tokens vs markdown). | Not computed on labeled GT-vs-candidate bench pairs. |

**Summary:** The labeled benchmark path has **only normalized edit distance** (block-matched
`nid`). Edit distance conflates insertions, deletions, and reorderings and has no explicit
"what fraction of reference content is present?" signal. A converter that **drops a
paragraph** can score surprisingly well on NID when remaining blocks align, while
content-recall axes (Nougat set-F1, Unstructured `cct-%missing`) would fall.

Prior synthesis: Tier-3 deferred feature, flagged by nougat + unstructured
(`notes/redteam-synthesis.md:43-44`).

---

## 2. Reference formulas (exact, with citations)

### 2.1 Nougat — per-stratum set-F1 (unique-word sets)

Source: `packages/whisker/research/repos/nougat/nougat/metrics.py` (MIT).

**Char NED** (order-sensitive), per page pair, skipped when `len(pred) < minlen` or
`len(gt) < minlen` (`minlen=4`):

```python
# metrics.py:27-31
metrics["edit_dist"] = edit_distance(pred, gt) / max(len(pred), len(gt))
```

**Set-F1** on **whitespace-split words** (unique tokens, not multiset):

```python
# metrics.py:32-43
reference = gt.split()
hypothesis = pred.split()
# ... bleu/meteor on lists ...
reference = set(reference)
hypothesis = set(hypothesis)
metrics["precision"] = nltk.scores.precision(reference, hypothesis)
metrics["recall"] = nltk.scores.recall(reference, hypothesis)
metrics["f_measure"] = nltk.scores.f_measure(reference, hypothesis)
```

NLTK set scores (standard):  
`precision = |ref ∩ hyp| / |hyp|` (0 if hyp empty),  
`recall = |ref ∩ hyp| / |ref|` (0 if ref empty),  
`f_measure = 2PR/(P+R)` (0 if P+R=0).

**Reporting:** Text / Math / Tables strata via `split_text` (regex strips inline/display
math and tabular blocks before text scoring); each stratum prints **separate** corpus
means for `edit_dist` and `f_measure`, never merged into one gate
(`metrics.py:63-83`, `104-117`).

### 2.2 Unstructured — `cct-%missing` (multiset bag-of-words)

Source: `unstructured/metrics/text_extraction.py` and
`unstructured/metrics/evaluate.py` on GitHub `Unstructured-IO/unstructured` main
(local clone under `research/repos/unstructured/` was not populated in this workspace;
formulas verified from upstream source).

**Per-document row** (`evaluate.py:412-426`, headers `evaluate.py:436-437`):

```python
percent_missing = round(calculate_percent_missing_text(output_cct, source_cct), 3)
# columns: filename, doctype, connector, cct-accuracy, cct-%missing
```

**`calculate_percent_missing_text`** (`text_extraction.py:160-203`):

1. `output = prepare_str(output)`, `source = prepare_str(source)` (optional whitespace
   standardization via `prepare_str`).
2. `output_bow = bag_of_words(output)`, `source_bow = bag_of_words(source)` — multiset
   counts; `bag_of_words` lowercases, strips sentence punctuation (keeping in-word
   `'`/`-`), splits on whitespace, rejects single-char tokens unless assembled into
   spaced-out "words" (`text_extraction.py:133-157`).
3. For each `source_word, source_count` in `source_bow`:
   - `total_source_word_count += source_count`
   - if word absent in output BOW: `total_missing_word_count += source_count`
   - else: `total_missing_word_count += max(source_count - output_bow[word], 0)`
4. If `total_source_word_count == 0`: return `0`.
5. `fraction_missing = round(total_missing / total_source, 3)`; return `min(fraction, 1)`.

**Properties:** Does **not** penalize extra/duplicate words in output; spaced-out
characters count as missing; complement is multiset **recall** on word counts:
`content_recall = 1 - fraction_missing`.

**Coupled accuracy axis:** `cct-accuracy` = `1 - min(Levenshtein.distance/max(len(source),1), 1)`
with RapidFuzz Levenshtein weights `(2,1,1)` (`text_extraction.py:57-117`,
`evaluate.py:420-424`). Wild byte-length ratio outside `(0.5, 2.0)` forces accuracy
sentinel `0.01` (`evaluate.py:418-424`).

### 2.3 whisker score-path analogue (not on bench today)

`tomd.lib.check_content._multiset_coverage` (`packages/tomd/src/tomd/lib/check_content.py:453-470`):
fraction of **source multiset** items matched in target (used for `unigram_coverage` at
`:621`). Same math as Unstructured missing-text complement when source=reference and
target=candidate, but tokens come from PDF/HTML extraction, not GT markdown.

---

## 3. Candidate implementations

| Approach | License | New dep? | Determinism | Matches Nougat set-F1? | Matches Unstructured %missing? | Notes |
|----------|---------|----------|-------------|------------------------|------------------------------|-------|
| **stdlib `set` + arithmetic** | PSF | No | Yes | Yes (unique-word P/R/F1) | No (set ignores multiplicity) | ~8 lines for F1; trivial. |
| **stdlib `collections.Counter`** | PSF | No | Yes | Partial (can derive set-F1 from Counters) | Yes (multiset recall / %missing) | ~12-15 lines; one implementation covers both recall and optional set-F1. |
| **`sklearn.metrics.f1_score`** | BSD | Yes (`scikit-learn`, not in whisker) | Yes | Awkward | Awkward | Designed for label vectors, not token bags; needs multilabel encoding or custom `average`; heavier than stdlib for this task. |
| **`rapidfuzz` `fuzz.token_set_ratio`** | MIT | Yes (not in whisker; uses `levenshtein` today) | Yes | No | No | Token-set **partial ratio** (sorted intersection heuristic), not F1; used by Unstructured for Levenshtein distance only. Different formula, different scale. |
| **`nltk.scores` (Nougat)** | Apache-2.0 | Yes (`nltk`, Nougat dep) | Yes | Yes (verbatim) | No | Imports NLTK + data deps; violates minimalism ladder for logic stdlib can express. |

**Conclusion:** No third-party library beats ~15 lines of stdlib for the actual math.
`sklearn` and `rapidfuzz` add weight without improving correctness or determinism for
bag-of-token F1 / multiset recall.

---

## 4. VERDICT: BUILD (stdlib)

### Why BUILD

1. **Minimalism ladder:** Bag-of-token precision/recall/F1 and multiset recall are
   counting; `Counter` is the correct tool and is already imported in `metrics.py`.
2. **No license risk:** stdlib only; `nltk`/`sklearn`/`rapidfuzz` are unnecessary.
3. **Determinism:** Pure integer counting on deterministic normalized strings; no
   float surprises beyond explicit division.
4. **whisker already owns normalization:** Reuse `normalized_text` / `textblock2unicode`
   pipeline rather than Unstructured's `bag_of_words` (different punctuation rules).

### Token unit (whisker-aligned)

`normalized_text` = `clean_string(textblock2unicode(text))` strips whitespace and
punctuation (`metrics.py:222-233`), so **whitespace `.split()` after `normalized_text`**
collapses English words (e.g. `"The quick brown"` → `"Thequickbrown"` one token).

**Recommended tokenization** (consistent with the content alphabet `clean_string` keeps):

```python
import re

_TOKEN_RE = re.compile(r"\w+|[\u4e00-\u9fff]")

def content_tokens(text: str) -> list[str]:
    """Tokens for recall/F1 after the whisker text-axis normalizer."""
    return _TOKEN_RE.findall(normalized_text(text))
```

- Alphanumeric runs and single CJK codepoints (CJK has no space delimiter in source).
- Same normalizer as block NED (`match.py:144` `normalize=normalized_text`).
- Document in tests that this is the whisker analogue of Nougat's `split()` on
  pre-stripped stratum text, not a byte-identical port.

### Stdlib formula sketch

```python
from collections import Counter

def multiset_recall(ref_tokens: list[str], hyp_tokens: list[str]) -> float:
    """Unstructured cct-%missing complement; 1.0 = no reference tokens missing."""
    if not ref_tokens:
        return 1.0
    rc, hc = Counter(ref_tokens), Counter(hyp_tokens)
    matched = sum(min(rc[t], hc[t]) for t in rc)
    return matched / sum(rc.values())

def percent_missing(ref_tokens: list[str], hyp_tokens: list[str]) -> float:
    return round(1.0 - multiset_recall(ref_tokens, hyp_tokens), 4)

def set_f1(ref_tokens: list[str], hyp_tokens: list[str]) -> float:
    """Nougat f_measure on unique tokens (not multiset)."""
    rs, hs = set(ref_tokens), set(hyp_tokens)
    if not rs and not hs:
        return 1.0
    inter = len(rs & hs)
    if not rs or not hs:
        return 0.0
    p = inter / len(hs)
    r = inter / len(rs)
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)
```

**Public API (proposed):** `metrics.content_recall(a, b)` and/or `metrics.set_f1(a, b)`
returning floats in `[0, 1]`; callers pass raw markdown; functions apply `content_tokens`
internally. Lib returns data only.

### Where it slots in bench + guard

| Layer | Change |
|-------|--------|
| `metrics.py` | Add `content_tokens`, `multiset_recall` / `set_f1` (or combined `content_recall` + `set_f1`). |
| `bench.py:BenchRow` | Add `content_recall` (primary gate) and optionally `set_f1` (Nougat parity). Keep `reading_order` advisory. |
| `bench.py:run_bench` | After `block_metrics`, compute tokens from `reference_md` / `candidate_md`; set new fields. Do **not** fold into `overall` initially (Nougat never merges strata). |
| `bench.py:aggregate` | Report corpus means; optional `below_floor` for new axis. |
| `constants.py` | `CONTENT_RECALL_FLOOR` (e.g. `0.90` provisional); add `content_recall` to `GUARD_REGRESSION_AXES`; keep `overall` report-only or drop from regression axes (nougat lesson). |
| `guard.py:_axes` | Include `content_recall` (and `set_f1` if added). |
| `guard.py:_FLOORS` | Backstop floor for `content_recall`. |
| Baseline JSON | New keys per row; refresh via existing `--update` ritual. |

**Primary axis choice:** Prefer **`content_recall`** (= `1 - percent_missing`) as the
Unstructured-aligned missing-content signal; add **`set_f1`** only if Nougat-style
unique-word F1 is needed for leaderboard comparability (multiset recall is stricter on
repeated terms).

**Block-level variant (later):** Multiset recall on tokens from **matched GT blocks only**
(mirror block NED locality); whole-doc recall is simpler and catches dropped sections
even when block matcher fails to align.

---

## 5. Risks

| Risk | Mitigation |
|------|------------|
| **Tokenization sensitivity** | `clean_string` removes word boundaries; regex tokenization is required. Golden tests on dropped-paragraph fixtures; document divergence from Nougat whitespace `split()` on unstripped text. |
| **Double-counting with edit axis** | `nid` and `content_recall` both react to missing text but measure different things (sequence edit vs multiset presence). Keep both; regress **independently** with separate slack/floors. Do not average into `overall`. |
| **Inflation on short/empty docs** | Nougat `minlen=4` skip; Unstructured returns 0 missing when source empty. whisker should treat `len(ref_tokens)==0` as recall=1.0 and optionally flag `scorable=False` for guard (nougat redteam §1.5). |
| **Extra content not penalized** | Multiset recall and set-F1 recall ignore hallucinated/duplicate words (Unstructured explicit). Rely on `check_content` drift / `unigram_drift` on score path for additions. |
| **CJK granularity** | Per-codepoint tokens overcount CJK vs English words; acceptable for WG21 corpus (mixed); revisit if comparing to Nougat English-only leaderboards. |
| **Normalization drift** | Baseline does not record normalizer generation today; a `normalized_text` change shifts recall without converter change. Record `WHISKER_SCHEMA_VERSION` bump on axis add (existing pattern). |
| **Block-match masking** | Whole-doc recall catches dropped sections; block NID can still miss drops inside a large matched block. Optional phase-2: recall on per-block GT tokens. |

---

## 6. BUY rejected

| Library | Rejection reason |
|---------|------------------|
| `sklearn` | No simpler than stdlib; new heavy dep; wrong API shape for token bags. |
| `rapidfuzz` | `token_set_ratio` ≠ F1; Levenshtein already covered by `levenshtein` package. |
| `nltk` | Nougat uses it for set-F1 and edit_distance; whisker already uses `levenshtein` + stdlib; NLTK adds data/packaging overhead for 10 lines. |

---

## Sources

- whisker: `packages/whisker/src/whisker/metrics.py`, `match.py`, `bench.py`, `guard.py`, `constants.py`, `score.py`
- Nougat: `packages/whisker/research/repos/nougat/nougat/metrics.py`
- Unstructured: `unstructured/metrics/text_extraction.py`, `unstructured/metrics/evaluate.py` (upstream main)
- tomd: `packages/tomd/src/tomd/lib/check_content.py`
- Prior research: `packages/whisker/research/redteam/nougat.md`, `unstructured.md`; `packages/whisker/notes/redteam-synthesis.md`
