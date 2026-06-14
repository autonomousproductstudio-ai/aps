"""System page + Pipeline platform + auth-telemetry endpoints (docs §3.1–3.2, §6, §7).

Process-level facts (uptime, run/evidence/tool counts) come from the shared engine's real
_stats(); everything else is the deterministic mock catalog in mockdata.py. The telemetry
endpoint deliberately increments a counter so the auth page sees "live" growth.
"""
from __future__ import annotations

import itertools

from fastapi import APIRouter, Depends

from aps.api.v1 import engine, mappers, mockdata
from aps.api.v1.auth import current_user
from aps.api.v1.envelope import ok, page_meta

router = APIRouter()

_AGENT_COUNT = 5
_telemetry_tick = itertools.count(0)


def _uptime_sec() -> int:
    try:
        return int(engine.stats().get("uptime_seconds", 0))
    except Exception:
        return 0


def _evidence_total() -> int:
    try:
        return int(engine.stats().get("total_evidence", 0))
    except Exception:
        return 0


# --------------------------------------------------------------------------- #
# §3.1 / §3.2 — pipeline page platform
# --------------------------------------------------------------------------- #
@router.get("/system/status")
def system_status(user=Depends(current_user)):
    return ok({
        "status": "Optimal", "agentCount": _AGENT_COUNT,
        "activeSwarms": 1204, "uptimePct": 99.9992,
        "apiStatus": "Optimal", "version": "4.0.2-STABLE",
    })


@router.get("/agents")
def agents_ready(user=Depends(current_user)):
    return ok([{"id": a["id"], "name": a["name"], "icon": a["icon"], "status": "ready"}
               for a in mockdata.AGENTS])


# --------------------------------------------------------------------------- #
# §6 — system page
# --------------------------------------------------------------------------- #
@router.get("/system/ping")
def system_ping():
    """Cheap, dependency-free liveness for the frontend's high-frequency poll (plan 2.6).

    No auth, no engine touch — kept deliberately trivial so it can never queue behind the
    heavier /system/health (which lists runs and reads the artifact store). This is the
    health/ping lane the plan protects: liveness must stay fast under load."""
    return ok({"ok": True})


@router.get("/system/health")
def system_health(user=Depends(current_user)):
    # Defensive (plan 2.6): a transient artifact-store error must not 500 the health lane —
    # degrade to zeros rather than take liveness reporting down with it.
    try:
        s = engine.stats()
    except Exception:
        s = {}
    runtime = _uptime_sec()
    return ok({
        "agentsActive": "5/5",
        "toolsOnline": "84/84",
        "memoryLoad": "2.4 GB",
        "modelsReady": "4/4",
        "evidenceItems": f"{s.get('total_evidence', 0):,}",
        "runsToday": int(s.get("total_runs", 0)),
        "tokensUsed": int(s.get("total_tool_calls", 0)) * 6400,
        "runtimeSec": runtime,
        "uptimePct": 99.98,
        "systemVersion": "4.0.2-STABLE",
        "statusLabel": "ALL SYSTEMS OPERATIONAL",
        "activeRunId": "—",
    })


@router.get("/system/agents")
def system_agents(user=Depends(current_user)):
    # No specific run → show the fleet against an empty state (all queued/idle vitals).
    from aps.state.models import StudioState
    return ok(mappers.agents(StudioState(idea=""), detailed=True))


@router.get("/system/models")
def system_models(user=Depends(current_user)):
    return ok(mappers.model_cards())   # REAL: provider/model names + live key availability


@router.get("/system/providers")
def system_providers(user=Depends(current_user)):
    # REAL: the multi-provider failover chain + circuit-breaker state + registry availability
    return ok(mappers.system_providers())


@router.get("/system/tools")
def system_tools(user=Depends(current_user)):
    return ok(mockdata.system_tools(engine.tool_names_by_namespace()))


@router.get("/system/memory")
def system_memory(user=Depends(current_user)):
    return ok(mockdata.system_memory(_evidence_total()))


@router.get("/system/knowledge-graph")
def system_kg(user=Depends(current_user)):
    return ok(mockdata.system_knowledge_graph())


@router.get("/system/quality")
def system_quality(user=Depends(current_user)):
    return ok(mockdata.system_quality())


@router.get("/system/cost")
def system_cost(user=Depends(current_user)):
    return ok(mockdata.system_cost())


@router.get("/system/observability")
def system_observability(user=Depends(current_user)):
    return ok(mockdata.system_observability())


@router.get("/system/activity-heatmap")
def system_heatmap(user=Depends(current_user)):
    return ok(mockdata.system_activity_heatmap())


@router.get("/system/events")
def system_events(user=Depends(current_user)):
    # No global event log in the engine; return an empty seed (WS pushes live ones).
    items: list[dict] = []
    return ok(items, **page_meta(items))


# --------------------------------------------------------------------------- #
# §7 — auth-page telemetry (unauthenticated; non-critical)
# --------------------------------------------------------------------------- #
@router.get("/system/telemetry/live")
def telemetry_live():
    tick = next(_telemetry_tick)
    return ok({
        "activeAgents": _AGENT_COUNT,
        "toolsOnline": 84,
        "memoryIndex": 327 + tick,                       # grows slightly each call
        "systemHealth": round(99.94 + (tick % 6) / 100, 2),
    })
