# Auditv4 — Refuted findings from Auditv3

Pre-audit ledger of Auditv3 findings that do not survive re-examination.
Full Auditv4 scoring is a separate pass; this file only prevents false
positives from being carried forward silently.

## L1 — `--enable-prefix-caching` "documented as a whisker flag" — REFUTED

**Auditv3 claim** (`CODE-AUDIT-RESULT.md`, Low table):

> `--enable-prefix-caching` documented as a whisker flag; it is a vLLM server flag.

**Source cited:** `raw/w2-cli-surface.md` §4.1, which called it the sole
"load-bearing finding" among documented-but-missing tokens and concluded the
flag appears in whisker lane documentation "as if it were an operator flag."

**Evidence against the claim.** The cited prose in
`packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md` (performance ceiling
section) reads:

> **Prefix caching.** Enabling `--enable-prefix-caching` on the vLLM server
> caches KV blocks for the shared system prompt (~3.7k chars, ~925 tokens).

The phrase "on the vLLM server" assigns the flag to the server, not to
`whisker-tapetum-llm` or any whisker console script. The Auditv3 raw surface
map itself quotes that context, including "on the vLLM server", then draws
the opposite conclusion. That inference does not follow from the quoted text.

**Disposition:** no code or documentation change. Do not re-score L1 as open
in Auditv4. Treat as a false positive of the Auditv3 CLI-surface pass.
