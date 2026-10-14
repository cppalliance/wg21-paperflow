# C09 License, Provenance, and Supply Chain

**Role**: Audit licensing accuracy, third-party notice completeness, and ported-algorithm provenance.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771
**Gates**: G7 (License compliance)

## 1. Scope

Verify BSL-1.0 header coverage, resolve the pylatexenc license conflict
between Auditv2 and this run's ledger by checking primary sources, and check
`THIRD_PARTY_NOTICES.md` completeness against every ported (not merely
dependency-imported) third-party algorithm in the codebase.

## 2. Commands and Exits

BSL-1.0 header scan: 69 of 69 `.py` files, zero missing (ledger E6).
Dependency license table: ledger E7. `THIRD_PARTY_NOTICES.md` read directly
(`packages/whisker/THIRD_PARTY_NOTICES.md`). pylatexenc distribution metadata
queried live this run via `importlib.metadata.distribution("pylatexenc")`,
exit 0, `version=2.10`, `License: MIT`,
`Classifier: License :: OSI Approved :: MIT License`.

## 3. Current Evidence

### 3.1 BSL-1.0 headers: unchanged, complete

E6: 69 of 69 `.py` files carry the header, zero missing. No regression from
Auditv2's equivalent finding.

### 3.2 The pylatexenc conflict, adjudicated

Auditv2's ledger (E11 in that audit) recorded pylatexenc as "LGPL-3.0+."
This run's ledger (E7) recorded the installed distribution metadata as MIT
and flagged the direct conflict for adjudication here rather than guessing.

Verification performed this run, independent of both prior ledgers:

1. **Installed distribution metadata** (the package actually resolved into
   this environment): `importlib.metadata.distribution("pylatexenc")`
   reports `version=2.10`, `License: MIT`, and the classifier
   `License :: OSI Approved :: MIT License`.
2. **Upstream project** (`github.com/phfaist/pylatexenc`): the repository's
   own `LICENSE.txt` is the MIT License text (Copyright 2015-2023 Philippe
   Faist). The GitHub repository metadata reports "License: MIT License
   (MIT)". `setup.py` in the upstream repo sets `license = "MIT"` and the
   classifier `'License :: OSI Approved :: MIT License'`.
3. **PyPI project page** (`pypi.org/project/pylatexenc/`): "License: MIT,"
   with the same LICENSE.txt reference.

All three independent sources (installed metadata, upstream repository,
PyPI listing) agree: pylatexenc is MIT-licensed. There is no LGPL variant of
this package on any of the three sources checked. **Auditv2's E11 was
incorrect; this run's E7 (MIT) is correct.** The practical consequence is
narrow, since MIT is at least as permissive as LGPL-3.0+ for whisker's
static-import, non-modified usage, so the mistake did not previously create
an actual compliance gap, only an inaccurate ledger entry. It is corrected
here for the record.

### 3.3 `THIRD_PARTY_NOTICES.md` covers one of at least three ports

The file's entire content (`packages/whisker/THIRD_PARTY_NOTICES.md`):

```
## langextract (Apache-2.0)

`src/whisker/tapetum_llm/grounding.py` contains a Python re-implementation of
the monotonic exact-occurrence alignment DP from Google's langextract project
(`langextract/resolver.py`, `_select_monotonic_matches` and its application),
Copyright Google LLC, licensed under the Apache License, Version 2.0.

The port is algorithm-only: no langextract code is imported at runtime, no
dependency was added. langextract's LCS fuzzy-alignment tier was deliberately
not ported.

Source: <https://github.com/google/langextract> @ 0dff5479 (v1.6.0).
```

This is a correct and specific notice for one ported algorithm. But
`packages/whisker/src/whisker/CLAUDE.md` documents at least two more ported
algorithms in `metrics.py`, described only in code comments, not in the
notices file:

- **TEDS** (`metrics.py`, the `teds` function): "a VERBATIM port of
  PubTabNet/OmniDocBench TEDS (lxml DOM -> `apted`, char-token cells,
  xpath-descendant denominator), so table scores are comparable to the
  published leaderboards" (`whisker/CLAUDE.md`, Module layout, `metrics.py`
  entry). "Verbatim port" is provenance language identical in kind to the
  langextract notice's "re-implementation," yet it has no corresponding
  entry in `THIRD_PARTY_NOTICES.md`.
- **The OmniDocBench text normalizer** (`normalized_text` /
  `textblock2unicode` / `clean_string`): "the OmniDocBench text-axis
  normalizer adopted verbatim" (same CLAUDE.md entry). Same "verbatim"
  language, same absence from the notices file.

Both are described only in `metrics.py` comments and the package's own
`CLAUDE.md`, which is developer-facing documentation, not a legal notices
file a downstream redistributor would think to check. A party relying on
`THIRD_PARTY_NOTICES.md` as the complete inventory of third-party-derived
code (its evident purpose, since it exists at all) would miss two of three
known ports.

### 3.4 No GPL contamination in the dependency graph

