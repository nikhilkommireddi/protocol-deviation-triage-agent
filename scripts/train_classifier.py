"""Phase 2: fine-tune a DeBERTa-v3 sequence classifier on the labeled
protocol deviation dataset.

Defaults to deberta-v3-small (44M params) rather than -base (184M) so a
full run finishes in a reasonable time on CPU -- this is a demo project,
not a production accuracy target, and the categories are lexically
distinguishable enough that -small should comfortably clear the F1 > 0.88
target from the build plan.

Uses the `split` column already baked into the combined dataset rather
than re-splitting, so train/val/test stay consistent with the rest of the
pipeline (and with the reviewed/unreviewed provenance from Chunk 1.5).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import torch
from datasets import load_dataset
from sklearn.metrics import accuracy_score, classification_report, f1_score
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

CATEGORIES = ["administrative", "major", "minor", "technical", "unreported"]
LABEL2ID = {label: i for i, label in enumerate(CATEGORIES)}
ID2LABEL = {i: label for label, i in LABEL2ID.items()}


def load_splits(data_path: Path):
    dataset = load_dataset("csv", data_files=str(data_path))["train"]
    dataset = dataset.map(lambda ex: {"label": LABEL2ID[ex["category"]]})
    return {
        "train": dataset.filter(lambda ex: ex["split"] == "train"),
        "val": dataset.filter(lambda ex: ex["split"] == "val"),
        "test": dataset.filter(lambda ex: ex["split"] == "test"),
    }


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1_macro": f1_score(labels, preds, average="macro"),
        "f1_weighted": f1_score(labels, preds, average="weighted"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-name", default="microsoft/deberta-v3-small")
    parser.add_argument("--data-path", type=Path, default=Path("data/processed/combined_deviations_labeled.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("models/deviation-classifier"))
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-train-samples", type=int, default=None, help="Cap train set for a quick smoke test.")
    args = parser.parse_args()

    torch.set_num_threads(os.cpu_count() or 4)
    print(f"CPU-only run: using {torch.get_num_threads()} torch threads")

    splits = load_splits(args.data_path)
    if args.max_train_samples:
        splits["train"] = splits["train"].select(range(min(args.max_train_samples, len(splits["train"]))))

    print(f"train={len(splits['train'])} val={len(splits['val'])} test={len(splits['test'])}")

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=args.max_length)

    keep_cols = {"input_ids", "attention_mask", "token_type_ids", "label"}
    tokenized = {}
    for name, ds in splits.items():
        ds = ds.map(tokenize, batched=True)
        drop_cols = [c for c in ds.column_names if c not in keep_cols]
        tokenized[name] = ds.remove_columns(drop_cols)

    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name, num_labels=len(CATEGORIES), id2label=ID2LABEL, label2id=LABEL2ID
    )

    # transformers>=5 dropped warmup_ratio from TrainingArguments in favor of
    # a raw step count -- compute the equivalent ourselves (10% of total steps).
    steps_per_epoch = max(1, len(tokenized["train"]) // args.batch_size)
    total_steps = steps_per_epoch * args.epochs
    warmup_steps = max(1, int(0.1 * total_steps))

    training_args = TrainingArguments(
        output_dir=str(args.output_dir / "checkpoints"),
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        num_train_epochs=args.epochs,
        learning_rate=args.learning_rate,
        warmup_steps=warmup_steps,
        max_grad_norm=1.0,
        fp16=False,
        bf16=False,
        # torch.optim.AdamW corrupts every model parameter to NaN on this
        # setup even with clean gradients and clipping (reproduced on
        # torch 2.6.0 and 2.13.0 CPU builds) -- Adafactor sidesteps it.
        optim="adafactor",
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=1,
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        logging_steps=10,
        seed=args.seed,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["val"],
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        compute_metrics=compute_metrics,
    )

    trainer.train()

    val_metrics = trainer.evaluate(tokenized["val"])
    print("\n=== Validation metrics ===")
    print(val_metrics)

    test_metrics = trainer.evaluate(tokenized["test"])
    print("\n=== Test metrics ===")
    print(test_metrics)

    test_preds = trainer.predict(tokenized["test"])
    pred_labels = np.argmax(test_preds.predictions, axis=-1)
    report_text = classification_report(
        test_preds.label_ids, pred_labels, target_names=CATEGORIES, digits=3
    )
    print("\n=== Test classification report ===")
    print(report_text)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))
    with open(args.output_dir / "label_map.json", "w", encoding="utf-8") as f:
        json.dump({"label2id": LABEL2ID, "id2label": ID2LABEL}, f, indent=2)
    with open(args.output_dir / "training_results.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "model_name": args.model_name,
                "max_length": args.max_length,
                "epochs": args.epochs,
                "batch_size": args.batch_size,
                "learning_rate": args.learning_rate,
                "seed": args.seed,
                "train_size": len(tokenized["train"]),
                "val_metrics": val_metrics,
                "test_metrics": test_metrics,
                "test_classification_report": report_text,
            },
            f,
            indent=2,
        )

    print(f"\nSaved model + training_results.json to {args.output_dir}")


if __name__ == "__main__":
    main()
