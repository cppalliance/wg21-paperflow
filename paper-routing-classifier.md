---
date: 2026-06-16
title: "Multi-Hypothesis Classifier for WG21 Paper Routing"
source: "Chat analysis of N3854 + architectural design session"
---

# Multi-Hypothesis Classifier for WG21 Paper Routing

A design specification for a sentence-level multi-hypothesis classifier that determines which review groups a C++ standards paper should be routed to. The classifier supports multi-label output - a single paper can be destined for more than one group.

---

## Background for Non-C++ Readers

The C++ programming language is maintained by an ISO working group called WG21. When someone wants to change the language or its standard library, they write a proposal paper. That paper gets reviewed by one or more sub-groups, each responsible for a different concern:

| Group | Name | What it reviews |
|---|---|---|
| **LEWG** | Library Evolution Working Group | Design of new library features or changes to existing ones. "Should we add this facility? Is the API shape right?" |
| **LWG** | Library Working Group | Precise specification text (wording) for library features. "Does the normative text say exactly the right thing?" |
| **EWG** | Evolution Working Group | Design of new language features or changes to existing ones. "Should the language support this syntax or semantic?" |
| **CWG** | Core Working Group | Precise specification text (wording) for language features. "Does the grammar and normative text say exactly the right thing?" |

The key distinction is two independent axes:

- **Domain**: Library (the pre-built toolkit that ships with the language) vs. Language (the grammar, syntax, and rules of the language itself)
- **Mode**: Design (proposing and justifying a new capability) vs. Wording (specifying the exact normative text that goes into the standard document)

These two axes produce a 2x2 grid that maps directly onto the four groups:

```
                  LIBRARY        LANGUAGE
               ┌────────────┬──────────────┐
  DESIGN       |   LEWG      │    EWG        |
               ├────────────┼──────────────┤
  WORDING      │   LWG       │    CWG        |
               └────────────┴──────────────┘
```

A paper can land in multiple cells. A paper proposing a new language keyword that also introduces library support functions would go to both EWG and LEWG. A paper that includes both the design rationale and the finished specification text might visit LEWG and then LWG.

---

## Architecture Overview

The classifier operates in six stages:

```
  ┌─────────────┐
  │  Raw Paper   │
  └──────┬──────┘
         ▼
  ┌─────────────────────┐
  │ 1. Sentence Splitting │
  └──────┬──────────────┘
         ▼
  ┌─────────────────────┐
  │ 2. Section Detection  │  (rule-based: which part of the paper is this?)
  └──────┬──────────────┘
         ▼
  ┌──────────────────────────┐
  │ 3. Hypothesis Scoring       │  (N binary classifiers per sentence)
  └──────┬───────────────────┘
         ▼
  ┌──────────────────────────┐
  │ 4. Section-Aware           │  (aggregate sentence vectors within
  │    Aggregation             │   and across sections)
  └──────┬───────────────────┘
         ▼
  ┌──────────────────────────┐
  │ 5. Sustained Signal Test    │  (suppress noise from stray mentions)
  └──────┬───────────────────┘
         ▼
  ┌──────────────────────────┐
  │ 6. Multi-Label Threshold    │  (emit 0-4 labels with confidence)
  └──────────────────────────┘
```

---

## Stage 1: Sentence Splitting

Split the paper into individual sentences. Standard NLP sentence tokenization, with one domain-specific rule: code blocks and declaration listings (template declarations, grammar productions) should each be treated as a single "sentence" so the hypothesis classifiers can evaluate them as units.

Inline code fragments within prose sentences stay attached to their enclosing sentence.

---

## Stage 2: Section Detection

WG21 papers follow a semi-structured format with recognizable section headings. Classify each sentence into a section type using pattern matching on headings.

| Section Type | Typical Headings |
|---|---|
| `PREAMBLE` | Title, document number, date, audience, reply-to, abstract |
| `MOTIVATION` | Introduction, Motivation, Motivation and Scope, Background, Problem Statement |
| `DESIGN` | Design, Design Decisions, Proposed Design, API, Interface, Proposal |
| `WORDING` | Wording, Proposed Wording, Standardese, Proposed Changes, Modifications to the Standard |
| `IMPACT` | Impact on the Standard, Compatibility, ABI Considerations, Feature Test Macro |
| `IMPLEMENTATION` | Implementation, Implementation Experience, Reference Implementation |
| `APPENDIX` | Acknowledgements, References, Appendix, Examples, Revision History |

