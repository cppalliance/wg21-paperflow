#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""On-disk basenames and relative data dirs for learned routing train/serve artifacts."""

from __future__ import annotations

from pathlib import Path

# Relative to packages/assay/ package root (directory containing data/)
ROUTING_METADATA_DIR = Path("data") / "routing"
NLI_FAMILY_DIR = Path("data") / "nli"
SEQCLS_FAMILY_DIR = Path("data") / "seqcls"

# Shared metadata (under ROUTING_METADATA_DIR)
FEATURE_NAMES_FILE = "feature_names.json"
GROUP_ORDER_FILE = "group_order.json"
TRAIN_REPORT_FILE = "train_report.json"

# Per-family artifacts (under NLI_FAMILY_DIR or SEQCLS_FAMILY_DIR)
AGGREGATOR_MODEL_FILE = "aggregator_hgb.joblib"
GROUP_THRESHOLDS_FILE = "group_thresholds.json"
PER_LABEL_THRESHOLDS_FILE = "per_label_thresholds.json"
PROVENANCE_FILE = "provenance.json"
