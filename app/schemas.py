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
    submitted_by_name: str | None = None
    submitted_by_role: str | None = None


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
    supervisor_plan: dict | None = None
    protocol_findings: dict | None = None
    history_findings: dict | None = None
    adjudication: dict | None = None
    capa_guidance: dict | None = None
    memo: dict | None = None
    verification: dict | None = None
    capa_actions_status: list[bool] | None = None
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
    category: str | None = None
    actor_name: str | None = None
    actor_role: str | None = None


class CapaActionsUpdate(BaseModel):
    actions_status: list[bool]
    actor_name: str | None = None
    actor_role: str | None = None


class AuditEvent(BaseModel):
    event_id: str
    report_id: str
    event_type: str
    description: str
    actor_name: str | None = None
    actor_role: str | None = None
    details: dict | None = None
    created_at: str


UserRole = Literal["site_coordinator", "cra", "quality_reviewer", "administrator"]


class UserCreate(BaseModel):
    name: str
    role: UserRole
    site_id: str | None = None


class UserUpdate(BaseModel):
    name: str
    role: UserRole
    site_id: str | None = None


class UserRecord(BaseModel):
    user_id: str
    name: str
    role: str
    site_id: str | None = None
    created_at: str
    updated_at: str


class SiteCreate(BaseModel):
    site_id: str
    name: str
    protocol_id: str | None = None
    status: Literal["active", "inactive"] = "active"


class SiteUpdate(BaseModel):
    name: str
    protocol_id: str | None = None
    status: Literal["active", "inactive"]


class SiteRecord(BaseModel):
    site_id: str
    name: str
    protocol_id: str | None = None
    status: str
    created_at: str
    updated_at: str


class ReferenceData(BaseModel):
    labels_markdown: str
    capa_guidance: dict


class VisitScheduleEntry(BaseModel):
    visit: str
    target_day: int
    window_days: int


class EligibilityCriteria(BaseModel):
    inclusion: list[str]
    exclusion: list[str]


class ConsentVersionEntry(BaseModel):
    version: str
    effective_date: str
    is_current: bool
    superseded_date: str
    summary: str
    material_safety_change: bool


class ProtocolExtraction(BaseModel):
    detected_protocol_id: str
    visit_schedule: list[VisitScheduleEntry]
    eligibility_criteria: EligibilityCriteria
    consent_versions: list[ConsentVersionEntry]


class ProtocolSaveRequest(BaseModel):
    visit_schedule: list[VisitScheduleEntry]
    eligibility_criteria: EligibilityCriteria
    consent_versions: list[ConsentVersionEntry]
