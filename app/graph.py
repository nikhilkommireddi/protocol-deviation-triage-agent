"""LangGraph triage workflow: ingest -> classify -> supervisor ->
protocol_investigate -> site_history -> adjudicate -> capa_lookup ->
memo_draft -> verify -> (loop back to adjudicate once on a flagged issue,
else) mock_queue.

Multiple specialized agents rather than one node doing everything: the
Classifier Agent (fine-tuned DeBERTa) gives a fast first-pass category; the
Supervisor Agent decides which of the two investigative agents are worth
running for this specific deviation (failing open to "run everything" if
it can't decide); the Protocol Investigator Agent and Site History Agent
independently gather evidence a text classifier can't see (what the
protocol actually says, what happened before at this site); the
Adjudication Agent makes the final call, confirming or explicitly
overriding the classifier with a cited reason; the Verification Agent
checks that call and the drafted memo against the evidence actually
gathered before it's allowed to queue.

Each node's external call (model inference, Claude API) is wrapped in a
small standalone function (predict_category, plan_investigation,
investigate_protocol, investigate_history, adjudicate, draft_memo, verify,
deliver_to_queue) so tests can mock just that call rather than the whole
node.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import TypedDict

import torch
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from app import db, protocol_lookup
from app.retry import RETRYABLE_ERRORS, call_with_retries as _call_with_retries, client as _client

load_dotenv()  # picks up ANTHROPIC_API_KEY from a local .env, if present


class TriageAgentError(Exception):
    """A critical agent (classifier, adjudication, memo draft, verification) failed
    even after retries. Distinct from a bare exception so app/main.py can surface a
    clear 502 to the caller instead of an opaque 500 -- the pipeline genuinely
    couldn't complete this triage right now, which is different from a bug."""


MODEL_DIR = Path("models/deviation-classifier")
CAPA_GUIDANCE_PATH = Path("data/capa_guidance.json")
LABELS_PATH = Path("data/labels.md")
# Model tiering: Sonnet 5 only where reasoning depth actually matters
# (Adjudication is the decision-maker; Memo Drafting needs real regulatory
# writing quality; Protocol Investigator does real tool-use reasoning over
# what to look up). Supervisor/Site History/Verification are comparatively
# thin agents by design (a routing decision, a short-list summary, a
# consistency check) -- Haiku 4.5 is a meaningful cost/latency cut there
# with low risk to quality.
MEMO_MODEL = "claude-sonnet-5"
SUPERVISOR_MODEL = "claude-haiku-4-5-20251001"
INVESTIGATOR_MODEL = "claude-sonnet-5"
HISTORY_MODEL = "claude-haiku-4-5-20251001"
ADJUDICATION_MODEL = "claude-sonnet-5"
VERIFICATION_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKEN_LENGTH = 176  # matches the max_length the classifier was fine-tuned with
MAX_TOOL_ITERATIONS = 4
MAX_ADJUDICATION_RETRIES = 1

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
    supervisor_plan: dict
    protocol_findings: dict
    history_findings: dict
    adjudication: dict
    capa_guidance: dict
    memo: dict
    verification: dict
    retry_count: int
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


# --- Supervisor Agent --------------------------------------------------------
#
# Orchestrates the two *investigative* agents (Protocol Investigator, Site
# History) -- deciding which are actually worth running for a given
# deviation, not whether they run at all. Classification, adjudication,
# memo drafting, and verification stay mandatory; skipping those isn't a
# cost optimization, it's a missing decision. Fails open: if the supervisor
# itself can't produce a plan, the default is to run everything rather than
# risk skipping an investigation a case actually needed.

SUPERVISOR_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "run_protocol_investigation": {
            "type": "boolean",
            "description": "True if this deviation plausibly involves protocol-specific facts "
            "(consent version, visit window, eligibility criteria) worth looking up.",
        },
        "run_site_history": {
            "type": "boolean",
            "description": "True if checking this site's prior deviation history is worth doing for this case.",
        },
        "reasoning": {"type": "string"},
    },
    "required": ["run_protocol_investigation", "run_site_history", "reasoning"],
    "additionalProperties": False,
}

