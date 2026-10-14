# opus-E - Steelman + balancing decision (orchestrator)

## The two steelmen, weighed

**Steelman current design (31):** the deterministic per-page recall screen already gives every page a calibrated check (PAGE_RECALL_FLOOR 0.90, 107-control-page flip-check, 0 false flags), the monolith sees the full text layer, and the strongest verification prior art (olmocr-bench, ParseBench) deliberately uses deterministic per-page checks INSTEAD of LLM judges because judge TNR is <25%. Exhaustive LLM judging risks manufacturing operator confidence that the numbers do not support.

**Steelman all-pages (32):** a golden is permanent ground truth; the screen measures token PRESENCE only (`content_recall` is a multiset overlap), so a page can hold recall >= 0.90 while heading levels, qualifiers, table cells, or emphasis on that page are mangled - the exact PR #282 defect class. The router's signal list is closed; a defect class outside it on an unrouted page is structurally invisible. And the workflow honesty point is real: pr-golden-review.md TELLS the operator that --inspect implies exhaustive unit checking, which is false for PDFs today. Review mode (one paper, hourly-billed pod, human triage) does not inherit the fleet-mode noise math: expected false findings scale as n*p (0.3-2 spurious findings per 33-page review at p=1-5%), which a human triages in minutes.

## Balance

Both steelmen survive verification, and they are not actually in conflict:

- 31 wins on: the LLM's "15/15 pages checked, 0 findings" line must NEVER be presented as proof of correctness (TNR <25%; empty-defect passes are the cheapest false pass, persona 30). All-pages is a defect FINDER upgrade, not a correctness CERTIFIER.
- 32 wins on: coverage accounting and workflow honesty. The current state (5/15 pages, dead flags, coverage_complete=True on zero checks, a command doc that lies) is indefensible regardless of how good the deterministic screen is.
- The decision is therefore not either/or. Ship --all-pages as an opt-in review-mode defect finder with fail-closed coverage accounting, and simultaneously fix the reporting so that a clean all-pages run is worded as "no additional findings" rather than "verified correct". The deterministic lanes remain the gate; the manual fidelity diff remains the load-bearing golden-review step (pr-golden-review.md already says so).

## Conditions attached to the verdict (binding for the implementation)

1. Fail-closed: required = every `page:N` from the extractor; any unchecked/failed/packet-missing page forces coverage_complete=False and verdict cap review. Never derive "complete" from an empty risk list in all-pages mode (unit_judge.py:287-288 bypass).
2. The all-pages unit prompt must inherit the FULL conversion contract including the cross-page anywhere-rule (pdf_judge.py:238-241) and the TOC-leak/wording/comment sanctions (pdf_judge.py:152-189), with a neutral full-audit instruction replacing the risk-signal line.
3. Fingerprint must encode the coverage mode (and fix the pre-existing --exhaustive-units cache hole); a _LANE_VERSION bump alone is insufficient.
4. Timeout must scale with page count (persona 23's shape: base + n * UNIT_CHECK_TIMEOUT_SECONDS).
5. Sidecar audit fields (all_pages_requested, unit_selection with required/checked/unchecked/failed) + schema bump; fusion must distinguish "complete because nothing flagged" from "complete because all pages checked"; inspect report must render a per-page coverage table.
6. Report wording: all-pages pass = "all pages checked, no additional findings (advisory)"; never "verified correct".
7. CLI: loud validation (reject or clearly define --all-pages on HTML papers), and fix the silent no-op of --exhaustive-units/--inspect on the PDF lane in the same change.
