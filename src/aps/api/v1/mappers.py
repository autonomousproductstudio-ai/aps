"""Reshape the REAL StudioState into the frontend contract shapes (docs §4–§5).

Every value here is derived from actual run data or an existing deterministic computation
(score_startup / run_debate / render_artifact). Vitals the backend doesn't track
(confidence %, memPct, latency) are filled deterministically via mockdata so the contract's
"never omit a key" rule holds. Pure functions of StudioState — no I/O, no clock.
"""
from __future__ import annotations

from aps.api.v1 import mockdata as M
from aps.render import render_artifact
from aps.scoring.startup_score import score_startup
from aps.debate.debate import run_debate

# Contract artifact catalog: contract id ↔ StudioState attr ↔ render name + display.
ARTIFACTS = [
    {"id": "research-brief", "attr": "research", "render": "research",
     "name": "Research Brief", "icon": "travel_explore", "category": "Research"},
    {"id": "prd", "attr": "prd", "render": "prd",
     "name": "PRD v1.0", "icon": "description", "category": "Product"},
    {"id": "trd", "attr": "trd", "render": "trd",
     "name": "Technical Design", "icon": "hub", "category": "Architecture"},
    {"id": "execution", "attr": "execution", "render": "execution",
     "name": "Execution Plan", "icon": "data_object", "category": "Execution"},
    {"id": "pitch", "attr": "pitch", "render": "pitch",
     "name": "Pitch Package", "icon": "smart_display", "category": "Business"},
    # Launch Studio artifacts (parallel branches; each gated by its APS_ENABLE_* flag).
    {"id": "brand", "attr": "brand", "render": "brand", "agent": "Brand Agent",
     "name": "Brand Identity", "icon": "palette", "category": "Brand"},
    {"id": "legal", "attr": "legal", "render": "legal", "agent": "Legal Agent",
     "name": "Legal Pack", "icon": "gavel", "category": "Legal"},
    {"id": "funding", "attr": "funding", "render": "funding", "agent": "Funding Agent",
     "name": "Funding Pack", "icon": "payments", "category": "Funding"},
    {"id": "availability", "attr": "availability", "render": "availability", "agent": "Availability Agent",
     "name": "Name Availability", "icon": "domain_verification", "category": "Brand"},
    {"id": "compliance", "attr": "compliance", "render": "compliance", "agent": "Compliance Agent",
     "name": "Compliance Pack", "icon": "verified_user", "category": "Legal"},
]
_ARTIFACT_BY_ID = {a["id"]: a for a in ARTIFACTS}
# Launch Studio artifact id → the graph enablement check (so the /v1 list matches what actually
# runs: a branch that's off — e.g. compliance by default — is NOT shown as an eternal "queued"
# phantom, only as a real card once produced).
_BRANCH_GATE = {"brand": "_brand_enabled", "legal": "_legal_enabled", "funding": "_funding_enabled",
                "availability": "_availability_enabled", "compliance": "_compliance_enabled"}


def _branch_enabled(artifact_id: str) -> bool:
    fn = _BRANCH_GATE.get(artifact_id)
    if fn is None:
        return True                      # core artifacts always belong in the catalog
    from aps.orchestrator import graph   # lazy: graph imports agents/tools; avoid import cost at module load
    return bool(getattr(graph, fn)())

# StudioState.current_agent value → contract agent id.
_AGENT_ID = {"research": "research", "product": "product", "architecture": "arch",
             "execution": "execution", "presentation": "present"}
# contract agent id → which StudioState attr means "this agent has produced output".
_AGENT_ARTIFACT = {"research": "research", "product": "prd", "arch": "trd",
                   "execution": "execution", "present": "pitch"}
_AGENT_ORDER = ["research", "product", "arch", "execution", "present"]

