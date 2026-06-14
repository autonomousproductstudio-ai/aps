"""Per-user run History — the personal archive behind the History page.

Three endpoints, all JWT-protected and scoped to the authenticated user (by email):
    GET /history          → the user's runs (cards), newest first
    GET /history/stats     → aggregate counters for the animated header
    GET /history/{alias}   → one run's full detail (overview · scores · artifacts · timeline)

History rows are written by the run engine (record_start/record_completion); these routes only
read. Aliases are re-ensured against the in-process idmap on listing so a stored run still
resolves through the existing /v1/runs/* endpoints after a restart (state is reloaded from disk).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from aps.api.v1 import engine, idmap, mappers
from aps.api.v1.auth import current_user
from aps.api.v1.envelope import V1Error, ok, page_meta
from aps.infra import history_store

router = APIRouter()


def _email(user: dict) -> str:
    return (user.get("email") or "").strip().lower()


@router.get("/history")
def list_history(user=Depends(current_user)):
    """Every startup this user has generated, newest first. Each card's `runId` is guaranteed to
    resolve through the existing run endpoints (alias re-minted into idmap if the process restarted)."""
    rows = history_store.list_for_user(_email(user))
    for r in rows:
        bid = r.get("backendId")
        if bid:
            r["runId"] = idmap.alias_for(bid)  # ensure the alias resolves this process
    return ok(rows, **page_meta(rows))


@router.get("/history/stats")
def history_stats(user=Depends(current_user)):
    return ok(history_store.stats_for_user(_email(user)))


@router.get("/history/{alias}")
def history_detail(alias: str, user=Depends(current_user)):
    """Consolidated detail for one archived run. Ownership-checked: a user can only open a run
    that lives in their own history."""
    bid = idmap.backend_id(alias)
    row = history_store.get(bid) if bid else None
    if row is None or (row.get("userEmail") or "") != _email(user):
        raise V1Error("RUN_NOT_FOUND", "Run is not in your history.", status=404)

    overview = {
        "runId": alias, "name": row["name"], "idea": row["idea"], "status": row["status"],
        "score": row["score"], "provider": row["provider"], "model": row["model"],
        "createdAt": row["createdAt"], "completedAt": row["completedAt"],
        "durationSec": row["durationSec"], "toolCalls": row["toolCalls"],
        "evidenceCount": row["evidenceCount"], "agentCount": row["agentCount"],
        "artifactCount": row["artifactCount"],
    }

    scores = None
    artifacts: list = []
    st = engine.state_for(alias)
    if st is not None:
        try:
            scores = mappers.viability(st)
        except Exception:
            scores = None
        try:
            artifacts = mappers.artifacts_list(st, detail=True)
        except Exception:
            artifacts = []

    # Prefer the persisted timeline (survives restart); fall back to the live event bus.
    timeline = row.get("timeline") or []
    if not timeline:
        try:
            timeline = mappers.stream_events(engine.bus_history(alias), limit=200)
        except Exception:
            timeline = []

    return ok({"overview": overview, "scores": scores,
               "artifacts": artifacts, "timeline": timeline})
