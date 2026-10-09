# Dev-Replay Corpus (Golden PRs #282–#295)

Nine golden-ideal PRs used as the development replay set for
tapetum_llm evidence verification and source-aware judging.

**These are NOT holdout papers.** Thresholds and logic may be tuned
against this set. The separate `../holdout/` set is locked.

## Papers

| PR | PID | Source | Known defects |
|----|-----|--------|---------------|
| #282 | p4020r0 | HTML | `### References` should be `##` (H2→H3 drift) |
| #283 | p2040r0 | PDF | None found |
| #284 | p0957r8 | PDF | Page 13 silently omitted (figures, table, prose); TOC leak |
| #285 | p3556r0 | PDF | TOC leak; dead figure ref; medium structural |
| #286 | p1068r11 | PDF | Unresolved marker; heading hierarchy; entities |
| #290 | p1122r3 | PDF | Front-matter errors; TOC leak; heading/bullet issues |
| #293 | p0533r9 | PDF | 151 missing `constexpr` qualifiers; TOC leak; tables flattened |
| #294 | p3411r5 | HTML | One dropped period after `any_view` |
| #295 | p3953r0 | HTML | None found |

## Verified counts (2026-07-17)

- P0533R9: PDF source has 231 `constexpr` tokens, PR ideal has 80 → delta 151.
  Source has 116 `constexpr type func(...)` declaration patterns; ideal has 17.
- P0957R8: page 13 has 2 raster figures, 1 table, connecting prose. Screen
  recall 0.881 on that page (below 0.90 floor).

## Usage

The `labels.json` file provides per-paper ground-truth labels for automated
acceptance testing. Sources live in `packages/tomd/tests/fixtures/golden/sources/`
(PDFs) or were extracted from the PR heads (HTML).
