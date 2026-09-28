---
title: "Nested Lists, Blockquotes, and Code Blocks"
document: P3004R0
date: 2026-09-28
intent: info
audience:
  - "LEWG"
---

## Design & Implementation {#design}

Key design requirements are grouped into priority tiers:

- High Priority:
  - Stable pointer guarantees across insertion
  - Constant time element erasure
- Medium Priority:
  - Full bidirectional iterator conformance
  - Custom memory allocator support
- Low Priority: Legacy interoperability wrappers

### Execution Steps {#steps}

1. Analyze existing benchmarks.
   Initial results indicate 2x speedup.
2. Implement prototype in reference repository.
3. Submit wording to LWG review.

---

### Code Synopsis {#synopsis}

```cpp title="hive_synopsis.hpp"
#include <hive>

template <typename T>
class hive {
public:
    using value_type = T;
};
```

### Markdown Fence Escaping {#fence-escape}

````markdown title="doc_snippet.md"
```cpp
// Nested markdown code fence inside block
auto x = 42;
```
````

> [Note 1: An implementation may choose block allocation chunk sizes based on cache line geometry.
> - end note]
