#
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from finetune_seqcls import (  # noqa: E402
    _assert_finite_parameters,
    _training_precision_kwargs,
)


def test_training_precision_kwargs_cpu_only() -> None:
    assert _training_precision_kwargs(cpu_only=True) == {
        "bf16": False,
        "fp16": False,
    }


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
