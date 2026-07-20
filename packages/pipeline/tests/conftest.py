#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

"""Shared test helpers for pipeline package tests."""

from __future__ import annotations

import sys
import types


class SeqClsStubModel:
    """Minimal HF sequence-classification model stub."""

    def __init__(
        self,
        *,
        id2label: dict[int, str],
        logits: list[float],
        problem_type: str | None = "multi_label_classification",
    ) -> None:
        self.config = types.SimpleNamespace(
            id2label=id2label,
            problem_type=problem_type,
        )
        self._logits = logits
        self.load_count = 0
        self.eval_called = False

    def eval(self) -> "SeqClsStubModel":
        self.eval_called = True
        return self

    def to(self, _device: str) -> "SeqClsStubModel":
        return self

    def parameters(self):
        yield types.SimpleNamespace(device="cpu")

    def __call__(self, **encoded: object) -> types.SimpleNamespace:
        input_ids = encoded["input_ids"]
        batch = len(input_ids)  # type: ignore[arg-type]
        try:
            import torch  # type: ignore[import-untyped]

            logits = torch.tensor(
                [self._logits] * batch,
                dtype=torch.float32,
            )
        except ImportError:
            logits = [self._logits for _ in range(batch)]
        return types.SimpleNamespace(logits=logits)


class SeqClsStubTokenizer:
    def __call__(self, texts, **kwargs):
        _ = kwargs
        return {
            "input_ids": [[1, 2] for _ in texts],
            "attention_mask": [[1, 1] for _ in texts],
        }


def install_seqcls_transformers_stub(
    monkeypatch,
    model: SeqClsStubModel,
    *,
    offline_first: bool = False,
    drop_kwargs_on_retry: bool = False,
) -> None:
    fake_mod = types.ModuleType("transformers")

    class _AutoTokenizer:
        @staticmethod
        def from_pretrained(_model_id, local_files_only=False):
            if offline_first and local_files_only:
                raise OSError("local cache miss")
            return SeqClsStubTokenizer()

    class _AutoModel:
        @staticmethod
        def from_pretrained(_model_id, local_files_only=False, **_kw):
            model.load_count += 1
            if offline_first and local_files_only:
                raise OSError("local cache miss")
            if drop_kwargs_on_retry and not local_files_only and _kw:
                raise TypeError("stub rejects model_kwargs")
            return model

    fake_mod.AutoTokenizer = _AutoTokenizer
    fake_mod.AutoModelForSequenceClassification = _AutoModel
    monkeypatch.setitem(sys.modules, "transformers", fake_mod)
