# Brief: Guaranteed Contract Enforcement Splits EWG

- **Shape:** contentious-paper
- **Brief ID:** brief-20260210-p4005-guaranteed-contracts
- **Generated:** 2026-02-10
- **Catalog window:** 2026-02-03 to 2026-02-10
- **Triage hypothesis:** D4005R0 proposes a parallel assertion facility to P2900 contracts, generating sharp opposing reactions across EWG participants, public blogs, and Reddit

---

## Who, what, when, where

- **Paper:** D4005R0 "A proposal for guaranteed-(quick-)enforced contracts"
- **Author:** Ville Voutilainen
- **Related paper:** P2900 "Contracts for C++" (Joshua Berne, Timur Doumler, et al.)
- **Related paper:** P3911 "Guaranteed enforcement of contracts" (earlier attempt, rejected)
- **When:** D4005R0 presented at EWG telecon, 2026-02-05
- **Where:** EWG telecon; follow-up discussion on std-proposals, Reddit r/cpp, personal blogs
- **Committee context:** P2900 contracts adopted into the C++26 working draft. Romanian NB comment RO 2-056 requests guaranteed-enforcement semantics not present in P2900. Croydon meeting (2026 spring) is the next plenary opportunity.

---

## Key quotes

> "If we ship just C++26 contracts for this purpose, you will fail miserably. Our toolbox in this multiverse domain is too incomplete to be viable."
- Ville Voutilainen, EWG telecon 2026-02-05 (source: public trip report by Braden Ganetsky)

> "This is actively hostile to interacting with C++ contracts, and it will cause a never-ending stream of problems. Because side effects are allowed, people will do that and depend on it."
- Joshua Berne, EWG telecon 2026-02-05 (source: public trip report by Braden Ganetsky)

> "Adding this will actively damage WG21's reputation."
- John Lakos, EWG telecon 2026-02-05 (source: public trip report by Braden Ganetsky)

> "For our 10,000 developers, we'll need to suppress usage of contracts in our code base. We have our own macros, don't touch this facility."
- David Sankel, EWG telecon 2026-02-05 (source: public trip report by Braden Ganetsky)

> "Rust has had both types of assertions, and people understand the differences between them. In that world, people are not actively confused about it."
- David Sankel, EWG telecon 2026-02-05 (source: public trip report by Braden Ganetsky)

---

## Background context

- **P2900 history.** Contracts have been pursued since C++20, when the original contracts design (P0542) was adopted and then removed before publication due to unresolved design issues. P2900 represents the second attempt, led by Joshua Berne and Timur Doumler, adopting the Minimum Viable Product philosophy: ship a core facility in C++26, extend with labels and guaranteed semantics in C++29. P2900 was adopted into the C++26 working draft with strong consensus in 2024.
  - Provenance: open-std.org paper archive, P2900R10, 2024

- **The "always check" demand.** Multiple national bodies and large codebases (Adobe, Bloomberg, embedded/automotive) want contract checks that cannot be disabled at build time. The existing `assert()` macro is defeatable via `NDEBUG`. P2900's design deliberately makes enforcement semantics build-mode-selectable, which these stakeholders consider insufficient for safety-critical code.
  - Provenance: public NB comments filed during CD ballot, 2025

- **P3911 precedent.** An earlier proposal (P3911, "Guaranteed enforcement of contracts") attempted to add a `check_always` evaluation semantic to P2900. It was rejected by EWG in late 2025 on grounds that it introduced "magic tokens" and interacted poorly with the label design space reserved for C++29.
  - Provenance: open-std.org, P3911R0, 2025

- **D4005 approach.** D4005R0 takes a different tack: instead of extending P2900, it proposes a syntactically and semantically distinct facility using context-sensitive keywords (`entry_cond`, `return_cond`, `mandatory_assert`). Key design differences from P2900: no constification of predicates, side effects permitted, checks always fire including through indirect calls, mixing with P2900 annotations is ill-formed. GCC 14-15 implementation experience cited.
  - Provenance: open-std.org, D4005R0, 2026

