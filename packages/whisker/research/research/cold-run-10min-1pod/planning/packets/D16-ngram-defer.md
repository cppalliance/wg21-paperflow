# D16 — Defer ngram / PLD speculation

**Date:** 2026-07-24  
**Status:** Deferred (not a cold ≤10 min lever)

---

## Decision needed

Enable ngram / prompt-lookup speculative decoding on `alliance-pod` as a cold-wall lever (instead of or beside MTP)?

## Recommendation from research

**Defer / do not bank.** Prefer MTP k=1 A/B on V4-Pro; keep ngram as fallback for non-MTP dense endpoints. Marginal ~**37–75 s** class; helps JSON keys/punctuation only. Short OSL (~20–77 tok pass) barely amortizes draft overhead. If ever tried on structured prompts, raise `prompt_lookup_min` to 4–8.

## If yes (enable now as central stack)

- Overstates savings; may displace healthier MTP config.
- Risk structured corruption at default `prompt_lookup_min=2` (vLLM #40875 class).

## If no (defer)

- Cold program stays on N/L cuts that move first greenfield.
- MTP remains the only measured speculative candidate on Pro (still unbanked).

## Evidence

| Claim | Source |
|-------|--------|
| Ngram marginal; MTP preferred on Pro; ~37–75 s | `05w-web-ngram-spec.md`, `SYNTHESIS.md` reject ledger |
| Short JSON @ c≈16 lose/flat for heavy spec | `05j`, ADR-014 |
| FAQ Q40 | `PLANNER-FAQ.md` |