**Why this matters**: The same sentence carries different weight depending on where it appears. A design rationale statement in the Motivation section is a strong signal. The same phrasing in an Appendix is background noise. Wording directives in a Wording section of a paper that also has substantial Design sections mean "design paper that includes its own spec text" - not "wording paper."

---

## Stage 3: Hypothesis Scoring

Each sentence is evaluated against a battery of binary hypotheses. Each hypothesis asks a yes/no question about the sentence. The output is a bit vector per sentence.

### Hypothesis Catalog

The hypotheses are organized into the same two axes (Domain and Mode) that define the four review groups, plus a set of structural/meta hypotheses.

#### Domain: Library (signals that the paper touches the standard library)

| ID | Name | What it detects | Example trigger |
|---|---|---|---|
| D1 | `REFERENCES_LIBRARY_HEADER` | Names a standard library header in angle brackets | "\<type_traits\>", "\<vector\>", "\<ranges\>" |
| D2 | `REFERENCES_LIBRARY_SECTION` | Cites a library clause number or stable name from the standard | "20.10.2 [meta.type.synop]", "[container.requirements]" |
| D3 | `NAMES_STD_ENTITY` | Names a specific type, function, template, or constant that lives in the standard library | "is_same", "std::vector", "tuple_size", "decay_t" |
| D4 | `NAMESPACE_STD_MUTATION` | Explicitly discusses adding to or modifying entities in namespace std | "adding new names to namespace std" |
| D5 | `REFERENCES_LWG_LEWG` | References an LWG or LEWG issue, defect report, or prior library paper | "LWG 2313", "LEWG", "Library Evolution" |
| D6 | `REFERENCES_LIBRARY_CONCEPT` | Discusses a standard library concept or named requirement | "Iterator", "Allocator model", "Ranges", "Container requirements" |
| D7 | `REFERENCES_LIBRARY_CUSTOMIZATION` | Discusses customization points, ADL-based extension, or trait specialization in a library context | "users may specialize", "customization point object" |

#### Domain: Language (signals that the paper touches the core language)

| ID | Name | What it detects | Example trigger |
|---|---|---|---|
| D8 | `REFERENCES_CORE_SECTION` | Cites a core language clause number or stable name | "[expr.prim]", "[dcl.dcl]", "[class.mem]", sections 1-16 |
| D9 | `NAMES_LANGUAGE_FEATURE` | Names a core language feature by its recognized name | "concepts", "modules", "coroutines", "structured bindings", "constexpr" |
| D10 | `GRAMMAR_PRODUCTION` | Contains or proposes a grammar production (BNF-style syntax rule) | "expression: assignment-expression", "lambda-expression" |
| D11 | `OVERLOAD_RESOLUTION` | Discusses overload resolution, argument-dependent lookup, or name lookup rules | "overload resolution", "ADL", "name lookup", "candidate set" |
| D12 | `TEMPLATE_INSTANTIATION` | Discusses template instantiation, specialization rules, or SFINAE in a language-rule context | "template argument deduction", "substitution failure", "instantiation" |
| D13 | `LIFETIME_SEMANTICS` | Discusses object lifetime, storage duration, or destruction order as language rules | "lifetime", "storage duration", "temporary materialization" |
| D14 | `REFERENCES_EWG_CWG` | References an EWG or CWG issue, defect report, or prior language paper | "CWG 1234", "EWG", "Evolution Working Group" |
| D15 | `TYPE_SYSTEM_RULES` | Discusses type deduction, conversion sequences, or type relationships as language rules | "implicit conversion sequence", "decltype", "type deduction" |

#### Mode: Design (signals that the paper is proposing or justifying a capability)

