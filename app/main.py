from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import db
from app.graph import deliver_to_queue, graph
from app.schemas import DeviationSubmission, TriageResult


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Protocol Deviation Triage Agent", lifespan=lifespan)


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


@app.get("/reports", response_model=list[TriageResult])
def list_reports():
    return db.list_reports()


@app.get("/reports/{report_id}", response_model=TriageResult)
def get_report(report_id: str):
    record = db.get_report(report_id)
    if record is None:
        raise HTTPException(status_code=404, detail="report not found")
    return record


@app.post("/queue")
def post_to_queue(submission: QueueSubmission):
    record = db.get_report(submission.report_id)
    if record is None:
        raise HTTPException(status_code=404, detail="report not found")
    return deliver_to_queue(record)