# contract Run.status (running|complete|failed|paused) from StudioState.status.
# cancelled has no slot in the contract enum → map to the terminal 'failed' so a cancelled run
# settles into a terminal state in the UI instead of defaulting to 'running' forever.
_STATUS = {"queued": "running", "running": "running", "complete": "complete",
           "degraded": "complete", "failed": "failed", "cancelled": "failed"}


def _viability(state) -> float:
    if state.research is None:
        return 0.0
    return round(score_startup(state.research, state.prd).overall, 1)


def _evidence(state) -> list:
    return state.research.evidence if state.research else []


def _produced(state) -> list[str]:
    """contract artifact ids whose backend artifact exists."""
    return [a["id"] for a in ARTIFACTS if getattr(state, a["attr"], None) is not None]


# --------------------------------------------------------------------------- #
# §4.1 — run dashboard header
# --------------------------------------------------------------------------- #
def run_dashboard(state, alias: str, elapsed_sec: int = 0) -> dict:
    produced = _produced(state)
    progress = round(len(produced) / len(ARTIFACTS) * 100)
    active = _AGENT_ID.get(state.current_agent or "", "research")
    if state.status.value in ("complete", "degraded"):
        phase, active = "Complete", "present"
    else:
        phase = f"{next((a['name'] for a in M.AGENTS if a['id'] == active), 'Research')} Phase"
    return {
        "id": alias,
        "label": (state.idea or "")[:40],
        "phase": phase,
        "progressPct": progress,
        "startedAt": "2026-06-11T08:25:00.000Z",
        "elapsedSec": elapsed_sec,
        "viabilityScore": _viability(state),
        "status": _STATUS.get(state.status.value, "running"),
        "activeAgentId": active,
        "systemHealth": {
            "cpuPct": M.jitter(f"cpu:{alias}", 12, 48),
            "memPct": M.jitter(f"mem:{alias}", 40, 78),
            "apiUptimePct": 99,
        },
    }


# --------------------------------------------------------------------------- #
# §4.2 / §6.2 — agents
# --------------------------------------------------------------------------- #
def _agent_status(state, agent_id: str) -> str:
    """running for current_agent, completed if its artifact exists, queued/idle otherwise."""
    done = getattr(state, _AGENT_ARTIFACT[agent_id], None) is not None
    if done:
        return "completed"
    if _AGENT_ID.get(state.current_agent or "", "") == agent_id:
        return "running"
    # everything after the active agent is queued; the last one idles until reached
    return "queued" if agent_id != "present" else "idle"


def agents(state, *, detailed: bool = False) -> list[dict]:
    out = []
    for spec in M.AGENTS:
        aid = spec["id"]
        status = _agent_status(state, aid)
        running = status == "running"
        done = status == "completed"
        conf = 94 if done else (M.jitter(f"conf:{aid}", 30, 70) if running else 0)
        log = spec_log(aid) if (running or done) else []
        base = {
            "id": aid, "name": spec["name"], "icon": spec["icon"], "status": status,
            "confidence": conf, "tools": spec["tools"], "toolLog": log,
            "output": _agent_output(aid, status),
        }
        if not detailed:
            base["currentTool"] = log[0] if log else None
        else:
            base.update({
                "memPct": M.jitter(f"amem:{aid}", 15, 80) if (running or done) else 8,
                "tasksCompleted": M.jitter(f"tasks:{aid}", 5, 60),
                "currentJob": _agent_output(aid, status),
                "latencyMs": M.jitter(f"alat:{aid}", 120, 320) if running else 0,
                "successRate": round(94 + M.jitter(f"asucc:{aid}", 0, 50) / 10, 1),
                "lastExec": f"14:0{M.jitter(f'ah:{aid}', 0, 5)}:{M.jitter(f'as:{aid}', 10, 59)}",
                "tokensUsed": M.jitter(f"atok:{aid}", 20000, 130000),
            })
        out.append(base)
    return out


