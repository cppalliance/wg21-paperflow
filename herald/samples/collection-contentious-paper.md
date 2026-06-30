# Collection: brief-20260210-p4005-guaranteed-contracts

Evidence package assembled for brief generation. This file contains the catalog
entries that triggered the story, full extracted texts from the content store,
research desk query results, and person records consumed during Step 4.

- **Catalog window:** 2026-02-03 to 2026-02-10
- **Triage shape:** contentious-paper (soft trigger)
- **Triage hypothesis:** D4005R0 proposes a parallel assertion facility to P2900 contracts, generating sharp opposing reactions across EWG participants, public blogs, and Reddit
- **Item count:** 8 catalog entries, 6 full evidence documents, 4 research desk queries, 5 person records

---

## 1. Catalog entries

Items from the daily catalog that triggered the contentious-paper shape during
triage. Each entry is the lightweight metadata stored in `urls` + `contents`.

### CAT-1

- **Source:** open-std.org (web)
- **URL:** https://open-std.org/jtc1/sc22/wg21/docs/papers/2026/d4005r0.pdf
- **Title:** A proposal for guaranteed-(quick-)enforced contracts
- **Date:** 2026-02-03
- **Entities:** Ville Voutilainen, contracts, P2900, guaranteed enforcement, EWG
- **Content type:** paper
- **One-liner:** Proposes entry_cond, return_cond, and mandatory_assert as a syntactically distinct facility from P2900 contracts with guaranteed enforcement semantics.

### CAT-2

- **Source:** r/cpp (Reddit)
- **URL:** https://reddit.com/r/cpp/comments/example1/d4005_guaranteed_contracts/
- **Title:** D4005: A proposal for guaranteed contracts - separate from P2900
- **Date:** 2026-02-06
- **Entities:** Ville Voutilainen, P2900, D4005, contracts, EWG
- **Content type:** discussion thread
- **One-liner:** Reddit thread discussing D4005R0; 287 comments, significant engagement and polarized reactions.

### CAT-3

- **Source:** bradenganetsky.com (blog, RSS)
- **URL:** https://bradenganetsky.com/2026/02/ewg-telecon-2026-02-05/
- **Title:** EWG Telecon Trip Report - February 5, 2026
- **Date:** 2026-02-06
- **Entities:** Braden Ganetsky, EWG, D4005, P2900, Ville Voutilainen, Joshua Berne, John Lakos, David Sankel, Timur Doumler, Lisa Lippincott, Anthony Williams
- **Content type:** post
- **One-liner:** Detailed public trip report from the EWG telecon including D4005 discussion, quotes from participants, and poll results.

### CAT-4

- **Source:** open-std.org (web)
- **URL:** https://open-std.org/jtc1/sc22/wg21/docs/papers/2025/p3911r0.pdf
- **Title:** Guaranteed enforcement of contracts
- **Date:** 2025-10-15
- **Entities:** contracts, P2900, guaranteed enforcement, EWG
- **Content type:** paper
- **One-liner:** Earlier proposal to add check_always evaluation semantic to P2900; rejected by EWG in late 2025.

### CAT-5

- **Source:** r/cpp (Reddit)
- **URL:** https://reddit.com/r/cpp/comments/example2/p2900_contracts_in_cpp26/
- **Title:** P2900 contracts in C++26 - what we got and what we didn't
- **Date:** 2025-12-18
- **Entities:** P2900, contracts, C++26, guaranteed enforcement
- **Content type:** discussion thread
- **One-liner:** Prior community discussion on P2900's enforcement model; highly upvoted comments requesting always-on checks.

### CAT-6

- **Source:** timur.audio (blog, RSS)
- **URL:** https://timur.audio/contracts-in-cpp26
- **Title:** Contracts in C++26: what, why, and what's next
- **Date:** 2025-09-22
- **Entities:** Timur Doumler, P2900, contracts, C++26, labels, C++29
- **Content type:** post
- **One-liner:** P2900 co-author explains MVP design philosophy, deferred features including labels and guaranteed semantics.

### CAT-7