SUPERVISOR_SYSTEM_PROMPT = (
    "You are the orchestrator for a protocol deviation triage pipeline. Given a deviation "
    "report, decide which specialist investigations are actually worth running: protocol "
    "investigation (consent version, visit window, eligibility facts) and site history "
    "(prior deviations at this site). Skip an investigation only when it plainly has no "
    "bearing on this deviation. When genuinely unsure, run it -- skipping is a cost/latency "
    "optimization, never a corner to cut on a case that might need it. Any mention of "
    "consent forms, informed consent versions, visit timing, eligibility, or protocol "
    "amendments means protocol investigation is relevant."
)

RUN_EVERYTHING_PLAN = {
    "run_protocol_investigation": True,
    "run_site_history": True,
    "reasoning": "Supervisor planning was unavailable; defaulting to running every "
    "investigation rather than risk skipping one that matters.",
}


def plan_investigation(text: str) -> dict:
    client = _client()
    response = client.messages.create(
        model=SUPERVISOR_MODEL,
        max_tokens=512,
        system=SUPERVISOR_SYSTEM_PROMPT,
        # Haiku 4.5 (SUPERVISOR_MODEL) rejects the "effort" field Sonnet 5 accepts.
        output_config={
            "format": {"type": "json_schema", "schema": SUPERVISOR_PLAN_SCHEMA},
        },
        messages=[{"role": "user", "content": f"Deviation report:\n{text}"}],
    )
    text_block = next(b.text for b in response.content if b.type == "text")
    return json.loads(text_block)


# --- Protocol Investigator Agent -------------------------------------------

PROTOCOL_FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "relevant": {
            "type": "boolean",
            "description": "Whether a protocol-specific fact materially affects how this deviation should be classified.",
        },
        "summary": {"type": "string"},
        "citation": {
            "type": "string",
            "description": "The specific protocol fact relied on, e.g. 'Consent v4.0, effective 2024-03-01, added a material safety warning'. Empty string if not relevant.",
        },
        "material_safety_change": {
            "type": "boolean",
            "description": "True only if a looked-up consent version change withheld or added material safety information.",
        },
    },
    "required": ["relevant", "summary", "citation", "material_safety_change"],
    "additionalProperties": False,
}

PROTOCOL_TOOLS = [
    {
        "name": "get_consent_version_in_effect",
        "description": (
            "Look up which informed consent version was in effect for a protocol on a given "
            "date, including whether that version involved a material safety-information "
            "change from the version it superseded."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "protocol_id": {"type": "string"},
                "on_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["protocol_id", "on_date"],
        },
    },
    {
        "name": "get_visit_window",
        "description": "Look up the target day and allowed window (in days) for a named protocol visit.",
        "input_schema": {
            "type": "object",
            "properties": {
                "protocol_id": {"type": "string"},
                "visit_label": {"type": "string"},
            },
            "required": ["protocol_id", "visit_label"],
        },
    },
    {
        "name": "get_eligibility_criteria",
        "description": "Look up the inclusion/exclusion eligibility criteria for a protocol.",
        "input_schema": {
            "type": "object",
            "properties": {"protocol_id": {"type": "string"}},
            "required": ["protocol_id"],
        },
    },
    {
        "name": "record_findings",
        "description": (
            "Submit your final investigation findings once you've looked up whatever "
            "protocol facts (if any) are actually relevant to this deviation."
        ),
        "input_schema": PROTOCOL_FINDINGS_SCHEMA,
    },
]

_PROTOCOL_TOOL_IMPL = {
    "get_consent_version_in_effect": lambda args: protocol_lookup.get_consent_version_in_effect(
        args["protocol_id"], args["on_date"]
    ),
    "get_visit_window": lambda args: protocol_lookup.get_visit_window(
        args["protocol_id"], args["visit_label"]
    ),
    "get_eligibility_criteria": lambda args: protocol_lookup.get_eligibility_criteria(
        args["protocol_id"]
    ),
}

INVESTIGATOR_SYSTEM_PROMPT = (
    "You investigate a clinical trial protocol deviation by looking up the actual protocol "
    "facts relevant to it -- which consent version was in effect, the real visit window, or "
    "eligibility criteria -- rather than judging from the deviation text alone. Only look up "
    "what's actually relevant to this specific deviation; don't call every tool "
    "unconditionally. When you're done, call record_findings with what you found. If nothing "
    "in the protocol data changes how this deviation should be read, say so plainly "
    "(relevant: false) rather than forcing a finding."
)

