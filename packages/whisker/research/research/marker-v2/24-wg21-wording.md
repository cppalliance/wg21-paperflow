# 24 - WG21 Wording

**Verdict:** garbage — Marker v2.0.0 has **no** WG21 ins/del wording detector. No font-color span roles, no strikethrough geometry, no `wording_role`, and no deterministic emit of `<ins>`/`<del>`. The only touchpoint is an opt-in LLM rewrite allowlist that permits `<del>` (not `<ins>`) if a user prompt asks for it.
**Confidence:** high

Clone: `packages/whisker/research/repos/marker-v2.0.0/` @ `947d768` (Marker 2.0.0). Comparison anchor: tomd `packages/tomd/src/tomd/lib/pdf/wording.py` + `wording_emit.py` (HSV color + drawing strikethrough → `span.wording_role` → fenced `<ins>`/`<del>`).

## Findings

- [CRITICAL] **Digital PDF path never reads span color.** `PdfProvider.pdftext_extraction` builds `Span` from font name/flags/size/weight/bbox/url/super-sub only; `formats` come solely from `font_flags_to_format` ∪ `font_names_to_format` (bold/italic/plain). Evidence: `marker/providers/pdf.py:245-275`, `157-194`. No `color` field is passed into `SpanClass(...)`. Impact: green=ins / red=del (tomd's primary signal) is invisible to Marker.

- [CRITICAL] **No strikethrough geometry / drawing correlation.** Repo-wide search under `marker/**/*.py` for `strikethrough`, `get_drawings`, and wording drawing matchers returns empty (aside from unrelated "Vector Operations" LLM examples). Impact: even if red text were known, Marker cannot confirm deletion via rule-overlap the way tomd `_match_strikethrough` does (`tomd/.../wording.py:155-191`, constants at `49-50`).

- [CRITICAL] **Span schema has no wording role and no strike format.** `Span.formats` Literal is `plain|math|chemical|bold|italic|highlight|subscript|superscript|small|code|underline` only — no `strikethrough`, no `ins`/`del`. No `color` / `wording_role` attributes. Evidence: `marker/schema/text/span.py:26-44`. `assemble_html` maps underline→`<u>`, highlight→`<mark>`, never `<ins>`/`<del>` (`span.py:120-143`). Impact: no place to hang a wording classification even if one were computed.

- [CRITICAL] **No Ins/Del/Wording block types.** `BlockTypes` enum lists Line/Span/Code/Equation/…/Diagram with no wording-related variant. Evidence: `marker/schema/__init__.py:4-35`. No wording processor appears in `marker/processors/*.py` (list, table, equation, etc. only). Impact: wording is not a first-class layout or post-process concept.

- [HIGH] **HTML input destroys semantic `<ins>`/`<del>`.** `HTMLProvider` WeasyPrint-renders HTML → temp PDF, then reuses `PdfProvider`. Evidence: `marker/providers/html.py:7-32`. Impact: papers that *do* ship real HTML wording tags lose tag identity before text extraction; color may survive as paint, but Marker still does not read color (finding 1).

- [MED] **Sole `del` mention is LLM correction allowlist, not detection.** `FORMAT_TAGS = ["b", "i", "u", "del", "math", ...]` — note **`ins` is absent**. Tags are injected into the page-correction prompt only when `block_correction_prompt` is set; default processor returns immediately if that prompt is None. Evidence: `marker/processors/llm/llm_page_correction.py:16`, `59`, `156`, `268-270`; README documents `--block_correction_prompt` as optional custom rewrite (`README.md:127`). Impact: at best a vision-LLM *might* invent `<del>` under a custom prompt; there is no deterministic green/red/strike path, and insertions are not even in the allowed tag set.

- [LOW] **Markdown renderer has no wording converters.** Custom `Markdownify` overrides cover div/p/chem/math/table/a/span — not `del`/`ins`/`s`. Evidence: `marker/renderers/markdown.py:75-238`. Any `<del>` that somehow appeared in HTML would rely on stock `markdownify` behavior, not Marker wording semantics. Debug red/green colors are bbox overlays only (`marker/processors/debug.py:146-155`).

## tomd vs Marker (wording axis)

| Signal | tomd | Marker v2.0.0 |
|---|---|---|
| Font / paint color (HSV green/red) | Yes (`wording.py` `is_green_ins` / `is_red_del`) | No — color never stored on Span |
| Strikethrough drawing overlap | Yes (`_match_strikethrough`, drawings from pipeline) | No drawings collection |
| `wording_role` on spans | Yes (`types.py:47`, set in `classify_wording`) | No field |
| Emit `<ins>` / `<del>` | Yes (`wording_emit.py`) | No emit path; LLM allowlist has `del` only |
| HTML wording tags | Preserved/rendered (`lib/html/render.py` inline tags include `ins`/`del`) | HTML→PDF→pdftext; tags lost |
| Syntax-highlight false-positive guards | Contamination filter, comment introducer, page-gated del promotion | N/A (no detector) |

**Adoption note:** This is the clearest Marker gap for WG21. Porting Marker as a convert backend would drop Proposed Wording diffs to plain text (or, with a custom LLM prompt, nondeterministic `<del>` guesses). tomd's wording stack has no Marker equivalent to adopt.

## False-pass hypothesis

An LLM page-correction run with a hand-written prompt that asks to wrap struck/red text in `<del>` could emit some `<del>` tags on a demo page, creating the appearance that "Marker supports deletions" while insertions remain unlabeled (`ins` not in `FORMAT_TAGS`) and digital-mode conversions without `--block_correction_prompt` still strip all wording semantics. Whisker/tomd goldens that score on fenced wording divs would look "partially fixed" only under that optional, non-reproducible path.

## False-fail hypothesis

None for Marker's own product claims (README never promises track-change / WG21 wording). Versus tomd goldens: Marker correctly emitting plain prose for a green/red wording section is a **true fail** on the wording axis, not a false fail.

## What would change my mind

A deterministic processor that (1) retains per-span RGB/HSV from pdftext or pdfium, (2) correlates horizontal drawings to red spans as strikethrough, (3) sets an explicit role, and (4) emits `<ins>`/`<del>` (or equivalent) in markdown/HTML with tests on colored WG21 fixtures — then this CRITICAL gap closes. Schema-only addition of `"strikethrough"` without a producer, or LLM-only `del` allowlisting, would not change the verdict.
