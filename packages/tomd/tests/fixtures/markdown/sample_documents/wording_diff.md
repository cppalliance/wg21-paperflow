---
title: "Proposed Wording for Standard Fixes"
document: P3002R0
date: 2026-09-28
intent: change
audience:
  - "LWG"
---

## Proposed Wording {#wording}

All wording modifications are relative to N4950.

### 24.3.11 Class template hive [hive.overview] {#hive.overview}

Modify paragraph 1 as follows:

A hive is a sequence container that supports constant-time insertion and erasure. An instance of `hive` <del>shall allocate elements using `std::allocator` exclusively.</del> <ins>may allocate memory using an allocator satisfying the `Allocator` requirements [allocator.requirements].</ins>

Modify 24.3.11.4 [hive.modifiers] as follows:

> iterator insert(const T& value);
> iterator insert(T&& value);
>
> -1- Effects: Inserts a copy or moved value into the hive.
> -2- Returns: An iterator pointing to the newly inserted element.
> -3- Complexity: Constant time.
> -4- Remarks: Does not invalidate any existing references or iterators.

<ins>A hive does not provide contiguous storage guarantee [container.reqmts].</ins>
