import json
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import db, protocol_lookup
from app.graph import (
    CAPA_GUIDANCE_PATH,
    LABELS_PATH,
    TriageAgentError,
    _log_audit,
    deliver_to_queue,
    graph,
)
from app.pdf_extract import extract_from_pdf
from app.protocol_extract import extract_protocol_from_pdf, to_storage_format
from app.retry import call_with_retries
from app.schemas import (
    AuditEvent,
    CapaActionsUpdate,
    CapaStatusUpdate,
    DeviationSubmission,
    ExtractedFields,
    ProtocolExtraction,
    ProtocolSaveRequest,
    ReferenceData,
    ReviewSubmission,
    SiteCreate,
    SiteRecord,
    SiteUpdate,
    TriageResult,
    UserCreate,
    UserRecord,
    UserUpdate,
)

MAX_PDF_SIZE_BYTES = 10 * 1024 * 1024
MAX_PROTOCOL_PDF_SIZE_BYTES = 20 * 1024 * 1024  # real protocols run 80-150 pages
SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")

CAPA_STATUS_TRANSITIONS = {
    "draft": "review",
    "review": "approved",
    "approved": "completed",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Protocol Deviation Triage Agent", lifespan=lifespan)

# Permissive for local dev against the Vite dev server. Tighten this to an
# explicit allow-list before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueueSubmission(BaseModel):
    report_id: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reports", response_model=TriageResult)
def submit_report(submission: DeviationSubmission):
    initial_state = {
        "protocol_id": submission.protocol_id,
        "site_id": submission.site_id,
        "subject_id": submission.subject_id,
        "deviation_date": submission.deviation_date,
        "discovery_date": submission.discovery_date,
        "raw_text": submission.text,
        "submitted_by_name": submission.submitted_by_name,
        "submitted_by_role": submission.submitted_by_role,
    }
    try:
        result_state = graph.invoke(initial_state)
    except TriageAgentError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return db.get_report(result_state["report_id"])


@app.post("/reports/extract-pdf", response_model=ExtractedFields)
async def extract_pdf_fields(file: UploadFile = File(...)):
    if file.content_type != "application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a PDF.")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_PDF_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="PDF exceeds the 10MB size limit.")
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        extracted = call_with_retries(extract_from_pdf, pdf_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"PDF extraction failed: {type(exc).__name__}: {exc}"
        ) from exc
    return extracted


@app.post("/protocols/extract-pdf", response_model=ProtocolExtraction)
async def extract_protocol_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a PDF.")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_PROTOCOL_PDF_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="PDF exceeds the 20MB size limit.")
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        extracted = call_with_retries(extract_protocol_from_pdf, pdf_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Protocol extraction failed: {type(exc).__name__}: {exc}"
        ) from exc
    return extracted


@app.post("/protocols/{protocol_id}")
def save_protocol(protocol_id: str, submission: ProtocolSaveRequest):
    if not SAFE_ID_PATTERN.match(protocol_id):
        raise HTTPException(
            status_code=400,
            detail="protocol_id may only contain letters, digits, '.', '_', and '-'.",
        )

    record = to_storage_format(protocol_id, submission.model_dump())
    protocol_lookup.PROTOCOLS_DIR.mkdir(parents=True, exist_ok=True)
    path = protocol_lookup.PROTOCOLS_DIR / f"{protocol_id}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    return record


@app.get("/reports", response_model=list[TriageResult])
def list_reports():
    return db.list_reports()


@app.get("/reports/{report_id}", response_model=TriageResult)
def get_report(report_id: str):
    record = db.get_report(report_id)
    if record is None:
        raise HTTPException(status_code=404, detail="report not found")
    return record


@app.post("/reports/{report_id}/review", response_model=TriageResult)
def review_report(report_id: str, submission: ReviewSubmission):
    record = db.get_report(report_id)
    if record is None:
        raise HTTPException(status_code=404, detail="report not found")

    fields_to_update = {"memo": submission.memo.model_dump(), "status": submission.status}
    if submission.category and submission.category != record["category"]:
        fields_to_update["category"] = submission.category
        _log_audit(
            report_id,
            "classification_changed",
            f"Reviewer changed classification: {record['category']} -> {submission.category}",
            actor_name=submission.actor_name,
            actor_role=submission.actor_role,
        )
    db.update_report(report_id, fields_to_update)

    _log_audit(
        report_id,
        "reviewed",
        "Approved" if submission.status == "approved" else "Rejected",
        actor_name=submission.actor_name,
        actor_role=submission.actor_role,
    )
    return db.get_report(report_id)