NO_FINDINGS = {
    "relevant": False,
    "summary": "Investigation did not conclude within the allotted tool-call budget.",
    "citation": "",
    "material_safety_change": False,
}


def investigate_protocol(text: str, protocol_id: str, deviation_date: str) -> dict:
    client = _client()
    messages = [
        {
            "role": "user",
            "content": (
                f"Deviation report (protocol {protocol_id}, deviation date {deviation_date}):\n{text}"
            ),
        }
    ]

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=INVESTIGATOR_MODEL,
            max_tokens=2048,
            system=INVESTIGATOR_SYSTEM_PROMPT,
            tools=PROTOCOL_TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            return dict(NO_FINDINGS)

        record_call = next((b for b in tool_uses if b.name == "record_findings"), None)
        if record_call:
            return record_call.input

        tool_results = [
            {
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": json.dumps(_PROTOCOL_TOOL_IMPL[call.name](call.input)),
            }
            for call in tool_uses
        ]
        messages.append({"role": "user", "content": tool_results})

    return dict(NO_FINDINGS)


# --- Site History Agent -----------------------------------------------------

HISTORY_FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "prior_count": {"type": "integer"},
        "pattern_detected": {"type": "boolean"},
        "summary": {"type": "string"},
    },
    "required": ["prior_count", "pattern_detected", "summary"],
    "additionalProperties": False,
}

HISTORY_SYSTEM_PROMPT = (
    "You review a clinical trial site's recent deviation history to judge whether a new "
    "deviation is an isolated event or part of a recurring pattern at that site. Base your "
    "judgment strictly on the prior deviations listed; do not speculate beyond them. A "
    "pattern generally means the same type of root cause recurring, not just multiple "
    "unrelated deviations existing at the site."
)


def investigate_history(text: str, site_id: str, prior_reports: list[dict]) -> dict:
    if not prior_reports:
        return {
            "prior_count": 0,
            "pattern_detected": False,
            "summary": "No prior deviations on file for this site.",
        }

    client = _client()
    prior_summaries = "\n".join(
        f"- {r['deviation_date']} ({r.get('category') or 'unclassified'}): {r['text']}"
        for r in prior_reports
    )
    user_prompt = (
        f"New deviation at site {site_id}:\n{text}\n\n"
        f"Prior deviations on file at this site:\n{prior_summaries}\n\n"
        "Does this look like a recurring pattern?"
    )
    response = client.messages.create(
        model=HISTORY_MODEL,
        max_tokens=1024,
        system=HISTORY_SYSTEM_PROMPT,
        # Haiku 4.5 (HISTORY_MODEL) rejects the "effort" field Sonnet 5 accepts.
        output_config={
            "format": {"type": "json_schema", "schema": HISTORY_FINDINGS_SCHEMA},
        },
        messages=[{"role": "user", "content": user_prompt}],
    )
    text_block = next(b.text for b in response.content if b.type == "text")
    return json.loads(text_block)


# --- Adjudication Agent ------------------------------------------------------

ADJUDICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "final_category": {
            "type": "string",
            "enum": ["major", "minor", "technical", "administrative", "unreported"],
        },
        "confidence": {"type": "number"},
        "overridden": {"type": "boolean"},
        "override_reason": {
            "type": "string",
            "description": "Empty string if not overridden. Otherwise the specific cited reason.",
        },
        "classifier_category": {"type": "string"},
    },
    "required": [
        "final_category",
        "confidence",
        "overridden",
        "override_reason",
        "classifier_category",
    ],
    "additionalProperties": False,
}

ADJUDICATION_SYSTEM_PROMPT = (
    "You are the final decision-maker on a protocol deviation's category, choosing among "
    "major, minor, technical, administrative, unreported (see the boundary definitions "
    "provided). You're given a fast classifier's guess plus findings from a protocol "
    "investigator and a site-history reviewer. Confirm the classifier if nothing overrides "
    "it. Override it only when the protocol or history findings give you a concrete, citable "
    "reason the classifier couldn't have known from the text alone -- and say exactly what "
    "that reason is in override_reason. Don't override on a hunch."
)


