---
title: "std::hive Wording Plan"
document: P3005R0
date: 2026-10-15
intent: info
audience:
  - "LEWG"
---

## Proposed Changes

This revision makes three changes:

1. Add a hive container
   - Header synopsis
   - Member functions
     - Insertion and erasure
2. Define a feature-test macro

   The macro tracks the library revision.

   ```cpp
   #define __cpp_lib_hive 202602L
   ```
3.
   ```cpp
   static_assert(std::ranges::range<std::hive<int>>);
   ```

## Open Questions

5. Should erasure invalidate other iterators?
6. Should the block capacity be configurable?

The allocator requirements are:

(a) the allocator is copy constructible
(b) rebinding preserves equality