- **Source:** open-std.org (web)
- **URL:** https://open-std.org/jtc1/sc22/wg21/docs/papers/2024/p2900r10.pdf
- **Title:** Contracts for C++
- **Date:** 2024-11-20
- **Entities:** Joshua Berne, Timur Doumler, contracts, C++26, EWG, CWG
- **Content type:** paper
- **One-liner:** The contracts MVP proposal adopted into the C++26 working draft.

### CAT-8

- **Source:** isocpp.org (web)
- **URL:** https://isocpp.org/blog/2025/08/cd-ballot-nb-comments
- **Title:** C++26 CD Ballot - National Body Comments Summary
- **Date:** 2025-08-30
- **Entities:** Romanian NB, RO 2-056, contracts, guaranteed enforcement, CD ballot
- **Content type:** announcement
- **One-liner:** Summary of CD ballot NB comments including Romanian NB comment RO 2-056 requesting guaranteed contract enforcement.

---

## 2. Evidence texts

Full extracted content for each item cited in the triage. Pulled from the
`contents` table by `content_hash_text`. In production these are the actual
extracted documents; here they are representative excerpts.

### EVIDENCE-1: D4005R0 paper (CAT-1)

**content_hash_text:** `sha256:a1b2c3...` | **visibility:** public

#### Abstract

This paper proposes a facility for guaranteed-enforced contract assertions in
C++, syntactically and semantically distinct from the contracts facility in
P2900. The proposed keywords `entry_cond`, `return_cond`, and `mandatory_assert`
provide assertions that are always checked, cannot be disabled at build time, and
prevent continuation into guarded code on failure.

#### Motivation

The contracts facility adopted for C++26 (P2900) makes enforcement semantics
build-mode-selectable. For safety-critical code, embedded systems, and large
codebases where assertion discipline is enforced by policy, this is insufficient.
Users in these domains require a standard facility that guarantees checks are
never elided.

Existing practice: every major codebase has a macro equivalent. Bloomberg has
`BSLS_ASSERT_OPT`. Google has `CHECK`. Adobe has `require`. These are always-on
assertions that cannot be compiled out. D4005 standardizes this existing practice.

#### Design summary

```cpp
int at(int index)
    entry_cond(index >= 0 && index < size());

std::string format(std::string_view fmt)
    return_cond(!result.empty());

void process(span<byte> data) {
    mandatory_assert(data.size() <= MAX_BUFFER);
    // ...
}
```

Key design choices:
- No constification: predicates follow usual expression evaluation rules
- Side effects permitted: no special restriction on predicate expressions
- Always checked: including through indirect calls (function pointers)
- Implementation-defined failure mode: enforce (terminate) or quick-enforce (trap), not user-selectable at the call site
- Mixing with P2900 `pre`/`post`/`contract_assert` on the same declaration is ill-formed
- Lambda expressions in `entry_cond` and `return_cond` are ill-formed (cannot be redeclared)

#### Implementation experience

GCC 14 and 15 shipped C++2a contract assertions with configurable evaluation
semantics including an always-enforce mode. GCC trunk has since replaced this
with P2900's semantics. A branch prototype demonstrated that two forms of
assertion (constified and non-constified) can coexist in the same program.

### EVIDENCE-2: EWG telecon trip report (CAT-3)

**content_hash_text:** `sha256:d4e5f6...` | **visibility:** public

#### D4005R0 discussion

Ville Voutilainen presented D4005R0. Key points from the presentation:

- The facility is syntactically distinct from P2900 to avoid interaction complexity
- "Guaranteed" means the check cannot be compiled out regardless of build mode
- The failure mode (terminate vs trap) is implementation-defined, not user-selectable
- Mixing D4005 and P2900 annotations on the same declaration is ill-formed for now
- GCC 14-15 implementation experience cited

Discussion was sharply divided.

