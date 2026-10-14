# vlm-pdf-qa - Research Index

- **slug:** vlm-pdf-qa
- **analyzed:** 2026-07-07
- **target:** multi-repo survey (no single SHA) - how open-source repos feed PDFs to LLMs/VLMs, to design the whisker LLM QA lane that always receives the original PDF and judges independently of the deterministic lane before fusion. Repos are read-only, git-ignored, checked out under `packages/whisker/research/repos/`.

## Hot repos (HEAD SHAs, read-only, 2026-07-07)

| repo | HEAD SHA |
|---|---|
| olmocr | f7cfe4c22098b154c76b6ec950d1c0a464eecf8d |
| marker | ef16c2caa29d76f3ca3126944d2e1be79f560bda |
| MinerU | 3e60291846cb7c3bf8fe7f4f16238f4fc6cce491 |
| Dolphin | befa5dad986f86396b73cbd8c37e557b5770c902 |
| nougat | 5a92920d342fb6acf05fc9b594ccb4053dbe8e7a |
| docling | fbd39b870859afbae21645ebe0e417109777da5a |

## Pointer

- **Synthesis:** [SYNTHESIS.md](./SYNTHESIS.md) - verdict `usable-with-conditions`, decision `adopt-partially`. Resolves the C-vs-B tension in favor of contender C (olmOCR-style VLM-as-second-converter + deterministic diff vs tomd), phased v1/v2, with the HTML-only (198/387) policy.
- Baseline: [00-baseline.md](./00-baseline.md). Web cards: [05-web.md](./05-web.md). Meta-reviews: opus-A..E.
