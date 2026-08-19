from __future__ import annotations

from pydantic import BaseModel


class DeviationSubmission(BaseModel):
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
    capa_guidance: dict | None = None
    memo: dict | None = None
    status: str
    created_at: str
    updated_at: str
