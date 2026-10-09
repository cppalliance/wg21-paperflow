# Third-party notices

## langextract (Apache-2.0)

`src/whisker/llm/grounding.py` contains a Python re-implementation of
the monotonic exact-occurrence alignment DP from Google's langextract project
(`langextract/resolver.py`, `_select_monotonic_matches` and its application),
Copyright Google LLC, licensed under the Apache License, Version 2.0
(<https://www.apache.org/licenses/LICENSE-2.0>).

The port is algorithm-only: no langextract code is imported at runtime, no
dependency was added. langextract's LCS fuzzy-alignment tier was deliberately
not ported.

Source: <https://github.com/google/langextract> @ 0dff5479 (v1.6.0).

## OmniDocBench / PubTabNet TEDS (Apache-2.0)

`src/whisker/metrics.py` contains verbatim ports of:

- **TEDS (Tree-Edit-Distance-based Similarity):** the table structural
  similarity algorithm from IBM's PubTabNet, as packaged by OmniDocBench
  (`src/metrics/table_metric.py`). The implementation uses lxml DOM walks into
  APTED with the xpath-descendant denominator so scores are comparable to
  published table leaderboards. Functions: `_TEDS`, `_normalize_table_html`,
  `teds`.

- **Text normalization pipeline:** the `clean_string` / `textblock2unicode`
  content normalizer from OmniDocBench
  (`src/core/preprocess/data_preprocess.py`, `text_postprocess.py`). Functions:
  `clean_string`, `textblock2unicode`, `replace_textcircle`,
  `safe_latex_to_text`, `normalized_text`, and the associated guards
  (`_is_likely_bad_latex`, `_is_weak_input`, `_is_plaintext_noise`).

- **Block matching:** `src/whisker/match.py` ports the block-level matching
  algorithm from OmniDocBench (`src/core/matching/match_quick.py`,
  `src/metrics/cal_metric.py`): NED cost matrix, Hungarian assignment, fuzzy
  substring rescue, and `reading_order_ned` (from `get_order_paired`).
  Functions: `match_blocks`, `block_edit_whole`, `reading_order_ned`,
  `block_text_nid`.

All ports are algorithm-only: no OmniDocBench code is imported at runtime, no
dependency was added.

Copyright IBM Corporation (PubTabNet TEDS), Copyright OpenDataLab
(OmniDocBench), licensed under the Apache License, Version 2.0
(<https://www.apache.org/licenses/LICENSE-2.0>).

Sources:
- PubTabNet: <https://github.com/ibm-aur-nlp/PubTabNet>
- OmniDocBench: <https://github.com/opendatalab/OmniDocBench>
