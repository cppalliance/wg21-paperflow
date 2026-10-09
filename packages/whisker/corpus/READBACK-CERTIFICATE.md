# Five-paper modal readback (de-needle-v2)

- **Date**: 2026-08-12
- **Protocol**: de-needle-v2
- **Service / model**: alliance-pod / deepseek-v4-pro
- **Clean result**: 31/37 pass, 6 fail, 0 transport errors
- **Corrupt control**: 26/37 pass, 11 fail, 0 transport errors (not an inverted canary)
- **100% claim**: no

Authored questions were used. Historical 8/8, 9/9, and 34/37 do not count.

## Failing facts (clean)

| Paper | Fact | Type | What happened |
|---|---|---|---|
| N5040 | order-headings | order | Model listed later agenda items (liaison reports) instead of 1.1 / 1.2 |
| P0876R23 | xref-p3472 | xref | Cited P0099R1 instead of [P3472R1] |
| P4182R0 | pmr-term | present | Answered `<memory_resource>` instead of quoting "polymorphic memory resources" |
| P4182R0 | section-flow | order | Summarized beats instead of recovering the authored sequence phrases |
| P4185R0 | table-anchored-true-zero | table | Wrong neighbors (N/A / check / Delta) |
| P4185R0 | section-flow | order | Listed extra numbered headings; did not recover "4 Non-negative quantities" as written |

P4234R0 was 6/6. N5040 was 5/6. No tomd edits were made to chase the number.