| ID | Name | What it detects | Example trigger |
|---|---|---|---|
| M1 | `PROPOSES_ADDITION` | Explicitly proposes adding new functionality to the standard | "proposal to add", "we propose", "this paper introduces" |
| M2 | `PROPOSES_MODIFICATION` | Proposes changing existing behavior or specification | "should be changed to", "we modify", "updated accordingly" |
| M3 | `PROPOSES_REMOVAL` | Proposes deprecating or removing something | "should be deprecated", "we propose removing" |
| M4 | `DESIGN_RATIONALE` | Explains why a design choice was made (the "why", not the "what") | "for consistency with", "because", "superior to", "for several reasons" |
| M5 | `NAMING_CONVENTION` | Discusses naming patterns, suffixes, prefixes, or naming policy | "_v suffix", "_t suffix", "naming convention" |
| M6 | `COMPARATIVE_EVALUATION` | Compares two or more alternative designs, syntaxes, or API forms | "superior to", "compared to", "alternative approach" |
| M7 | `USER_ERGONOMICS` | Argues about developer experience, learnability, verbosity, or usability | "simple to learn", "less verbose", "easier to", "unintuitive" |
| M8 | `API_SURFACE_DESCRIPTION` | Describes the shape of a proposed interface (signatures, template parameters, return types) | "the function takes", "returns a", "template parameter" |
| M9 | `PURE_EXTENSION_CLAIM` | Claims the change is purely additive and non-breaking | "pure extension", "no breaking changes", "backward compatible" |
| M10 | `SCOPE_BOUNDARY` | Bounds what the proposal does or does not affect | "this proposal doesn't touch", "limited to", "out of scope" |
| M11 | `IMPLEMENTATION_EVIDENCE` | Reports implementation experience, compilation, or deployment | "successfully compiled with", "implemented in", "existing practice" |
| M12 | `EXISTING_PRACTICE` | Appeals to existing practice in real-world codebases or other languages | "existing practice in Boost", "other languages provide", "widely used" |
| M13 | `PERFORMANCE_ARGUMENT` | Argues about runtime or compile-time performance characteristics | "zero overhead", "compile-time cost", "no runtime penalty" |

#### Mode: Wording (signals that the paper specifies exact normative text)

| ID | Name | What it detects | Example trigger |
|---|---|---|---|
| W1 | `NORMATIVE_SPECIFICATION` | Contains normative specification language | "shall", "Effects:", "Returns:", "Mandates:", "Preconditions:" |
| W2 | `WORDING_DIRECTIVE` | Instructs an editorial change to the standard text | "add the following", "modify paragraph X", "strike", "insert before" |
| W3 | `STABLE_NAME_EDIT` | Targets a specific stable name for textual modification | "modify [meta.type.synop] as follows" |
| W4 | `TABLE_MODIFICATION` | Proposes changes to a table in the standard | "add a row to Table 49", "modify Table X" |
| W5 | `FEATURE_TEST_MACRO` | Proposes or modifies a feature-test macro | "__cpp_lib_", "__has_cpp_attribute" |

#### Structural / Meta (signals about the paper itself, not its domain or mode)

| ID | Name | What it detects | Example trigger |
|---|---|---|---|
| S1 | `AUDIENCE_METADATA` | The paper's metadata explicitly names a target audience | "audience: Library", "audience: EWG, LEWG" |
| S2 | `CROSS_REFERENCE_PAPER` | References another WG21 paper by document number | "P1234R5", "N3854", "see [1]" |
| S3 | `BACKWARD_COMPATIBILITY` | Discusses backward compatibility or migration burden | "does not affect existing user code", "migration path" |
| S4 | `ABI_DISCUSSION` | Discusses ABI stability or breakage | "ABI break", "layout compatible", "binary compatibility" |
| S5 | `POLL_RESULT` | Reports the result of a committee poll or straw poll | "unanimous consent", "no objection", "poll result", "SF/F/N/A/SA" |

**Total: 40 hypotheses** (7 library-domain, 8 language-domain, 13 design-mode, 5 wording-mode, 5 structural, plus room to grow to 50 as needed).

---

## Stage 4: Section-Aware Aggregation

This is the most important stage. The goal is to convert per-sentence hypothesis vectors into four real-valued quadrant scores, one per review group.

### 4a. Group the hypotheses by axis

```
LIBRARY_DOMAIN  = {D1, D2, D3, D4, D5, D6, D7}
LANGUAGE_DOMAIN = {D8, D9, D10, D11, D12, D13, D14, D15}
DESIGN_MODE     = {M1, M2, M3, M4, M5, M6, M7, M8, M9, M10, M11, M12, M13}
WORDING_MODE    = {W1, W2, W3, W4, W5}
```

### 4b. Compute density per section per axis

For a given section type S and hypothesis group G:

```
count(G, S)   = number of sentences in S where at least one hypothesis in G fires
density(G, S) = count(G, S) / |S|       (fraction of section's sentences that trigger the group)
mass(G, S)    = count(G, S) / M_total   (fraction of entire paper's sentences)
```

If section S is absent from the paper, all its values are 0.

`|S|` is the number of sentences in section S. `M_total` is the total number of sentences in the paper.

### 4c. Compute quadrant scores

