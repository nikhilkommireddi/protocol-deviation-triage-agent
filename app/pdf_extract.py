"""Extract deviation-report fields from an uploaded PDF via Claude's native
document understanding, rather than a traditional PDF-parsing + regex
approach -- real deviation reports are free-text narratives, not structured
forms with predictable labels, so this is the same "extract structured data
from unstructured text" problem app/graph.py's draft_memo already solves.

Deliberately a standalone function, not inlined in the endpoint, for the
same reason predict_category/draft_memo are standalone in app/graph.py:
easy to mock in tests without needing a real API key or a real PDF.
"""

from __future__ import annotations

import base64
import json

from dotenv import load_dotenv

from app.retry import client as _client

load_dotenv()  # picks up ANTHROPIC_API_KEY from a local .env, if present

EXTRACTION_MODEL = "claude-sonnet-5"

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "protocol_id": {"type": "string"},
        "site_id": {"type": "string"},
        "subject_id": {"type": "string"},
        "deviation_date": {"type": "string"},
        "discovery_date": {"type": "string"},
        "text": {"type": "string"},
    },
    "required": [
        "protocol_id",
        "site_id",
        "subject_id",
        "deviation_date",
        "discovery_date",
        "text",
    ],
    "additionalProperties": False,
}

EXTRACTION_SYSTEM_PROMPT = (
    "You extract structured fields from an uploaded clinical trial protocol "
    "deviation report document, to pre-fill a submission form for a human to "
    "review and edit -- you are not making the final record.\n\n"
    "Fields: protocol_id, site_id, subject_id, deviation_date (YYYY-MM-DD), "
    "discovery_date (YYYY-MM-DD), and text (the deviation narrative itself -- "
    "the actual description of what happened, not the whole document "
    "verbatim if it includes letterhead, signatures, or unrelated "
    "boilerplate).\n\n"
    "If a field is not actually present in the document, return an empty "
    "string for it. Do not guess or invent a plausible-looking value for "
    "anything you cannot find -- an empty field the human fills in "
    "themselves is far better than a wrong one they don't notice."
)


def extract_from_pdf(pdf_bytes: bytes) -> dict:
    client = _client()
    encoded = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    response = client.messages.create(
        model=EXTRACTION_MODEL,
        max_tokens=2048,
        system=EXTRACTION_SYSTEM_PROMPT,
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA},
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
                        "text": "Extract the deviation report fields from this document.",
                    },
                ],
            }
        ],
    )
    text_block = next(b.text for b in response.content if b.type == "text")
    return json.loads(text_block)