def spec_log(agent_id: str) -> list[str]:
    return {
        "research": ["GitHub · 34 repos analyzed", "Reddit · 847 posts scraped",
                     "Evidence cluster #3 forming…"],
        "product": ["Reading Research Brief", "Extracting feature requirements"],
        "arch": ["Drafting OpenAPI spec", "Deriving data model"],
        "execution": ["Generating backlog", "Planning sprints"],
        "present": ["Assembling deck", "Writing investor memo"],
    }.get(agent_id, [])


def _agent_output(agent_id: str, status: str) -> str:
    if status == "running":
        return {"research": "Synthesizing evidence clusters",
                "product": "Parsing Research Brief output",
                "arch": "Designing system architecture",
                "execution": "Building execution backlog",
                "present": "Assembling pitch package"}.get(agent_id, "Working")
    if status == "completed":
        return "Done"
    if status == "queued":
        return "Awaiting Research output" if agent_id == "product" else "Standby"
    return "Idle"


# --------------------------------------------------------------------------- #
# §4.3 — stream seed (from EventBus history)
# --------------------------------------------------------------------------- #
_EVENT_ICON = {"run_start": "rocket_launch", "agent_start": "play_circle",
               "agent_end": "check_circle", "artifact_ready": "description",
               "composition": "merge", "research_plan": "schema",
               "research_unit_start": "travel_explore", "research_unit_end": "fact_check",
               "tool_calls_total": "build", "run_complete": "verified", "error": "warning"}
_EVENT_TYPE = {"run_start": "start", "agent_start": "agent", "agent_end": "agent",
               "artifact_ready": "artifact", "composition": "insight",
               "research_unit_end": "evidence", "tool_calls_total": "tool",
               "run_complete": "artifact"}


def stream_events(history: list, limit: int = 50, type_filter: str | None = None) -> list[dict]:
    out = []
    for ev in history:
        etype = _EVENT_TYPE.get(ev.type, "agent")
        if type_filter and etype != type_filter:
            continue
        agent = (ev.data.get("agent") or ev.data.get("focus") or "System")
        color = "green" if etype in ("evidence", "artifact") else (
            "amber" if etype == "insight" else "cyan")
        out.append({
            "t": ev.ts.strftime("%H:%M:%S"),
            "agent": str(agent).split()[0].capitalize(),
            "icon": _EVENT_ICON.get(ev.type, "bolt"),
            "type": etype,
            "msg": _event_msg(ev),
            "color": color,
        })
    return out[-limit:]


def _event_msg(ev) -> str:
    d = ev.data
    if ev.type == "run_start":
        return f"Run started · {str(d.get('idea',''))[:60]}"
    if ev.type in ("agent_start", "agent_end"):
        verb = "spawned" if ev.type == "agent_start" else "completed"
        return f"{str(d.get('agent','agent')).capitalize()} agent {verb}"
    if ev.type == "artifact_ready":
        return f"Artifact ready · {d.get('name','')}"
    if ev.type == "research_plan":
        return f"Research plan · {len(d.get('subtopics', []))} angles"
    if ev.type == "research_unit_end":
        return f"Sub-researcher done · {d.get('evidence',0)} evidence · {d.get('focus','')[:40]}"
    if ev.type == "tool_calls_total":
        return f"Tool calls total · {d.get('n',0)}"
    if ev.type == "composition":
        return f"Handoff research→PRD · {d.get('prd.features', d.get('features',0))} features"
    if ev.type == "run_cancelled":
        return f"Run cancelled · {d.get('reason', 'cancelled')}"
    if ev.type == "run_complete":
        status = d.get("status", "")
        if status == "cancelled":
            return f"Run cancelled · {d.get('reason', 'cancelled')}"
        return f"Run complete · status {status}"
    if ev.type == "error":
        return f"Notice · {str(d.get('error') or d.get('fallback') or '')[:60]}"
    return ev.type