Each review group's score is the sum across all sections of a term that requires *both* the relevant domain axis *and* the relevant mode axis to fire. A section full of library entity names but with no design reasoning contributes to LWG (library + wording-by-default), not LEWG.

The combination function uses `min(domain_density, mode_density)`. This implements AND logic: both axes must be active for the section to contribute. A section with high library density but zero design density scores zero for LEWG.

```
LEWG_score = SUM over all section types S of:
    w(S, "design") * min(density(LIBRARY_DOMAIN, S), density(DESIGN_MODE, S)) * mass_factor(S)

LWG_score = SUM over all section types S of:
    w(S, "wording") * min(density(LIBRARY_DOMAIN, S), density(WORDING_MODE, S)) * mass_factor(S)

EWG_score = SUM over all section types S of:
    w(S, "design") * min(density(LANGUAGE_DOMAIN, S), density(DESIGN_MODE, S)) * mass_factor(S)

CWG_score = SUM over all section types S of:
    w(S, "wording") * min(density(LANGUAGE_DOMAIN, S), density(WORDING_MODE, S)) * mass_factor(S)
```

Where `mass_factor(S) = |S| / M_total` prevents a tiny section with high density from dominating.

### 4d. Section weights

The weights encode which sections are most informative for design vs. wording labels.

```
                   PREAMBLE  MOTIVATION  DESIGN  WORDING  IMPACT  IMPL  APPENDIX
  w(S, "design"):   0.3       1.0        1.0     0.1     0.5    0.3    0.0
  w(S, "wording"):  0.1       0.1        0.1     1.0     0.2    0.0    0.0
```

Interpretation:
- Design rationale in MOTIVATION or DESIGN sections gets full weight.
- Wording directives in a WORDING section get full weight.
- Design rationale found inside a WORDING section is heavily downweighted (0.1) - it's likely just a brief explanatory note alongside the spec text.
- Wording directives found inside a DESIGN section are heavily downweighted (0.1) - they're likely forward references or previews, not the paper's primary contribution.
- APPENDIX contributes zero to design scores. Acknowledgements and references are not evidence of design intent.

### 4e. Metadata override

If hypothesis S1 (`AUDIENCE_METADATA`) fires, extract the explicitly stated audience. Add a bonus to the corresponding quadrant scores:

```
If metadata says "Library":        LEWG_score += 0.15, LWG_score += 0.10
If metadata says "Library Evolution": LEWG_score += 0.20
If metadata says "Core":           CWG_score += 0.15, EWG_score += 0.10
If metadata says "Evolution":      EWG_score += 0.20
```

The bonus is modest. Metadata is evidence, not gospel - some papers have incorrect or outdated audience fields.

---

## Stage 5: Sustained Signal Test

A label should only fire if its supporting evidence is *sustained*, not a single stray mention.

For each candidate label L, define the relevant sentences as those where hypotheses from *both* the required domain group and the required mode group co-fire (in the same sentence or in adjacent sentences within the same section).

```
relevant_count(LEWG) = sentences where any LIBRARY_DOMAIN hyp AND any DESIGN_MODE hyp fire
relevant_count(LWG)  = sentences where any LIBRARY_DOMAIN hyp AND any WORDING_MODE hyp fire
relevant_count(EWG)  = sentences where any LANGUAGE_DOMAIN hyp AND any DESIGN_MODE hyp fire
relevant_count(CWG)  = sentences where any LANGUAGE_DOMAIN hyp AND any WORDING_MODE hyp fire
```

Apply a minimum threshold:

```
min_sustained = max(3, floor(M_total * 0.02))
```

If `relevant_count(L) < min_sustained`, suppress the label regardless of its aggregated score. This prevents a paper that casually mentions "this interacts with overload resolution" from being flagged EWG.

The floor of 3 ensures very short papers (fewer than 150 sentences) still require at least 3 co-firing sentences. The 2% scaling ensures long papers need proportionally more evidence.

---

## Stage 6: Multi-Label Thresholding

After aggregation and sustained signal testing, apply per-label thresholds to produce the final output.

```
paper_labels = []

for label in [LEWG, LWG, EWG, CWG]:
    if score(label) > threshold(label) AND sustained_test(label) passes:
        confidence = normalize(score(label))
        paper_labels.append((label, confidence))

sort paper_labels by confidence descending
```

**Threshold calibration**: The thresholds should be tuned on a labeled dataset. As a starting point:

```
threshold(LEWG) = 0.08
threshold(LWG)  = 0.10
threshold(EWG)  = 0.08
threshold(CWG)  = 0.12
```

