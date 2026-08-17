"""Chunk 1.5 quality-review support: run structural sanity checks over the
full combined dataset, then draw a stratified ~20% sample for semantic
spot-checking (label correctness, category drift, phrasing repetition).

This script does the mechanical parts (things a script can check reliably).
The semantic judgment call -- "does this text actually read like a
`technical` deviation and not a `minor` one" -- still needs an actual read
of the sampled text against data/labels.md; this script just produces that
sample and flags obvious structural problems.
"""

from __future__ import annotations

import csv
import random
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

CATEGORIES = ["major", "minor", "technical", "administrative", "unreported"]
SOURCES = ["template", "claude"]


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def structural_checks(rows: list[dict]) -> list[str]:
    problems = []

    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        dupes = [i for i, c in Counter(ids).items() if c > 1]
        problems.append(f"duplicate ids: {dupes}")

    bad_category = [r["id"] for r in rows if r["category"] not in CATEGORIES]
    if bad_category:
        problems.append(f"rows with invalid category value: {bad_category}")

    bad_source = [r["id"] for r in rows if r["source"] not in SOURCES]
    if bad_source:
        problems.append(f"rows with invalid source value: {bad_source}")

    for r in rows:
        try:
            d1 = date.fromisoformat(r["deviation_date"])
            d2 = date.fromisoformat(r["discovery_date"])
        except ValueError:
            problems.append(f"{r['id']}: unparseable date")
            continue
        if d2 < d1:
            problems.append(f"{r['id']}: discovery_date before deviation_date")

    unreported_gaps = []
    other_gaps = []
    for r in rows:
        gap = (date.fromisoformat(r["discovery_date"]) - date.fromisoformat(r["deviation_date"])).days
        (unreported_gaps if r["category"] == "unreported" else other_gaps).append(gap)
    if unreported_gaps and other_gaps and min(unreported_gaps) <= max(other_gaps):
        problems.append(
            f"unreported reporting-gap invariant broken: min unreported gap "
            f"{min(unreported_gaps)}d <= max other-category gap {max(other_gaps)}d"
        )

    exact_text_dupes = [t for t, c in Counter(r["text"] for r in rows).items() if c > 1]
    if exact_text_dupes:
        problems.append(f"{len(exact_text_dupes)} exact-duplicate text values found")

    return problems


def report_balance(rows: list[dict]) -> None:
    print("Category counts:", Counter(r["category"] for r in rows))
    print("Source counts:  ", Counter(r["source"] for r in rows))
    print("Split counts:   ", Counter(r["split"] for r in rows))
    by_cat_source = Counter((r["category"], r["source"]) for r in rows)
    print("Category x source breakdown:")
    for cat in CATEGORIES:
        print(f"  {cat:15s} template={by_cat_source[(cat, 'template')]:3d}  claude={by_cat_source[(cat, 'claude')]:3d}")


def stratified_sample(rows: list[dict], seed: int, per_cell: int) -> list[dict]:
    """per_cell records from each (category, source) cell -- 5 categories x
    2 sources x per_cell gives the review sample size."""
    rng = random.Random(seed)
    by_cell: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        by_cell[(r["category"], r["source"])].append(r)

    sample = []
    for cat in CATEGORIES:
        for source in SOURCES:
            cell = by_cell[(cat, source)]
            sample.extend(rng.sample(cell, k=min(per_cell, len(cell))))
    return sample


def main() -> None:
    combined_path = Path("data/processed/combined_deviations_labeled.csv")
    rows = load(combined_path)

    print(f"Loaded {len(rows)} rows from {combined_path}\n")

    print("=== Structural checks ===")
    problems = structural_checks(rows)
    if problems:
        for p in problems:
            print(f"  [FAIL] {p}")
    else:
        print("  all structural checks passed")
    print()

    print("=== Balance ===")
    report_balance(rows)
    print()

    sample = stratified_sample(rows, seed=42, per_cell=12)
    sample_path = Path("data/processed/review_sample.csv")
    with sample_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(sample)

    print(f"=== Wrote {len(sample)} sampled rows ({len(sample) / len(rows):.0%} of dataset) to {sample_path} ===")


if __name__ == "__main__":
    main()