Reconfirmed from ledger E7: core dependencies are apted MIT, grits-metric
MIT, lxml BSD-3, markitdown MIT, mistune BSD-3, numpy BSD-3, paperstore
BSL-1.0, pylatexenc MIT (corrected per 3.2), rapidfuzz MIT, rich MIT, scipy
BSD-3, tomd BSL-1.0. Extra: openai Apache-2.0, pipeline BSL-1.0, pydantic-ai
MIT, pydantic MIT, python-dotenv BSD-3. No GPL-family package in the core
set. scipy's metadata embeds bundled-GCC-runtime notices mentioning
"GPL-3.0-or-later WITH GCC-exception-3.1" (E7); this is the GCC runtime
exception carve-out scipy ships as a build artifact notice, not a GPL
obligation on scipy's own Python code, and is unchanged from the general
scientific-Python ecosystem norm.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | BSL-1.0 header coverage remains complete: 69/69 files | Informational | HIGH |
| F2 | pylatexenc is MIT, not LGPL-3.0+; Auditv2's ledger entry was incorrect and is corrected here against three independent sources | MEDIUM | HIGH |
| F3 | `THIRD_PARTY_NOTICES.md` documents only the langextract port; the PubTabNet/OmniDocBench TEDS port and the OmniDocBench text normalizer port are undocumented in the notices file despite being described as "verbatim port[s]" in `CLAUDE.md` | MEDIUM | HIGH |
| F4 | No GPL-family dependency in the core or optional dependency set | Informational | HIGH |

## 5. False-Pass Hypothesis

**Could the missing TEDS/normalizer notices be a false negative, i.e. are
they actually independent implementations rather than ports that need
attribution?** The project's own documentation forecloses this reading:
`CLAUDE.md` uses the word "port" and "verbatim" for both, the same
provenance language used for the langextract entry that IS in the notices
file. If the omission were intentional (e.g. because PubTabNet/OmniDocBench's
license does not require a notice), that determination is not recorded
anywhere this audit could find; the omission is more consistent with the
notices file having been written before, or independently of, the
`metrics.py` provenance comments, than with a deliberate legal decision.

**Could the pylatexenc correction itself be wrong?** Checked against three
independent sources that all agree (installed metadata, upstream repo,
PyPI). A fourth check, of pylatexenc's `tools/unicode.xml` sub-license
noted separately in the upstream README (a W3C-sourced data file with its
own license terms), was not performed; it is a data file, not code, and is
unlikely to affect whisker's use of the `pylatexenc.latex2text` module, but
is flagged as unverified rather than silently assumed clean.

## 6. Gate/Dimension Mapping (PROPOSED)

| Gate | Dimension | Proposed status |
|------|-----------|------------------|
| G7 License compliance | BSL-1.0 header coverage | PROPOSED PASS |
| G7 License compliance | Dependency license cleanliness (no GPL) | PROPOSED PASS |
| G7 License compliance | Third-party notice completeness for ported algorithms | PROPOSED FAIL: 1 of at least 3 known ports is documented |
| G7 License compliance | License-metadata accuracy (pylatexenc) | PROPOSED corrected finding, not a compliance failure (MIT is more permissive than the LGPL-3.0+ previously recorded) |

## 7. Limitations

- The `pylatexenc.tools/unicode.xml` sub-license (a separate, data-file-scoped
  license noted in the upstream project) was not independently verified.
- This audit did not exhaustively walk every transitive dependency's license
  (e.g. `grits-metric`'s own dependency tree); it relies on the same
  known-package-reputation method Auditv2 used, corrected only where a
  specific conflict was flagged for adjudication.
- Whether the TEDS/normalizer omissions constitute an actual license
  violation (as opposed to a documentation gap) depends on the specific
  license terms of PubTabNet/OmniDocBench, which were not independently
  researched here; this report establishes the provenance-documentation gap,
  not a legal conclusion about violation.

## 8. Conclusion

BSL-1.0 coverage and the absence of GPL-family dependencies both hold, as in
Auditv2. This run resolves a real, direct disagreement between the two
audits' ledgers, pylatexenc's license, and finds against Auditv2: pylatexenc
is MIT, confirmed against the installed distribution metadata, the upstream
GitHub repository's own LICENSE.txt, and the PyPI listing. Separately, and
independent of that correction, `THIRD_PARTY_NOTICES.md` is incomplete: the
codebase's own `CLAUDE.md` describes two additional "verbatim port[s]"
(PubTabNet/OmniDocBench TEDS, the OmniDocBench text normalizer) that carry no
entry in the notices file, only comments in `metrics.py` and developer
documentation a downstream legal reviewer would not think to consult.

## 9. Delta vs Auditv2

Auditv2's C09 recorded pylatexenc as MIT in its own dependency table (3.3 of
that report lists "pylatexenc >= 2.10 | MIT | None") while its ledger entry
elsewhere (referenced by this run's E7 as "the v2 ledger (E11)") recorded
LGPL-3.0+, an internal inconsistency Auditv2 itself did not resolve. This run
closes that inconsistency with primary-source verification (3.2): MIT is
correct. Auditv2's C09 also did not examine `THIRD_PARTY_NOTICES.md` at all;
its Section 3.5 covered only wheel packaging structure. This run adds the
notices-completeness finding (F3) as new evidence Auditv2 never gathered,
surfaced by the ledger's E7 note that the file "covers only langextract."