@app.post("/reports/{report_id}/capa-actions", response_model=TriageResult)
def update_capa_actions(report_id: str, submission: CapaActionsUpdate):
    record = db.get_report(report_id)
    if record is None:
        raise HTTPException(status_code=404, detail="report not found")
    fields_to_update = {"capa_actions_status": submission.actions_status}

    completed = sum(1 for done in submission.actions_status if done)
    total = len(submission.actions_status)
    _log_audit(
        report_id,
        "capa_updated",
        f"CAPA actions updated ({completed}/{total} complete)",
        actor_name=submission.actor_name,
        actor_role=submission.actor_role,
    )

    current_capa_status = record.get("capa_status") or "draft"
    if current_capa_status == "approved" and total > 0 and completed == total:
        fields_to_update["capa_status"] = "completed"
        _log_audit(
            report_id,
            "capa_status_changed",
            "CAPA marked completed -- all actions done",
            actor_name=submission.actor_name,
            actor_role=submission.actor_role,
        )

    db.update_report(report_id, fields_to_update)
    return db.get_report(report_id)


@app.post("/reports/{report_id}/capa-status", response_model=TriageResult)
def update_capa_status(report_id: str, submission: CapaStatusUpdate):
    record = db.get_report(report_id)
    if record is None:
        raise HTTPException(status_code=404, detail="report not found")

    current_capa_status = record.get("capa_status") or "draft"
    if CAPA_STATUS_TRANSITIONS.get(current_capa_status) != submission.status:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid CAPA status transition from '{current_capa_status}' to '{submission.status}'.",
        )

    db.update_report(report_id, {"capa_status": submission.status})
    _log_audit(
        report_id,
        "capa_status_changed",
        f"CAPA status changed: {current_capa_status} -> {submission.status}",
        actor_name=submission.actor_name,
        actor_role=submission.actor_role,
    )
    return db.get_report(report_id)


@app.get("/reports/{report_id}/audit", response_model=list[AuditEvent])
def get_audit_trail(report_id: str):
    record = db.get_report(report_id)
    if record is None:
        raise HTTPException(status_code=404, detail="report not found")
    return db.list_audit_events(report_id)


@app.get("/reference", response_model=ReferenceData)
def get_reference_data():
    labels_markdown = LABELS_PATH.read_text(encoding="utf-8")
    with CAPA_GUIDANCE_PATH.open(encoding="utf-8") as f:
        capa_guidance = json.load(f)
    return {"labels_markdown": labels_markdown, "capa_guidance": capa_guidance}


@app.get("/users", response_model=list[UserRecord])
def list_users():
    return db.list_users()


@app.post("/users", response_model=UserRecord)
def create_user(submission: UserCreate):
    return db.insert_user(submission.model_dump())


@app.get("/users/{user_id}", response_model=UserRecord)
def get_user(user_id: str):
    record = db.get_user(user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="user not found")
    return record


@app.put("/users/{user_id}", response_model=UserRecord)
def update_user(user_id: str, submission: UserUpdate):
    record = db.get_user(user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="user not found")
    db.update_user(user_id, submission.model_dump())
    return db.get_user(user_id)


@app.delete("/users/{user_id}")
def delete_user(user_id: str):
    record = db.get_user(user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="user not found")
    if record["role"] == "administrator" and db.count_users_by_role("administrator") <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the last remaining Administrator.",
        )
    db.delete_user(user_id)
    return {"deleted": user_id}


@app.get("/sites", response_model=list[SiteRecord])
def list_sites():
    return db.list_sites()


@app.post("/sites", response_model=SiteRecord)
def create_site(submission: SiteCreate):
    if not SAFE_ID_PATTERN.match(submission.site_id):
        raise HTTPException(
            status_code=400,
            detail="site_id may only contain letters, digits, '.', '_', and '-'.",
        )
    if db.get_site(submission.site_id) is not None:
        raise HTTPException(status_code=400, detail="A site with this site_id already exists.")
    return db.insert_site(submission.model_dump())


@app.get("/sites/{site_id}", response_model=SiteRecord)
def get_site(site_id: str):
    record = db.get_site(site_id)
    if record is None:
        raise HTTPException(status_code=404, detail="site not found")
    return record


@app.put("/sites/{site_id}", response_model=SiteRecord)
def update_site(site_id: str, submission: SiteUpdate):
    record = db.get_site(site_id)
    if record is None:
        raise HTTPException(status_code=404, detail="site not found")
    db.update_site(site_id, submission.model_dump())
    return db.get_site(site_id)


@app.delete("/sites/{site_id}")
def delete_site(site_id: str):
    record = db.get_site(site_id)
    if record is None:
        raise HTTPException(status_code=404, detail="site not found")
    db.delete_site(site_id)
    return {"deleted": site_id}


@app.post("/queue")
def post_to_queue(submission: QueueSubmission):
    record = db.get_report(submission.report_id)
    if record is None:
        raise HTTPException(status_code=404, detail="report not found")
    return deliver_to_queue(record)
