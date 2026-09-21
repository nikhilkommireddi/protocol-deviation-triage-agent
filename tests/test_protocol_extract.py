import unittest

from app.protocol_extract import to_storage_format


class TestToStorageFormat(unittest.TestCase):
    def test_current_version_gets_none_superseded_date(self):
        extracted = {
            "visit_schedule": [],
            "eligibility_criteria": {"inclusion": [], "exclusion": []},
            "consent_versions": [
                {
                    "version": "v3.0",
                    "effective_date": "2024-01-01",
                    "is_current": True,
                    "superseded_date": "",
                    "summary": "Current version.",
                    "material_safety_change": False,
                }
            ],
        }

        result = to_storage_format("PROTO-1", extracted)

        self.assertIsNone(result["consent_versions"][0]["superseded_date"])
        self.assertEqual(result["protocol_id"], "PROTO-1")

    def test_superseded_version_keeps_its_date(self):
        extracted = {
            "visit_schedule": [],
            "eligibility_criteria": {"inclusion": [], "exclusion": []},
            "consent_versions": [
                {
                    "version": "v2.0",
                    "effective_date": "2023-01-01",
                    "is_current": False,
                    "superseded_date": "2024-01-01",
                    "summary": "Superseded.",
                    "material_safety_change": True,
                }
            ],
        }

        result = to_storage_format("PROTO-1", extracted)

        self.assertEqual(result["consent_versions"][0]["superseded_date"], "2024-01-01")
        self.assertTrue(result["consent_versions"][0]["material_safety_change"])

    def test_not_current_but_missing_superseded_date_becomes_none(self):
        # Defensive: the model said this version isn't current but didn't
        # give a superseded_date -- don't silently fabricate a date, but
        # also don't leave an empty string that would break
        # protocol_lookup.py's `on_date < superseded_date` comparison.
        extracted = {
            "visit_schedule": [],
            "eligibility_criteria": {"inclusion": [], "exclusion": []},
            "consent_versions": [
                {
                    "version": "v1.0",
                    "effective_date": "2022-01-01",
                    "is_current": False,
                    "superseded_date": "",
                    "summary": "Unclear when superseded.",
                    "material_safety_change": False,
                }
            ],
        }

        result = to_storage_format("PROTO-1", extracted)

        self.assertIsNone(result["consent_versions"][0]["superseded_date"])

    def test_passes_through_visit_schedule_and_eligibility(self):
        extracted = {
            "visit_schedule": [{"visit": "Week 4", "target_day": 28, "window_days": 3}],
            "eligibility_criteria": {"inclusion": ["Age 18-75"], "exclusion": ["Pregnancy"]},
            "consent_versions": [],
        }

        result = to_storage_format("PROTO-1", extracted)

        self.assertEqual(result["visit_schedule"], extracted["visit_schedule"])
        self.assertEqual(result["eligibility_criteria"], extracted["eligibility_criteria"])


if __name__ == "__main__":
    unittest.main()