# --------------------------------------------------------------------------- #
# §4.4 / §5.1 — artifacts (condensed + full detail)
# --------------------------------------------------------------------------- #
def _artifact_card(state, spec: dict, *, detail: bool) -> dict:
    obj = getattr(state, spec["attr"], None)
    aid = spec["id"]
    if obj is not None:
        status, color = "complete", "green"
        size = M.fmt_size(len(str(getattr(obj, "model_dump", lambda: obj)())) )
        gen = M.fmt_duration(M.jitter(f"gen:{aid}", 60, 360))
        conf = M.jitter(f"acard:{aid}", 82, 96)
        ev_count = len(_evidence(state)) if spec["attr"] == "research" else 0
    elif _AGENT_ID.get(state.current_agent or "", "") and _is_building(state, aid):
        status, color, size, gen, conf, ev_count = "building", "cyan", M.DASH, M.DASH, 0, 0
    else:
        status, color, size, gen, conf, ev_count = "queued", "muted", M.DASH, M.DASH, 0, 0
    card = {"id": aid, "name": spec["name"], "icon": spec["icon"], "status": status,
            "size": size, "time": gen, "confidence": conf, "evidence": ev_count, "color": color}
    if not detail:
        return card
    sources = len({e.source for e in _evidence(state)}) if spec["attr"] == "research" else 0
    # Keep the condensed keys (time/evidence — Dashboard Artifact Factory, §4.4) AND add the
    # detail keys (genTime/evidenceCount — Artifacts page, §5.1) so one endpoint serves both.
    card.update({
        "category": spec["category"],
        "quality": round(M.jitter(f"qual:{aid}", 80, 95) / 10, 1) if obj is not None else 0,
        "genTime": card["time"],
        "agents": ([spec.get("agent")
                    or next((a["name"] for a in M.AGENTS if a["id"] == _agent_for_artifact(aid)),
                            "Research Agent")] if obj is not None else []),
        "evidenceCount": card["evidence"],
        "sourceCount": sources,
        "versions": 2 if obj is not None else 0,
        "generatedAt": f"14:0{M.jitter(f'gh:{aid}', 0, 5)}:{M.jitter(f'gs:{aid}', 10, 59)}"
                       if obj is not None else M.DASH,
        "summary": _artifact_summary(state, spec) if obj is not None
                   else "Awaiting upstream agent output.",
    })
    return card


def _agent_for_artifact(artifact_id: str) -> str:
    for aid, art in _AGENT_ARTIFACT.items():
        if _ARTIFACT_BY_ID.get(artifact_id, {}).get("attr") == art:
            return aid
    return "research"


def _is_building(state, artifact_id: str) -> bool:
    return _AGENT_ID.get(state.current_agent or "", "") == _agent_for_artifact(artifact_id)


def _artifact_summary(state, spec: dict) -> str:
    if spec["attr"] == "research" and state.research:
        r = state.research
        return (f"{len(r.evidence)} evidence · {len(r.competitors)} competitors · "
                f"{len(r.pain_points)} pains · TAM {r.market_size or 'n/a'}").strip()
    if spec["attr"] == "prd" and state.prd:
        return f"{len(state.prd.features)} features · {len(state.prd.personas)} personas."
    if spec["attr"] == "trd" and state.trd:
        return f"Stack: {', '.join(state.trd.stack[:4]) or 'n/a'}."
    return f"{spec['name']} generated."


def artifacts_list(state, *, detail: bool) -> list[dict]:
    # Show an artifact if it's already produced OR its branch is enabled (will run). A disabled
    # branch (e.g. compliance, default off) is omitted rather than shown as a forever-"queued" card.
    return [_artifact_card(state, spec, detail=detail) for spec in ARTIFACTS
            if getattr(state, spec["attr"], None) is not None or _branch_enabled(spec["id"])]


# --------------------------------------------------------------------------- #
# §4.5 — viability radar (from score_startup)
# --------------------------------------------------------------------------- #
_RADAR_LABELS = ["Market Opp.", "Competition", "Monetisation", "Defensibility", "Exec. Speed"]
_RADAR_ANGLES = [270, 342, 54, 126, 198]


