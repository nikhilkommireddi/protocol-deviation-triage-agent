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

    def test_update_capa_actions_logs_audit_event(self):
        self._insert_report("r1")
        with TestClient(app) as client:
            client.post(
                "/reports/r1/capa-actions",
                json={
                    "actions_status": [True, False],
                    "actor_name": "Jordan CRA",
                    "actor_role": "CRA",
                },
            )
        events = db.list_audit_events("r1")
        capa_events = [e for e in events if e["event_type"] == "capa_updated"]
        self.assertEqual(len(capa_events), 1)
        self.assertIn("1/2", capa_events[0]["description"])
        self.assertEqual(capa_events[0]["actor_name"], "Jordan CRA")

    def test_update_capa_status_valid_transition(self):
        self._insert_report("r1")
        db.update_report("r1", {"capa_status": "draft"})
        with TestClient(app) as client:
            response = client.post(
                "/reports/r1/capa-status",
                json={"status": "review", "actor_name": "Jordan CRA", "actor_role": "cra"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["capa_status"], "review")

        events = db.list_audit_events("r1")
        status_events = [e for e in events if e["event_type"] == "capa_status_changed"]
        self.assertEqual(len(status_events), 1)
        self.assertIn("draft -> review", status_events[0]["description"])
        self.assertEqual(status_events[0]["actor_name"], "Jordan CRA")

    def test_update_capa_status_rejects_illegal_skip(self):
        self._insert_report("r1")
        db.update_report("r1", {"capa_status": "draft"})
        with TestClient(app) as client:
            response = client.post("/reports/r1/capa-status", json={"status": "approved"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(db.get_report("r1")["capa_status"], "draft")

    def test_update_capa_status_treats_null_as_draft(self):
        self._insert_report("r1")
        with TestClient(app) as client:
            response = client.post("/reports/r1/capa-status", json={"status": "review"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["capa_status"], "review")

    def test_update_capa_actions_auto_completes_when_approved_and_fully_checked(self):
        self._insert_report("r1")
        db.update_report("r1", {"capa_status": "approved"})
        with TestClient(app) as client:
            response = client.post("/reports/r1/capa-actions", json={"actions_status": [True, True]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["capa_status"], "completed")

        events = db.list_audit_events("r1")
        self.assertTrue(
            any(
                e["event_type"] == "capa_status_changed" and "completed" in e["description"]
                for e in events
            )
        )

    def test_update_capa_actions_does_not_auto_complete_when_not_approved(self):
        self._insert_report("r1")
        db.update_report("r1", {"capa_status": "draft"})
        with TestClient(app) as client:
            response = client.post("/reports/r1/capa-actions", json={"actions_status": [True, True]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["capa_status"], "draft")

    def _minimal_memo(self):
        return {
            "summary": "s",
            "root_cause_narrative": "r",
            "regulatory_citation": "c",
            "recommended_capa_actions": ["a"],
            "requires_expedited_reporting": False,
            "responsible_party": "QA",
            "target_resolution_date": "2024-06-01",
        }

    def test_review_report_logs_classification_change_when_category_differs(self):
        self._insert_report("r1", status="drafted")
        db.update_report("r1", {"category": "administrative"})

        with TestClient(app) as client:
            response = client.post(
                "/reports/r1/review",
                json={
                    "memo": self._minimal_memo(),
                    "status": "approved",
                    "category": "major",
                    "actor_name": "Sam Reviewer",
                    "actor_role": "Quality Reviewer",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["category"], "major")

        events = db.list_audit_events("r1")
        change_events = [e for e in events if e["event_type"] == "classification_changed"]
        self.assertEqual(len(change_events), 1)
        self.assertIn("administrative -> major", change_events[0]["description"])
        self.assertEqual(change_events[0]["actor_name"], "Sam Reviewer")

        reviewed_events = [e for e in events if e["event_type"] == "reviewed"]
        self.assertEqual(len(reviewed_events), 1)
        self.assertEqual(reviewed_events[0]["description"], "Approved")

    def test_review_report_no_classification_change_event_when_category_unchanged(self):
        self._insert_report("r1", status="drafted")
        db.update_report("r1", {"category": "major"})

        with TestClient(app) as client:
            client.post(
                "/reports/r1/review",
                json={"memo": self._minimal_memo(), "status": "rejected", "category": "major"},
            )

        events = db.list_audit_events("r1")
        self.assertFalse(any(e["event_type"] == "classification_changed" for e in events))
        self.assertTrue(any(e["event_type"] == "reviewed" for e in events))

    def test_get_audit_trail_returns_events_in_order(self):
        self._insert_report("r1", status="drafted")
        db.update_report("r1", {"category": "minor"})

        with TestClient(app) as client:
            client.post(
                "/reports/r1/capa-actions", json={"actions_status": [False]}
            )
            client.post(
                "/reports/r1/review",
                json={"memo": self._minimal_memo(), "status": "approved"},
            )
            response = client.get("/reports/r1/audit")

        self.assertEqual(response.status_code, 200)
        events = response.json()
        self.assertEqual([e["event_type"] for e in events], ["capa_updated", "reviewed"])

    def test_get_audit_trail_404_for_missing_report(self):
        with TestClient(app) as client:
            response = client.get("/reports/does-not-exist/audit")
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