CWG has the highest threshold because CWG papers are rare and highly specific - false positives are more costly. LEWG and EWG have lower thresholds because design papers are common and varied.

**Valid outputs**:
- Zero labels: the paper is a trip report, direction paper, poll summary, or other non-proposal document
- One label: the common case - a paper targeting a single group
- Two labels: a paper with both design and wording for one domain (LEWG + LWG), or a cross-domain design paper (LEWG + EWG)
- Three or four labels: rare but legitimate for large cross-cutting proposals

---

## Worked Example: N3854

Paper: "Variable Templates For Type Traits" by Stephan T. Lavavej (2014). Proposes adding `_v` variable template aliases (like `is_same_v`) as shorthand for type trait `::value` access throughout the standard library.

### Hypothesis hits (selected sentences)

> "This is a proposal to add variable templates like is_same_v\<T, U\> as less-verbose synonyms for type traits like is_same\<T, U\>::value."

- D3 `NAMES_STD_ENTITY`: is_same_v, is_same - yes
- M1 `PROPOSES_ADDITION`: "proposal to add" - yes
- Section: MOTIVATION

> "...the C++17 Standard Library should be updated accordingly."

- D4 `NAMESPACE_STD_MUTATION`: "Standard Library should be updated" - yes
- M2 `PROPOSES_MODIFICATION`: "updated accordingly" - yes
- Section: MOTIVATION

> "Variable templates like is_same_v\<T, U\> are superior to nested constants like is_same\<T, U\>::value for several reasons:"

- D3 `NAMES_STD_ENTITY`: is_same_v, is_same - yes
- M6 `COMPARATIVE_EVALUATION`: "superior to" - yes
- Section: MOTIVATION

> "This proposal is a pure extension."

- M9 `PURE_EXTENSION_CLAIM`: "pure extension" - yes
- Section: IMPACT

> "It doesn't affect existing user code at all, except for adding new names to namespace std."

- D4 `NAMESPACE_STD_MUTATION`: "adding new names to namespace std" - yes
- S3 `BACKWARD_COMPATIBILITY`: "doesn't affect existing user code" - yes
- Section: IMPACT

> "In 20.10.2 [meta.type.synop], at the end of the... chunk, add:"

- D2 `REFERENCES_LIBRARY_SECTION`: "20.10.2 [meta.type.synop]" - yes
- W2 `WORDING_DIRECTIVE`: "add:" - yes
- Section: WORDING

### Aggregated profile

```
  LIBRARY_DOMAIN:   ████████████  (high - D2, D3, D4, D5 fire throughout)
  LANGUAGE_DOMAIN:  █             (minimal - one mention of "variable templates" as a language feature)
  DESIGN_MODE:      ████████      (strong - M1, M2, M4, M5, M6, M7, M9, M10 fire in MOTIVATION/DESIGN)
  WORDING_MODE:     ██████        (moderate - W2 fires repeatedly in WORDING section)
```

### Quadrant scores (illustrative)

```
  LEWG:  min(high_library, strong_design) * high_mass_in_design_sections     = 0.32
  LWG:   min(high_library, moderate_wording) * moderate_mass_in_wording_section = 0.11
  EWG:   min(minimal_language, strong_design) * near_zero_mass               = 0.01
  CWG:   min(minimal_language, moderate_wording) * near_zero_mass             = 0.00
```

### Result

```
  LEWG:  0.32 > 0.08 threshold, sustained = 12 sentences (passes)  -> LEWG (confidence: high)
  LWG:   0.11 > 0.10 threshold, sustained = 8 sentences (passes)   -> LWG  (confidence: low)
  EWG:   0.01 < 0.08 threshold                                     -> suppressed
  CWG:   0.00 < 0.12 threshold                                     -> suppressed
```

**Output: LEWG (primary), LWG (secondary)**

This matches reality. N3854 is fundamentally a library design paper that includes its own wording. It was reviewed by LEWG for the design decision, and the wording was processed by LWG.

---

## Golden Set Sentences for Classifier Training

The following sentences from N3854 are labeled with their hypothesis hits. Use these as positive examples when training or few-shotting the sentence-level hypothesis classifiers.

### Strong LEWG signals (library domain + design mode co-firing)