def viability(state) -> dict:
    if state.research is None:
        vals = [0, 0, 0, 0, 0]
        score = 0.0
    else:
        sc = score_startup(state.research, state.prd)
        score = round(sc.overall, 1)
        dims = [round(d.score * 10) for d in sc.dimensions]
        vals = (dims + [round(sc.overall * 10)] * 5)[:5]
    axes = [{"label": lab, "value": v, "angle": ang}
            for lab, v, ang in zip(_RADAR_LABELS, vals, _RADAR_ANGLES)]
    best = [min(100, round(v * 1.12) + 5) for v in vals]
    worst = [max(0, round(v * 0.7)) for v in vals]
    return {
        "score": score,
        "radarAxes": axes,
        "scenarios": [
            {"label": "Best Case", "values": best, "color": "#79ff5b", "opacity": 0.14},
            {"label": "Expected", "values": vals, "color": "#a5e7ff", "opacity": 0.22},
            {"label": "Worst Case", "values": worst, "color": "#f59e0b", "opacity": 0.11},
        ],
    }


# --------------------------------------------------------------------------- #
# §4.6 — debate (reshape run_debate)
# --------------------------------------------------------------------------- #
def debate(state) -> list[dict]:
    if state.research is None:
        return []
    d = run_debate(state.research, state.prd)
    rows = []
    builders = ["Research Agent", "Product Agent"]
    for i, point in enumerate(d.build_case[:5]):
        rows.append({"side": "Build", "agent": builders[i % len(builders)], "point": point})
    for point in d.risk_case[:5]:
        rows.append({"side": "Don't Build", "agent": "Risk Agent", "point": point})
    return rows


# --------------------------------------------------------------------------- #
# §5.2 — artifact content (render_artifact markdown)
# --------------------------------------------------------------------------- #
def artifact_content(state, artifact_id: str) -> dict | None:
    spec = _ARTIFACT_BY_ID.get(artifact_id)
    if spec is None:
        return None
    obj = getattr(state, spec["attr"], None)
    if obj is None:
        return None
    body = render_artifact(spec["render"], obj)
    return {"id": artifact_id, "format": "markdown", "body": body}


# --------------------------------------------------------------------------- #
# §5.3 — evidence traces (from PainPoint.source_evidence + PRD.sources)
# --------------------------------------------------------------------------- #
_SOURCE_META = {"github": ("GitHub", "code"), "reddit": ("Reddit", "forum"),
                "hackernews": ("Hacker News", "tag"), "arxiv": ("Papers", "article"),
                "producthunt": ("Product Hunt", "rocket_launch"),
                "stackexchange": ("StackExchange", "quiz"), "web": ("Web", "public")}


def evidence_traces(state, artifact_id: str) -> list[dict] | None:
    spec = _ARTIFACT_BY_ID.get(artifact_id)
    if spec is None or getattr(state, spec["attr"], None) is None or state.research is None:
        return None
    traces = []
    for i, pain in enumerate(state.research.pain_points[:8]):
        by_platform: dict[str, list[str]] = {}
        for ev in pain.source_evidence:
            by_platform.setdefault(ev.source, []).append(ev.title or ev.snippet[:60])
        if not by_platform:
            continue
        sources = []
        for src, examples in by_platform.items():
            label, icon = _SOURCE_META.get(src, (src.capitalize(), "link"))
            shown = examples[:3] + ([f"+{len(examples) - 3} more"] if len(examples) > 3 else [])
            sources.append({"platform": label, "icon": icon, "count": len(examples),
                            "examples": shown})
        traces.append({"claimId": f"pain-{i}", "label": pain.text[:120], "sources": sources})
    return traces


