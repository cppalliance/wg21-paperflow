# tomd: PDF Vector Graphics with Semantic Meaning

## Status: OPEN
**Created**: 2026-05-21
**Component**: `packages/tomd/src/tomd/lib/pdf/`
**Priority**: MEDIUM (data loss: bullets, diagram structure, code block boundaries)

---

## Problem

PDF papers use **vector graphics** (drawn paths, filled shapes) to carry semantic meaning that MuPDF's text extraction silently drops. This affects two distinct categories:

1. **Inline figures** (flow diagrams, concept hierarchies, box-arrow diagrams): text labels extracted but graphical structure lost.
2. **Vector-rendered bullet points**: bullet symbols drawn as filled circles/squares instead of Unicode characters. The bullet is invisible to text extraction, destroying list structure.

### Example: P4003R1 Section 3

**PDF original** (box-arrow flow diagram):
```
┌──────────────┐  refined by  ┌──────────────┐  modeled by  ┌──────────────┐
│ IoAwaitable  │─────────────▶│ IoRunnable   │─────────────▶│ io_task<T>   │
└──────────────┘              └──────────────┘              └──────────────┘
```

**Current markdown output** (line 167):
```
#### refined by modeled by IoAwaitable IoRunnable io_task<T>
```

Two defects:
1. The text fragments are concatenated without structure, losing the directional relationship.
2. The bold/large font causes misclassification as an `#### H4` heading, disrupting document flow.

### Variants seen in WG21 papers

| Variant | Description | Example |
|---------|-------------|---------|
| Concept refinement chain | Boxes with labeled arrows showing concept hierarchy | P4003R1 Section 3 (p8) |
| UML sequence diagram | Lifeline boxes with labeled arrows showing call/return flow | P4003R1 Section 3.2 (p13) |
| Inheritance diagram | Class boxes connected by inheritance arrows | Common in type-erasure papers |
| Pipeline / data flow | Stages connected by arrows showing data transformation | Networking papers |
| State machine | States with labeled transitions | Concurrency papers |

### Category B: Vector-Rendered Bullet Points (P4003R1 Section 3.2)

In section 3.2 IoRunnable, four definition-list items use bullet points rendered as **vector-drawn filled circles**, not Unicode characters (U+2022 etc.):

**PDF original**:
```
• handle()  - Returns the typed coroutine handle...
• release() - Transfers frame ownership...
• exception() - Returns any stored std::exception_ptr...
• result()  - Returns the stored value...
```

**Current markdown output** (lines 301-307):
```
`handle()` - Returns the typed coroutine handle...

`release()` - Transfers frame ownership...

through a type-erased function pointer.

`result()` - Returns the stored value...
```

Three defects:
1. No bullet markers: items render as plain paragraphs, losing list structure.
2. `exception()` description split to next page (page 12), appearing as orphan text.
3. Interleaved orphan fragment "through a type-erased function pointer." (line 305) is a continuation of `release()` that got separated.

**Evidence**: MuPDF extraction for these blocks shows `bullet=False` at x0=81. The filled circles are drawn via `page.get_drawings()` vector paths, not text characters.

**Impact**: Common across WG21 papers. Many papers use drawn bullets instead of Unicode bullets, particularly papers generated from LaTeX with `itemize` environments.

### Related: Code Block Truncation (P4003R1 Section 3.2)

The `IoRunnable` concept code block ends prematurely at `p.result();`. The closing `});` is a separate MuPDF block (Block 37, page 11, y=486, monospace) that the code-fence detector fails to absorb. This causes `});` to leak into body text and merge with the `exception()` bullet description.

**Current output** (line 295):
```
`});` `exception()` - Returns any stored `std::exception_ptr` after the task completes.
```

This is a `structure.py` code-absorption bug, not a vector-graphics issue, but it compounds the bullet-loss problem in the same section.

### Why figures are NOT tables

Tables have a regular grid structure with rows and columns. Flow diagrams have:
- Irregular spatial layout (not grid-aligned)
- Directional relationships (arrows, not cells)
- Labels on connections, not just in cells
- Variable box sizes and positions

---

## Proposed Approach (tiered)

### Tier 1: Degrade gracefully (minimal fix)

Prevent misclassification as heading. Detect that a block contains interleaved graphic-text fragments and emit as a plain paragraph instead. This preserves the text content without the broken heading.

**Result**: `IoAwaitable refined by IoRunnable modeled by io_task<T>` (flat text, no heading)

### Tier 2: Figure placeholder (pragmatic)

Detect vector-graphic regions (MuPDF drawing commands or isolated text-fragments with large gaps between them) and emit a Markdown comment placeholder:

```markdown
<!-- figure: IoAwaitable refined by IoRunnable modeled by io_task<T> -->
```

This signals to downstream consumers (LLM pipelines, human readers) that a figure existed here.

