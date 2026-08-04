#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from conftest import SeqClsStubTokenizer  # noqa: E402
from finetune_seqcls import (  # noqa: E402
    _abort_if_training_logs_non_finite,
    _assert_finite_parameters,
    _collect_label_names,
    _load_jsonl,
    _rows_to_dataset,
    _training_precision_kwargs,
)


def _install_fake_torch(monkeypatch, *, cuda: bool = False, bf16: bool = False) -> None:
    """Minimal fake torch for :func:`_training_precision_kwargs` CUDA probes."""
    fake_torch = types.ModuleType("torch")

    class _Cuda:
        @staticmethod
        def is_available() -> bool:
            return cuda

        @staticmethod
        def is_bf16_supported() -> bool:
            return bf16

    fake_torch.cuda = _Cuda()
    monkeypatch.setitem(sys.modules, "torch", fake_torch)


# ---------------------------------------------------------------------------
# _training_precision_kwargs
# ---------------------------------------------------------------------------


def test_training_precision_kwargs_cpu_only() -> None:
    assert _training_precision_kwargs(cpu_only=True) == {
        "bf16": False,
        "fp16": False,
    }


def test_training_precision_kwargs_cuda_bf16(monkeypatch) -> None:
    _install_fake_torch(monkeypatch, cuda=True, bf16=True)
    assert _training_precision_kwargs(cpu_only=False) == {
        "bf16": True,
        "fp16": False,
    }


def test_training_precision_kwargs_cuda_no_bf16(monkeypatch) -> None:
    _install_fake_torch(monkeypatch, cuda=True, bf16=False)
    assert _training_precision_kwargs(cpu_only=False) == {
        "bf16": False,
        "fp16": False,
    }


# ---------------------------------------------------------------------------
# _assert_finite_parameters
# ---------------------------------------------------------------------------


def test_assert_finite_parameters_accepts_finite_weights() -> None:
    torch = pytest.importorskip("torch")

    class _Model:
        def named_parameters(self):
            yield "w", torch.tensor([1.0, 2.0])

    _assert_finite_parameters(_Model())


def test_assert_finite_parameters_rejects_nan() -> None:
    torch = pytest.importorskip("torch")

    class _Model:
        def named_parameters(self):
            yield "bad", torch.tensor([float("nan")])

    with pytest.raises(RuntimeError, match="non-finite weights"):
        _assert_finite_parameters(_Model())


def test_assert_finite_parameters_rejects_inf() -> None:
    torch = pytest.importorskip("torch")

    class _Model:
        def named_parameters(self):
            yield "bad", torch.tensor([float("inf")])

    with pytest.raises(RuntimeError, match="non-finite weights"):
        _assert_finite_parameters(_Model())


# ---------------------------------------------------------------------------
# _abort_if_training_logs_non_finite
# ---------------------------------------------------------------------------


def test_abort_if_training_logs_non_finite_no_op_for_empty() -> None:
    _abort_if_training_logs_non_finite(None)
    _abort_if_training_logs_non_finite({})


def test_abort_if_training_logs_non_finite_accepts_finite_values() -> None:
    _abort_if_training_logs_non_finite({"loss": 1.5, "grad_norm": 0.42})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("loss", float("nan")),
        ("loss", float("inf")),
        ("grad_norm", float("nan")),
        ("grad_norm", float("inf")),
    ],
)
def test_abort_if_training_logs_non_finite_rejects_non_finite(
    field: str,
    value: float,
) -> None:
    with pytest.raises(RuntimeError, match="non-finite"):
        _abort_if_training_logs_non_finite({field: value})


# ---------------------------------------------------------------------------
# _load_jsonl
# ---------------------------------------------------------------------------


def test_load_jsonl_valid_rows(tmp_path: Path) -> None:
    path = tmp_path / "train.jsonl"
    path.write_text(
        '{"text": "a", "labels": ["D3"]}\n\n{"text": "b", "labels": []}\n',
        encoding="utf-8",
    )
    rows = _load_jsonl(path)
    assert len(rows) == 2
    assert rows[0]["text"] == "a"


def test_load_jsonl_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text("not json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        _load_jsonl(path)


def test_load_jsonl_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text("[1, 2]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected JSON object"):
        _load_jsonl(path)


# ---------------------------------------------------------------------------
# _collect_label_names
# ---------------------------------------------------------------------------


def test_collect_label_names_sorted_union() -> None:
    rows = [
        {"labels": ["M1", "D3"]},
        {"labels": ["A1"]},
        {"text": "no labels"},
    ]
    assert _collect_label_names(rows) == ["A1", "D3", "M1"]


def test_collect_label_names_rejects_non_list_labels() -> None:
    with pytest.raises(ValueError, match="labels must be a JSON array"):
        _collect_label_names([{"labels": "D3"}])


def test_collect_label_names_rejects_empty_label_string() -> None:
    with pytest.raises(ValueError, match="non-empty string"):
        _collect_label_names([{"labels": [""]}])


# ---------------------------------------------------------------------------
# _rows_to_dataset
# ---------------------------------------------------------------------------


def test_rows_to_dataset_multi_hot_vectors() -> None:
    datasets = pytest.importorskip("datasets")
    rows = [
        {"text": "first", "labels": ["B"]},
        {"text": "second", "labels": ["A", "B"]},
    ]
    label_names = ["A", "B"]
    ds = _rows_to_dataset(
        rows,
        label_names=label_names,
        tokenizer=SeqClsStubTokenizer(),
        max_length=8,
        dataset_cls=datasets.Dataset,
    )
    assert ds["labels"] == [[0.0, 1.0], [1.0, 1.0]]


def test_rows_to_dataset_rejects_empty_text() -> None:
    datasets = pytest.importorskip("datasets")
    with pytest.raises(ValueError, match="non-empty text"):
        _rows_to_dataset(
            [{"text": "  ", "labels": []}],
            label_names=["A"],
            tokenizer=SeqClsStubTokenizer(),
            max_length=8,
            dataset_cls=datasets.Dataset,
        )


def test_rows_to_dataset_rejects_unknown_label() -> None:
    datasets = pytest.importorskip("datasets")
    with pytest.raises(ValueError, match="unknown label"):
        _rows_to_dataset(
            [{"text": "x", "labels": ["Z"]}],
            label_names=["A"],
            tokenizer=SeqClsStubTokenizer(),
            max_length=8,
            dataset_cls=datasets.Dataset,
        )


def test_rows_to_dataset_rejects_bad_label_type() -> None:
    datasets = pytest.importorskip("datasets")
    with pytest.raises(ValueError, match="each label must be a string"):
        _rows_to_dataset(
            [{"text": "x", "labels": [1]}],
            label_names=["A"],
            tokenizer=SeqClsStubTokenizer(),
            max_length=8,
            dataset_cls=datasets.Dataset,
        )