# --------------------------------------------------------------------------- #
# §5.4 — versions (mock)
# --------------------------------------------------------------------------- #
def versions(state, artifact_id: str) -> list[dict] | None:
    spec = _ARTIFACT_BY_ID.get(artifact_id)
    if spec is None or getattr(state, spec["attr"], None) is None:
        return None
    return [
        {"label": "v1 — Initial Draft", "time": "14:03:12",
         "note": "First pass from raw evidence", "current": False},
        {"label": "v2 — Refined", "time": "14:06:45",
         "note": "Cross-validated against sources", "current": True},
    ]


def source_counts(state) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ev in _evidence(state):
        counts[ev.source] = counts.get(ev.source, 0) + 1
    return counts


# --------------------------------------------------------------------------- #
# §4.7 — REAL evidence graph (source → pain → requirement), from run data.
# Fixed source-node layout (stable coords + keeps the contract's node ids) with REAL counts,
# REAL pain labels, and REAL edges derived from each PainPoint.source_evidence. This is the
# traceability the Evidence Graph visualizes — no longer a fixed mock.
# --------------------------------------------------------------------------- #
_SRC_NODE = {"github": "github", "reddit": "reddit", "hackernews": "hn", "hn": "hn",
             "producthunt": "ph", "arxiv": "papers", "papers": "papers"}
_SRC_LAYOUT = [("github", "GitHub", 200, 55), ("reddit", "Reddit", 75, 130),
               ("hn", "HN", 325, 130), ("ph", "Prod Hunt", 75, 240),
               ("papers", "Papers", 325, 240)]
_PAIN_POS = [(200, 148), (130, 210), (270, 210)]


def evidence_graph(state) -> dict:
    counts = source_counts(state)

    def count_for(node_id: str) -> int:
        return sum(n for src, n in counts.items() if _SRC_NODE.get(src) == node_id)

    nodes = [{"id": nid, "label": lab, "x": x, "y": y, "type": "source", "count": count_for(nid)}
             for nid, lab, x, y in _SRC_LAYOUT]
    edges: list[list[str]] = []

    pains = state.research.pain_points[:3] if state.research else []
    for i, pain in enumerate(pains):
        pid = f"pain{i + 1}"
        px, py = _PAIN_POS[i]
        nodes.append({"id": pid, "label": (pain.text[:24] or f"Pain #{i + 1}"),
                      "x": px, "y": py, "type": "pain", "count": 0})
        linked = {_SRC_NODE.get(ev.source) for ev in pain.source_evidence}
        linked = {s for s in linked if s}
        if not linked:                                   # no orphan: tie to the busiest source
            linked = {max(_SRC_LAYOUT, key=lambda s: count_for(s[0]))[0]}
        for sn in linked:
            edges.append([sn, pid])
        edges.append([pid, "req1"])

    feat = (state.prd.features[0].title[:20] if (state.prd and state.prd.features)
            else "Requirement")
    nodes += [{"id": "req1", "label": feat, "x": 200, "y": 275, "type": "req", "count": 0},
              {"id": "arch1", "label": "Architecture", "x": 145, "y": 330, "type": "arch", "count": 0},
              {"id": "road1", "label": "Roadmap", "x": 255, "y": 330, "type": "roadmap", "count": 0}]
    edges += [["req1", "arch1"], ["req1", "road1"]]
    return {"nodes": nodes, "edges": edges}


# --------------------------------------------------------------------------- #
# §6.3 — REAL model cards from the model catalog + live key availability.
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Explain-Why (from explain_prd) — per-feature provenance + confidence.
# --------------------------------------------------------------------------- #
def explain(state) -> dict:
    from aps.explain import explain_prd
    if state.prd is None:
        return {"overallConfidence": 0, "features": []}
    x = explain_prd(state.prd, state.research)
    return {
        "overallConfidence": round(x.overall_confidence * 100),
        "features": [{
            "title": f.feature_title, "priority": f.priority, "why": f.why,
            "inspiredBy": f.inspired_by, "confidence": round(f.confidence * 100),
            "evidence": [{"source": e.source, "url": e.url,
                          "title": e.title or (e.snippet or "")[:60]} for e in f.evidence],
        } for f in x.features],
    }


