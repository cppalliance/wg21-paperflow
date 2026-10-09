# CARD: 05r — Extractor LLM verification / judge stages

## Bottom line
MinerU, Marker, Docling, and olmOCR cores are still extraction-(+optional refine)-only. None shipped a fail-closed LLM verification stage on the convert path that can absorb tapetum unit-check work. Closest ecosystem novelty is third-party mineru-refine (fixer + mechanical fidelity), pattern interest only.

## Numbers
- MinerU: optional `title_aided` heading LLM; default `enable: false`.
- Marker: optional `--use_llm` refine (tables/math/forms); `LLMScorer` is bench-only.
- Docling ≥v2.34: `confidence` grades from model certainty, not LLM re-read.
- olmOCR: VLM extraction only; bench deliberately rejects LLM-as-judge (binary unit tests).
- mineru-refine: mechanical suspects → LLM pick-one-op → `C_out ⊆ C_in` gate; **fail-open** if LLM missing.

## Architecture implication
Do not plan to replace or cut tapetum verification by “using docling/MinerU/marker/olmocr.” Steal patterns only: mechanical suspect set → small op picker → deterministic fidelity gate (orthogonal workload). Docling confidence is a cheap human-routing gate, not a unit-check substitute.

## Reject-or-A-B
- **Reject:** treating extractor refine/eval as verification; expecting extractors to cut UnitCheck N.
- **Footnote only:** mineru-refine pattern (not a ship dependency; cloud/default DeepSeek conflicts with no-cloud-judge baseline unless pointed at Alliance).
- **Reopen only if:** a core ships score(source, md) → accept|reject with fail-closed default on convert.

## Links
- Source: `05r-web-extractor-judge.md`
- Related: `00-baseline.md` (no cloud judges; “just use docling” wrong workload)
- https://github.com/opendatalab/MinerU , https://github.com/LcpMarvel/mineru-refine
- https://github.com/datalab-to/marker , https://docling-project.github.io/docling/advanced/confidence-scores/
- https://github.com/allenai/olmocr , arXiv:2502.18443
