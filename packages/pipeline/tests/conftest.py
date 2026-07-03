#
# Copyright (c) 2026 Vinnie Falco (vinnie.falco@gmail.com)
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
    ) -> None:
        self.config = types.SimpleNamespace(id2label=id2label)
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


def install_seqcls_transformers_stub(monkeypatch, model: SeqClsStubModel) -> None:
    fake_mod = types.ModuleType("transformers")

    class _AutoTokenizer:
        @staticmethod
        def from_pretrained(_model_id, local_files_only=False):
            _ = local_files_only
            return SeqClsStubTokenizer()

    class _AutoModel:
        @staticmethod
        def from_pretrained(_model_id, local_files_only=False, **_kw):
            _ = local_files_only, _kw
            model.load_count += 1
            return model

    fake_mod.AutoTokenizer = _AutoTokenizer
    fake_mod.AutoModelForSequenceClassification = _AutoModel
    monkeypatch.setitem(sys.modules, "transformers", fake_mod)
