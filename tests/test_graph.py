import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import anthropic

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

        events = db.list_audit_events(result["report_id"])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "submitted")

    def test_ingest_node_attributes_submitter_when_provided(self):
        state = {
            "protocol_id": "PDA-2024-001",
            "site_id": "001",
            "subject_id": "001-1234",
            "deviation_date": "2024-05-01",
            "discovery_date": "2024-05-02",
            "raw_text": "text",
            "submitted_by_name": "Alex Coordinator",
            "submitted_by_role": "Site Coordinator",
        }
        result = graph.ingest_node(state)

        events = db.list_audit_events(result["report_id"])
        self.assertEqual(events[0]["actor_name"], "Alex Coordinator")
        self.assertEqual(events[0]["actor_role"], "Site Coordinator")

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

        events = db.list_audit_events(ingested["report_id"])
        classify_events = [e for e in events if e["event_type"] == "ai_classified"]
        self.assertEqual(len(classify_events), 1)
        self.assertIn("major", classify_events[0]["description"])

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
        self.assertEqual(result["capa_status"], "draft")
        record = db.get_report(ingested["report_id"])
        self.assertEqual(record["memo"], fake_memo)
        self.assertEqual(record["capa_status"], "draft")

    def test_mock_queue_node(self):
        ingested = self._ingest()
        state = {"report_id": ingested["report_id"]}

        result = graph.mock_queue_node(state)

        self.assertEqual(result["status"], "queued")
        events = db.list_audit_events(ingested["report_id"])
        self.assertTrue(any(e["event_type"] == "queued" for e in events))
        record = db.get_report(ingested["report_id"])
        self.assertEqual(record["status"], "queued")

    @patch("app.graph.investigate_protocol")
    def test_protocol_investigate_node(self, mock_investigate):
        fake_findings = {
            "relevant": True,
            "summary": "Consent v4.0 was in effect and added a material safety warning.",
            "citation": "Consent v4.0, effective 2024-03-01",
            "material_safety_change": True,
        }
        mock_investigate.return_value = fake_findings
        ingested = self._ingest()
        state = {
            "report_id": ingested["report_id"],
            "text": ingested["text"],
            "protocol_id": "EVL-2024-106",
            "deviation_date": "2024-07-06",
        }

        result = graph.protocol_investigate_node(state)

        self.assertEqual(result["protocol_findings"], fake_findings)
        record = db.get_report(ingested["report_id"])
        self.assertEqual(record["protocol_findings"], fake_findings)

    @patch("app.graph.investigate_history")
    def test_site_history_node(self, mock_investigate):
        fake_findings = {"prior_count": 2, "pattern_detected": True, "summary": "Recurring dosing-time slip."}
        mock_investigate.return_value = fake_findings
        ingested = self._ingest()
        state = {
            "report_id": ingested["report_id"],
            "text": ingested["text"],
            "protocol_id": "PDA-2024-001",
            "site_id": "001",
        }

        result = graph.site_history_node(state)

        self.assertEqual(result["history_findings"], fake_findings)
        mock_investigate.assert_called_once()
        record = db.get_report(ingested["report_id"])
        self.assertEqual(record["history_findings"], fake_findings)

    @patch("app.graph.plan_investigation")
    def test_supervisor_node(self, mock_plan):
        fake_plan = {
            "run_protocol_investigation": False,
            "run_site_history": True,
            "reasoning": "No consent/visit/eligibility language present.",
        }
        mock_plan.return_value = fake_plan
        ingested = self._ingest()
        state = {"report_id": ingested["report_id"], "text": ingested["text"]}

        result = graph.supervisor_node(state)

        self.assertEqual(result["supervisor_plan"], fake_plan)
        record = db.get_report(ingested["report_id"])
        self.assertEqual(record["supervisor_plan"], fake_plan)

    @patch("app.graph.investigate_protocol")
    def test_protocol_investigate_node_skipped_by_supervisor(self, mock_investigate):
        ingested = self._ingest()
        state = {
            "report_id": ingested["report_id"],
            "text": ingested["text"],
            "protocol_id": "PDA-2024-001",
            "deviation_date": "2024-05-01",
            "supervisor_plan": {"run_protocol_investigation": False, "run_site_history": True, "reasoning": "n/a"},
        }

        result = graph.protocol_investigate_node(state)

        mock_investigate.assert_not_called()
        self.assertFalse(result["protocol_findings"]["relevant"])
        self.assertIn("Skipped by the Supervisor Agent", result["protocol_findings"]["summary"])

    @patch("app.graph.investigate_history")
    def test_site_history_node_skipped_by_supervisor(self, mock_investigate):
        ingested = self._ingest()
        state = {
            "report_id": ingested["report_id"],
            "text": ingested["text"],
            "protocol_id": "PDA-2024-001",
            "site_id": "001",
            "supervisor_plan": {"run_protocol_investigation": True, "run_site_history": False, "reasoning": "n/a"},
        }

        result = graph.site_history_node(state)

        mock_investigate.assert_not_called()
        self.assertIn("Skipped by the Supervisor Agent", result["history_findings"]["summary"])

    @patch("app.graph.investigate_protocol")
    def test_protocol_investigate_node_defaults_to_run_when_no_plan(self, mock_investigate):
        # No supervisor_plan key at all (e.g. an older/partial state) should
        # fail open to running the investigation, not silently skip it.
        mock_investigate.return_value = {
            "relevant": False,
            "summary": "n/a",
            "citation": "",
            "material_safety_change": False,
        }
        ingested = self._ingest()
        state = {
            "report_id": ingested["report_id"],
            "text": ingested["text"],
            "protocol_id": "PDA-2024-001",
            "deviation_date": "2024-05-01",
        }

        graph.protocol_investigate_node(state)

        mock_investigate.assert_called_once()

    @patch("app.graph.adjudicate")
    def test_adjudicate_node_first_pass(self, mock_adjudicate):
        mock_adjudicate.return_value = {
            "final_category": "major",
            "confidence": 0.9,
            "overridden": True,
            "override_reason": "Consent v4.0 withheld material safety info.",
            "classifier_category": "administrative",
        }
        ingested = self._ingest()
        state = {
            "report_id": ingested["report_id"],
            "text": ingested["text"],
            "category": "administrative",
            "confidence": 0.6,
            "protocol_findings": {"relevant": True},
            "history_findings": {"pattern_detected": False},
        }

        result = graph.adjudicate_node(state)

        self.assertEqual(result["category"], "major")
        self.assertEqual(result["retry_count"], 0)
        self.assertTrue(result["adjudication"]["overridden"])
        record = db.get_report(ingested["report_id"])
        self.assertEqual(record["category"], "major")

        events = db.list_audit_events(ingested["report_id"])
        adjudication_events = [e for e in events if e["event_type"] == "ai_adjudicated"]
        self.assertEqual(len(adjudication_events), 1)
        self.assertIn("overrode", adjudication_events[0]["description"])

    @patch("app.graph.adjudicate")
    def test_adjudicate_node_retry_increments_count(self, mock_adjudicate):
        mock_adjudicate.return_value = {
            "final_category": "major",
            "confidence": 0.9,
            "overridden": True,
            "override_reason": "Corrected per verification feedback.",
            "classifier_category": "administrative",
        }
        ingested = self._ingest()
        state = {
            "report_id": ingested["report_id"],
            "text": ingested["text"],
            "category": "administrative",
            "confidence": 0.6,
            "protocol_findings": {"relevant": True},
            "history_findings": {"pattern_detected": False},
            "verification": {"passes": False, "issues": ["category doesn't match citation"]},
            "retry_count": 0,
        }

        result = graph.adjudicate_node(state)

        self.assertEqual(result["retry_count"], 1)
        call_kwargs = mock_adjudicate.call_args.kwargs
        self.assertIn("category doesn't match citation", call_kwargs["verification_feedback"])

    @patch("app.graph.verify")
    def test_verify_node(self, mock_verify):
        mock_verify.return_value = {"passes": True, "issues": []}
        ingested = self._ingest()
        state = {
            "report_id": ingested["report_id"],
            "adjudication": {"final_category": "major"},
            "memo": {"summary": "s"},
            "protocol_findings": {"relevant": False},
            "history_findings": {"pattern_detected": False},
        }

        result = graph.verify_node(state)

        self.assertEqual(result["status"], "verified")
        record = db.get_report(ingested["report_id"])
        self.assertEqual(record["status"], "verified")

        events = db.list_audit_events(ingested["report_id"])
        self.assertTrue(any(e["event_type"] == "ai_verified" for e in events))

    def test_route_after_verify_passes(self):
        state = {"verification": {"passes": True, "issues": []}, "retry_count": 0}
        self.assertEqual(graph.route_after_verify(state), "proceed")

    def test_route_after_verify_retries_once(self):
        state = {"verification": {"passes": False, "issues": ["x"]}, "retry_count": 0}
        self.assertEqual(graph.route_after_verify(state), "retry")

    def test_route_after_verify_stops_after_max_retries(self):
        state = {"verification": {"passes": False, "issues": ["x"]}, "retry_count": 1}
        self.assertEqual(graph.route_after_verify(state), "proceed")

    @patch("app.graph.verify")
    @patch("app.graph.draft_memo")
    @patch("app.graph.adjudicate")
    @patch("app.graph.investigate_history")
    @patch("app.graph.investigate_protocol")
    @patch("app.graph.plan_investigation")
    @patch("app.graph.predict_category")
    def test_full_graph_end_to_end(
        self,
        mock_predict,
        mock_plan,
        mock_investigate_protocol,
        mock_investigate_history,
        mock_adjudicate,
        mock_draft,
        mock_verify,
    ):
        mock_predict.return_value = ("technical", 0.88)
        mock_plan.return_value = {
            "run_protocol_investigation": True,
            "run_site_history": True,
            "reasoning": "No reason to skip either investigation.",
        }
        mock_investigate_protocol.return_value = {
            "relevant": False,
            "summary": "No relevant protocol facts.",
            "citation": "",
            "material_safety_change": False,
        }
        mock_investigate_history.return_value = {
            "prior_count": 0,
            "pattern_detected": False,
            "summary": "No prior deviations on file for this site.",
        }
        mock_adjudicate.return_value = {
            "final_category": "technical",
            "confidence": 0.88,
            "overridden": False,
            "override_reason": "",
            "classifier_category": "technical",
        }
        mock_draft.return_value = {
            "summary": "s",
            "root_cause_narrative": "r",
            "regulatory_citation": "c",
            "recommended_capa_actions": ["a"],
            "requires_expedited_reporting": False,
            "responsible_party": "IT",
            "target_resolution_date": "2024-07-01",
        }
        mock_verify.return_value = {"passes": True, "issues": []}

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
        self.assertIn("adjudication", final_state)
        self.assertIn("verification", final_state)
        self.assertIn("supervisor_plan", final_state)

        record = db.get_report(final_state["report_id"])
        self.assertEqual(record["status"], "queued")
        self.assertEqual(record["category"], "technical")
        self.assertIsInstance(record["memo"], dict)
        self.assertIsInstance(record["capa_guidance"], dict)
        self.assertIsInstance(record["adjudication"], dict)
        self.assertIsInstance(record["verification"], dict)

    @patch("app.graph.verify")
    @patch("app.graph.draft_memo")
    @patch("app.graph.adjudicate")
    @patch("app.graph.investigate_history")
    @patch("app.graph.investigate_protocol")
    @patch("app.graph.plan_investigation")
    @patch("app.graph.predict_category")
    def test_full_graph_retries_once_on_verification_failure(
        self,
        mock_predict,
        mock_plan,
        mock_investigate_protocol,
        mock_investigate_history,
        mock_adjudicate,
        mock_draft,
        mock_verify,
    ):
        mock_predict.return_value = ("administrative", 0.6)
        mock_plan.return_value = {
            "run_protocol_investigation": True,
            "run_site_history": True,
            "reasoning": "Consent form version mentioned -- protocol investigation is relevant.",
        }
        mock_investigate_protocol.return_value = {
            "relevant": True,
            "summary": "Consent v4.0 withheld material safety info.",
            "citation": "Consent v4.0, effective 2024-03-01",
            "material_safety_change": True,
        }
        mock_investigate_history.return_value = {
            "prior_count": 0,
            "pattern_detected": False,
            "summary": "No prior deviations on file for this site.",
        }
        # First adjudication call misses the override; second (after verify
        # flags it) corrects it -- this is the retry loop actually working.
        mock_adjudicate.side_effect = [
            {
                "final_category": "administrative",
                "confidence": 0.6,
                "overridden": False,
                "override_reason": "",
                "classifier_category": "administrative",
            },
            {
                "final_category": "major",
                "confidence": 0.9,
                "overridden": True,
                "override_reason": "Consent v4.0 withheld material safety info.",
                "classifier_category": "administrative",
            },
        ]
        mock_draft.return_value = {
            "summary": "s",
            "root_cause_narrative": "r",
            "regulatory_citation": "c",
            "recommended_capa_actions": ["a"],
            "requires_expedited_reporting": True,
            "responsible_party": "QA",
            "target_resolution_date": "2024-07-01",
        }
        mock_verify.side_effect = [
            {"passes": False, "issues": ["final_category doesn't reflect the material safety change found"]},
            {"passes": True, "issues": []},
        ]

        initial_state = {
            "protocol_id": "EVL-2024-106",
            "site_id": "106",
            "subject_id": "106-9006",
            "deviation_date": "2024-07-06",
            "discovery_date": "2024-07-08",
            "raw_text": "Site 106 used informed consent form v2.1 instead of the currently approved v4.0.",
        }
        final_state = graph.graph.invoke(initial_state)

        self.assertEqual(final_state["category"], "major")
        self.assertEqual(mock_adjudicate.call_count, 2)
        self.assertEqual(mock_verify.call_count, 2)
        self.assertEqual(final_state["status"], "queued")


