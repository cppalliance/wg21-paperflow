# D22 — Presence index (payload scoping)

**Date:** 2026-07-24  
**Status:** Open (dense enabler; land before dense lane bump)

---

## Decision needed

Build a per-paper mechanical **presence index** (headings, 5-grams, C++ keywords, dehyphen variants; ≤512 entries, ~200–300 tok) into every scoped unit prompt?

## Recommendation from research

**Yes, as half of minimal scoping (with D23).** Index is the ANYWHERE oracle for cross-page reflow; window is local fidelity only. Pure function, no I/O; serialize under a fixed header; sort entries (D7). Post-hoc grounding stays on full `raw_tomd_md`.

## If yes

- Unblocks dense S=32–48 + FP8 KV math assumed by Option B.
- Cuts cross-page join false-fail vs window-only.
- Prefill savings on MoE secondary (~7%); primary win is dense KV headroom.

## If no

- H2 window alone still hides remote defects → higher false-clear/false-fail.
- Dense offload without full scoping package stays **negative EV** (S≤16, L≈20 s).

## Evidence

| Claim | Source |
|-------|--------|
| Presence index + H2±1 = minimal design | ADR-004, `23-payload-scope-dense.md` |
| Without scope: NEGATIVE-EV-WITHOUT-SCOPE | `12`, `105` via ADR-004 |
| Glossary: scoping unlocks dense concurrency | `GLOSSARY.md` |
