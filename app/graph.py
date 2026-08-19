"""LangGraph triage workflow: ingest -> classify -> CAPA lookup -> memo
draft -> mock queue.

Each node's external call (model inference, Claude API) is wrapped in a
small standalone function (predict_category, draft_memo, deliver_to_queue)
so tests can mock just that call rather than the whole node.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import TypedDict

import anthropic
import torch
from langgraph.graph import END, START, StateGraph

from app import db

MODEL_DIR = Path("models/deviation-classifier")
CAPA_GUIDANCE_PATH = Path("data/capa_guidance.json")
MEMO_MODEL = "claude-sonnet-5"
MAX_TOKEN_LENGTH = 176  # matches the max_length the classifier was fine-tuned with

_model = None
_tokenizer = None


class TriageState(TypedDict, total=False):
    protocol_id: str
    site_id: str
    subject_id: str
    deviation_date: str
    discovery_date: str
    raw_text: str
    report_id: str
    text: str
    category: str
    confidence: float
    capa_guidance: dict
    memo: dict
    status: str


def _load_classifier():
    global _model, _tokenizer
    if _model is None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        _tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
        # The checkpoint was saved with dtype float16 (Colab GPU run); fp16
        # ops are unsupported/very slow on most CPU kernels, so force fp32.
        _model = AutoModelForSequenceClassification.from_pretrained(
            str(MODEL_DIR), dtype=torch.float32
        )
        _model.eval()
    return _model, _tokenizer


def predict_category(text: str) -> tuple[str, float]:
    model, tokenizer = _load_classifier()
    inputs = tokenizer(text, truncation=True, max_length=MAX_TOKEN_LENGTH, return_tensors="pt")
    with torch.no_grad():
        logits = model(**inputs).logits
    probs = torch.softmax(logits, dim=-1)[0]
    pred_id = int(torch.argmax(probs).item())
    category = model.config.id2label[pred_id]
    confidence = float(probs[pred_id].item())
    return category, confidence


MEMO_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "root_cause_narrative": {"type": "string"},
        "regulatory_citation": {"type": "string"},
        "recommended_capa_actions": {"type": "array", "items": {"type": "string"}},
        "requires_expedited_reporting": {"type": "boolean"},
        "responsible_party": {"type": "string"},
        "target_resolution_date": {"type": "string"},
    },
    "required": [
        "summary",
        "root_cause_narrative",
        "regulatory_citation",
        "recommended_capa_actions",
        "requires_expedited_reporting",
        "responsible_party",
        "target_resolution_date",
    ],
    "additionalProperties": False,
}

MEMO_SYSTEM_PROMPT = (
    "You draft CAPA (Corrective and Preventive Action) review memos for clinical "
    "trial protocol deviations, for a human quality reviewer to approve or edit -- "
    "you are not the final decision-maker. Base your memo strictly on the deviation "
    "text and CAPA guidance provided; do not invent facts not present in either. "
    "recommended_capa_actions should be concrete and specific to this deviation, not "
    "generic restatements of the required elements. responsible_party and "
    "target_resolution_date are your best-informed recommendation for a human to "
    "confirm or change, not a final assignment."
)


def draft_memo(text: str, category: str, capa_guidance: dict) -> dict:
    client = anthropic.Anthropic()
    user_prompt = (
        f"Deviation report (category: {category}):\n{text}\n\n"
        f"CAPA guidance for this category:\n{json.dumps(capa_guidance, indent=2)}\n\n"
        "Draft the review memo."
    )
    response = client.messages.create(
        model=MEMO_MODEL,
        max_tokens=2048,
        system=MEMO_SYSTEM_PROMPT,
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": MEMO_SCHEMA},
        },
        messages=[{"role": "user", "content": user_prompt}],
    )
    text_block = next(b.text for b in response.content if b.type == "text")
    return json.loads(text_block)


def deliver_to_queue(record: dict) -> dict:
    db.update_report(record["report_id"], {"status": "queued"})
    return {"report_id": record["report_id"], "status": "queued"}


def ingest_node(state: TriageState) -> dict:
    report_id = str(uuid.uuid4())
    text = state["raw_text"].strip()
    record = {
        "report_id": report_id,
        "protocol_id": state["protocol_id"],
        "site_id": state["site_id"],
        "subject_id": state["subject_id"],
        "deviation_date": state["deviation_date"],
        "discovery_date": state["discovery_date"],
        "text": text,
        "status": "ingested",
    }
    db.insert_report(record)
    return {"report_id": report_id, "text": text, "status": "ingested"}


def classify_node(state: TriageState) -> dict:
    category, confidence = predict_category(state["text"])
    db.update_report(state["report_id"], {"category": category, "confidence": confidence, "status": "classified"})
    return {"category": category, "confidence": confidence, "status": "classified"}


def capa_lookup_node(state: TriageState) -> dict:
    with CAPA_GUIDANCE_PATH.open(encoding="utf-8") as f:
        guidance_by_category = json.load(f)
    capa_guidance = guidance_by_category[state["category"]]
    db.update_report(state["report_id"], {"capa_guidance": capa_guidance, "status": "capa_reviewed"})
    return {"capa_guidance": capa_guidance, "status": "capa_reviewed"}


def memo_draft_node(state: TriageState) -> dict:
    memo = draft_memo(state["text"], state["category"], state["capa_guidance"])
    db.update_report(state["report_id"], {"memo": memo, "status": "drafted"})
    return {"memo": memo, "status": "drafted"}


def mock_queue_node(state: TriageState) -> dict:
    result = deliver_to_queue({"report_id": state["report_id"]})
    return {"status": result["status"]}


def build_graph():
    builder = StateGraph(TriageState)
    builder.add_node("ingest", ingest_node)
    builder.add_node("classify", classify_node)
    builder.add_node("capa_lookup", capa_lookup_node)
    builder.add_node("memo_draft", memo_draft_node)
    builder.add_node("mock_queue", mock_queue_node)

    builder.add_edge(START, "ingest")
    builder.add_edge("ingest", "classify")
    builder.add_edge("classify", "capa_lookup")
    builder.add_edge("capa_lookup", "memo_draft")
    builder.add_edge("memo_draft", "mock_queue")
    builder.add_edge("mock_queue", END)

    return builder.compile()


graph = build_graph()
