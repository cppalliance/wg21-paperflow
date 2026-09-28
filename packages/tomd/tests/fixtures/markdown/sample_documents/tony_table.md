---
title: "Tony Table Comparison Demonstration"
document: P3001R0
date: 2026-09-28
intent: change
audience:
  - "LEWG"
---

## Code Comparison {#comparison}

The following Tony Table illustrates the syntactic delta:

| Before (C++23) | After (Proposed) |
| --- | --- |
| `// Manual iteration`<br>`for (auto it = c.begin(); it != c.end(); ++it) {`<br>`    process(*it);`<br>`}` | `// Range-based view`<br>`for (auto&& x : c \| std::views::filter(pred)) {`<br>`    process(x);`<br>`}` |
| `std::vector<int> v;`<br>`// Potential reallocation`<br>`v.push_back(42);` | `std::hive<int> h;`<br>`// Never reallocates elements`<br>`h.insert(42);` |

*Table 1: Side-by-side comparison*
