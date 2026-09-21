import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import protocol_lookup
from app.main import app


class TestProtocolEndpoints(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._orig_protocols_dir = protocol_lookup.PROTOCOLS_DIR
        protocol_lookup.PROTOCOLS_DIR = Path(self._tmp_dir.name)

    def tearDown(self):
        protocol_lookup.PROTOCOLS_DIR = self._orig_protocols_dir
        self._tmp_dir.cleanup()

    @patch("app.main.extract_protocol_from_pdf")
    def test_extract_protocol_pdf_returns_extraction(self, mock_extract):
        mock_extract.return_value = {
            "detected_protocol_id": "PROTO-9",
            "visit_schedule": [{"visit": "Week 4", "target_day": 28, "window_days": 3}],
            "eligibility_criteria": {"inclusion": [], "exclusion": []},
            "consent_versions": [],
        }
        with TestClient(app) as client:
            response = client.post(
                "/protocols/extract-pdf",
                files={"file": ("protocol.pdf", b"%PDF-1.4 fake", "application/pdf")},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["detected_protocol_id"], "PROTO-9")

    def test_extract_protocol_pdf_rejects_non_pdf(self):
        with TestClient(app) as client:
            response = client.post(
                "/protocols/extract-pdf",
                files={"file": ("protocol.txt", b"not a pdf", "text/plain")},
            )
        self.assertEqual(response.status_code, 400)

    @patch("app.main.extract_protocol_from_pdf")
    def test_extract_protocol_pdf_wraps_failure_as_502(self, mock_extract):
        mock_extract.side_effect = RuntimeError("boom")
        with TestClient(app) as client:
            response = client.post(
                "/protocols/extract-pdf",
                files={"file": ("protocol.pdf", b"%PDF-1.4 fake", "application/pdf")},
            )
        self.assertEqual(response.status_code, 502)

    def test_save_protocol_writes_file_in_lookup_format(self):
        payload = {
            "visit_schedule": [{"visit": "Week 4", "target_day": 28, "window_days": 3}],
            "eligibility_criteria": {"inclusion": ["Age 18-75"], "exclusion": []},
            "consent_versions": [
                {
                    "version": "v2.0",
                    "effective_date": "2024-01-01",
                    "is_current": True,
                    "superseded_date": "",
                    "summary": "Current.",
                    "material_safety_change": False,
                }
            ],
        }
        with TestClient(app) as client:
            response = client.post("/protocols/TEST-PROTO-1", json=payload)

        self.assertEqual(response.status_code, 200)
        saved_path = protocol_lookup.PROTOCOLS_DIR / "TEST-PROTO-1.json"
        self.assertTrue(saved_path.exists())
        with saved_path.open(encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved["protocol_id"], "TEST-PROTO-1")
        self.assertIsNone(saved["consent_versions"][0]["superseded_date"])

        # Confirm the saved file is actually usable by protocol_lookup, not
        # just structurally similar to what it expects.
        result = protocol_lookup.get_consent_version_in_effect("TEST-PROTO-1", "2024-06-01")
        self.assertTrue(result["found"])
        self.assertEqual(result["version"], "v2.0")

    def test_save_protocol_rejects_invalid_id_characters(self):
        payload = {
            "visit_schedule": [],
            "eligibility_criteria": {"inclusion": [], "exclusion": []},
            "consent_versions": [],
        }
        with TestClient(app) as client:
            response = client.post("/protocols/bad id!", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertFalse((protocol_lookup.PROTOCOLS_DIR / "bad id!.json").exists())


if __name__ == "__main__":
    unittest.main()
