# D18 — HTML-first deterministic metadata

**Date:** 2026-07-24  
**Status:** Open (shadow → HTML flip)

---

## Decision needed

Stage deterministic metadata (`compare_metadata_outline`) **HTML-first**: shadow both paths, then flip HTML only after HTML gates, keep PDF on LLM until D19?

## Recommendation from research

**Yes.** Fleet is 201 HTML / 180 PDF. HTML router already diffs levels; HTML tranche ~**251 s** @ S=16 without waiting on PDF outline hardening. Gate: HTML shadow ≥**98%** metadata verdict agreement + **zero** holdout fused drift on HTML papers.

## If yes

- Lands largest early MoE N cut after v11; stacks toward ~1191 s class on 3003 s baseline (still >600 s).
- Temporary lane asymmetry (HTML det vs PDF LLM) until D19.
- Rollback: `--llm-metadata` per flipped lane.

## If no (wait for fleet-wide or skip staging)

- Delays ~251 s harvest behind PDF parity work.
- Or risks PDF false-fires if fleet-flipped too early.

## Evidence

| Claim | Source |
|-------|--------|
| HTML-first ~251 s; staging order | ADR-021, ADR-006, `22-html-vs-pdf-mix.md` |
| Det assets already in HTML outline / router | `13-deterministic-metadata.md` |
| Option A phase order | `PLANNING-HANDOFF.md` §6 |
