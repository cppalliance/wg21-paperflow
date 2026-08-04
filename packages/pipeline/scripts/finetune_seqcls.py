#!/usr/bin/env python3
# Copyright (c) 2026 Henry Wang(henryw910816@outlook.com)
#
# Distributed under the Boost Software License, Version 1.0. (See accompanying
# file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#
"""Fine-tune a multi-label sequence classifier from labeled JSONL.

Each input line is a JSON object::

    {"text": "...", "labels": ["D3", "M1"]}

Label names are derived from the union of all ``labels`` fields in the
corpus and written into the saved checkpoint's ``id2label`` /
``label2id``. The output checkpoint is loadable by
:class:`pipeline.transformer_backend.SeqClassificationBackend` and
:class:`pipeline.classifier_backends.MultiLabelClassifierBackend`.

Requires the optional ``pipeline[train]`` extra. From repo root, install via::

    uv sync --group dev

The dev dependency group includes ``pipeline[train]``.

Usage (from repo root)::

    uv run --extra train --directory packages/pipeline \\
        python scripts/finetune_seqcls.py \\
        --train data/train.jsonl \\
        --output artifacts/my-tagger-v1 \\
        --base-model microsoft/deberta-v3-base
"""

from __future__ import annotations

import argparse
import inspect
import json
import logging
import math
from pathlib import Path

_log = logging.getLogger(__name__)

_TRAIN_SEED = 0
_DEFAULT_MAX_LENGTH = 128
_EVAL_PREDICTION_THRESHOLD = 0.5
_TRAIN_LOGGING_STEPS = 50
_TRAIN_EXTRA_HINT = (
    "Install training dependencies with: "
    "uv sync --group dev from repo root "
    "(includes pipeline[train])"
)


def _import_train_deps() -> dict[str, object]:
    """Import optional training deps; fail with an actionable message."""
    try:
        from datasets import Dataset  # type: ignore[import-untyped]
        import numpy as np  # type: ignore[import-untyped]
        from sklearn.metrics import f1_score  # type: ignore[import-untyped]
        from transformers import (  # type: ignore[import-untyped]
            AutoModelForSequenceClassification,
            AutoTokenizer,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        raise ImportError(_TRAIN_EXTRA_HINT) from exc
    return {
        "Dataset": Dataset,
        "np": np,
        "f1_score": f1_score,
        "AutoModelForSequenceClassification": AutoModelForSequenceClassification,
        "AutoTokenizer": AutoTokenizer,
        "Trainer": Trainer,
        "TrainingArguments": TrainingArguments,
    }


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no}: expected JSON object")
        rows.append(row)
    return rows


def _collect_label_names(rows: list[dict[str, object]]) -> list[str]:
    names: set[str] = set()
    for row in rows:
        labels = row.get("labels")
        if labels is None:
            continue
        if not isinstance(labels, list):
            raise ValueError("labels must be a JSON array of strings")
        for label in labels:
            if not isinstance(label, str) or not label:
                raise ValueError("each label must be a non-empty string")
            names.add(label)
    return sorted(names)


def _training_precision_kwargs(*, cpu_only: bool) -> dict[str, bool]:
    """Mixed-precision flags for :class:`TrainingArguments`.

    Transformers 5.x may load CUDA weights in fp16 by default; that is
    unstable for DeBERTa multi-label fine-tuning on this corpus.  We always
    load the model in fp32 (see :func:`_load_model_for_training`) and enable
    bf16 autocast on Ampere+ CUDA for speed.
    """
    if cpu_only:
        return {"bf16": False, "fp16": False}
    try:
        import torch  # type: ignore[import-untyped]
    except ImportError:
        return {"bf16": False, "fp16": False}
    if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
        return {"bf16": True, "fp16": False}
    return {"bf16": False, "fp16": False}


def _load_model_for_training(
    model_cls: type,
    base_model: str,
    *,
    num_labels: int,
    id2label: dict[int, str],
    label2id: dict[str, int],
) -> object:
    """Load a sequence-classification head in fp32 for stable fine-tuning."""
    import torch  # type: ignore[import-untyped]

    load_kwargs: dict[str, object] = {
        "num_labels": num_labels,
        "problem_type": "multi_label_classification",
        "id2label": id2label,
        "label2id": label2id,
        "dtype": torch.float32,
    }
    sig = inspect.signature(model_cls.from_pretrained)
    dtype_param = "torch_dtype" if "torch_dtype" in sig.parameters else "dtype"
    if dtype_param == "torch_dtype":
        load_kwargs.pop("dtype", None)
        load_kwargs["torch_dtype"] = torch.float32
    try:
        return model_cls.from_pretrained(base_model, **load_kwargs)
    except TypeError as exc:
        msg = str(exc).lower()
        if "dtype" not in msg and "torch_dtype" not in msg:
            raise
        alt = "dtype" if dtype_param == "torch_dtype" else "torch_dtype"
        load_kwargs.pop(dtype_param, None)
        load_kwargs[alt] = torch.float32
        return model_cls.from_pretrained(base_model, **load_kwargs)


