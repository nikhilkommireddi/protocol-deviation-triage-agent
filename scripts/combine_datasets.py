"""Combine the offline template-generated dataset and the Claude-generated
dataset into one labeled set for downstream fine-tuning.

Both source datasets were already split 70/15/15 (train/val/test) per
category independently, so concatenating preserves that ratio in the
combined set without needing to re-split (and avoids any risk of shuffling
a record across splits after the fact).

Adds a `source` column ("template" or "claude") so provenance isn't lost --
useful if the classifier's errors turn out to correlate with which
generator produced a record.
"""

from __future__ import annotations

import csv
from pathlib import Path

FIELDNAMES = [
    "id", "source", "protocol_id", "site_id", "subject_id",
    "deviation_date", "discovery_date", "text", "category",
    "voice", "length", "register", "scenario_hint",
    "reviewed", "generated_at", "model", "split",
]


def _read_rows(path: Path, source: str) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["source"] = source
        row.setdefault("voice", "")
        row.setdefault("length", "")
        row.setdefault("register", "")
        row.setdefault("scenario_hint", "")
        row.setdefault("reviewed", "False")
        row.setdefault("generated_at", "")
        row.setdefault("model", source)
    return rows


def combine(
    template_csv: Path,
    claude_csv: Path,
    raw_template_jsonl: Path,
    raw_claude_jsonl: Path,
    processed_out: Path,
    raw_out: Path,
) -> list[dict]:
    template_rows = _read_rows(template_csv, "template")
    claude_rows = _read_rows(claude_csv, "claude")
    combined = template_rows + claude_rows

    processed_out.parent.mkdir(parents=True, exist_ok=True)
    with processed_out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in combined:
            writer.writerow({k: row.get(k, "") for k in FIELDNAMES})

    raw_out.parent.mkdir(parents=True, exist_ok=True)
    with raw_out.open("w", encoding="utf-8") as out_f:
        for src_path in (raw_template_jsonl, raw_claude_jsonl):
            with src_path.open(encoding="utf-8") as in_f:
                for line in in_f:
                    out_f.write(line)

    return combined


def main() -> None:
    combined = combine(
        template_csv=Path("data/processed/deviations_labeled.csv"),
        claude_csv=Path("data/processed/claude_generated_deviations_labeled.csv"),
        raw_template_jsonl=Path("data/raw/synthetic_deviations.jsonl"),
        raw_claude_jsonl=Path("data/raw/claude_generated_deviations.jsonl"),
        processed_out=Path("data/processed/combined_deviations_labeled.csv"),
        raw_out=Path("data/raw/combined_deviations.jsonl"),
    )
    print(f"Combined {len(combined)} records into data/processed/combined_deviations_labeled.csv")


if __name__ == "__main__":
    main()
