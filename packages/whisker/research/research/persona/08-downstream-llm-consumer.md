# 08 - The Downstream-LLM Consumer

**Verdict:** usable-with-conditions — whisker `pass` certifies structural well-formedness and high token-set recall against the source text layer, not that a dissect/agora LLM can recover facts, table geometry, math structure, or argument order; Lane 3 exists for that job but runs on **0/382** papers.
**Confidence:** high

## Findings

- [CRITICAL] **`pass` is not an LLM-comprehension certificate.** The spec states explicitly that fidelity axes "measure resemblance, not comprehension" and that only Lane 3 catches scrambled table cells or dropped exponents while fidelity stays green (`CLAUDE.md:30-40`). The default `whisker` verb calls `score_paper` only (`__main__.py:204`); it never invokes `check_facts`. Impact: **163/382 (42.7%)** ref-free passes (`00` §3a) and **368/382 (96.3%)** papers at default CI `--gate review` (`CLAUDE.md:302-303`) reach downstream pipelines with **zero** deterministic fact assertions enforced.

- [CRITICAL] **Lane 3 comprehension coverage is 0% on real data.** Corpus holds only `README.md` + template `EXAMPLE.facts.jsonl`; `whisker facts --corpus packages/whisker/corpus` errors with no staged candidates (`00` §4). `FactReport.passed` is vacuously true when no verified facts exist (`facts.py:128-130`: "a paper with no verified facts passes"). Impact: the five designed assertion types (`present`, `absent`, `order`, `table`, `math` in `facts.py:59-64`) have **0** production checks; comprehension blind spot is **100% of the corpus** by construction, not a sampling gap.

- [HIGH] **The operational hard gate optimizes multiset token presence, which dissect/agora cannot equate to readable structure.** Content hard-fail uses `unigram_coverage` only below **0.85** (`score.py:156-160`, `constants.py:37`); pass (ref-free) additionally requires `unigram_coverage >= 0.95`, zero soft flags (`score.py:161-184`). `unigram_coverage` is explicitly "ignoring order" (`check_content.py:141-142`). The order-sensitive shingle `coverage` is "never a verdict flag" (`score.py:136-137`). Impact: a conversion that **permutes paragraphs, list items, or table rows** but preserves word multiset can still `pass` while an LLM mis-attributes claims to the wrong section or reads "row 3, column 2" from the wrong cell; only Lane 3 `order` / `table` facts would catch this (`facts.py:353-367`, `corpus/README.md:58-62`).

- [HIGH] **Math and table semantics are structurally invisible to the pass bar.** `normalized_text` keeps alnum + CJK only (`metrics.py:118-126`), erasing `^`, `_`, `=` that carry exponent/subscript meaning; Lane 3 `math` facts deliberately use a surface that keeps those symbols (`facts.py:173-181`). Table fidelity (`teds`) lives in `bench`/`guard` against `<pid>.gt.md` (`score.py:19-20`, `CLAUDE.md:30-31`), not in the default score path. Impact: dropping `^2` from `$x^2$` or swapping adjacent pipe-table cells can leave `unigram_coverage` near **0.966** corpus mean (`00` §3b) and still `pass`; only **3/382 (0.8%)** ref-free fails hit the unigram floor (`00` §3a), leaving enormous headroom for token-preserving semantic corruption.

- [HIGH] **Review tier is also not a comprehension sieve.** **205/382 (53.7%)** land in `review` (`00` §3a), mostly on **186** "misaligned region(s)" flags the spec declares "expected on clean papers" (`00` §3c; `CLAUDE.md:233-236`). Those papers still ship markdown to LLM pipelines under default `--gate review`. Impact: **96.3%** of conversions are CI-admissible without any fact check; review flags localize furniture stripping, not "LLM will misread this table."

- [MED] **The markitdown oracle adds cross-converter text agreement, not comprehension.** `ref_nid` uses the same `normalized_text` axis (`score.py:212-213`) and is advisory-only (`score.py:175-178`: never hard-fails). With oracle on, mean `ref_nid` **0.836** and **147/382** below the **0.85** edge (`00` §3b) mean two fallible converters disagreeing, not "tomd scrambled a fact." Impact: oracle-on pass (**126/382**, `00` §3b) is stricter on formatting agreement but still **0%** comprehension-tested; oracle-off pass (**163/382**) is the documented trustworthy hard gate (`constants.py:78-79`) and still ignores table neighbor / math structure.

- [MED] **353 passing unit tests validate Lane 3 code, not Lane 3 deployment.** `test_facts.py` (219 LOC, `00` §1) exercises synthetic markdown in isolation; runtime corpus has no `<pid>.facts.jsonl` paired with staged candidates (`00` §4). Impact: tests prove `check_facts` works on fixtures; they provide **no bound** on how many of the **163** current passes would fail verified `table`/`math`/`order` facts if authored from source PDFs.

- [LOW] **Dissect/agora do not consume whisker verdicts today.** No `whisker` import in `packages/dissect` or `packages/cli` (repo grep). Impact: even a perfect comprehension gate would not protect the LLM pipeline until wired into convert/dissect entry; operators relying on manual `whisker --all` inherit the blind spot above.

## False-pass hypothesis

A WG21 paper whose pipe table swaps two body cells (e.g. feature name and status columns transposed) while every token still appears somewhere in the document: **`unigram_coverage` stays ≥ 0.95**, structural gates pass (`gates.py:153-161`), **`verdict == pass`**. A dissect agent citing "the cell to the right of *executors* says *wip*" reads the wrong feature row. Lane 3 `table` facts with `cell` + `neighbors` (`facts.py:309-335`, `EXAMPLE.facts.jsonl:5`) are the designed catch; with **0** verified facts on **382** papers (`00` §4), whisker cannot detect it.

## False-fail hypothesis

**P3941R2/R3/R4**: `uni=0.999`, `drift=0.001`, fail solely on `heading_monotone` H2→H4 (`00` §3c; `gates.py:105-109`). Markdown is fully legible to an LLM; section hierarchy in the PDF used `#`/`##`/`####` without an intermediate `###`. Whisker hard-fails on heading pedantry while comprehension-critical content is intact.

## What would change my mind

Author **≥20** `<pid>.facts.jsonl` files from source PDF/HTML (`checked: verified`, per `corpus/README.md:35-37`), rerun on the **163** current ref-free passes, and report **(a)** how many passes fail at least one `table`/`math`/`order` fact, **(b)** macro pass rates by fact type — giving a measured upper bound on the comprehension false-pass rate instead of the current **0/382 (0%)** operational coverage.
