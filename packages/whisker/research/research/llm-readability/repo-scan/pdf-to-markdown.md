# Repo scan: pdf-to-markdown

**Does it verify LLM-readability?** **no**

v0.1.3 JS PDF→markdown pipeline with four mocha spec files covering string/headline helpers only. No end-to-end PDF fixtures, no expected markdown goldens, no comprehension/fact assertions, no LLM judge, no CI workflow, no downstream consumability benchmark. Final markdown is rendered in the browser with zero automated assertion.

---

## Findings

1. **[CRITICAL] No end-to-end output verification** — `ResultView` runs all transforms and concatenates `item + '\n'` into state; no test asserts converted markdown. Evidence: `src/javascript/components/ResultView.jsx:21-44`. Impact: negative control for #254; exactly the blind spot whisker guard/Lane 3 closes.

2. **[CRITICAL] Tests are helper-only (no PDF fixtures)** — `npm test` runs mocha on `test/stringFunctions.spec.js`, `test/HeadlineFinder.spec.js`, `test/models/StashingStream.spec.js` only. Evidence: `package.json:11-12`. No `.pdf` references anywhere under `test/`. Impact: zero portable comprehension corpus; no fact assertions.

3. **[HIGH] No CI / no committed goldens** — scripts are `lint`, `mocha`, `webpack` only; no `.github/workflows`. Evidence: `package.json:6-14`; glob shows no `.github/` in clone. Impact: redteam claim "manual-only QA" confirmed.

4. **[HIGH] 12-stage pipeline with debug replay but no stage regression gates** — transforms listed in `AppState.jsx:53-67`; `DebugView.jsx:83-89` replays stages `0..N` for manual inspection. Impact: stage-counter pattern is portable to tomd hooks, but nothing is scored in CI.

5. **[MED] Per-stage count messages (manual QA signals)** — e.g. `'Detected ' + detectedHeaders + ' headlines.'` Evidence: `src/javascript/models/transformations/lineitem/DetectHeaders.jsx:116-120`; `'Removed Header/Footers'` at `RemoveRepetitiveElements.jsx:93-96`; list counts at `DetectListItems.jsx:55-58` (file continues message block). Impact: candidate whisker baseline `stages` dict when tomd exposes counters.

6. **[MED] Annotation-filtered diff UI (not automated)** — `PageView.jsx:20-22` filters to `block.annotation` when `modificationsOnly`; annotations defined at `Annotation.jsx:11-28`. `ToLineItemTransformation.jsx:31-38` strips `REMOVED_ANNOTATION` between stages. Impact: localization pattern for guard findings; not wired to tests.

7. **[MED] Hardcoded fuzzy thresholds without corpus calibration** — TOC headline recovery uses `wordMatch(...) >= 0.5`. Evidence: `DetectTOC.jsx:276-277`; formula at `stringFunctions.jsx:112-118`. Header/footer quorum: `Math.max(3, parseResult.pages.length * 2 / 3)`. Evidence: `RemoveRepetitiveElements.jsx:77-78`. Impact: same "invent metric, pick cutoff by hand" anti-pattern whisker `calibrate.py` is meant to replace.

8. **[LOW] Exact unit tests on deterministic helpers** — `wordMatch` floats locked at `1.0`, `0.5`, `0.666...`, `0.25`, `0.0`. Evidence: `test/stringFunctions.spec.js:182-193`. Impact: meta-test style for whisker guard edges; not document comprehension.

9. **[CONFIRMED ABSENT] LLM, comprehension, benchmark, fact assertions, downstream QA** — no references in source or tests. Markdown preview uses Remarkable HTML render (`ResultView.jsx:66-75`) for human eyeballing only.

---

## Portable to whisker (ranked)

1. **`wordMatch` set-overlap + explicit operating point** — uppercase token overlap `intersection.size / Math.max(words1.size, words2.size)` with hand-set `>= 0.5` for TOC/headline linking. Source: `stringFunctions.jsx:112-118`, `DetectTOC.jsx:276-277`, tests `stringFunctions.spec.js:182-193`. Fit cutoff via `calibrate.py` on labeled headline-recovery samples; optional fifth guard axis.

2. **Stage message counters in baseline schema** — snapshot `{headlines_detected, headers_removed, list_items_found}` per paper when tomd exposes hooks. Source: `DetectHeaders.jsx:118-120`, `RemoveRepetitiveElements.jsx:93-96`. Localizes regressions guard's terminal NID/TEDS cannot.

3. **Annotation change-set counts** — track `{added, removed, detected}` annotation totals per run. Source: `Annotation.jsx:11-28`, `PageView.jsx:20-22`. Follow-on to whisker `missing_regions`/`extra_regions`.

4. **Repetitive furniture quorum `max(3, pages*2/3)`** — if whisker adds reference-free header/footer confidence. Source: `RemoveRepetitiveElements.jsx:77-78`.

5. **Exact helper unit-test style for guard meta-tests** — duplicate pid, NaN axes, baseline-metadata override. Source: `stringFunctions.spec.js:182-193`.

**Not portable as LLM-readability proof:** repo never validates markdown output; debug UI is manual. Whisker Lane 3 + corpus remain strictly ahead.

---

## Cross-check vs redteam report (`packages/whisker/research/redteam/pdf-to-markdown.md`)

| Redteam claim | Verdict | Evidence |
|---------------|---------|----------|
| No automated regression gate (no goldens, no CI) | **CONFIRMED** | `package.json:11-12`; no `.github/`; `ResultView.jsx:21-44` unasserted |
| 12-stage pipeline in `AppState.jsx:53-67` | **CONFIRMED** | 12 transforms listed (CalculateGlobalStats through ToMarkdown) |
| Debug replay `DebugView.jsx:83-89` | **CONFIRMED** | loop `for (i = 0; i <= currentTransformation; i++)` |
| Per-stage count messages (`DetectHeaders.jsx:118-120`) | **CONFIRMED** | `'Detected ' + detectedHeaders + ' headlines.'` |
| Annotation-filtered diffs (`PageView.jsx:20-22`) | **CONFIRMED** (path: `components/debug/PageView.jsx`, not `components/PageView.jsx`) | `items.filter(block => block.annotation)` |
| `wordMatch >= 0.5` at `DetectTOC.jsx:276-277` | **CONFIRMED** | exact lines |
| `wordMatch` tests at `stringFunctions.spec.js:182-193` | **CONFIRMED** | including `0.6666666666666666` boundary case |
| Quorum `max(3, pages*2/3)` at `RemoveRepetitiveElements.jsx:77-78` | **CONFIRMED** | exact lines |
| No end-to-end markdown gate | **CONFIRMED** | no PDF in tests; `ToMarkdown.jsx:16-27` only mutates in-memory strings |
| whisker guard baseline metadata bug | **N/A to this repo** | redteam whisker-internal finding; pdf-to-markdown has no baseline JSON |

**Minor correction:** redteam cites `PageView.jsx` without `debug/` subpath; file lives at `src/javascript/components/debug/PageView.jsx:20-22`. Substance unchanged.

**No contradictions** on LLM-readability or output verification claims. Redteam correctly identifies pdf-to-markdown as a **negative control**: rich manual debug UX, zero automated comprehension or markdown QA.