def adjudicate(
    text: str,
    classifier_category: str,
    classifier_confidence: float,
    protocol_findings: dict,
    history_findings: dict,
    label_definitions: str,
    verification_feedback: str | None = None,
) -> dict:
    client = _client()
    user_prompt = (
        f"Deviation text:\n{text}\n\n"
        f"Classifier's prediction: {classifier_category} (confidence {classifier_confidence:.2f})\n\n"
        f"Protocol investigator findings:\n{json.dumps(protocol_findings, indent=2)}\n\n"
        f"Site history findings:\n{json.dumps(history_findings, indent=2)}\n\n"
        f"Category boundary definitions:\n{label_definitions}\n\n"
    )
    if verification_feedback:
        user_prompt += (
            f"A verification pass flagged an issue with your previous decision: "
            f"{verification_feedback}\nReconsider and correct it if warranted.\n\n"
        )
    user_prompt += "Decide the final category."

    response = client.messages.create(
        model=ADJUDICATION_MODEL,
        max_tokens=1024,
        system=ADJUDICATION_SYSTEM_PROMPT,
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": ADJUDICATION_SCHEMA},
        },
        messages=[{"role": "user", "content": user_prompt}],
    )
    text_block = next(b.text for b in response.content if b.type == "text")
    return json.loads(text_block)


# --- Memo Drafting Agent ------------------------------------------------------

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
    "text, CAPA guidance, and any adjudication/investigation findings provided; do not "
    "invent facts not present in any of them. If the category was overridden from the "
    "classifier's initial guess, or a site-history pattern was detected, reflect that "
    "explicitly in root_cause_narrative and recommended_capa_actions. "
    "recommended_capa_actions should be concrete and specific to this deviation, not "
    "generic restatements of the required elements. responsible_party and "
    "target_resolution_date are your best-informed recommendation for a human to "
    "confirm or change, not a final assignment."
)


def draft_memo(
    text: str,
    category: str,
    capa_guidance: dict,
    adjudication: dict | None = None,
    protocol_findings: dict | None = None,
    history_findings: dict | None = None,
) -> dict:
    client = _client()
    user_prompt = (
        f"Deviation report (category: {category}):\n{text}\n\n"
        f"CAPA guidance for this category:\n{json.dumps(capa_guidance, indent=2)}\n\n"
    )
    if adjudication:
        user_prompt += f"Adjudication reasoning:\n{json.dumps(adjudication, indent=2)}\n\n"
    if protocol_findings and protocol_findings.get("relevant"):
        user_prompt += f"Protocol investigator findings:\n{json.dumps(protocol_findings, indent=2)}\n\n"
    if history_findings and history_findings.get("pattern_detected"):
        user_prompt += f"Site history findings:\n{json.dumps(history_findings, indent=2)}\n\n"
    user_prompt += "Draft the review memo."

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


# --- Verification Agent -------------------------------------------------------

VERIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "passes": {"type": "boolean"},
        "issues": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["passes", "issues"],
    "additionalProperties": False,
}

VERIFICATION_SYSTEM_PROMPT = (
    "You check a deviation adjudication and its drafted memo for internal consistency "
    "against the evidence actually gathered: does the memo's regulatory citation match the "
    "final category, does any claimed protocol or history fact actually appear in the "
    "findings provided, and does an override have a concrete cited reason rather than a "
    "vague one. Flag only real inconsistencies, not stylistic preferences."
)


def verify(adjudication: dict, memo: dict, protocol_findings: dict, history_findings: dict) -> dict:
    client = _client()
    user_prompt = (
        f"Adjudication:\n{json.dumps(adjudication, indent=2)}\n\n"
        f"Drafted memo:\n{json.dumps(memo, indent=2)}\n\n"
        f"Protocol investigator findings:\n{json.dumps(protocol_findings, indent=2)}\n\n"
        f"Site history findings:\n{json.dumps(history_findings, indent=2)}\n\n"
        "Does the adjudication and memo hold up against this evidence?"
    )
    response = client.messages.create(
        model=VERIFICATION_MODEL,
        max_tokens=1024,
        system=VERIFICATION_SYSTEM_PROMPT,
        # Haiku 4.5 (VERIFICATION_MODEL) rejects the "effort" field Sonnet 5 accepts.
        output_config={
            "format": {"type": "json_schema", "schema": VERIFICATION_SCHEMA},
        },
        messages=[{"role": "user", "content": user_prompt}],
    )
    text_block = next(b.text for b in response.content if b.type == "text")
    return json.loads(text_block)