| Sentence | Hypotheses |
|---|---|
| "This is a proposal to add variable templates like is_same_v\<T, U\> as less-verbose synonyms for type traits like is_same\<T, U\>::value." | D3, M1 |
| "...the C++17 Standard Library should be updated accordingly." | D4, M2 |
| "Variable templates like is_same_v\<T, U\> are superior to nested constants like is_same\<T, U\>::value for several reasons:" | D3, M6 |
| "We can't go back in time and change the design of type traits, but we can provide their ideal forms at the cost of 2 characters." | D3, M4, M7 |
| "This proposal uses an '_v' suffix to replace '::value', following N3655's use of '_t' to replace '::type'." | D3, M5, S2 |
| "This proposal adds variable templates for all of the UnaryTypeTraits and BinaryTypeTraits in \<type_traits\>, and for the rest of the Standard Library's '::value' machinery." | D1, D3, D4, M1 |
| "I believe that adding variable templates for everything is valuable - this allows users to learn the simple rule 'just say _t and _v' without exceptions." | M4, M5, M7 |
| "This alias template should exist for consistency with the type traits alias templates, for consistency with this proposal's tuple_size_v, and (most importantly) because 'typename ::type' is so horrible." | D3, M4, M7 |
| "It's simple to learn that '_v' means 'get the value' like how '_t' means 'get the type'." | M5, M7 |

### Impact / compatibility signals

| Sentence | Hypotheses |
|---|---|
| "This proposal is a pure extension." | M9 |
| "It doesn't affect existing user code at all, except for adding new names to namespace std." | D4, M9, S3 |
| "This proposal is limited to replacing '::value' systematically." | M10 |

### LWG signals (library domain + wording mode co-firing)

| Sentence | Hypotheses |
|---|---|
| "In 20.10.2 [meta.type.synop], at the end of the '// 20.10.4.1, primary type categories:' chunk, add:" | D2, W2, W3 |
| "In 20.4.1 [tuple.general]/2, at the end of the '// 20.4.2.5, tuple helper classes:' chunk, add:" | D2, W2, W3 |
| "In 20.9 [function.objects]/2, after the declaration of is_placeholder, add:" | D2, D3, W2, W3 |

### Negative examples (sentences that should NOT fire EWG/CWG despite surface similarity)

| Sentence | Why it's a false positive risk | Correct label |
|---|---|---|
| "Now that Gabriel Dos Reis has added variable templates to the C++14 Core Language..." | Mentions a language feature (D9), but as context for a library proposal, not as a proposed language change. No DESIGN_MODE co-fires with LANGUAGE_DOMAIN in a sustained way. | D9 fires, but no EWG label. |
| "After the C++11 Core Language gained alias templates..." | Same pattern - historical background about a language feature used as motivation for a library addition. | D9 fires in isolation, no EWG label. |

---

## Known Limitations

1. **Hybrid design-wording papers with blurry section boundaries.** When a paper interleaves design rationale with normative wording in the same section without clear headings, section detection fails and the aggregation cannot cleanly separate design signals from wording signals. Mitigation: fall back to paper-level aggregation without section weighting.

2. **Study Group papers.** Some WG21 sub-groups (SG1 Concurrency, SG7 Reflection, SG14 Low Latency, SG16 Unicode) do not map to the four review groups. The classifier will either output one of the four labels (acceptable if the paper eventually routes there) or output zero labels. If SG routing is needed, add dedicated labels.

3. **Very short papers (under ~15 sentences).** The sustained signal test requires at least 3 co-firing sentences, which may not be achievable. Scale `min_sustained` down for short papers, or bypass the test entirely and rely on raw scores.

4. **Revision drift.** Early revisions of a paper (R0, R1) tend to be design-heavy. Late revisions (R5, R6) tend to be wording-heavy. The classifier handles this naturally because it reads content, not document numbers - but training data must treat each revision as a separate document.

5. **Metadata disagreement.** Some papers list an audience that does not match their content. The classifier intentionally treats the metadata as weak evidence (a small bonus, not a deterministic override). When the classifier disagrees with the metadata, the classifier is often more informative.

---

## Implementation Notes

- The sentence-level hypothesis classifiers (Stage 3) can be implemented as a fine-tuned model, a zero-shot LLM with the hypothesis catalog as a system prompt, or a bank of regex/keyword matchers for the simpler hypotheses (D1, D2, D8, W2 are largely pattern-matchable).
- Stages 2, 4, 5, and 6 are deterministic computation - no ML required.
- The section weights and thresholds in this document are starting values. Calibrate on a labeled dataset of 100-200 papers with known routing history.
- To build the training set: WG21 paper metadata often includes an "audience" field, and committee minutes record which group reviewed each paper. These are ground-truth multi-labels.
