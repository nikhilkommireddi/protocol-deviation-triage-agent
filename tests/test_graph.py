import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db, graph


class TestGraphNodes(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "test_triage.db"
        self._orig_db_path = db.DB_PATH
        db.DB_PATH = self._db_path
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self._orig_db_path
        self._tmp_dir.cleanup()

    def _ingest(self, text="Subject 001-1234 received an incorrect dose of Study Drug X."):
        state = {
            "protocol_id": "PDA-2024-001",
            "site_id": "001",
            "subject_id": "001-1234",
            "deviation_date": "2024-05-01",
            "discovery_date": "2024-05-02",
            "raw_text": text,
        }
        return graph.ingest_node(state)

    def test_ingest_node_creates_record(self):
        result = self._ingest("  padded text  ")
        self.assertEqual(result["status"], "ingested")
        self.assertEqual(result["text"], "padded text")
        self.assertTrue(result["report_id"])

        record = db.get_report(result["report_id"])
        self.assertIsNotNone(record)
        self.assertEqual(record["protocol_id"], "PDA-2024-001")
        self.assertEqual(record["status"], "ingested")

    @patch("app.graph.predict_category")
    def test_classify_node(self, mock_predict):
        mock_predict.return_value = ("major", 0.97)
        ingested = self._ingest()
        state = {"report_id": ingested["report_id"], "text": ingested["text"]}

        result = graph.classify_node(state)

        self.assertEqual(result["category"], "major")
        self.assertAlmostEqual(result["confidence"], 0.97)
        self.assertEqual(result["status"], "classified")
        record = db.get_report(ingested["report_id"])
        self.assertEqual(record["category"], "major")

    def test_capa_lookup_node_reads_real_guidance(self):
        with open("data/capa_guidance.json", encoding="utf-8") as f:
            expected = json.load(f)["major"]

        ingested = self._ingest()
        state = {"report_id": ingested["report_id"], "category": "major"}
        result = graph.capa_lookup_node(state)

        self.assertEqual(result["capa_guidance"], expected)
        self.assertEqual(result["status"], "capa_reviewed")

    @patch("app.graph.draft_memo")
    def test_memo_draft_node(self, mock_draft):
        fake_memo = {
            "summary": "test summary",
            "root_cause_narrative": "test narrative",
            "regulatory_citation": "test citation",
            "recommended_capa_actions": ["action 1"],
            "requires_expedited_reporting": True,
            "responsible_party": "QA",
            "target_resolution_date": "2024-06-01",
        }
        mock_draft.return_value = fake_memo
        ingested = self._ingest()
        state = {
            "report_id": ingested["report_id"],
            "text": ingested["text"],
            "category": "major",
            "capa_guidance": {"routing_team": "Safety"},
        }

        result = graph.memo_draft_node(state)

        self.assertEqual(result["memo"], fake_memo)
        self.assertEqual(result["status"], "drafted")
        record = db.get_report(ingested["report_id"])
        self.assertEqual(record["memo"], fake_memo)

    def test_mock_queue_node(self):
        ingested = self._ingest()
        state = {"report_id": ingested["report_id"]}

        result = graph.mock_queue_node(state)

        self.assertEqual(result["status"], "queued")
        record = db.get_report(ingested["report_id"])
        self.assertEqual(record["status"], "queued")

    @patch("app.graph.draft_memo")
    @patch("app.graph.predict_category")
    def test_full_graph_end_to_end(self, mock_predict, mock_draft):
        mock_predict.return_value = ("technical", 0.88)
        mock_draft.return_value = {
            "summary": "s",
            "root_cause_narrative": "r",
            "regulatory_citation": "c",
            "recommended_capa_actions": ["a"],
            "requires_expedited_reporting": False,
            "responsible_party": "IT",
            "target_resolution_date": "2024-07-01",
        }

        initial_state = {
            "protocol_id": "PDA-2024-002",
            "site_id": "002",
            "subject_id": "002-5678",
            "deviation_date": "2024-05-10",
            "discovery_date": "2024-05-11",
            "raw_text": "An IVRS outage caused an incorrect kit assignment.",
        }
        final_state = graph.graph.invoke(initial_state)

        self.assertEqual(final_state["category"], "technical")
        self.assertEqual(final_state["status"], "queued")
        self.assertIn("capa_guidance", final_state)
        self.assertIn("memo", final_state)

        record = db.get_report(final_state["report_id"])
        self.assertEqual(record["status"], "queued")
        self.assertEqual(record["category"], "technical")
        self.assertIsInstance(record["memo"], dict)
        self.assertIsInstance(record["capa_guidance"], dict)


if __name__ == "__main__":
    unittest.main()
