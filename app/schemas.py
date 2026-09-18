from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class DeviationSubmission(BaseModel):
    protocol_id: str
    site_id: str
    subject_id: str
    deviation_date: str
    discovery_date: str
    text: str


class ExtractedFields(BaseModel):
    protocol_id: str
    site_id: str
    subject_id: str
    deviation_date: str
    discovery_date: str
    text: str


class TriageResult(BaseModel):
    report_id: str
    protocol_id: str
    site_id: str
    subject_id: str
    deviation_date: str
    discovery_date: str
    text: str
    category: str | None = None
    confidence: float | None = None
    protocol_findings: dict | None = None
    history_findings: dict | None = None
    adjudication: dict | None = None
    capa_guidance: dict | None = None
    memo: dict | None = None
    verification: dict | None = None
    status: str
    created_at: str
    updated_at: str


class MemoUpdate(BaseModel):
    summary: str
    root_cause_narrative: str
    regulatory_citation: str
    recommended_capa_actions: list[str]
    requires_expedited_reporting: bool
    responsible_party: str
    target_resolution_date: str
    reviewer_note: str = ""


class ReviewSubmission(BaseModel):
    memo: MemoUpdate
    status: Literal["approved", "rejected"]
