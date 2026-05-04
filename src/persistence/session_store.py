"""SQLite persistence for sessions, datasets, artifacts, and P1 analysis state."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from configs.settings import settings

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = settings.PROJECT_ROOT / "data" / "sessions.db"


def _now() -> str:
    return datetime.now().isoformat()


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _loads(data: str | None, default: Any = None) -> Any:
    if not data:
        return default
    return json.loads(data)


class SessionStore:
    """Small SQLite store used by the local P1 backend.

    The schema mirrors a production relational model closely enough to migrate
    to Postgres later: plans, tasks, evidence, validations, and clarification
    requests are first-class rows instead of opaque artifacts.
    """

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_tables(self) -> None:
        with self._get_conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    turn_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS datasets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    meta_json TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    turn_id TEXT,
                    artifact_type TEXT NOT NULL,
                    content TEXT,
                    file_path TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_plans (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    turn_id TEXT,
                    user_message TEXT NOT NULL,
                    intent_json TEXT NOT NULL,
                    assumptions_json TEXT,
                    expected_outputs_json TEXT,
                    risk_controls_json TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_turns (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_id TEXT,
                    user_message TEXT NOT NULL,
                    status TEXT NOT NULL,
                    plan_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_tasks (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    description TEXT NOT NULL,
                    depends_on_json TEXT,
                    input_datasets_json TEXT,
                    expected_evidence_json TEXT,
                    status TEXT NOT NULL,
                    attempt_count INTEGER DEFAULT 0,
                    result_summary TEXT,
                    failure_reason TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    FOREIGN KEY (plan_id) REFERENCES analysis_plans(id) ON DELETE CASCADE,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_evidence (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    turn_id TEXT,
                    evidence_type TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    code TEXT,
                    stdout TEXT,
                    stderr TEXT,
                    figure_paths_json TEXT,
                    dataset_refs_json TEXT,
                    metric_refs_json TEXT,
                    success INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (plan_id) REFERENCES analysis_plans(id) ON DELETE CASCADE,
                    FOREIGN KEY (task_id) REFERENCES analysis_tasks(id) ON DELETE CASCADE,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_validations (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    task_id TEXT,
                    session_id TEXT NOT NULL,
                    turn_id TEXT,
                    validation_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    checks_json TEXT NOT NULL,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (plan_id) REFERENCES analysis_plans(id) ON DELETE CASCADE,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_audit_events (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    turn_id TEXT,
                    plan_id TEXT,
                    task_id TEXT,
                    actor TEXT,
                    event_type TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,
                    status TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS memory_candidates (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    turn_id TEXT,
                    plan_id TEXT,
                    memory_type TEXT NOT NULL,
                    memory_key TEXT NOT NULL,
                    memory_value_json TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    business_domain TEXT,
                    confidence REAL NOT NULL,
                    status TEXT NOT NULL,
                    source_json TEXT NOT NULL,
                    rationale TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS clarification_requests (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    turn_id TEXT,
                    plan_id TEXT,
                    question TEXT NOT NULL,
                    missing_fields_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
                CREATE INDEX IF NOT EXISTS idx_datasets_session ON datasets(session_id);
                CREATE INDEX IF NOT EXISTS idx_artifacts_session ON artifacts(session_id);
                CREATE INDEX IF NOT EXISTS idx_plans_session ON analysis_plans(session_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_plan ON analysis_tasks(plan_id);
                CREATE INDEX IF NOT EXISTS idx_evidence_plan ON analysis_evidence(plan_id);
                CREATE INDEX IF NOT EXISTS idx_validations_plan ON analysis_validations(plan_id);
                CREATE INDEX IF NOT EXISTS idx_audit_session ON analysis_audit_events(session_id);
                CREATE INDEX IF NOT EXISTS idx_audit_plan ON analysis_audit_events(plan_id);
                CREATE INDEX IF NOT EXISTS idx_clarifications_session ON clarification_requests(session_id);
                """
            )
            self._ensure_columns(conn)
            conn.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_turn ON messages(turn_id);
                CREATE INDEX IF NOT EXISTS idx_turns_session ON analysis_turns(session_id);
                CREATE INDEX IF NOT EXISTS idx_plans_turn ON analysis_plans(turn_id);
                CREATE INDEX IF NOT EXISTS idx_evidence_turn ON analysis_evidence(turn_id);
                CREATE INDEX IF NOT EXISTS idx_validations_turn ON analysis_validations(turn_id);
                CREATE INDEX IF NOT EXISTS idx_audit_turn ON analysis_audit_events(turn_id);
                CREATE INDEX IF NOT EXISTS idx_memory_user ON memory_candidates(user_id);
                CREATE INDEX IF NOT EXISTS idx_memory_turn ON memory_candidates(turn_id);
                """
            )
            conn.commit()

    def _ensure_columns(self, conn: sqlite3.Connection) -> None:
        migrations = {
            "messages": {"turn_id": "TEXT"},
            "artifacts": {"turn_id": "TEXT"},
            "analysis_plans": {"turn_id": "TEXT"},
            "analysis_evidence": {"turn_id": "TEXT"},
            "analysis_validations": {"turn_id": "TEXT"},
            "analysis_audit_events": {"turn_id": "TEXT"},
            "clarification_requests": {"turn_id": "TEXT"},
        }
        for table, columns in migrations.items():
            existing = {
                row["name"]
                for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            for name, column_type in columns.items():
                if name not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}")

    # ---- Session CRUD ----

    def create_session(self, session_id: str, name: str) -> dict:
        now = _now()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sessions (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, name, now, now),
            )
            conn.commit()
        return {"id": session_id, "name": name, "created_at": now, "updated_at": now}

    def list_sessions(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM sessions ORDER BY updated_at DESC").fetchall()
            return [dict(row) for row in rows]

    def get_session(self, session_id: str) -> dict | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            return dict(row) if row else None

    def update_session_name(self, session_id: str, name: str) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE sessions SET name = ?, updated_at = ? WHERE id = ?",
                (name, _now(), session_id),
            )
            conn.commit()

    def delete_session(self, session_id: str) -> None:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()

    def touch_session(self, session_id: str) -> None:
        with self._get_conn() as conn:
            conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (_now(), session_id))
            conn.commit()

    # ---- Turns ----

    def create_turn(self, session_id: str, user_message: str, user_id: str = "") -> str:
        turn_id = str(uuid.uuid4())
        now = _now()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO analysis_turns
                (id, session_id, user_id, user_message, status, plan_ids_json,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (turn_id, session_id, user_id, user_message, "running", _json([]), now, now),
            )
            conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
            conn.commit()
        return turn_id

    def append_turn_plan(self, turn_id: str, plan_id: str) -> None:
        if not turn_id or not plan_id:
            return
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT plan_ids_json FROM analysis_turns WHERE id = ?",
                (turn_id,),
            ).fetchone()
            if not row:
                return
            plan_ids = _loads(row["plan_ids_json"], [])
            if plan_id not in plan_ids:
                plan_ids.append(plan_id)
            conn.execute(
                "UPDATE analysis_turns SET plan_ids_json = ?, updated_at = ? WHERE id = ?",
                (_json(plan_ids), _now(), turn_id),
            )
            conn.commit()

    def update_turn_status(self, turn_id: str, status: str) -> None:
        if not turn_id:
            return
        with self._get_conn() as conn:
            fields = ["status = ?", "updated_at = ?"]
            values: list[Any] = [status, _now()]
            if status in {"completed", "failed"}:
                fields.append("completed_at = ?")
                values.append(_now())
            values.append(turn_id)
            conn.execute(f"UPDATE analysis_turns SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()

    def get_turn(self, turn_id: str) -> dict | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM analysis_turns WHERE id = ?", (turn_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["plan_ids"] = _loads(item.pop("plan_ids_json"), [])
        return item

    # ---- Messages ----

    def add_message(self, session_id: str, role: str, content: str, turn_id: str = "") -> None:
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, turn_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                (session_id, turn_id, role, content, _now()),
            )
            conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (_now(), session_id))
            conn.commit()

    def get_messages(self, session_id: str) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT turn_id, role, content, timestamp FROM messages WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    # ---- Datasets ----

    def save_dataset(self, session_id: str, dataset_meta: dict) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO datasets (session_id, meta_json) VALUES (?, ?)",
                (session_id, _json(dataset_meta)),
            )
            conn.commit()

    def save_datasets(self, session_id: str, datasets: list[dict]) -> None:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM datasets WHERE session_id = ?", (session_id,))
            for ds in datasets:
                conn.execute(
                    "INSERT INTO datasets (session_id, meta_json) VALUES (?, ?)",
                    (session_id, _json(ds)),
                )
            conn.commit()

    def get_datasets(self, session_id: str) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT meta_json FROM datasets WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
            return [_loads(row["meta_json"], {}) for row in rows]

    # ---- Artifacts ----

    def save_artifact(
        self,
        session_id: str,
        artifact_type: str,
        content: str = "",
        file_path: str = "",
        turn_id: str = "",
    ) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO artifacts (session_id, turn_id, artifact_type, content, file_path, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, turn_id, artifact_type, content, file_path, _now()),
            )
            conn.commit()

    def get_artifacts(self, session_id: str, artifact_type: str | None = None) -> list[dict]:
        with self._get_conn() as conn:
            if artifact_type:
                rows = conn.execute(
                    "SELECT * FROM artifacts WHERE session_id = ? AND artifact_type = ? ORDER BY id",
                    (session_id, artifact_type),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM artifacts WHERE session_id = ? ORDER BY id",
                    (session_id,),
                ).fetchall()
            return [dict(row) for row in rows]

    # ---- P1 plans/tasks/evidence/validation ----

    def create_analysis_plan(self, session_id: str, user_message: str, plan: dict) -> str:
        plan_id = plan.get("id") or str(uuid.uuid4())
        now = _now()
        intent = plan.get("intent", {})
        turn_id = plan.get("turn_id", "")
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO analysis_plans
                (id, session_id, turn_id, user_message, intent_json, assumptions_json,
                 expected_outputs_json, risk_controls_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    session_id,
                    turn_id,
                    user_message,
                    _json(intent),
                    _json(plan.get("assumptions", [])),
                    _json(plan.get("expected_outputs", [])),
                    _json(plan.get("risk_controls", [])),
                    plan.get("status", "planned"),
                    now,
                    now,
                ),
            )
            for task in plan.get("tasks", []):
                self._insert_task(conn, session_id, plan_id, task)
            if turn_id:
                row = conn.execute(
                    "SELECT plan_ids_json FROM analysis_turns WHERE id = ?",
                    (turn_id,),
                ).fetchone()
                if row:
                    plan_ids = _loads(row["plan_ids_json"], [])
                    if plan_id not in plan_ids:
                        plan_ids.append(plan_id)
                    conn.execute(
                        "UPDATE analysis_turns SET plan_ids_json = ?, updated_at = ? WHERE id = ?",
                        (_json(plan_ids), now, turn_id),
                    )
            conn.commit()
        return plan_id

    def _insert_task(self, conn: sqlite3.Connection, session_id: str, plan_id: str, task: dict) -> None:
        task_id = task.get("id") or str(uuid.uuid4())
        conn.execute(
            """
            INSERT OR REPLACE INTO analysis_tasks
            (id, plan_id, session_id, agent, description, depends_on_json,
             input_datasets_json, expected_evidence_json, status, attempt_count,
             result_summary, failure_reason, created_at, started_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                plan_id,
                session_id,
                task.get("agent", "chat"),
                task.get("description", ""),
                _json(task.get("depends_on", [])),
                _json(task.get("input_dataset_ids", [])),
                _json(task.get("expected_evidence", [])),
                task.get("status", "pending"),
                task.get("attempt_count", 0),
                task.get("result_summary", ""),
                task.get("failure_reason", ""),
                _now(),
                task.get("started_at"),
                task.get("completed_at"),
            ),
        )

    def add_analysis_task(self, session_id: str, plan_id: str, task: dict) -> str:
        task_id = task.get("id") or str(uuid.uuid4())
        task["id"] = task_id
        with self._get_conn() as conn:
            self._insert_task(conn, session_id, plan_id, task)
            conn.commit()
        return task_id

    def update_plan_status(self, plan_id: str, status: str) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE analysis_plans SET status = ?, updated_at = ? WHERE id = ?",
                (status, _now(), plan_id),
            )
            conn.commit()

    def update_task_status(
        self,
        task_id: str,
        status: str,
        result_summary: str = "",
        failure_reason: str = "",
        attempt_count: int | None = None,
    ) -> None:
        with self._get_conn() as conn:
            fields = ["status = ?", "result_summary = ?", "failure_reason = ?"]
            values: list[Any] = [status, result_summary, failure_reason]
            if status == "running":
                fields.append("started_at = COALESCE(started_at, ?)")
                values.append(_now())
            if status in {"completed", "failed"}:
                fields.append("completed_at = ?")
                values.append(_now())
            if attempt_count is not None:
                fields.append("attempt_count = ?")
                values.append(attempt_count)
            values.append(task_id)
            conn.execute(f"UPDATE analysis_tasks SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()

    def save_evidence(self, session_id: str, plan_id: str, task_id: str, evidence: dict) -> str:
        evidence_id = evidence.get("id") or str(uuid.uuid4())
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO analysis_evidence
                (id, plan_id, task_id, session_id, turn_id, evidence_type, content_json, code,
                 stdout, stderr, figure_paths_json, dataset_refs_json, metric_refs_json,
                 success, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    plan_id,
                    task_id,
                    session_id,
                    evidence.get("turn_id", ""),
                    evidence.get("evidence_type", "unknown"),
                    _json(evidence.get("content", {})),
                    evidence.get("code", ""),
                    evidence.get("stdout", ""),
                    evidence.get("stderr", ""),
                    _json(evidence.get("figure_paths", [])),
                    _json(evidence.get("dataset_refs", [])),
                    _json(evidence.get("metric_refs", {})),
                    1 if evidence.get("success", False) else 0,
                    _now(),
                ),
            )
            conn.commit()
        return evidence_id

    def list_evidence(self, plan_id: str) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM analysis_evidence WHERE plan_id = ? ORDER BY created_at",
                (plan_id,),
            ).fetchall()
        evidence = []
        for row in rows:
            item = dict(row)
            item["content"] = _loads(item.pop("content_json"), {})
            item["figure_paths"] = _loads(item.pop("figure_paths_json"), [])
            item["dataset_refs"] = _loads(item.pop("dataset_refs_json"), [])
            item["metric_refs"] = _loads(item.pop("metric_refs_json"), {})
            item["success"] = bool(item["success"])
            evidence.append(item)
        return evidence

    def save_validation(
        self,
        session_id: str,
        plan_id: str,
        task_id: str | None,
        validation: dict,
    ) -> str:
        validation_id = validation.get("id") or str(uuid.uuid4())
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO analysis_validations
                (id, plan_id, task_id, session_id, turn_id, validation_type, status,
                 checks_json, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    validation_id,
                    plan_id,
                    task_id,
                    session_id,
                    validation.get("turn_id", ""),
                    validation.get("validation_type", "unknown"),
                    validation.get("status", "failed"),
                    _json(validation.get("checks", [])),
                    validation.get("error_message", ""),
                    _now(),
                ),
            )
            conn.commit()
        return validation_id

    def save_audit_event(
        self,
        session_id: str,
        event_type: str,
        resource_type: str,
        status: str,
        details: dict[str, Any] | None = None,
        plan_id: str | None = None,
        task_id: str | None = None,
        turn_id: str = "",
        actor: str = "",
        resource_id: str = "",
    ) -> str:
        event_id = str(uuid.uuid4())
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO analysis_audit_events
                (id, session_id, turn_id, plan_id, task_id, actor, event_type, resource_type,
                 resource_id, status, details_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    session_id,
                    turn_id,
                    plan_id,
                    task_id,
                    actor,
                    event_type,
                    resource_type,
                    resource_id,
                    status,
                    _json(details or {}),
                    _now(),
                ),
            )
            conn.commit()
        return event_id

    def list_audit_events(
        self,
        session_id: str | None = None,
        plan_id: str | None = None,
        turn_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        query = "SELECT * FROM analysis_audit_events"
        clauses = []
        values: list[Any] = []
        if session_id:
            clauses.append("session_id = ?")
            values.append(session_id)
        if plan_id:
            clauses.append("plan_id = ?")
            values.append(plan_id)
        if turn_id:
            clauses.append("turn_id = ?")
            values.append(turn_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC LIMIT ?"
        values.append(limit)

        with self._get_conn() as conn:
            rows = conn.execute(query, values).fetchall()
        events = []
        for row in rows:
            item = dict(row)
            item["details"] = _loads(item.pop("details_json"), {})
            events.append(item)
        return events

    def create_clarification(
        self,
        session_id: str,
        question: str,
        missing_fields: list[str],
        plan_id: str | None = None,
        turn_id: str = "",
    ) -> str:
        clarification_id = str(uuid.uuid4())
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO clarification_requests
                (id, session_id, turn_id, plan_id, question, missing_fields_json, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clarification_id,
                    session_id,
                    turn_id,
                    plan_id,
                    question,
                    _json(missing_fields),
                    "open",
                    _now(),
                ),
            )
            conn.commit()
        return clarification_id

    def save_memory_candidate(self, candidate: dict[str, Any]) -> str:
        candidate_id = candidate.get("id") or str(uuid.uuid4())
        now = _now()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO memory_candidates
                (id, user_id, session_id, turn_id, plan_id, memory_type, memory_key,
                 memory_value_json, scope, business_domain, confidence, status,
                 source_json, rationale, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    candidate.get("user_id", "anonymous"),
                    candidate.get("session_id", ""),
                    candidate.get("turn_id", ""),
                    candidate.get("plan_id", ""),
                    candidate.get("memory_type", "user_preference"),
                    candidate.get("memory_key", ""),
                    _json(candidate.get("memory_value", {})),
                    candidate.get("scope", "user"),
                    candidate.get("business_domain", ""),
                    float(candidate.get("confidence", 0.0)),
                    candidate.get("status", "candidate"),
                    _json(candidate.get("source", {})),
                    candidate.get("rationale", ""),
                    now,
                    now,
                ),
            )
            conn.commit()
        return candidate_id

    def list_memory_candidates(
        self,
        user_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        query = "SELECT * FROM memory_candidates"
        clauses = []
        values: list[Any] = []
        if user_id:
            clauses.append("user_id = ?")
            values.append(user_id)
        if status:
            clauses.append("status = ?")
            values.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC LIMIT ?"
        values.append(limit)
        with self._get_conn() as conn:
            rows = conn.execute(query, values).fetchall()
        candidates = []
        for row in rows:
            item = dict(row)
            item["memory_value"] = _loads(item.pop("memory_value_json"), {})
            item["source"] = _loads(item.pop("source_json"), {})
            candidates.append(item)
        return candidates
