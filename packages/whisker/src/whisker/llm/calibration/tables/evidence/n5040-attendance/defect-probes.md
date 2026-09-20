# N5040 Defect Probe Results (v1.0.5 count-then-score)

Date: 2026-08-15
Model: deepseek-v4-pro
Service: alliance-pod
Paper: data\paperstore\n5040.md
Contract: v1.0.5

Label shift detected (deterministic): True
Continuation header detected (deterministic): True

## Approach

v1.0.4 used semantic YES/NO questions (column association), which hit the
model's measured weakness (CoTabBench TableQA ~52%). v1.0.5 sends only the
isolated table fragment with an R1-aware system prompt and asks the model to
count delimiters and dump cells by index. The dump is scored deterministically.

## Probes

### count-dump-shift [PASS]

**Question:** Count the pipe delimiters in each row of the table below. List every cell left-to-right using 1-based column indices.

Use this exact format (one line per row, EMPTY for blank cells):
HEADER: [1]=... [2]=... [3]=...
BODY ROW 1, BODY ROW 2, BODY ROW 3

Then write one final line:
UNDER header[2]: body[1][2]

That line reports what body row 1's cell at position 2 contains, according to the header at position 2.

**Expected:** label-shift dump (dump matches label-shift structure)

**Answer (13343ms):**

```
HEADER: [1]=EMPTY [2]=Name [3]=National Body
BODY ROW 1: [1]=Adams, Michael [2]=EMPTY [3]=SCC
BODY ROW 2: [1]=Alday, Juan [2]=EMPTY [3]=ANSI
BODY ROW 3: [1]=ALEXANDRESCU, Andrei Cristian [2]=EMPTY [3]=ASRO
BODY ROW 4: [1]=Arutyunyan, Ruslan [2]=EMPTY [3]=ANSI
BODY ROW 5: [1]=Ažman, Gašper [2]=EMPTY [3]=BSI
BODY ROW 6: [1]=Bagdonas, Ignas [2]=EMPTY [3]=BSI
BODY ROW 7: [1]=Baker, Billy [2]=EMPTY [3]=ANSI
BODY ROW 8: [1]=Balog, Pal [2]=EMPTY [3]=ANSI
BODY ROW 9: [1]=Banglawala, Neelofer [2]=EMPTY [3]=BSI
BODY ROW 10: [1]=Benetkiewicz, Paweł [2]=EMPTY [3]=PKN
BODY ROW 11: [1]=Berge', Agustin [2]=EMPTY [3]=UNI
BODY ROW 12: [1]=Berne, Joshua [2]=EMPTY [3]=ANSI
BODY ROW 13: [1]=Beyls, Kristof [2]=EMPTY [3]=BSI
BODY ROW 14: [1]=Bi, Brian [2]=EMPTY [3]=ANSI
BODY ROW 15: [1]=Bindels, Peter [2]=EMPTY [3]=NEN
BODY ROW 16: [1]=Birbacher, Frank [2]=EMPTY [3]=ANSI
BODY ROW 17: [1]=Blackwell, Bianca [2]=EMPTY [3]=SCC
BODY ROW 18: [1]=Boeckel, Ben [2]=EMPTY [3]=ANSI
```

### diag-continuation-header [PASS]

**Question:** Are the values 'de Wever, Mark' and 'ANSI' actual column header names (like field labels), or are they data values (like a person's name and their organization)? Answer 'column headers' or 'data values'.

**Expected:** data values

**Answer (516ms):**

```
data values
```

## Summary

DeepSeek V4 Pro **recognizes** the N5040 Attendance defect when asked to count delimiters: all probes passed.

This is evidence about model comprehension, not a certification.
