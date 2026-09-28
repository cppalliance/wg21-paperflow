---
title: "std::hive: An Unordered Contiguous-Block Container for C++26"
document: P0447R26
date: 2026-09-28
intent: change
audience:
  - "LEWG"
  - "LWG"
author:
  - "Matthew Bentley <matt.bentley.k-17@outlook.com>"
  - "Jane Doe <jane@example.com>"
reply-to: "matt.bentley.k-17@outlook.com"
---

## Abstract {#abstract}

This paper proposes `std::hive` (formerly *colony*) as a new standard container. It guarantees **pointer stability** and fast element removal without shifting subsequent elements.

## 1. Introduction {#intro}

Standard sequence containers require tradeoffs between pointer validity and cache friendliness. While vector forces reallocations, hive uses segmented contiguous blocks.

### 1.1 Key Characteristics {#intro-key}

- Stable pointers across insertions
- Constant time erasure with tombstone tracking
- No relocation of existing elements

## 2. Code Comparison {#comparison}

| Before (C++23) | After (Proposed) |
| --- | --- |
| `// Vector with pointer invalidation`<br>`std::vector<Item> items;`<br>`items.push_back(item);` | `// Hive with pointer stability`<br>`std::hive<Item> items;`<br>`items.insert(item);` |

*Table 1: Usage comparison*

## 3. Design Synopsis {#synopsis}

```cpp title="hive.hpp"
template <typename T, typename Alloc = std::allocator<T>>
class hive {
public:
    iterator insert(const T& val);
    iterator erase(const_iterator it);
};
```

> [Note 1: Iterators are bidirectional and not random access.
> - end note]

---

## 4. Proposed Wording {#wording}

Modify 24.3 [containers.summary] paragraph 1 as follows: <del>The library provides sequence containers.</del> <ins>The library provides sequence containers, including hive.</ins>

<ins>A hive fulfills all requirements of a SequenceContainer.</ins>

## 5. Polls & Consensus {#polls}

| Motion | SF | F | N | A | SA | Outcome |
| :--- | :---: | :---: | :---: | :---: | :---: | ---: |
| Send P0447R26 to LWG for C++26? | 24 | 6 | 0 | 0 | 0 | Unanimous |

## 6. References {#references}

1. [P0447R26: Introduction of std::hive](https://wg21.link/p0447r26)
2. [P2300R10: std::execution](https://wg21.link/p2300r10)