def deliver_to_queue(record: dict) -> dict:
    db.update_report(record["report_id"], {"status": "queued"})
    return {"report_id": record["report_id"], "status": "queued"}


# --- Graph nodes ---------------------------------------------------------------


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
    try:
        category, confidence = predict_category(state["text"])
    except Exception as exc:
        raise TriageAgentError(f"Classifier Agent failed: {exc}") from exc
    db.update_report(state["report_id"], {"category": category, "confidence": confidence, "status": "classified"})
    return {"category": category, "confidence": confidence, "status": "classified"}


def supervisor_node(state: TriageState) -> dict:
    try:
        plan = _call_with_retries(plan_investigation, state["text"])
    except RETRYABLE_ERRORS:
        plan = dict(RUN_EVERYTHING_PLAN)
    db.update_report(state["report_id"], {"supervisor_plan": plan, "status": "planned"})
    return {"supervisor_plan": plan, "status": "planned"}


PROTOCOL_INVESTIGATION_UNAVAILABLE = {
    "relevant": False,
    "summary": "Protocol investigation could not be completed after repeated failures; "
    "proceeding without it. A human reviewer should check protocol-specific facts manually.",
    "citation": "",
    "material_safety_change": False,
}

PROTOCOL_INVESTIGATION_SKIPPED = {
    "relevant": False,
    "summary": "Skipped by the Supervisor Agent -- this deviation was judged unlikely to "
    "involve protocol-specific facts.",
    "citation": "",
    "material_safety_change": False,
}

HISTORY_INVESTIGATION_UNAVAILABLE = {
    "prior_count": -1,
    "pattern_detected": False,
    "summary": "Site history could not be checked after repeated failures; "
    "proceeding without it. A human reviewer should check for prior similar deviations manually.",
}

HISTORY_INVESTIGATION_SKIPPED = {
    "prior_count": -1,
    "pattern_detected": False,
    "summary": "Skipped by the Supervisor Agent for this deviation.",
}


def protocol_investigate_node(state: TriageState) -> dict:
    plan = state.get("supervisor_plan") or RUN_EVERYTHING_PLAN
    if not plan.get("run_protocol_investigation", True):
        findings = dict(PROTOCOL_INVESTIGATION_SKIPPED)
        db.update_report(state["report_id"], {"protocol_findings": findings, "status": "protocol_reviewed"})
        return {"protocol_findings": findings, "status": "protocol_reviewed"}

    # Advisory, not authoritative -- if this keeps failing after retries, degrade
    # gracefully rather than blocking the whole triage on a helper agent.
    try:
        findings = _call_with_retries(
            investigate_protocol, state["text"], state["protocol_id"], state["deviation_date"]
        )
    except RETRYABLE_ERRORS:
        findings = dict(PROTOCOL_INVESTIGATION_UNAVAILABLE)
    db.update_report(state["report_id"], {"protocol_findings": findings, "status": "protocol_reviewed"})
    return {"protocol_findings": findings, "status": "protocol_reviewed"}


def site_history_node(state: TriageState) -> dict:
    plan = state.get("supervisor_plan") or RUN_EVERYTHING_PLAN
    if not plan.get("run_site_history", True):
        findings = dict(HISTORY_INVESTIGATION_SKIPPED)
        db.update_report(state["report_id"], {"history_findings": findings, "status": "history_reviewed"})
        return {"history_findings": findings, "status": "history_reviewed"}

    prior_reports = db.list_reports_by_site(
        state["protocol_id"], state["site_id"], exclude_report_id=state["report_id"]
    )
    try:
        findings = _call_with_retries(investigate_history, state["text"], state["site_id"], prior_reports)
    except RETRYABLE_ERRORS:
        findings = dict(HISTORY_INVESTIGATION_UNAVAILABLE)
    db.update_report(state["report_id"], {"history_findings": findings, "status": "history_reviewed"})
    return {"history_findings": findings, "status": "history_reviewed"}


