"""Per-user run history — a small, durable SQLite store (stdlib only).

Why a real database (not the JSON artifact store): the History page is a *personal archive*.
Each signed-in user must see only their own past startups, fast, and that survives process
restarts and redeploys. SQLite gives us indexed per-user queries + aggregate stats with zero
new dependencies and a single portable file (deploy-friendly; swap the DSN for Postgres later).

Design notes:
  * This layer is deliberately dumb — pure SQL over plain dicts. All app-specific extraction
    (score, counts, timeline) happens in the caller (aps.api.main) and is handed in as a dict,
    so this module imports nothing from the orchestrator and can never cause an import cycle.
  * Every public function is best-effort and self-contained: callers wrap them in try/except so
    history bookkeeping can NEVER break or slow a real run.
  * Identity key is the user's email (lowercased) — stable across the demo JWT and Firebase
    Google sign-in (both carry an email), so "sign in with my Gmail → see my history" holds.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_CONN: sqlite3.Connection | None = None

_COLUMNS = (
    "run_id", "alias", "user_email", "user_id", "name", "idea", "status", "score",
    "provider", "model", "artifacts", "artifact_count", "tool_calls", "evidence_count",
    "agent_count", "duration_sec", "created_at", "completed_at", "timeline",
)


def _db_path() -> Path:
    raw = os.getenv("APS_HISTORY_DB")
    if raw:
        return Path(raw)
    base = Path(os.getenv("APS_ARTIFACT_DIR", ".artifacts"))
    base.mkdir(parents=True, exist_ok=True)
    return base / "history.db"


def _conn() -> sqlite3.Connection:
    global _CONN
    if _CONN is None:
        c = sqlite3.connect(str(_db_path()), check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id         TEXT PRIMARY KEY,
                alias          TEXT,
                user_email     TEXT,
                user_id        TEXT,
                name           TEXT,
                idea           TEXT,
                status         TEXT,
                score          REAL,
                provider       TEXT,
                model          TEXT,
                artifacts      TEXT,
                artifact_count INTEGER DEFAULT 0,
                tool_calls     INTEGER DEFAULT 0,
                evidence_count INTEGER DEFAULT 0,
                agent_count    INTEGER DEFAULT 0,
                duration_sec   REAL,
                created_at     TEXT,
                completed_at   TEXT,
                timeline       TEXT
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_runs_user ON runs(user_email)")
        c.commit()
        _CONN = c
    return _CONN


def record_start(run_id: str, *, alias: str | None, user_email: str | None,
                 user_id: str | None, idea: str, provider: str | None,
                 model: str | None, created_at: str) -> None:
    """Insert a fresh row the moment a user-initiated run is admitted (status = running).

    Runs with no user (the lean root API path) simply never call this, so they never appear in
    anyone's history — exactly the intended per-user scoping.
    """
    email = (user_email or "").strip().lower() or None
    with _LOCK:
        c = _conn()
        c.execute(
            """
            INSERT INTO runs (run_id, alias, user_email, user_id, name, idea, status,
                              provider, model, artifacts, artifact_count, tool_calls,
                              evidence_count, agent_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?, '[]', 0, 0, 0, 0, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                alias=excluded.alias, user_email=excluded.user_email,
                user_id=excluded.user_id, idea=excluded.idea
            """,
            (run_id, alias, email, user_id, (idea or "")[:120], idea, provider, model, created_at),
        )
        c.commit()


def record_completion(run_id: str, summary: dict[str, Any]) -> None:
    """Update a run's row with final results (status, score, counts, timeline, duration).

    No-op if no row exists (i.e. the run wasn't user-initiated). `summary` is a plain dict built
    by the caller; recognized keys mirror the column names plus `name`, `artifacts` (list),
    `timeline` (list). duration_sec is computed here from created_at → completed_at when absent.
    """
    with _LOCK:
        c = _conn()
        row = c.execute("SELECT created_at FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            return  # not a tracked (user) run
        artifacts = summary.get("artifacts") or []
        timeline = summary.get("timeline") or []
        completed_at = summary.get("completed_at")
        duration = summary.get("duration_sec")
        if duration is None and completed_at and row["created_at"]:
            duration = _elapsed(row["created_at"], completed_at)
        c.execute(
            """
            UPDATE runs SET
                name=COALESCE(?, name), status=?, score=?, artifacts=?, artifact_count=?,
                tool_calls=?, evidence_count=?, agent_count=?, duration_sec=?,
                completed_at=?, timeline=?
            WHERE run_id=?
            """,
            (
                summary.get("name"), summary.get("status"), summary.get("score"),
                json.dumps(artifacts), len(artifacts), summary.get("tool_calls", 0),
                summary.get("evidence_count", 0), summary.get("agent_count", 0),
                duration, completed_at, json.dumps(timeline), run_id,
            ),
        )
        c.commit()


def mark_status(run_id: str, status: str, *, completed_at: str | None = None) -> None:
    """Best-effort status flip (e.g. a run that threw before producing state → 'failed')."""
    with _LOCK:
        c = _conn()
        if c.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone() is None:
            return
        c.execute("UPDATE runs SET status=?, completed_at=COALESCE(?, completed_at) WHERE run_id=?",
                  (status, completed_at, run_id))
        c.commit()


def list_for_user(user_email: str) -> list[dict]:
    """All of a user's runs, newest first."""
    email = (user_email or "").strip().lower()
    if not email:
        return []
    with _LOCK:
        c = _conn()
        rows = c.execute(
            "SELECT * FROM runs WHERE user_email=? ORDER BY created_at DESC", (email,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def stats_for_user(user_email: str) -> dict:
    """Aggregate counters powering the animated header stats."""
    runs = list_for_user(user_email)
    scored = [r["score"] for r in runs if isinstance(r.get("score"), (int, float)) and r["score"]]
    successful = sum(1 for r in runs if r.get("status") in ("complete", "degraded"))
    return {
        "totalStartups": len(runs),
        "successful": successful,
        "avgScore": round(sum(scored) / len(scored), 1) if scored else 0.0,
        "totalSources": sum(int(r.get("evidenceCount") or 0) for r in runs),
        "totalArtifacts": sum(int(r.get("artifactCount") or 0) for r in runs),
        "totalToolCalls": sum(int(r.get("toolCalls") or 0) for r in runs),
    }


def get(run_id: str) -> dict | None:
    with _LOCK:
        c = _conn()
        r = c.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    return _row_to_dict(r) if r else None


def owner_email(run_id: str) -> str | None:
    row = get(run_id)
    return row.get("userEmail") if row else None


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _row_to_dict(r: sqlite3.Row) -> dict:
    """SQLite row → camelCase frontend card."""
    return {
        "runId": r["alias"] or r["run_id"],
        "backendId": r["run_id"],
        "userEmail": r["user_email"],
        "name": r["name"] or (r["idea"] or "")[:120],
        "idea": r["idea"],
        "status": r["status"],
        "score": r["score"],
        "provider": r["provider"],
        "model": r["model"],
        "artifacts": _loads(r["artifacts"], []),
        "artifactCount": r["artifact_count"] or 0,
        "toolCalls": r["tool_calls"] or 0,
        "evidenceCount": r["evidence_count"] or 0,
        "agentCount": r["agent_count"] or 0,
        "durationSec": r["duration_sec"],
        "createdAt": r["created_at"],
        "completedAt": r["completed_at"],
        "timeline": _loads(r["timeline"], []),
    }


def _loads(raw: Any, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _elapsed(start_iso: str, end_iso: str) -> float | None:
    from datetime import datetime
    try:
        a = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        b = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
        return round((b - a).total_seconds(), 1)
    except Exception:
        return None