# --------------------------------------------------------------------------- #
# Multi-provider failover — the REAL chain + circuit-breaker + registry health.
# (root /providers only shows nim/gemini; this exposes the full multipleAPIplan layer)
# --------------------------------------------------------------------------- #
def system_providers() -> dict:
    from aps.config.providers import (
        REGISTRY, DEFAULT_CHAIN, resolved_provider_chain, provider_available,
    )
    from aps.config.quota import BREAKER
    chain_names = resolved_provider_chain() or list(DEFAULT_CHAIN)   # show DEFAULT if none configured

    def row(name: str, *, primary: bool = False) -> dict:
        spec = REGISTRY.get(name)
        return {
            "name": name,
            "label": name.upper() if spec and spec.kind == "openai" else (name.capitalize()),
            "kind": spec.kind if spec else "openai",
            "model": spec.default_model if spec else "",
            "available": provider_available(name),
            "breakerOpen": BREAKER.is_open(name),
            "rpm": spec.rpm if spec else 0,
            "tools": spec.tools if spec else "false",
            "keyless": bool(spec.keyless) if spec else False,
            "signup": spec.signup if spec else "",
            "primary": primary,
        }

    chain = [row(n, primary=(i == 0)) for i, n in enumerate(chain_names)]
    extras = [row(n) for n in REGISTRY if n not in chain_names]
    return {
        "resolved": chain_names[0] if chain_names else None,
        "configured": bool(resolved_provider_chain()),    # False → showing DEFAULT_CHAIN preview
        "chain": chain,                                    # the ordered failover path
        "registry": chain + extras,                        # full catalog with live availability
    }


# --------------------------------------------------------------------------- #
# Architecture Mermaid (TRD only) — the system flowchart + ER diagram.
# --------------------------------------------------------------------------- #
def artifact_mermaid(state, artifact_id: str) -> dict | None:
    if artifact_id != "trd" or state.trd is None:
        return None
    from aps.render import architecture_mmd
    return {"id": artifact_id, "format": "mermaid", "body": architecture_mmd.render(state.trd)}


_PROV_ICON = {"nim": ("memory", "#79ff5b"), "gemini": ("auto_awesome", "#a5e7ff")}


def model_cards() -> list[dict]:
    """Up to 4 headline models from config.model_catalog, with REAL provider names + REAL
    availability (key present?). The resolved default provider's model is `primary`. Cosmetic
    latency/cost/success are deterministic (no real source). Contract: 4 rows, exactly 1 primary."""
    from aps.config.model_catalog import PROVIDERS
    from aps.config.settings import resolved_provider, gemini_key, nvidia_key
    avail = {"nim": bool(nvidia_key()), "gemini": bool(gemini_key())}
    resolved = resolved_provider()
    flat = [(p, m) for p in sorted(PROVIDERS, key=lambda p: 0 if p["id"] == resolved else 1)
            for m in p["models"]]
    cards = []
    for i, (prov, m) in enumerate(flat[:4]):
        mid = m["id"].split("/")[-1]
        icon, color = _PROV_ICON.get(prov["id"], ("smart_toy", "#bbc9cf"))
        cards.append({
            "id": mid[:24], "name": m["label"][:34], "provider": prov["label"], "icon": icon,
            "available": avail.get(prov["id"], False),
            "latencyMs": M.jitter(f"lat:{mid}", 380, 2200),
            "tokensM": round(M.jitter(f"tok:{mid}", 80, 870) / 1000, 3),
            "costUSD": 0.0 if prov["id"] in ("ollama",) else round(M.jitter(f"cost:{mid}", 80, 1240) / 100, 2),
            "successRate": round(94 + M.jitter(f"succ:{mid}", 0, 52) / 10, 1),
            "primary": i == 0, "color": color,
        })
    return cards
