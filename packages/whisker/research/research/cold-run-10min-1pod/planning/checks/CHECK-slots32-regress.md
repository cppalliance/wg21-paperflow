# CHECK: S=32 regresses wall by +57%

**Claim:** Raising `--max-num-seqs` to 32 costs +57% wall vs S=16.
**Source:** `00-baseline.md`, `SYNTHESIS.md`

## Quote

> Raise `--max-num-seqs` to 32 (+57% wall measured)  
> — `00-baseline.md`
>
> Twin / S=32 / c>32 | **Forbidden** | Operator + measured regression  
> — `SYNTHESIS.md`

## Verdict

**CONFIRMED** — baseline states measured +57%; synthesis forbids S=32.