**In favor:**
- Ville Voutilainen: "If we ship just C++26 contracts for this purpose, you will fail miserably. Our toolbox in this multiverse domain is too incomplete to be viable."
- David Sankel (Adobe): "For our 10,000 developers, we'll need to suppress usage of contracts in our code base." Cited Rust's `assert!` vs `debug_assert!` as evidence that two assertion facilities can coexist without user confusion.
- Darius Neatu (Romanian NB): Confirmed D4005 satisfies the Romanian NB comment RO 2-056. "Besides NB comments, we have safety concerns with certain industries, and we need to address these issues now."
- Anthony Williams: "This is just an attempt to add guaranteed precondition assertions and postconditions. [...] If there will be a way to guarantee them with labels, then labels will have exactly the same problems."

**Against:**
- Joshua Berne: "This is actively hostile to interacting with C++ contracts, and it will cause a never-ending stream of problems. Because side effects are allowed, people will do that and depend on it." Called it "trying to do 2 very different things badly."
- John Lakos: "It would double the cognitive load for new users. It's not welcome. The design is not incomplete. It's procedurally and practically years late to C++26. Adding this will actively damage WG21's reputation."
- Timur Doumler: Raised virtual function incompatibility. D4005's guarantee of exactly-once evaluation is incompatible with caller-side checking needed for virtual contracts. "Either we make entry cond and return cond behave differently, which isn't good language design. But on the other hand, we close the door for virtual functions."
- Jan Schultke: "I don't want to see side effects. That would be very weird, and I think constification is for the better."
- Lisa Lippincott: Presented a dynamic-library scenario where optimizer reliance on guaranteed predicates causes breakage when the library upgrades independently.
- Andrzej Krzemienski: "If we were to adopt it, we would be going against the idea of standardization. The whole idea is that we are deciding on one way for everyone to do things."

#### Poll results

| Poll | SF | F | N | A | SA | Result |
|------|----|----|---|---|-----|--------|
| Encourage more work on D4005 for C++26 | 8 | 5 | 2 | 9 | 14 | Not consensus |
| Encourage more work on D4005 for C++29 | 9 | 4 | 8 | 8 | 6 | Not consensus |

Neither direction achieved consensus. Voutilainen indicated he could bring a paper to Croydon regardless, noting it addresses an NB comment.

### EVIDENCE-3: Reddit r/cpp thread on D4005 (CAT-2)

**content_hash_text:** `sha256:g7h8i9...` | **visibility:** public

Thread posted 2026-02-06, 287 comments, score 342.

Selected high-engagement comments (top-level, sorted by score):

- "So we're getting two incompatible contract systems that can't be mixed? This is the C++ way I guess." (score 189)
- "As someone writing safety-critical embedded code: I need this. P2900's 'maybe we check, maybe we don't' is useless to me. I have regulators who want proof that assertions fire in production." (score 156)
- "The side effects thing is a dealbreaker. The whole point of contracts is that you can reason about them as pure predicates. Once you allow side effects, you have function decorators with bad syntax." (score 134)
- "Bloomberg and Adobe telling the committee they'll suppress P2900 usage should be a wakeup call. These are exactly the codebases contracts are supposed to help." (score 128)
- "Ville is right that labels are vaporware. They're not designed, not specified, not implemented. Telling people to wait for C++29 labels is telling them to wait for Godot." (score 112)

### EVIDENCE-4: Timur Doumler blog post (CAT-6)

**content_hash_text:** `sha256:j0k1l2...` | **visibility:** public

Relevant excerpts:

> The design philosophy behind P2900 is deliberate minimalism. We ship the core
> facility - preconditions, postconditions, and assertions with a clean syntax and
> well-defined semantics - and we defer extensions to future standards. Labels,
> guaranteed enforcement, virtual function contracts: these are all on the roadmap
> for C++29 and beyond.

> Why not ship everything now? Because the interactions between these features are
> not yet understood well enough. The label design space in particular has
> significant open questions around ODR, mangling, and library ABI. Getting these
> wrong would be worse than deferring.

> The MVP is stable, implementable, and useful today. Three major compilers are
> working on implementations. That is the measure of success for C++26.

### EVIDENCE-5: Reddit r/cpp prior thread on P2900 (CAT-5)

**content_hash_text:** `sha256:m3n4o5...` | **visibility:** public

Thread posted 2025-12-18, 203 comments, score 278.