- **EWG poll results.** Two polls taken at the 2026-02-05 telecon. "Encourage more work in the direction of D4005 for C++26": SF 8, F 5, N 2, A 9, SA 14 - not consensus. "Encourage more work in the direction of D4005 for C++29": SF 9, F 4, N 8, A 8, SA 6 - not consensus.
  - Provenance: public trip report by Braden Ganetsky, 2026-02-05

- **Fault lines.** The debate maps onto a known structural divide. Safety-critical and large-codebase stakeholders (Adobe, Bloomberg, Romanian NB, embedded vendors) want guaranteed enforcement now. P2900 authors and a majority of EWG regulars consider the MVP complete and want to defer guaranteed semantics to the label system in C++29. Neither camp achieved consensus to block the other's direction.
  - Provenance: public Reddit r/cpp discussion threads, February 2026

---

## Source list

| # | Source | Type | Visibility | Used for |
|---|--------|------|------------|----------|
| 1 | D4005R0, open-std.org | paper | public | Primary paper text, design rationale |
| 2 | P2900R10, open-std.org | paper | public | Contracts MVP design, history |
| 3 | P3911R0, open-std.org | paper | public | Prior rejected approach |
| 4 | Braden Ganetsky public trip report, 2026-02-05 | blog post | public | EWG telecon quotes, poll results |
| 5 | Reddit r/cpp "D4005 guaranteed contracts" thread, 2026-02-06 | discussion | public | Community reaction, vote analysis |
| 6 | Reddit r/cpp "P2900 contracts in C++26" thread, 2025-12 | discussion | public | Prior community sentiment |
| 7 | Timur Doumler blog, "Contracts in C++26", 2025-09 | blog post | public | P2900 design philosophy |
| 8 | Romanian NB comment RO 2-056, CD ballot | NB comment | public | Guaranteed enforcement requirement |
| 9 | EWG reflector discussion thread, 2026-02 | reflector | private | Internal committee positions |
| 10 | CWG reflector discussion thread, 2026-02 | reflector | private | Wording interaction concerns |

---

## Suggested angles

1. **The safety schism.** Frame around the structural divide between "ship MVP now, extend later" and "guaranteed enforcement is table stakes for safety-critical adoption." The poll results show neither side commands consensus - a political stalemate with C++26 feature-freeze approaching.

2. **The Rust comparison.** David Sankel's invocation of Rust's dual-assertion model (`assert!` vs `debug_assert!`) as evidence that two facilities can coexist without confusion. Counter: Joshua Berne's argument that P2900's constification guarantee is what makes contracts useful for reasoning, and D4005 destroys that property.

3. **The labels bet.** P2900 proponents are betting that the label system (C++29) will eventually deliver guaranteed semantics within the P2900 framework. D4005 proponents argue that deferring to an undesigned feature is not a credible plan. Timur Doumler's own admission that the labels design "hasn't been pinned down yet" is cited by both sides.

4. **NB comment pressure.** Romanian NB comment RO 2-056 creates procedural obligation to address guaranteed enforcement. The committee must respond to NB comments during the CD ballot resolution process. D4005 is one possible response; dismissing the comment is another. The procedural angle is distinct from the technical merits.

5. **Reputation risk.** John Lakos's claim that adding D4005 "will actively damage WG21's reputation" vs. Ville Voutilainen's claim that shipping P2900 without guaranteed enforcement means "you will fail miserably." Both frame the other's position as an existential risk to the committee's credibility.

---

## Constraints

- **Word count:** 1500-2500 (News Response shape)
- **Embargo:** None. All cited sources are public or have been publicly reported.
- **Visibility restrictions:** Sources 9-10 (reflector threads) are private. Do not quote or paraphrase private reflector content. Use only for background awareness of positions already stated publicly.
- **Freshness window:** Story is current through 2026-02-10. If Croydon agenda is published before draft clears editorial review, update the "where next" framing.
