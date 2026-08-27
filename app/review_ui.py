"""Streamlit review UI: submit a new deviation report through the full
LangGraph pipeline, then browse the queue and approve/reject drafted memos.

Reads/writes the SQLite DB directly (app/db.py) rather than going through
the FastAPI HTTP layer -- simpler for a demo, one process to run, and
consistent with how app/graph.py itself talks to the DB.
"""

from __future__ import annotations

import sys
from pathlib import Path

# `streamlit run app/review_ui.py` puts this file's own directory on
# sys.path, not the repo root -- so `app` isn't importable as a package
# without this. (Running it via `python -m` or importing it as a module,
# as the tests do, doesn't hit this since the repo root is already on the
# path in those cases.)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from app import db, graph

st.set_page_config(page_title="Protocol Deviation Triage", layout="wide")
db.init_db()

st.title("Protocol Deviation Triage Agent")

submit_tab, review_tab = st.tabs(["Submit New Deviation", "Review Queue"])

with submit_tab:
    st.subheader("Submit a deviation report")
    with st.form("submit_form"):
        col1, col2, col3 = st.columns(3)
        protocol_id = col1.text_input("Protocol ID", value="PDA-2024-001")
        site_id = col2.text_input("Site ID", value="001")
        subject_id = col3.text_input("Subject ID", value="001-1234")

        col4, col5 = st.columns(2)
        deviation_date = col4.text_input("Deviation date (YYYY-MM-DD)")
        discovery_date = col5.text_input("Discovery date (YYYY-MM-DD)")

        text = st.text_area("Deviation report text", height=150)
        submitted = st.form_submit_button("Submit for triage")

    if submitted:
        if not text.strip() or not deviation_date or not discovery_date:
            st.error("Deviation report text, deviation date, and discovery date are all required.")
        else:
            with st.spinner("Running triage pipeline (classify + draft memo)..."):
                initial_state = {
                    "protocol_id": protocol_id,
                    "site_id": site_id,
                    "subject_id": subject_id,
                    "deviation_date": deviation_date,
                    "discovery_date": discovery_date,
                    "raw_text": text,
                }
                result = graph.graph.invoke(initial_state)
            st.success(
                f"Triaged as **{result['category']}** "
                f"(confidence {result['confidence']:.2f}) and drafted for review. "
                f"See the Review Queue tab."
            )

with review_tab:
    st.subheader("Review queue")
    records = db.list_reports()

    if not records:
        st.info("No reports yet -- submit one on the first tab.")
    else:
        statuses = sorted({r["status"] for r in records})
        status_filter = st.multiselect("Filter by status", statuses, default=statuses)
        filtered = [r for r in records if r["status"] in status_filter]

        st.dataframe(
            [
                {
                    "report_id": r["report_id"][:8],
                    "protocol_id": r["protocol_id"],
                    "subject_id": r["subject_id"],
                    "category": r["category"],
                    "confidence": r["confidence"],
                    "status": r["status"],
                    "created_at": r["created_at"],
                }
                for r in filtered
            ],
            width="stretch",
        )

        if filtered:
            options = {
                f"{r['report_id'][:8]} — {r['protocol_id']}/{r['subject_id']} "
                f"— {r['category']} ({r['status']})": r["report_id"]
                for r in filtered
            }
            selected_label = st.selectbox("Select a report to review", list(options.keys()))
            selected_id = options[selected_label]
            record = db.get_report(selected_id)

            st.divider()
            left, right = st.columns([2, 1])

            with left:
                st.markdown(f"**Original report** ({record['protocol_id']} / {record['subject_id']})")
                st.text_area("Deviation text", value=record["text"], height=120, disabled=True)
                st.caption(
                    f"Deviation date: {record['deviation_date']} | "
                    f"Discovery date: {record['discovery_date']}"
                )

            with right:
                st.markdown("**Classification**")
                if record["category"]:
                    st.write(f"Category: **{record['category']}**")
                    confidence = record["confidence"] or 0.0
                    st.write(f"Confidence: {confidence:.2f}")
                    if confidence < 0.6:
                        st.warning("Low confidence -- review the category assignment carefully.")
                else:
                    st.write("Not yet classified.")

            if record.get("capa_guidance"):
                with st.expander("CAPA guidance"):
                    capa = record["capa_guidance"]
                    st.write(f"**Routing team:** {capa['routing_team']}")
                    st.write(f"**Regulatory reference:** {capa['regulatory_reference']}")
                    st.write("**Required CAPA elements:**")
                    for element in capa["required_capa_elements"]:
                        st.write(f"- {element}")

            if record.get("memo"):
                st.divider()
                st.markdown("**Drafted memo** (edit as needed before approving)")
                memo = record["memo"]

                summary = st.text_area("Summary", value=memo.get("summary", ""), height=80)
                root_cause = st.text_area(
                    "Root cause narrative", value=memo.get("root_cause_narrative", ""), height=100
                )
                citation = st.text_area(
                    "Regulatory citation", value=memo.get("regulatory_citation", ""), height=60
                )
                actions_text = "\n".join(memo.get("recommended_capa_actions", []))
                actions_text = st.text_area(
                    "Recommended CAPA actions (one per line)", value=actions_text, height=120
                )
                requires_expedited = st.checkbox(
                    "Requires expedited reporting",
                    value=bool(memo.get("requires_expedited_reporting", False)),
                )
                col_a, col_b = st.columns(2)
                responsible_party = col_a.text_input(
                    "Responsible party", value=memo.get("responsible_party", "")
                )
                target_date = col_b.text_input(
                    "Target resolution date", value=memo.get("target_resolution_date", "")
                )
                reviewer_note = st.text_input("Reviewer note (optional)", value=memo.get("reviewer_note", ""))

                def _edited_memo() -> dict:
                    return {
                        "summary": summary,
                        "root_cause_narrative": root_cause,
                        "regulatory_citation": citation,
                        "recommended_capa_actions": [
                            line.strip() for line in actions_text.splitlines() if line.strip()
                        ],
                        "requires_expedited_reporting": requires_expedited,
                        "responsible_party": responsible_party,
                        "target_resolution_date": target_date,
                        "reviewer_note": reviewer_note,
                    }

                approve_col, reject_col = st.columns(2)
                if approve_col.button("Approve", type="primary", width="stretch"):
                    db.update_report(selected_id, {"memo": _edited_memo(), "status": "approved"})
                    st.success("Approved.")
                    st.rerun()
                if reject_col.button("Reject", width="stretch"):
                    db.update_report(selected_id, {"memo": _edited_memo(), "status": "rejected"})
                    st.warning("Rejected.")
                    st.rerun()
            else:
                st.info("Memo not yet drafted for this report.")
