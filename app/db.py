"""SQLite persistence for triage state.

Plain stdlib sqlite3 rather than an ORM -- a single table doesn't warrant
the extra dependency, and it keeps this consistent with the project's
existing minimal-dependency convention (see scripts/generate_synthetic_deviations.py).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
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
    supervisor_plan TEXT,
    protocol_findings TEXT,
    history_findings TEXT,
    adjudication TEXT,
    capa_guidance TEXT,
    memo TEXT,
    verification TEXT,
    capa_actions_status TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

USERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    site_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    description TEXT NOT NULL,
    actor_name TEXT,
    actor_role TEXT,
    details TEXT,
    created_at TEXT NOT NULL
)
"""

SITES_SCHEMA = """
CREATE TABLE IF NOT EXISTS sites (
    site_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    protocol_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
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
        conn.execute(USERS_SCHEMA)
        conn.execute(SITES_SCHEMA)
        conn.execute(AUDIT_SCHEMA)
        conn.commit()
        _seed_defaults_if_empty(conn)
    finally:
        conn.close()


def _seed_defaults_if_empty(conn: sqlite3.Connection) -> None:
    (user_count,) = conn.execute("SELECT COUNT(*) FROM users").fetchone()
    (site_count,) = conn.execute("SELECT COUNT(*) FROM sites").fetchone()
    now = _now()

    if site_count == 0:
        conn.execute(
            "INSERT INTO sites (site_id, name, protocol_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("001", "Example Clinic - Site 001", "PDA-2024-001", "active", now, now),
        )

    if user_count == 0:
        defaults = [
            ("Alex Coordinator", "site_coordinator", "001"),
            ("Jordan CRA", "cra", None),
            ("Sam Reviewer", "quality_reviewer", None),
            ("Taylor Admin", "administrator", None),
        ]
        for name, role, site_id in defaults:
            conn.execute(
                "INSERT INTO users (user_id, name, role, site_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), name, role, site_id, now, now),
            )

    conn.commit()


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
    for key in (
        "supervisor_plan",
        "protocol_findings",
        "history_findings",
        "adjudication",
        "capa_guidance",
        "memo",
        "verification",
        "capa_actions_status",
    ):
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


# --- Users -------------------------------------------------------------------


def insert_user(record: dict, db_path: Path | str | None = None) -> dict:
    conn = get_connection(db_path)
    try:
        now = _now()
        user_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO users (user_id, name, role, site_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, record["name"], record["role"], record.get("site_id"), now, now),
        )
        conn.commit()
        return {**record, "user_id": user_id, "created_at": now, "updated_at": now}
    finally:
        conn.close()


def list_users(db_path: Path | str | None = None) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at ASC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_user(user_id: str, db_path: Path | str | None = None) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def count_users_by_role(role: str, db_path: Path | str | None = None) -> int:
    conn = get_connection(db_path)
    try:
        (count,) = conn.execute("SELECT COUNT(*) FROM users WHERE role = ?", (role,)).fetchone()
        return count
    finally:
        conn.close()


def update_user(user_id: str, fields: dict, db_path: Path | str | None = None) -> None:
    if not fields:
        return
    conn = get_connection(db_path)
    try:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [_now(), user_id]
        conn.execute(f"UPDATE users SET {set_clause}, updated_at = ? WHERE user_id = ?", values)
        conn.commit()
    finally:
        conn.close()


def delete_user(user_id: str, db_path: Path | str | None = None) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


# --- Sites -------------------------------------------------------------------


def insert_site(record: dict, db_path: Path | str | None = None) -> dict:
    conn = get_connection(db_path)
    try:
        now = _now()
        conn.execute(
            "INSERT INTO sites (site_id, name, protocol_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                record["site_id"],
                record["name"],
                record.get("protocol_id"),
                record.get("status", "active"),
                now,
                now,
            ),
        )
        conn.commit()
        return {**record, "status": record.get("status", "active"), "created_at": now, "updated_at": now}
    finally:
        conn.close()


def list_sites(db_path: Path | str | None = None) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT * FROM sites ORDER BY created_at ASC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_site(site_id: str, db_path: Path | str | None = None) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM sites WHERE site_id = ?", (site_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_site(site_id: str, fields: dict, db_path: Path | str | None = None) -> None:
    if not fields:
        return
    conn = get_connection(db_path)
    try:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [_now(), site_id]
        conn.execute(f"UPDATE sites SET {set_clause}, updated_at = ? WHERE site_id = ?", values)
        conn.commit()
    finally:
        conn.close()


def delete_site(site_id: str, db_path: Path | str | None = None) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute("DELETE FROM sites WHERE site_id = ?", (site_id,))
        conn.commit()
    finally:
        conn.close()


# --- Audit trail ---------------------------------------------------------------
# Append-only by construction: no update/delete function is defined for this
# table. Audit history must be immutable from the frontend -- there's simply
# no code path that could change or remove a row once written.


def insert_audit_event(record: dict, db_path: Path | str | None = None) -> dict:
    conn = get_connection(db_path)
    try:
        now = _now()
        event_id = str(uuid.uuid4())
        details = record.get("details")
        conn.execute(
            "INSERT INTO audit_events "
            "(event_id, report_id, event_type, description, actor_name, actor_role, details, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event_id,
                record["report_id"],
                record["event_type"],
                record["description"],
                record.get("actor_name"),
                record.get("actor_role"),
                json.dumps(details) if details is not None else None,
                now,
            ),
        )
        conn.commit()
        return {**record, "event_id": event_id, "created_at": now}
    finally:
        conn.close()


def list_audit_events(report_id: str, db_path: Path | str | None = None) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE report_id = ? ORDER BY created_at ASC",
            (report_id,),
        ).fetchall()
        events = []
        for row in rows:
            d = dict(row)
            if d.get("details"):
                d["details"] = json.loads(d["details"])
            events.append(d)
        return events
    finally:
        conn.close()
