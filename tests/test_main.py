import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db, protocol_lookup
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


class TestReferenceAndCapaActionsEndpoints(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "test_triage.db"
        self._orig_db_path = db.DB_PATH
        db.DB_PATH = self._db_path
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self._orig_db_path
        self._tmp_dir.cleanup()

    def _insert_report(self, report_id: str, status: str = "approved"):
        db.insert_report(
            {
                "report_id": report_id,
                "protocol_id": "PDA-2024-001",
                "site_id": "001",
                "subject_id": "001-0001",
                "deviation_date": "2024-05-01",
                "discovery_date": "2024-05-02",
                "text": "Some deviation.",
                "status": status,
            }
        )

    def test_get_reference_data(self):
        with TestClient(app) as client:
            response = client.get("/reference")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("major", body["capa_guidance"])
        self.assertIn("## major", body["labels_markdown"])

    def test_update_capa_actions_persists_and_round_trips(self):
        self._insert_report("r1")
        with TestClient(app) as client:
            response = client.post(
                "/reports/r1/capa-actions", json={"actions_status": [True, False, True]}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["capa_actions_status"], [True, False, True])

        record = db.get_report("r1")
        self.assertEqual(record["capa_actions_status"], [True, False, True])

    def test_update_capa_actions_404_for_missing_report(self):
        with TestClient(app) as client:
            response = client.post(
                "/reports/does-not-exist/capa-actions", json={"actions_status": [True]}
            )
        self.assertEqual(response.status_code, 404)


class TestUserAndSiteEndpoints(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "test_triage.db"
        self._orig_db_path = db.DB_PATH
        db.DB_PATH = self._db_path
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self._orig_db_path
        self._tmp_dir.cleanup()

    def test_fresh_db_seeds_one_user_per_role_and_one_site(self):
        with TestClient(app) as client:
            users = client.get("/users").json()
            sites = client.get("/sites").json()

        roles = {u["role"] for u in users}
        self.assertEqual(
            roles, {"site_coordinator", "cra", "quality_reviewer", "administrator"}
        )
        self.assertEqual(len(sites), 1)
        self.assertEqual(sites[0]["site_id"], "001")

    def test_create_update_delete_user(self):
        with TestClient(app) as client:
            created = client.post(
                "/users", json={"name": "New Coordinator", "role": "site_coordinator", "site_id": "001"}
            ).json()
            self.assertEqual(created["name"], "New Coordinator")
            user_id = created["user_id"]

            updated = client.put(
                f"/users/{user_id}",
                json={"name": "Renamed Coordinator", "role": "site_coordinator", "site_id": "001"},
            ).json()
            self.assertEqual(updated["name"], "Renamed Coordinator")

            delete_response = client.delete(f"/users/{user_id}")
            self.assertEqual(delete_response.status_code, 200)
            self.assertIsNone(db.get_user(user_id))

    def test_cannot_delete_last_administrator(self):
        with TestClient(app) as client:
            users = client.get("/users").json()
            admin = next(u for u in users if u["role"] == "administrator")
            response = client.delete(f"/users/{admin['user_id']}")
        self.assertEqual(response.status_code, 400)
        self.assertIsNotNone(db.get_user(admin["user_id"]))

    def test_deleting_one_of_two_administrators_is_allowed(self):
        with TestClient(app) as client:
            second_admin = client.post(
                "/users", json={"name": "Second Admin", "role": "administrator"}
            ).json()
            first_admin = next(u for u in client.get("/users").json() if u["role"] == "administrator" and u["user_id"] != second_admin["user_id"])

            response = client.delete(f"/users/{first_admin['user_id']}")
        self.assertEqual(response.status_code, 200)

    def test_create_site_rejects_duplicate_id(self):
        with TestClient(app) as client:
            response = client.post(
                "/sites", json={"site_id": "001", "name": "Duplicate"}
            )
        self.assertEqual(response.status_code, 400)

    def test_create_site_rejects_invalid_id_characters(self):
        with TestClient(app) as client:
            response = client.post("/sites", json={"site_id": "bad id!", "name": "Bad"})
        self.assertEqual(response.status_code, 400)

    def test_create_update_delete_site(self):
        with TestClient(app) as client:
            created = client.post(
                "/sites", json={"site_id": "042", "name": "New Site", "protocol_id": "PDA-2024-001"}
            ).json()
            self.assertEqual(created["status"], "active")

            updated = client.put(
                "/sites/042",
                json={"name": "Renamed Site", "protocol_id": "PDA-2024-001", "status": "inactive"},
            ).json()
            self.assertEqual(updated["status"], "inactive")

            delete_response = client.delete("/sites/042")
            self.assertEqual(delete_response.status_code, 200)
            self.assertIsNone(db.get_site("042"))


if __name__ == "__main__":
    unittest.main()
