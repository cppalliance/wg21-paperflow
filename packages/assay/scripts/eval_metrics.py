# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
"""Shared multilabel evaluation helpers for paper-routing scripts."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BinaryCounts:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    def update(self, gold: bool, pred: bool) -> None:
        if gold and pred:
            self.tp += 1
        elif not gold and pred:
            self.fp += 1
        elif gold and not pred:
            self.fn += 1
        else:
            self.tn += 1


@dataclass
class PrfScores:
    precision: float
    recall: float
    f1: float
    support: int


def prf_from_counts(counts: BinaryCounts) -> PrfScores:
    support = counts.tp + counts.fn
    precision = counts.tp / (counts.tp + counts.fp) if counts.tp + counts.fp else 0.0
    recall = counts.tp / (counts.tp + counts.fn) if counts.tp + counts.fn else 0.0
    if precision + recall:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0
    return PrfScores(precision=precision, recall=recall, f1=f1, support=support)


@dataclass
class MultilabelReport:
    """Aggregated multilabel metrics over labeled items."""

    labels: list[str] = field(default_factory=list)
    per_label: dict[str, BinaryCounts] = field(default_factory=dict)
    exact_match: int = 0
    item_count: int = 0

    def ensure_label(self, label: str) -> None:
        if label not in self.per_label:
            self.labels.append(label)
            self.per_label[label] = BinaryCounts()

    def add_item(self, gold: set[str], pred: set[str], *, label_universe: set[str]) -> None:
        self.item_count += 1
        if gold == pred:
            self.exact_match += 1
        for label in sorted(label_universe):
            self.ensure_label(label)
            self.per_label[label].update(label in gold, label in pred)

    def micro_prf(self) -> PrfScores:
        total = BinaryCounts()
        for counts in self.per_label.values():
            total.tp += counts.tp
            total.fp += counts.fp
            total.fn += counts.fn
            total.tn += counts.tn
        return prf_from_counts(total)

    def macro_prf(self) -> PrfScores:
        if not self.labels:
            return PrfScores(0.0, 0.0, 0.0, 0)
        precisions: list[float] = []
        recalls: list[float] = []
        f1s: list[float] = []
        support = 0
        for label in self.labels:
            scores = prf_from_counts(self.per_label[label])
            precisions.append(scores.precision)
            recalls.append(scores.recall)
            f1s.append(scores.f1)
            support += scores.support
        n = len(self.labels)
        return PrfScores(
            precision=sum(precisions) / n,
            recall=sum(recalls) / n,
            f1=sum(f1s) / n,
            support=support,
        )

    def exact_match_rate(self) -> float:
        if not self.item_count:
            return 0.0
        return self.exact_match / self.item_count