def adjudicate_node(state: TriageState) -> dict:
    is_retry = state.get("verification") is not None
    retry_count = state.get("retry_count", 0) + (1 if is_retry else 0)

    verification_feedback = None
    if is_retry:
        verification_feedback = "; ".join(state["verification"].get("issues", []))

    with LABELS_PATH.open(encoding="utf-8") as f:
        label_definitions = f.read()

    try:
        result = _call_with_retries(
            adjudicate,
            state["text"],
            state["category"],
            state["confidence"],
            state["protocol_findings"],
            state["history_findings"],
            label_definitions,
            verification_feedback=verification_feedback,
        )
    except RETRYABLE_ERRORS as exc:
        raise TriageAgentError(f"Adjudication Agent failed: {exc}") from exc

    final_category = result["final_category"]
    db.update_report(
        state["report_id"],
        {
            "category": final_category,
            "confidence": result["confidence"],
            "adjudication": result,
            "status": "adjudicated",
        },
    )
    return {
        "category": final_category,
        "confidence": result["confidence"],
        "adjudication": result,
        "retry_count": retry_count,
        "status": "adjudicated",
    }


def capa_lookup_node(state: TriageState) -> dict:
    with CAPA_GUIDANCE_PATH.open(encoding="utf-8") as f:
        guidance_by_category = json.load(f)
    capa_guidance = guidance_by_category[state["category"]]
    db.update_report(state["report_id"], {"capa_guidance": capa_guidance, "status": "capa_reviewed"})
    return {"capa_guidance": capa_guidance, "status": "capa_reviewed"}


def memo_draft_node(state: TriageState) -> dict:
    try:
        memo = _call_with_retries(
            draft_memo,
            state["text"],
            state["category"],
            state["capa_guidance"],
            adjudication=state.get("adjudication"),
            protocol_findings=state.get("protocol_findings"),
            history_findings=state.get("history_findings"),
        )
    except RETRYABLE_ERRORS as exc:
        raise TriageAgentError(f"Memo Drafting Agent failed: {exc}") from exc
    db.update_report(state["report_id"], {"memo": memo, "status": "drafted"})
    return {"memo": memo, "status": "drafted"}


def verify_node(state: TriageState) -> dict:
    try:
        result = _call_with_retries(
            verify, state["adjudication"], state["memo"], state["protocol_findings"], state["history_findings"]
        )
    except RETRYABLE_ERRORS as exc:
        raise TriageAgentError(f"Verification Agent failed: {exc}") from exc
    status = "verified" if result["passes"] else "verification_flagged"
    db.update_report(state["report_id"], {"verification": result, "status": status})
    return {"verification": result, "status": status}


def route_after_verify(state: TriageState) -> str:
    if state["verification"]["passes"]:
        return "proceed"
    if state.get("retry_count", 0) >= MAX_ADJUDICATION_RETRIES:
        return "proceed"
    return "retry"


def mock_queue_node(state: TriageState) -> dict:
    result = deliver_to_queue({"report_id": state["report_id"]})
    return {"status": result["status"]}


def build_graph():
    builder = StateGraph(TriageState)
    builder.add_node("ingest", ingest_node)
    builder.add_node("classify", classify_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("protocol_investigate", protocol_investigate_node)
    builder.add_node("site_history", site_history_node)
    builder.add_node("adjudicate", adjudicate_node)
    builder.add_node("capa_lookup", capa_lookup_node)
    builder.add_node("memo_draft", memo_draft_node)
    builder.add_node("verify", verify_node)
    builder.add_node("mock_queue", mock_queue_node)

    builder.add_edge(START, "ingest")
    builder.add_edge("ingest", "classify")
    builder.add_edge("classify", "supervisor")
    builder.add_edge("supervisor", "protocol_investigate")
    builder.add_edge("protocol_investigate", "site_history")
    builder.add_edge("site_history", "adjudicate")
    builder.add_edge("adjudicate", "capa_lookup")
    builder.add_edge("capa_lookup", "memo_draft")
    builder.add_edge("memo_draft", "verify")
    builder.add_conditional_edges("verify", route_after_verify, {"retry": "adjudicate", "proceed": "mock_queue"})
    builder.add_edge("mock_queue", END)

    return builder.compile()


graph = build_graph()