### Tier 3: Mermaid reconstruction (ambitious, deferred)

Use text fragment positions and spatial relationships to reconstruct a Mermaid diagram:

````markdown
```mermaid
graph LR
    IoAwaitable -->|refined by| IoRunnable -->|modeled by| io_task
```
````

This would require:
- Detecting horizontal/vertical alignment patterns in text fragments
- Inferring directional relationships from spatial ordering (left-to-right, top-to-bottom)
- Mapping common diagram patterns (chain, tree, grid) to Mermaid syntax

**Complexity**: HIGH. Deferred until Tier 1/2 are validated and more examples are catalogued.

---

## Detection Signals

### For figures (Category A)

1. **Text fragment isolation**: Multiple small text blocks with large horizontal gaps (> 3x font size) between them on the same y-band, not matching table column patterns.
2. **Mixed font in non-heading context**: Bold text fragments at body-level y-position that don't match heading patterns.
3. **MuPDF vector paths**: Drawing commands (lines, rectangles, arrows) in the page region confirm a figure. Requires `page.get_drawings()` API.
4. **Low text density**: Region with few words spread over a large bounding box area (words-per-pt² below threshold).

### For vector bullets (Category B)

1. **`page.get_drawings()` small filled shapes**: Look for filled circles (radius < 4pt) or filled squares (side < 4pt) at x-positions just left of a text block's x0. These are vector-rendered bullets.
2. **Consistent x-offset pattern**: Multiple text blocks at the same x0, each preceded by a small filled shape at x0 - 10..15pt, suggest a bullet list.
3. **Definition-list pattern**: Text starting with `identifier()` or backtick-wrapped code followed by " - " (dash separator) is a definition list item, often bulleted.

### For code block absorption (related)

1. **Monospace orphan after code fence**: A monospace-only block immediately below a code section (small y-gap, same x-indent) should be absorbed into the code fence.

---

## Scope

- **Category A**: Inline figures within body text (flow diagrams, concept maps).
- **Category B**: Vector-rendered bullet points that MuPDF text extraction misses.
- **Related**: Code block truncation when closing tokens are in separate MuPDF blocks.
- **Out of scope**: Full-page figures, charts, photographs (image extraction problem). Table-like flowcharts (handled by table pipeline, see `tomd_body_pdf_tables.md`).

---

## Files likely affected

| Category | File | Change |
|----------|------|--------|
| A (figures) | `structure.py` | Heading classification guard (Tier 1) |
| A (figures) | `emit.py` | Figure placeholder emission (Tier 2) |
| A+B (shared) | `extract.py` or new `vectors.py` | `page.get_drawings()` analysis |
| B (bullets) | `extract.py` | Inject synthetic bullet spans from vector analysis |
| B (bullets) | `structure.py` | List detection from synthetic bullets |
| Related | `structure.py` | `_coalesce_code_paragraphs` / `_rescue_unfenced_code` |

## Papers to catalogue

A corpus scan for similar elements is needed before implementation. Known:

| Paper | Category | Element |
|-------|----------|---------|
| P4003R1 Section 3 (p8) | A (figure) | Concept refinement chain (IoAwaitable -> IoRunnable -> io_task) |
| P4003R1 Section 3.2 (p13) | A (figure) | UML sequence diagram (run_async / parent task / child task / I/O operation lifecycle with handle(), set_environment, await_suspend, resume, symmetric transfer) |
| P4003R1 Section 3.2 (p11-12) | B (bullets) | Vector-drawn bullets on handle()/release()/exception()/result() definition list |
| P4003R1 Section 3.4 (p15) | B (bullets) | Vector-drawn bullets on std::stop_token/alloc/h1/h2 parameter list. Four items collapsed into one paragraph (md line 440). |
| P4003R1 Section 5.3 (p35) | A (figure) | Vertical flowchart: TLS frame allocator propagation lifecycle (parent resumes -> parent calls child() -> child operator new reads TLS -> child created -> parent await_suspend -> child resumes -> child calls grandchild()). Seven boxes with downward arrows. |
| P4003R1 Section 5.3 (p35) | B (bullets) | Vector-drawn bullets on "This is safe because:" list (TLS read-only in operator new, TLS written by running coroutine, thread migration handling, no dangling, deallocation thread-independent). Five items. |
| P4003R1 Section 3.2 (p11) | Related | Code block truncation (`});` orphaned) |
| TBD | B (bullets) | LaTeX `itemize` papers with drawn bullets (common) |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-21 | Ticket created. Problem identified in P4003R1 Section 3. |
| 2026-05-21 | Expanded: added Category B (vector-rendered bullets) and related code block truncation from P4003R1 Section 3.2 analysis. Renamed ticket from "Inline Figures" to "Vector Graphics with Semantic Meaning". Priority raised to MEDIUM. |
