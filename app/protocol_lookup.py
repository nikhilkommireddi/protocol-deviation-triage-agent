"""Deterministic lookups against structured protocol documents in
data/protocols/<protocol_id>.json, used as tools by the Protocol
Investigator Agent (app/graph.py).

Deliberately plain file-backed lookups rather than embedding-based
retrieval -- at this data scale a lookup is both simpler and more
auditable than vector search, which matters for a compliance-adjacent
use case where "what fact did the agent rely on" needs a precise answer.
"""

from __future__ import annotations

import json
from pathlib import Path

PROTOCOLS_DIR = Path("data/protocols")

NOT_FOUND_PROTOCOL = {"found": False, "detail": "No protocol data available for this protocol_id."}


def load_protocol(protocol_id: str) -> dict | None:
    path = PROTOCOLS_DIR / f"{protocol_id}.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def get_consent_version_in_effect(protocol_id: str, on_date: str) -> dict:
    protocol = load_protocol(protocol_id)
    if protocol is None:
        return dict(NOT_FOUND_PROTOCOL)
    for version in protocol.get("consent_versions", []):
        if version["effective_date"] <= on_date and (
            version["superseded_date"] is None or on_date < version["superseded_date"]
        ):
            return {"found": True, **version}
    return {"found": False, "detail": f"No consent version on file covers {on_date}."}


def get_visit_window(protocol_id: str, visit_label: str) -> dict:
    protocol = load_protocol(protocol_id)
    if protocol is None:
        return dict(NOT_FOUND_PROTOCOL)
    for visit in protocol.get("visit_schedule", []):
        if visit["visit"].lower() == visit_label.lower():
            return {"found": True, **visit}
    return {"found": False, "detail": f"No visit named '{visit_label}' on file for this protocol."}


def get_eligibility_criteria(protocol_id: str) -> dict:
    protocol = load_protocol(protocol_id)
    if protocol is None:
        return dict(NOT_FOUND_PROTOCOL)
    return {"found": True, **protocol.get("eligibility_criteria", {})}
