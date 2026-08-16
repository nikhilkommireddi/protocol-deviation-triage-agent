import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from generate_synthetic_deviations import CATEGORIES, generate_records, stratified_split


class TestGenerateSyntheticDeviations(unittest.TestCase):
    def test_total_and_per_category_counts(self):
        records = generate_records(seed=42, n_per_category=60)
        self.assertEqual(len(records), 300)
        counts = {c: 0 for c in CATEGORIES}
        for r in records:
            counts[r["category"]] += 1
        for category in CATEGORIES:
            self.assertEqual(counts[category], 60)

    def test_unique_ids(self):
        records = generate_records(seed=42, n_per_category=60)
        ids = [r["id"] for r in records]
        self.assertEqual(len(ids), len(set(ids)))

    def test_deterministic_with_seed(self):
        records_a = generate_records(seed=7, n_per_category=20)
        records_b = generate_records(seed=7, n_per_category=20)
        self.assertEqual(records_a, records_b)

    def test_different_seed_differs(self):
        records_a = generate_records(seed=1, n_per_category=20)
        records_b = generate_records(seed=2, n_per_category=20)
        self.assertNotEqual(records_a, records_b)

    def test_unreported_has_larger_report_gap(self):
        records = generate_records(seed=42, n_per_category=60)
        from datetime import date as _date

        def gap_days(r):
            d1 = _date.fromisoformat(r["deviation_date"])
            d2 = _date.fromisoformat(r["discovery_date"])
            return (d2 - d1).days

        unreported_gaps = [gap_days(r) for r in records if r["category"] == "unreported"]
        other_gaps = [gap_days(r) for r in records if r["category"] != "unreported"]
        self.assertGreater(min(unreported_gaps), max(other_gaps))

    def test_split_assignment(self):
        records = generate_records(seed=42, n_per_category=60)
        split_records = stratified_split(records, seed=42)

        self.assertEqual(len(split_records), 300)
        for r in split_records:
            self.assertIn(r["split"], {"train", "val", "test"})

        for category in CATEGORIES:
            cat_records = [r for r in split_records if r["category"] == category]
            splits = {r["split"] for r in cat_records}
            self.assertTrue({"train", "val", "test"}.issubset(splits))
            train_count = sum(1 for r in cat_records if r["split"] == "train")
            self.assertTrue(38 <= train_count <= 46)


if __name__ == "__main__":
    unittest.main()