def _assert_finite_parameters(model: object) -> None:
    """Fail before persisting a checkpoint whose weights contain NaN/Inf."""
    import torch  # type: ignore[import-untyped]

    bad: list[str] = []
    for name, param in model.named_parameters():  # type: ignore[union-attr]
        if not torch.isfinite(param).all():
            bad.append(name)
    if bad:
        sample = ", ".join(bad[:5])
        suffix = "..." if len(bad) > 5 else ""
        raise RuntimeError(
            f"training produced non-finite weights in {len(bad)} parameter "
            f"tensor(s) (e.g. {sample}{suffix}); refusing to save checkpoint",
        )


def _abort_if_training_logs_non_finite(logs: dict[str, object] | None) -> None:
    """Raise when Trainer logs contain a non-finite loss or grad norm (NaN/Inf)."""
    if not logs:
        return
    grad_norm = logs.get("grad_norm")
    if grad_norm is not None and not math.isfinite(float(grad_norm)):  # type: ignore[arg-type]
        raise RuntimeError(
            "training diverged: grad_norm is non-finite; aborting",
        )
    loss = logs.get("loss")
    if loss is not None and not math.isfinite(float(loss)):  # type: ignore[arg-type]
        raise RuntimeError(
            "training diverged: loss is non-finite; aborting",
        )


def _rows_to_dataset(
    rows: list[dict[str, object]],
    *,
    label_names: list[str],
    tokenizer: object,
    max_length: int,
    dataset_cls: type,
    fixed_padding: bool = False,
) -> object:
    label_to_idx = {name: i for i, name in enumerate(label_names)}
    texts: list[str] = []
    label_vectors: list[list[float]] = []

    for row in rows:
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("each row must include non-empty text")
        raw_labels = row.get("labels", [])
        if raw_labels is None:
            raw_labels = []
        if not isinstance(raw_labels, list):
            raise ValueError("labels must be a JSON array of strings")
        vec = [0.0] * len(label_names)
        for label in raw_labels:
            if not isinstance(label, str):
                raise ValueError("each label must be a string")
            idx = label_to_idx.get(label)
            if idx is None:
                raise ValueError(f"unknown label {label!r} not in corpus label set")
            vec[idx] = 1.0
        texts.append(text)
        label_vectors.append(vec)

    enc = tokenizer(  # type: ignore[operator]
        texts,
        truncation=True,
        padding="max_length" if fixed_padding else False,
        max_length=max_length,
    )
    enc["labels"] = label_vectors
    return dataset_cls.from_dict(enc)


