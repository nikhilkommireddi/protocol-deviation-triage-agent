import unittest

from app import protocol_lookup


class TestProtocolLookup(unittest.TestCase):
    def test_load_protocol_missing_returns_none(self):
        self.assertIsNone(protocol_lookup.load_protocol("NOT-A-REAL-PROTOCOL"))

    def test_get_consent_version_in_effect_material_change(self):
        result = protocol_lookup.get_consent_version_in_effect("EVL-2024-106", "2024-07-06")
        self.assertTrue(result["found"])
        self.assertEqual(result["version"], "v4.0")
        self.assertTrue(result["material_safety_change"])

    def test_get_consent_version_in_effect_no_material_change(self):
        result = protocol_lookup.get_consent_version_in_effect("EVL-2024-123", "2024-07-23")
        self.assertTrue(result["found"])
        self.assertEqual(result["version"], "v4.0")
        self.assertFalse(result["material_safety_change"])

    def test_get_consent_version_before_any_version_effective(self):
        result = protocol_lookup.get_consent_version_in_effect("EVL-2024-106", "2020-01-01")
        self.assertFalse(result["found"])

    def test_get_consent_version_unknown_protocol(self):
        result = protocol_lookup.get_consent_version_in_effect("NOT-A-REAL-PROTOCOL", "2024-07-06")
        self.assertFalse(result["found"])

    def test_get_visit_window_found(self):
        result = protocol_lookup.get_visit_window("EVL-2024-106", "Week 8")
        self.assertTrue(result["found"])
        self.assertEqual(result["target_day"], 56)

    def test_get_visit_window_case_insensitive(self):
        result = protocol_lookup.get_visit_window("EVL-2024-106", "week 8")
        self.assertTrue(result["found"])

    def test_get_visit_window_not_found(self):
        result = protocol_lookup.get_visit_window("EVL-2024-106", "Week 99")
        self.assertFalse(result["found"])

    def test_get_eligibility_criteria(self):
        result = protocol_lookup.get_eligibility_criteria("EVL-2024-123")
        self.assertTrue(result["found"])
        self.assertIn("exclusion", result)


if __name__ == "__main__":
    unittest.main()