def _fake_connection_error():
    request = Mock()
    return anthropic.APIConnectionError(message="boom", request=request)


class TestRetryAndFailureHandling(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "test_triage.db"
        self._orig_db_path = db.DB_PATH
        db.DB_PATH = self._db_path
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self._orig_db_path
        self._tmp_dir.cleanup()

    def test_call_with_retries_succeeds_after_transient_failures(self):
        fn = Mock(side_effect=[_fake_connection_error(), _fake_connection_error(), "ok"])
        result = graph._call_with_retries(fn, max_attempts=3, base_delay=0)
        self.assertEqual(result, "ok")
        self.assertEqual(fn.call_count, 3)

    def test_call_with_retries_raises_after_exhausting_attempts(self):
        fn = Mock(side_effect=_fake_connection_error())
        with self.assertRaises(anthropic.APIConnectionError):
            graph._call_with_retries(fn, max_attempts=3, base_delay=0)
        self.assertEqual(fn.call_count, 3)

    def test_call_with_retries_does_not_retry_other_exceptions(self):
        fn = Mock(side_effect=ValueError("not retryable"))
        with self.assertRaises(ValueError):
            graph._call_with_retries(fn, max_attempts=3, base_delay=0)
        self.assertEqual(fn.call_count, 1)

    @patch("app.graph.predict_category")
    def test_classify_node_wraps_failure_as_triage_agent_error(self, mock_predict):
        mock_predict.side_effect = RuntimeError("model weights missing")
        state = {"report_id": "r1", "text": "text"}
        with self.assertRaises(graph.TriageAgentError):
            graph.classify_node(state)

    @patch("app.graph.plan_investigation")
    def test_supervisor_node_fails_open_to_run_everything(self, mock_plan):
        mock_plan.side_effect = _fake_connection_error()
        state = {"report_id": "r1", "text": "text"}

        result = graph.supervisor_node(state)

        self.assertTrue(result["supervisor_plan"]["run_protocol_investigation"])
        self.assertTrue(result["supervisor_plan"]["run_site_history"])

    @patch("app.graph.investigate_protocol")
    def test_protocol_investigate_node_degrades_gracefully(self, mock_investigate):
        mock_investigate.side_effect = _fake_connection_error()
        state = {
            "report_id": "r1",
            "text": "text",
            "protocol_id": "PDA-2024-001",
            "deviation_date": "2024-05-01",
        }
        result = graph.protocol_investigate_node(state)
        self.assertFalse(result["protocol_findings"]["relevant"])
        self.assertIn("could not be completed", result["protocol_findings"]["summary"])

    @patch("app.graph.investigate_history")
    def test_site_history_node_degrades_gracefully(self, mock_investigate):
        mock_investigate.side_effect = _fake_connection_error()
        # Give it a prior report so investigate_history is actually reached
        # (with none on file, site_history_node short-circuits before calling it).
        db.insert_report(
            {
                "report_id": "prior-1",
                "protocol_id": "PDA-2024-001",
                "site_id": "001",
                "subject_id": "001-0000",
                "deviation_date": "2024-04-01",
                "discovery_date": "2024-04-01",
                "text": "Some prior deviation.",
                "status": "queued",
            }
        )
        state = {"report_id": "r1", "text": "text", "protocol_id": "PDA-2024-001", "site_id": "001"}
        result = graph.site_history_node(state)
        self.assertEqual(result["history_findings"]["prior_count"], -1)
        self.assertIn("could not be checked", result["history_findings"]["summary"])

    @patch("app.graph.adjudicate")
    def test_adjudicate_node_wraps_failure_as_triage_agent_error(self, mock_adjudicate):
        mock_adjudicate.side_effect = _fake_connection_error()
        state = {
            "report_id": "r1",
            "text": "text",
            "category": "minor",
            "confidence": 0.7,
            "protocol_findings": {"relevant": False},
            "history_findings": {"pattern_detected": False},
        }
        with self.assertRaises(graph.TriageAgentError):
            graph.adjudicate_node(state)

    @patch("app.graph.draft_memo")
    def test_memo_draft_node_wraps_failure_as_triage_agent_error(self, mock_draft):
        mock_draft.side_effect = _fake_connection_error()
        state = {"report_id": "r1", "text": "text", "category": "minor", "capa_guidance": {}}
        with self.assertRaises(graph.TriageAgentError):
            graph.memo_draft_node(state)

    @patch("app.graph.verify")
    def test_verify_node_wraps_failure_as_triage_agent_error(self, mock_verify):
        mock_verify.side_effect = _fake_connection_error()
        state = {
            "report_id": "r1",
            "adjudication": {"final_category": "minor"},
            "memo": {"summary": "s"},
            "protocol_findings": {"relevant": False},
            "history_findings": {"pattern_detected": False},
        }
        with self.assertRaises(graph.TriageAgentError):
            graph.verify_node(state)


if __name__ == "__main__":
    unittest.main()
