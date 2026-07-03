#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Batch NLI entailment scoring for sentence-level classifiers."""

from __future__ import annotations

from pipeline.classifier_backends import NliCrossEncoderBackend

NLI_ENTAILMENT_THRESHOLD = 0.3


def score_entailment_pairs(
    classifier: NliCrossEncoderBackend,
    pairs: list[tuple[str, str]],
    *,
    threshold: float = NLI_ENTAILMENT_THRESHOLD,
    debug_log: list[str] | None = None,
) -> tuple[list[bool], list[dict[str, float]]]:
    """Score premise/hypothesis pairs in input order.

    Returns ``(fired, raw_scores)`` where *fired* is True when entailment
    exceeds *threshold*. *raw_scores* preserves the classifier output
    dicts for trace/debug. No concurrency; order matches *pairs*.
    """
    if not pairs:
        return [], []

    if debug_log is not None:
        debug_log.append("### NLI entailment batch\n")
        debug_log.append(f"pairs: {len(pairs)}\n")

    raw_scores = classifier.nli_entailment_pairs(pairs)
    fired: list[bool] = []

    for i, ((premise, _hypothesis), score) in enumerate(
        zip(pairs, raw_scores, strict=True)
    ):
        entailment = score.get("entailment", 0.0)
        hit = entailment > threshold
        fired.append(hit)
        if debug_log is not None:
            debug_log.append(
                f"- [{i}] entailment={entailment:.4f} "
                f"hit={hit} text={premise[:120]!r}\n",
            )

    return fired, raw_scores
