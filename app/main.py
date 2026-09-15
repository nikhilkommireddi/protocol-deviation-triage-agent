from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import db
from app.graph import deliver_to_queue, graph
from app.pdf_extract import extract_from_pdf
from app.schemas import DeviationSubmission, ExtractedFields, ReviewSubmission, TriageResult

MAX_PDF_SIZE_BYTES = 10 * 1024 * 1024


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
    }
    result_state = graph.invoke(initial_state)
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
        extracted = extract_from_pdf(pdf_bytes)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"PDF extraction failed: {exc}") from exc
    return extracted


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
    db.update_report(report_id, {"memo": submission.memo.model_dump(), "status": submission.status})
    return db.get_report(report_id)


@app.post("/queue")
def post_to_queue(submission: QueueSubmission):
    record = db.get_report(submission.report_id)
    if record is None:
        raise HTTPException(status_code=404, detail="report not found")
    return deliver_to_queue(record)
