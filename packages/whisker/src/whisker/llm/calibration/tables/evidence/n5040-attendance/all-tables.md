# N5040 All-Tables Count-Dump Results (v1.0.6)

Date: 2026-08-16
Model: deepseek-v4-pro
Service: alliance-pod
Paper: data\paperstore\n5040.md
Contract: v1.0.6

Total units probed: 8
Pass: 0  Fail: 0  Skip: 0

## Per-unit results

### T0 [aligned] [FAIL]

**Question:** Count the pipe delimiters in each row of the table below. List every cell left-to-right using 1-based column indices.

Use this exact format (one line per row, EMPTY for blank cells):
HEADER: [1]=... ...

**Expected:** aligned cell dump

**Answer (0ms):**
```
(transport error: ReadTimeout: The read operation timed out)
```

### T1 [aligned] [FAIL]

**Question:** Count the pipe delimiters in each row of the table below. List every cell left-to-right using 1-based column indices.

Use this exact format (one line per row, EMPTY for blank cells):
HEADER: [1]=... ...

**Expected:** aligned cell dump

**Answer (0ms):**
```
(transport error: ReadTimeout: The read operation timed out)
```

### T2 [label_shift] [FAIL]

**Question:** Count the pipe delimiters in each row of the table below. List every cell left-to-right using 1-based column indices.

Use this exact format (one line per row, EMPTY for blank cells):
HEADER: [1]=... ...

**Expected:** cell dump showing label shift

**Answer (0ms):**
```
(transport error: ReadTimeout: The read operation timed out)
```

### T3 [continuation] [FAIL]

**Question:** Are the values 'de Wever, Mark' and 'ANSI' actual column header names (like field labels), or are they data values (like a person's name and their organization)? Answer 'column headers' or 'data value...

**Expected:** data values

**Answer (0ms):**
```
(transport error: ReadTimeout: The read operation timed out)
```

### T4 [continuation] [FAIL]

**Question:** Are the values 'Kawulak, Robert' and 'PKN' actual column header names (like field labels), or are they data values (like a person's name and their organization)? Answer 'column headers' or 'data value...

**Expected:** data values

**Answer (0ms):**
```
(transport error: ReadTimeout: The read operation timed out)
```

### T5 [continuation] [FAIL]

**Question:** Are the values 'Nash, Phil' and 'BSI' actual column header names (like field labels), or are they data values (like a person's name and their organization)? Answer 'column headers' or 'data values'....

**Expected:** data values

**Answer (0ms):**
```
(transport error: ReadTimeout: The read operation timed out)
```

### T6 [continuation] [FAIL]

**Question:** Are the values 'Tanwar Preeti' and 'ANSI' actual column header names (like field labels), or are they data values (like a person's name and their organization)? Answer 'column headers' or 'data values...

**Expected:** data values

**Answer (0ms):**
```
(transport error: ReadTimeout: The read operation timed out)
```

### T7 [continuation] [FAIL]

**Question:** Are the values 'Mara Bos' and 'NEN' actual column header names (like field labels), or are they data values (like a person's name and their organization)? Answer 'column headers' or 'data values'....

**Expected:** data values

**Answer (0ms):**
```
(transport error: ReadTimeout: The read operation timed out)
```

## Punch-list comparison

- Label shift detected by LLM: NO
- Continuation headers found by LLM: []
- Missing from punch-list: ['Kawulak, Robert', 'Mara Bos', 'Nash, Phil', 'Tanwar Preeti', 'de Wever, Mark']
- Aligned units that false-failed: ['T0', 'T1']

Punch-list NOT fully covered:
  - Label shift not seen by LLM
  - Missing continuation headers: ['Kawulak, Robert', 'Mara Bos', 'Nash, Phil', 'Tanwar Preeti', 'de Wever, Mark']
  - Aligned false-fails: ['T0', 'T1']