def finetune_multilabel_seqcls(
    *,
    train_path: Path,
    output_dir: Path,
    base_model: str,
    val_path: Path | None = None,
    max_length: int = _DEFAULT_MAX_LENGTH,
    num_train_epochs: int = 3,
    learning_rate: float = 2e-5,
    per_device_train_batch_size: int = 16,
    seed: int = _TRAIN_SEED,
    cpu_only: bool = False,
    fixed_padding: bool = False,
) -> Path:
    """Train and save a multi-label sequence classifier checkpoint."""
    deps = _import_train_deps()
    Dataset = deps["Dataset"]
    np = deps["np"]
    f1_score = deps["f1_score"]
    AutoModelForSequenceClassification = deps["AutoModelForSequenceClassification"]
    AutoTokenizer = deps["AutoTokenizer"]
    Trainer = deps["Trainer"]
    TrainingArguments = deps["TrainingArguments"]

    train_rows = _load_jsonl(train_path)
    if not train_rows:
        raise ValueError(f"no training rows in {train_path}")

    label_names = _collect_label_names(train_rows)
    if not label_names:
        raise ValueError("corpus contains no labels")

    id2label = {i: name for i, name in enumerate(label_names)}
    label2id = {name: i for i, name in enumerate(label_names)}

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = _load_model_for_training(
        AutoModelForSequenceClassification,
        base_model,
        num_labels=len(label_names),
        id2label=id2label,
        label2id=label2id,
    )
    precision_kwargs = _training_precision_kwargs(cpu_only=cpu_only)
    if precision_kwargs.get("bf16"):
        _log.info("CUDA bf16 training enabled (fp32 weight load)")
    elif not cpu_only:
        _log.info("CUDA fp32 training (no bf16)")

    train_ds = _rows_to_dataset(
        train_rows,
        label_names=label_names,
        tokenizer=tokenizer,
        max_length=max_length,
        dataset_cls=Dataset,
        fixed_padding=fixed_padding,
    )
    eval_ds = None
    if val_path is not None:
        val_rows = _load_jsonl(val_path)
        eval_ds = _rows_to_dataset(
            val_rows,
            label_names=label_names,
            tokenizer=tokenizer,
            max_length=max_length,
            dataset_cls=Dataset,
            fixed_padding=fixed_padding,
        )

    def _compute_metrics(eval_pred: object) -> dict[str, float]:
        logits, labels = eval_pred  # type: ignore[misc]
        probs = 1.0 / (1.0 + np.exp(-logits))
        preds = (probs >= _EVAL_PREDICTION_THRESHOLD).astype(int)
        labels_arr = np.array(labels).astype(int)
        return {
            "micro_f1": float(
                f1_score(labels_arr, preds, average="micro", zero_division=0),
            ),
            "macro_f1": float(
                f1_score(labels_arr, preds, average="macro", zero_division=0),
            ),
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=num_train_epochs,
        learning_rate=learning_rate,
        per_device_train_batch_size=per_device_train_batch_size,
        seed=seed,
        data_seed=seed,
        eval_strategy="epoch" if eval_ds is not None else "no",
        save_strategy="epoch" if eval_ds is not None else "no",
        load_best_model_at_end=eval_ds is not None,
        metric_for_best_model="micro_f1" if eval_ds is not None else None,
        logging_steps=_TRAIN_LOGGING_STEPS,
        report_to=[],
        use_cpu=cpu_only,
        **precision_kwargs,
    )

    from transformers import TrainerCallback  # type: ignore[import-untyped]

    class _AbortOnNonFiniteCallback(TrainerCallback):
        """Stop early when the Trainer logs a non-finite loss or grad norm."""

        def on_log(self, args, state, control, logs=None, **kwargs):  # type: ignore[no-untyped-def]
            del args, state, kwargs
            _abort_if_training_logs_non_finite(logs)

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        processing_class=tokenizer,
        compute_metrics=_compute_metrics if eval_ds is not None else None,
        callbacks=[_AbortOnNonFiniteCallback()],
    )
    trainer.train()
    _assert_finite_parameters(trainer.model)
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    _log.info("saved checkpoint to %s (%d labels)", output_dir, len(label_names))
    return output_dir


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fine-tune a multi-label sequence classifier from JSONL.",
    )
    parser.add_argument(
        "--train",
        type=Path,
        required=True,
        help="Training JSONL path ({text, labels}).",
    )
    parser.add_argument(
        "--val",
        type=Path,
        default=None,
        help="Optional validation JSONL path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Directory for the saved checkpoint.",
    )
    parser.add_argument(
        "--base-model",
        default="microsoft/deberta-v3-base",
        help="HF model id or local path to fine-tune.",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=_DEFAULT_MAX_LENGTH,
        help="Tokenizer max_length (default: %(default)s).",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=3,
        help="Training epochs (default: %(default)s).",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=2e-5,
        help="Learning rate (default: %(default)s).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="Per-device train batch size (default: %(default)s).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=_TRAIN_SEED,
        help="Random seed (default: %(default)s).",
    )
    parser.add_argument(
        "--cpu-only",
        action="store_true",
        help="Force CPU training, bypassing CUDA/MPS auto-detection "
        "(useful when the accelerator lacks headroom for the batch size).",
    )
    parser.add_argument(
        "--fixed-padding",
        action="store_true",
        help="Pad every batch to --max-length instead of the batch's longest "
        "sequence. Trades some compute for stable tensor shapes, which "
        "avoids MPS allocator fragmentation on memory-constrained hosts.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)
    finetune_multilabel_seqcls(
        train_path=args.train,
        val_path=args.val,
        output_dir=args.output,
        base_model=args.base_model,
        max_length=args.max_length,
        num_train_epochs=args.epochs,
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.batch_size,
        seed=args.seed,
        cpu_only=args.cpu_only,
        fixed_padding=args.fixed_padding,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