Recurring themes:
- Disappointment that always-on enforcement was deferred
- Comparison to Rust's assertion model
- Concern that P2900 will be "just another assert macro" without guaranteed semantics
- Support for the MVP approach: "ship something, iterate later"
- Skepticism about the C++29 timeline for labels

### EVIDENCE-6: CD ballot NB comments summary (CAT-8)

**content_hash_text:** `sha256:p6q7r8...` | **visibility:** public

Romanian NB comment RO 2-056:

> Romania requests that the contracts facility in C++26 provide a means for
> guaranteed enforcement of contract assertions that cannot be disabled by build
> configuration. Safety-critical industries regulated by IEC 61508 and ISO 26262
> require demonstrable evidence that runtime checks are present in deployed
> software. The current design's build-mode-selectable semantics do not satisfy
> this requirement.

---

## 3. Research desk queries

Background context retrieved from the research desk's semantic index during brief
generation. Each query returns chunks with provenance.

### QUERY-1: "History of C++ contracts proposals"

**Results (3 chunks):**

**Chunk 1** - P0542R5 "Support for contract based programming in C++"
- **Source:** open-std.org, P0542R5, 2018
- **Publish date:** 2018-06-25
- **Relevance:** Original contracts proposal adopted for C++20. Introduced `expects`, `ensures`, `assert` syntax with build levels (default, audit, axiom). Removed from the C++20 working draft in Cologne (July 2019) after unresolved issues with continuation semantics, literal semantics, and the interaction between build levels and optimization.

**Chunk 2** - Trip report: C++ committee meeting in Cologne, July 2019
- **Source:** herbsutter.com, 2019-07-20
- **Publish date:** 2019-07-20
- **Relevance:** Herb Sutter's trip report documenting the removal of contracts from C++20. Key quote: "Contracts was removed from C++20 by a plenary vote because of concerns about the feature's maturity and unresolved semantic issues." The removal was driven by a combination of technical concerns (continuation mode) and process concerns (insufficient implementation experience).

**Chunk 3** - P2900R0 "Contracts for C++"
- **Source:** open-std.org, P2900R0, 2023
- **Publish date:** 2023-02-10
- **Relevance:** The restart. P2900 adopts a fundamentally different design philosophy from P0542: no build levels, no continuation semantics, constification of predicates, evaluation-undefined semantics as the default. Explicitly targets MVP for C++26 with extensions deferred.

### QUERY-2: "What committee roles do D4005 discussion participants hold?"

**Results (4 chunks):**

**Chunk 1** - Ville Voutilainen
- **Source:** isocpp.org committee page, accessed 2026-01
- **Relevance:** Finnish NB head of delegation. Former EWG chair. GCC maintainer (libstdc++). Implemented C++2a contracts in GCC. Long-standing advocate for guaranteed contract enforcement.

**Chunk 2** - Joshua Berne
- **Source:** isocpp.org committee page, accessed 2026-01
- **Relevance:** Co-author of P2900 (contracts MVP). Bloomberg employee. SG21 (Contracts) active participant. Has championed the MVP approach and constification as a core design principle.

**Chunk 3** - Timur Doumler
- **Source:** isocpp.org committee page, accessed 2026-01
- **Relevance:** Co-author of P2900. Chair of SG21 (Contracts study group). Has written extensively about the contracts design philosophy and the deferred-features roadmap.

**Chunk 4** - John Lakos
- **Source:** isocpp.org committee page, accessed 2026-01
- **Relevance:** Bloomberg VP and chief C++ architect. Author of "Large-Scale C++ Software Design." P2900 co-author (P2914 labels proposal). Has called P2900+labels the complete solution and opposed parallel facilities.

### QUERY-3: "P3911 guaranteed enforcement rejection"

**Results (2 chunks):**

**Chunk 1** - P3911R0 "Guaranteed enforcement of contracts"
- **Source:** open-std.org, P3911R0, 2025
- **Publish date:** 2025-10-15
- **Relevance:** Proposed adding `check_always` as a fourth evaluation semantic to P2900 alongside `ignore`, `observe`, and `enforce`. Would have allowed `pre check_always(x > 0)` syntax. Rejected by EWG on grounds that it introduced a "magic token" that conflicted with the label design space (labels are intended to carry evaluation-semantic information in C++29).

