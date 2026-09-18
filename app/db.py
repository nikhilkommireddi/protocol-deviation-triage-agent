"""SQLite persistence for triage state.

Plain stdlib sqlite3 rather than an ORM -- a single table doesn't warrant
the extra dependency, and it keeps this consistent with the project's
existing minimal-dependency convention (see scripts/generate_synthetic_deviations.py).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("triage.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS triage_records (
    report_id TEXT PRIMARY KEY,
    protocol_id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    deviation_date TEXT NOT NULL,
    discovery_date TEXT NOT NULL,
    text TEXT NOT NULL,
    category TEXT,
    confidence REAL,
    protocol_findings TEXT,
    history_findings TEXT,
    adjudication TEXT,
    capa_guidance TEXT,
    memo TEXT,
    verification TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path if db_path is not None else DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | str | None = None) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def insert_report(record: dict, db_path: Path | str | None = None) -> None:
    conn = get_connection(db_path)
    try:
        now = _now()
        conn.execute(
            """
            INSERT INTO triage_records
                (report_id, protocol_id, site_id, subject_id, deviation_date,
                 discovery_date, text, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["report_id"],
                record["protocol_id"],
                record["site_id"],
                record["subject_id"],
                record["deviation_date"],
                record["discovery_date"],
                record["text"],
                record["status"],
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def update_report(report_id: str, fields: dict, db_path: Path | str | None = None) -> None:
    if not fields:
        return
    serializable = {
        k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in fields.items()
    }
    conn = get_connection(db_path)
    try:
        set_clause = ", ".join(f"{k} = ?" for k in serializable)
        values = list(serializable.values()) + [_now(), report_id]
        conn.execute(
            f"UPDATE triage_records SET {set_clause}, updated_at = ? WHERE report_id = ?",
            values,
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("protocol_findings", "history_findings", "adjudication", "capa_guidance", "memo", "verification"):
        if d.get(key):
            d[key] = json.loads(d[key])
    return d


def get_report(report_id: str, db_path: Path | str | None = None) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM triage_records WHERE report_id = ?", (report_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def list_reports(db_path: Path | str | None = None) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM triage_records ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def list_reports_by_site(
    protocol_id: str,
    site_id: str,
    exclude_report_id: str | None = None,
    db_path: Path | str | None = None,
) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT * FROM triage_records
            WHERE protocol_id = ? AND site_id = ? AND report_id != ?
            ORDER BY deviation_date ASC
            """,
            (protocol_id, site_id, exclude_report_id or ""),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()
