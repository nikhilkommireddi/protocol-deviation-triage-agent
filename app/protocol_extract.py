"""Protocol Ingestion Agent: extract structured protocol facts (visit
schedule, eligibility criteria, consent version history) from a real,
uploaded protocol PDF, via the same Claude document-understanding approach
app/pdf_extract.py already uses for deviation reports.

The output matches app/protocol_lookup.py's expected shape for
data/protocols/<protocol_id>.json, but this module never writes that file
itself -- extraction only returns structured data for a human to review,
same "extract pre-fills, human confirms" principle as the deviation-report
PDF upload. app/main.py's save endpoint does the actual write, after review.

Real protocols document amendments (a date + a description of what
changed) rather than an explicit "was this a material safety change"
flag -- the agent has to make that judgment from the amendment's own
wording, the same interpretive call app/graph.py's Protocol Investigator
Agent already makes when investigating a live deviation. Deliberately a
standalone function, not inlined in the endpoint, so it's easy to mock in
tests without a real API key or a real PDF.
"""

from __future__ import annotations

import base64
import json

from dotenv import load_dotenv

from app.retry import client as _client

load_dotenv()  # picks up ANTHROPIC_API_KEY from a local .env, if present

PROTOCOL_EXTRACTION_MODEL = "claude-sonnet-5"

PROTOCOL_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "detected_protocol_id": {
            "type": "string",
            "description": "The protocol number/ID as stated in the document's cover page or "
            "header, if found. Empty string if not found -- the human confirms the actual "
            "protocol_id to save under, this is only a cross-check.",
        },
        "visit_schedule": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "visit": {"type": "string"},
                    "target_day": {"type": "integer"},
                    "window_days": {"type": "integer"},
                },
                "required": ["visit", "target_day", "window_days"],
                "additionalProperties": False,
            },
        },
        "eligibility_criteria": {
            "type": "object",
            "properties": {
                "inclusion": {"type": "array", "items": {"type": "string"}},
                "exclusion": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["inclusion", "exclusion"],
            "additionalProperties": False,
        },
        "consent_versions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "version": {"type": "string"},
                    "effective_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD if determinable, else the raw date text found.",
                    },
                    "is_current": {
                        "type": "boolean",
                        "description": "True if this is the most recent version per the document "
                        "(not yet superseded).",
                    },
                    "superseded_date": {
                        "type": "string",
                        "description": "Empty string if is_current is true.",
                    },
                    "summary": {"type": "string"},
                    "material_safety_change": {
                        "type": "boolean",
                        "description": "True only if this version's own description indicates a "
                        "safety-relevant change (new warning, dose modification for safety, "
                        "updated risk information) -- judge strictly from what the document says "
                        "this amendment changed, not from general assumptions about amendments.",
                    },
                },
                "required": [
                    "version",
                    "effective_date",
                    "is_current",
                    "superseded_date",
                    "summary",
                    "material_safety_change",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["detected_protocol_id", "visit_schedule", "eligibility_criteria", "consent_versions"],
    "additionalProperties": False,
}

PROTOCOL_EXTRACTION_SYSTEM_PROMPT = (
    "You extract structured facts from an uploaded clinical trial protocol document, to "
    "pre-fill lookup data a triage system will later query against -- you are not making any "
    "clinical or regulatory decision, and a human reviews everything you extract before it's "
    "saved.\n\n"
    "Extract: the visit/assessment schedule (target day and allowed window per visit), the "
    "eligibility criteria (inclusion and exclusion lists), and the consent/protocol version "
    "history from the document's amendment history or summary-of-changes section. For each "
    "version, judge material_safety_change strictly from that version's own documented "
    "changes -- true only if the document itself describes a safety-relevant change (a new "
    "warning, a dose change made for safety, updated risk information), not because amendments "
    "are common or because you'd expect one to matter.\n\n"
    "If a section genuinely isn't in the document, return an empty array/object for it rather "
    "than inventing plausible-looking entries -- an incomplete extraction a human fills in "
    "is far better than a fabricated one they don't catch."
)


def extract_protocol_from_pdf(pdf_bytes: bytes) -> dict:
    client = _client()
    encoded = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    response = client.messages.create(
        model=PROTOCOL_EXTRACTION_MODEL,
        # Real protocols vary hugely in how much amendment history and how
        # many eligibility criteria they document -- 4096 truncated mid-JSON
        # on a content-rich real protocol (a multi-amendment Phase 3 trial),
        # producing an unparseable response with no warning.
        max_tokens=8192,
        system=PROTOCOL_EXTRACTION_SYSTEM_PROMPT,
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": PROTOCOL_EXTRACTION_SCHEMA},
        },
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": encoded,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract the visit schedule, eligibility criteria, and consent "
                        "version history from this protocol document.",
                    },
                ],
            }
        ],
    )
    text_block = next(b.text for b in response.content if b.type == "text")
    return json.loads(text_block)


def to_storage_format(protocol_id: str, extracted: dict) -> dict:
    """Convert the LLM's extraction shape (is_current/superseded_date as a
    plain string, for reliable structured-output enforcement) into the
    shape app/protocol_lookup.py actually reads (superseded_date: None for
    the current version) -- keeps that translation isolated here rather
    than changing the proven, already-tested lookup contract."""
    consent_versions = [
        {
            "version": v["version"],
            "effective_date": v["effective_date"],
            "superseded_date": None if v["is_current"] else (v["superseded_date"] or None),
            "summary": v["summary"],
            "material_safety_change": v["material_safety_change"],
        }
        for v in extracted["consent_versions"]
    ]
    return {
        "protocol_id": protocol_id,
        "visit_schedule": extracted["visit_schedule"],
        "eligibility_criteria": extracted["eligibility_criteria"],
        "consent_versions": consent_versions,
    }