**Chunk 2** - EWG meeting minutes summary (public)
- **Source:** isocpp.org blog, 2025-11-05
- **Publish date:** 2025-11-05
- **Relevance:** Summary of the P3911 rejection. Poll: "Pursue P3911's approach of adding guaranteed enforcement as an evaluation semantic in P2900 for C++26" - SF 6, F 8, N 5, A 11, SA 9 - not consensus. The rejection's rationale centered on reserving the syntax space for labels, not on the goal being invalid.

### QUERY-4: "Has Herald covered contracts before?"

**Results:** No prior Herald coverage found. This would be the first Herald article on the contracts topic.

---

## 4. Person records

Relevant entries from the people store for individuals central to this story.

### Ville Voutilainen

- **person_id:** `uuid:ville-voutilainen`
- **Status:** active
- **Primary domain:** C++ standardization, compiler implementation
- **Affiliations:** Finnish NB (head of delegation), GCC (maintainer, libstdc++)
- **Committee roles:** EWG (former chair), Finnish NB representative
- **Recent events:**
  - 2026-02-05: Presented D4005R0 at EWG telecon
  - 2025-10: Spoke against P2900's enforcement model at Wroclaw plenary
  - 2024-03: Removed C++2a contracts implementation from GCC trunk in favor of P2900

### Joshua Berne

- **person_id:** `uuid:joshua-berne`
- **Status:** active
- **Primary domain:** C++ standardization, library design
- **Affiliations:** Bloomberg (senior developer)
- **Committee roles:** SG21 (Contracts), EWG, P2900 co-author
- **Recent events:**
  - 2026-02-05: Opposed D4005R0 at EWG telecon
  - 2024-11: P2900R10 adopted into C++26 working draft
  - 2024-06: Presented P2900 implementation status at CppNow

### Timur Doumler

- **person_id:** `uuid:timur-doumler`
- **Status:** active
- **Primary domain:** C++ standardization, audio programming
- **Affiliations:** Independent consultant
- **Committee roles:** SG21 chair, EWG, P2900 co-author
- **Recent events:**
  - 2026-02-05: Opposed D4005R0 at EWG telecon, raised virtual function incompatibility
  - 2025-09: Published blog post explaining P2900 MVP philosophy
  - 2024-11: P2900R10 adopted into C++26 working draft

### John Lakos

- **person_id:** `uuid:john-lakos`
- **Status:** active
- **Primary domain:** Large-scale C++ design, library architecture
- **Affiliations:** Bloomberg (VP, chief C++ architect)
- **Committee roles:** EWG, P2914 (labels) author
- **Recent events:**
  - 2026-02-05: Opposed D4005R0 at EWG telecon, called it reputationally damaging
  - 2025-06: Presented P2914 labels proposal at Wroclaw

### David Sankel

- **person_id:** `uuid:david-sankel`
- **Status:** active
- **Primary domain:** C++ standardization, software architecture
- **Affiliations:** Adobe (principal architect)
- **Committee roles:** EWG
- **Recent events:**
  - 2026-02-05: Supported D4005R0 at EWG telecon, cited Rust assertion model and Adobe's need for guaranteed enforcement
  - 2025-06: Presented Adobe's contracts usage requirements at Wroclaw

---

## 5. Sufficiency assessment

**Result: SUFFICIENT**

The contentious-paper shape requires: paper number, author, working group, at
least two sources with opposing reactions.

- Paper identified: D4005R0 (Voutilainen)
- Working group: EWG
- Opposing reactions confirmed across 6 evidence sources:
  - Pro-D4005: Voutilainen, Sankel (Adobe), Neatu (Romanian NB), Williams
  - Anti-D4005: Berne, Lakos, Doumler, Schultke, Lippincott, Krzemienski
- Poll data with exact vote counts available
- Background context on P2900 history, P3911 rejection, and NB comment pressure available
- Person records for all central participants available

Evidence clears the sufficiency gate. Proceed to brief generation.
