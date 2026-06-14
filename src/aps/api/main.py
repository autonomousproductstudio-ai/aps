"""aps.api.main — FastAPI surface wired to the orchestrator.

Implements docs/API_CONTRACT.md: POST /runs, GET /runs/{id}, GET /runs/{id}/events (SSE),
GET /runs/{id}/artifacts/{name}. Auth header X-APS-Key. A run executes in a background
thread (run_sync is synchronous); lifecycle Events are streamed from the EventBus by
polling its per-run history, which is thread-safe across the worker thread and the loop.

This is the backend boundary the React frontend consumes; the frontend itself is separate.
"""
from __future__ import annotations

import asyncio
import json
import os
import queue
import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, PlainTextResponse, HTMLResponse
from pydantic import BaseModel

from aps.config.settings import (
    get_settings, describe_runtime, resolved_provider, nvidia_key, gemini_key,
    set_run_model, reset_run_model,
)
from aps.config.model_catalog import catalog as model_catalog, PROVIDERS
from aps.state.models import StudioState, RunStatus, Event
from aps.orchestrator.events import EventBus
from aps.orchestrator.graph import run_sync
from aps.infra.metrics import setup_metrics
from aps.infra.logging import get_logger, install_log_capture, get_log_lines
from aps.infra import artifact_store
from aps.infra import history_store
from aps.render import render_artifact
from aps.render import score_md
from aps.render import architecture_mmd
from aps.render import debate_md
from aps.render import explain_md
from aps.scoring import score_startup
from aps.debate import run_debate
from aps.explain import explain_prd
from aps.launch import build_launch_plan, launch_github

_LOG = get_logger("aps.api")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Mirror all logs (uvicorn/httpx/openai/langchain + our events) into the ring buffer
    # so GET / and GET /logs.json can show them. Done here so uvicorn's own loggers exist.
    install_log_capture()
    # First line in the server log makes a key/provider misconfig obvious immediately,
    # instead of it surfacing only as silent `degraded` artifacts later.
    _LOG.info("aps_api_startup", runtime=describe_runtime())
    yield


app = FastAPI(title="Autonomous Product Studio", lifespan=_lifespan)
setup_metrics(app)   # mounts /metrics when prometheus_client is installed (no-op otherwise)

# CORS so the Vite dev frontend (localhost:5173) can call this API from the browser.
_cors = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_LOG_VIEWER_HTML = """<!doctype html><html><head><meta charset=utf-8>
<title>APS backend logs</title><style>
 body{margin:0;background:#0b0e14;color:#cdd6f4;font:12px/1.45 ui-monospace,Consolas,monospace}
 header{position:sticky;top:0;background:#11151f;padding:8px 12px;border-bottom:1px solid #222a3a;
   display:flex;gap:10px;align-items:center;flex-wrap:wrap}
 header b{color:#89b4fa} select,input,button{background:#1a2030;color:#cdd6f4;border:1px solid #2a3450;
   border-radius:4px;padding:3px 6px;font:inherit} #log{padding:8px 12px;white-space:pre-wrap;word-break:break-word}
 .row{padding:1px 0;border-bottom:1px solid #161b26} .t{color:#6c7393} .lg{color:#94e2d5}
 .INFO{color:#cdd6f4}.WARNING{color:#f9e2af}.ERROR{color:#f38ba8}.CRITICAL{color:#f38ba8;font-weight:700}
 .DEBUG{color:#7f849c} .lvl{display:inline-block;width:62px}
</style></head><body>
<header><b>APS backend logs</b>
 <label>level <select id=level>
  <option value="">all</option><option>DEBUG</option><option selected>INFO</option>
  <option>WARNING</option><option>ERROR</option></select></label>
 <label>filter <input id=q placeholder="429, RUN_0002, /chat ..." size=22></label>
 <label><input type=checkbox id=auto checked> auto-refresh</label>
 <label><input type=checkbox id=follow checked> follow tail</label>
 <button id=clear>clear view</button>
 <span id=stat class=t></span></header>
<div id=log></div>
<script>
const $=s=>document.querySelector(s), log=$('#log');
function esc(s){return s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
async function pull(){
 const lvl=$('#level').value, q=$('#q').value.trim();
 const u=new URL('/logs.json',location.origin); u.searchParams.set('limit','1500');
 if(lvl)u.searchParams.set('level',lvl); if(q)u.searchParams.set('contains',q);
 let rows; try{rows=await (await fetch(u)).json();}catch(e){$('#stat').textContent='backend unreachable';return;}
 log.innerHTML=rows.map(r=>{const d=new Date(r.ts*1000).toISOString().slice(11,23);
  return `<div class="row"><span class=t>${d}</span> <span class="lvl ${r.level}">${r.level}</span> `
   +`<span class=lg>${esc(r.logger)}</span> <span class="${r.level}">${esc(r.msg)}</span></div>`}).join('');
 $('#stat').textContent=rows.length+' lines';
 if($('#follow').checked)window.scrollTo(0,document.body.scrollHeight);
}
$('#clear').onclick=()=>{log.innerHTML='';};
['level','q'].forEach(id=>$('#'+id).addEventListener('input',pull));
setInterval(()=>{if($('#auto').checked)pull();},2000); pull();
</script></body></html>"""


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def log_viewer() -> str:
    """Browser log console — live-tails the in-memory buffer (uvicorn/httpx/429/our events)."""
    return _LOG_VIEWER_HTML


@app.get("/logs.json", include_in_schema=False)
def logs_json(limit: int = Query(1000, le=4000), level: str | None = None,
              contains: str | None = None):
    """Raw buffered log lines (newest last) — powers the / console; also curl-friendly."""
    return get_log_lines(limit=limit, level=level, contains=contains)


# v1 in-memory stores (ADR-0003)
_RUNS: dict[str, dict] = {}
_STATES: dict[str, StudioState] = {}
_BUSES: dict[str, EventBus] = {}

# ── concurrency, fairness & reliability (plan §2) ─────────────────────────────
# Admission control (2.1): runs are enqueued onto a bounded queue drained by a fixed worker
# pool, so concurrent runs are capped (FIFO fairness, back-pressure) instead of each POST
# spawning an unbounded daemon thread that fights over the shared rate buckets.
_MAX_CONCURRENT_RUNS = int(os.getenv("APS_MAX_CONCURRENT_RUNS", "2"))
_QUEUE_BACKLOG = int(os.getenv("APS_RUN_QUEUE_BACKLOG", "32"))
_RUN_DEADLINE_S = float(os.getenv("APS_RUN_DEADLINE_SECONDS", "180"))   # 2.3 per-run cap
_RUN_QUEUE: "queue.Queue[tuple[str, str, dict | None]]" = queue.Queue(maxsize=_QUEUE_BACKLOG)
_CANCEL: dict[str, threading.Event] = {}          # 2.2 per-run cooperative cancel flag
_CANCEL_REASON: dict[str, str] = {}               # why a run was cancelled (deadline vs user)
_IDEM: dict[str, str] = {}                         # 2.4 idempotency key -> run_id
_workers_started = False
_workers_lock = threading.Lock()

_ARTIFACTS = ("research", "prd", "trd", "execution", "pitch", "brand", "legal", "funding",
              "availability", "compliance")
_STARTED = time.monotonic()   # process start, for /health uptime


def _idem_key(idea: str, cfg: dict, header_key: str | None = None) -> str:
    """Idempotency key (2.4): an explicit Idempotency-Key header wins; else a stable hash of
    idea + provider/model, so a double-click / retried POST collapses to the in-flight run."""
    if header_key:
        return f"hdr:{header_key}"
    import hashlib
    raw = f"{idea}|{cfg.get('provider')}|{cfg.get('model')}"
    return "auto:" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def _ensure_workers() -> None:
    """Start the fixed run-worker pool once, lazily on first submission."""
    global _workers_started
    if _workers_started:
        return
    with _workers_lock:
        if _workers_started:
            return
        for n in range(max(1, _MAX_CONCURRENT_RUNS)):
            threading.Thread(target=_run_worker, name=f"aps-run-worker-{n}",
                             daemon=True).start()
        _workers_started = True


def _run_worker() -> None:
    while True:
        run_id, idea, config = _RUN_QUEUE.get()
        try:
            # A run can be cancelled while still queued — skip it without doing the work.
            ev = _CANCEL.get(run_id)
            if ev is not None and ev.is_set():
                _RUNS[run_id]["status"] = RunStatus.CANCELLED.value
                _RUNS[run_id]["cancel_reason"] = _CANCEL_REASON.get(
                    run_id, "cancelled before it started")
            else:
                _RUNS[run_id]["status"] = RunStatus.RUNNING.value
                _run_in_background(run_id, idea, config)
        except Exception:  # a worker must never die — the pool drains forever
            pass
        finally:
            _RUN_QUEUE.task_done()


def submit_run(idea: str, config: dict | None, *,
               idempotency_key: str | None = None) -> dict:
    """Register a run and enqueue it for a worker (the single admission path for both APIs).

    Returns the run record. Idempotent (2.4): a duplicate submission of an in-flight idea
    returns the existing record. Raises HTTPException(503) when the backlog is full (2.1
    back-pressure) so a flood gets a clean signal instead of unbounded thread growth.
    """
    cfg = config or {}
    key = _idem_key(idea, cfg, idempotency_key)
    existing = _IDEM.get(key)
    if existing and _RUNS.get(existing, {}).get("status") in (
            RunStatus.QUEUED.value, RunStatus.RUNNING.value):
        return _RUNS[existing]

    run_id = "run_" + uuid.uuid4().hex[:6]
    _BUSES[run_id] = EventBus()
    _CANCEL[run_id] = threading.Event()
    _RUNS[run_id] = {"run_id": run_id, "idea": idea,
                     "status": RunStatus.QUEUED.value, "artifacts": [],
                     "provider": cfg.get("provider"), "model": cfg.get("model")}
    _IDEM[key] = run_id
    _ensure_workers()
    try:
        _RUN_QUEUE.put_nowait((run_id, idea, config))
    except queue.Full:
        for store in (_RUNS, _BUSES, _CANCEL):
            store.pop(run_id, None)
        _IDEM.pop(key, None)
        raise HTTPException(503, "run queue full; retry shortly")
    return _RUNS[run_id]


def cancel_run(run_id: str, reason: str = "cancelled by user") -> bool:
    """Signal a run to stop (2.2). Returns False if the run is unknown. The run unwinds at its
    next checkpoint (research loop / stage boundary) and reaches a CANCELLED terminal state.
    `reason` is recorded so the run_cancelled event names WHY (user vs deadline)."""
    ev = _CANCEL.get(run_id)
    if ev is None:
        return False
    _CANCEL_REASON.setdefault(run_id, reason)   # first cause wins (don't let user-cancel mask a deadline)
    ev.set()
    return True


class StartReq(BaseModel):
    idea: str
    config: dict | None = None


class LaunchReq(BaseModel):
    token: str | None = None       # falls back to APS_GITHUB_PAT
    owner: str | None = None
    private: bool = False
    dry_run: bool = False          # True (or no token) → preview only, no repo created


def _auth(key: str | None) -> None:
    if key != get_settings().api_key:
        raise HTTPException(401, "bad api key")


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# Friendly timeline labels for the History page replay, derived from the raw event stream.
_EVENT_LABEL = {
    "run_start": "Run initiated", "agent_start": "{agent} started",
    "agent_end": "{agent} complete", "tool_call": "Tool · {tool}",
    "tool_result": "Tool result · {tool}", "artifact_ready": "{name} generated",
    "research_unit_end": "Research unit complete", "composition": "Handoff to product",
    "run_complete": "Startup complete", "run_cancelled": "Run cancelled",
    "run_failed": "Run failed", "error": "Notice",
}


def _history_summary(state: StudioState) -> dict:
    """Build the per-run archive record (plain dict) handed to history_store on completion.

    All extraction is guarded so a malformed artifact never derails recording the run."""
    produced = [a for a in _ARTIFACTS if getattr(state, a, None) is not None]
    score = None
    evidence = 0
    try:
        if state.research is not None:
            score = round(score_startup(state.research, state.prd).overall, 1)
            evidence = len(state.research.evidence or [])
    except Exception:
        pass
    agents = set()
    timeline: list[dict] = []
    for ev in (state.events or []):
        data = ev.data or {}
        if ev.type == "agent_start" and data.get("agent"):
            agents.add(data["agent"])
        tmpl = _EVENT_LABEL.get(ev.type)
        if tmpl:
            try:
                label = tmpl.format(agent=data.get("agent", "Agent"),
                                    tool=data.get("tool", "tool"),
                                    name=data.get("name", "Artifact"))
            except Exception:
                label = ev.type
            ts = ev.ts.isoformat() if hasattr(ev.ts, "isoformat") else str(ev.ts)
            timeline.append({"ts": ts, "type": ev.type, "label": label})
    name = None
    if getattr(state, "brand", None) is not None:
        name = getattr(state.brand, "name", None)
    name = name or (state.idea or "")[:120]
    status = state.status.value if hasattr(state.status, "value") else str(state.status)
    return {
        "name": name, "status": status, "score": score,
        "artifacts": produced, "tool_calls": getattr(state, "tool_calls", 0),
        "evidence_count": evidence, "agent_count": len(agents) or len(produced),
        "timeline": timeline, "completed_at": _now_iso(),
    }


def _run_in_background(run_id: str, idea: str, config: dict | None) -> None:
    bus = _BUSES[run_id]
    cfg = config or {}
    # Pin the per-run model/provider chosen in the UI for THIS thread; the research fan-out
    # copies this context into its workers (see supervisor). Cleared in finally.
    token = None
    if cfg.get("provider") or cfg.get("model"):
        token = set_run_model(cfg.get("provider"), cfg.get("model"))
    # Per-run deadline (2.3): a wall-clock cap that trips the SAME cancel flag the cancel
    # endpoint uses, so a run that hangs past the budget unwinds cleanly instead of holding a
    # worker slot forever. The clock starts HERE (work begins), not at enqueue, so queue wait
    # doesn't eat the budget. Layered above the per-tool HTTP timeout in infra/http.py.
    cancel_ev = _CANCEL.get(run_id) or threading.Event()

    def _trip_deadline() -> None:
        # Record WHY before flipping the flag, so run_cancelled names the deadline (not a bare
        # "cancelled"). setdefault: if the user already cancelled, keep their reason.
        _CANCEL_REASON.setdefault(run_id, f"run exceeded {int(_RUN_DEADLINE_S)}s deadline")
        cancel_ev.set()

    deadline = threading.Timer(_RUN_DEADLINE_S, _trip_deadline)
    deadline.daemon = True
    deadline.start()
    try:
        # Publish partial state as each artifact is produced (plan 1.6): GET …/artifacts/{name}
        # then serves research/prd/trd/… the moment they exist, paired with the live
        # `artifact_ready` SSE events, so the UI renders the package assembling. The final
        # assignment below overwrites these partials with the completed state.
        def _on_state(partial: StudioState) -> None:
            _STATES[run_id] = partial
        state = run_sync(idea, bus, run_id=run_id, on_state=_on_state,
                         should_cancel=cancel_ev.is_set,
                         cancel_reason=lambda: _CANCEL_REASON.get(run_id))
        _STATES[run_id] = state
        _RUNS[run_id]["status"] = state.status.value   # complete|degraded|failed|cancelled (honest)
        _RUNS[run_id]["artifacts"] = [a for a in _ARTIFACTS if getattr(state, a) is not None]
        if state.status == RunStatus.CANCELLED:        # surface the specific cause in GET /runs
            _RUNS[run_id]["cancel_reason"] = _CANCEL_REASON.get(run_id, "cancelled")
        artifact_store.save_run(run_id, state)   # durable: survives restart, inspectable on disk
        if meta := artifact_store.load_meta(run_id):
            _RUNS[run_id].update({k: meta[k] for k in ("degrade_reason",) if k in meta})
        try:  # archive into per-user history (no-op for non-user/lean runs) — never break a run
            history_store.record_completion(run_id, _history_summary(state))
        except Exception:
            pass
    except Exception as e:  # never leave a run hanging
        _RUNS[run_id]["status"] = RunStatus.FAILED.value
        _RUNS[run_id]["error"] = str(e)[:300]
        bus.publish(run_id, Event(type="run_failed", data={"error": str(e)[:300]}))
        try:
            history_store.mark_status(run_id, RunStatus.FAILED.value, completed_at=_now_iso())
        except Exception:
            pass
    finally:
        deadline.cancel()
        _CANCEL_REASON.pop(run_id, None)
        if token is not None:
            reset_run_model(token)


@app.post("/runs", status_code=202)
def start_run(req: StartReq, x_aps_key: str | None = Header(default=None),
              idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    _auth(x_aps_key)
    # Admission control + idempotency (plan 2.1/2.4): enqueue onto the bounded queue drained by
    # the worker pool; a duplicate in-flight idea collapses to the existing run.
    return submit_run(req.idea, req.config, idempotency_key=idempotency_key)


@app.post("/runs/{run_id}/cancel", status_code=202)
def cancel(run_id: str, x_aps_key: str | None = Header(default=None)):
    """Cooperatively cancel a queued or running run (plan 2.2). The run stops at its next
    checkpoint and settles into a CANCELLED terminal state; idempotent (cancel-twice is fine)."""
    _auth(x_aps_key)
    if run_id not in _RUNS and not cancel_run(run_id):
        raise HTTPException(404, "no such run")
    cancel_run(run_id)
    return {"run_id": run_id, "cancelling": True}


@app.get("/models")
def models(x_aps_key: str | None = Header(default=None)):
    """Catalog the frontend model-selector binds to: supported providers + their models, plus
    the current default (what a run uses if config.model is omitted). Single source of truth is
    config/model_catalog.py — add a model there and it appears in the UI with no frontend change."""
    _auth(x_aps_key)
    s = get_settings()
    cat = model_catalog()
    default_provider = resolved_provider()
    default_model = s.gemini_model if default_provider == "gemini" else s.nim_model
    return {**cat, "default": {"provider": default_provider, "model": default_model},
            "runtime": describe_runtime()}


@app.get("/health")
def health():
    """Liveness + real process uptime (no auth — used by the System page's status widget)."""
    return {"status": "ok", "uptime_seconds": round(time.monotonic() - _STARTED, 1),
            "runtime": describe_runtime()}


@app.get("/providers")
def providers(x_aps_key: str | None = Header(default=None)):
    """Per-provider availability for the System page: which providers have a usable key set.
    The catalog providers are 'enabled' when their key is present; resolved is the active one."""
    _auth(x_aps_key)
    have = {"nim": bool(nvidia_key()), "gemini": bool(gemini_key())}
    rows = [{"id": p["id"], "label": p["label"], "key_env": p["key_env"],
             "enabled": have.get(p["id"], False)} for p in PROVIDERS]
    return {"providers": rows, "resolved": resolved_provider()}


def _stats() -> dict:
    """Honest derived metrics — real run counts, evidence/tool totals, in-flight, uptime.
    Replaces the mockup's vanity numbers. Merges in-memory runs with the durable store."""
    metas: dict[str, dict] = {}
    for rid in artifact_store.list_runs():
        m = artifact_store.load_meta(rid)
        if m is not None:
            metas[rid] = m
    metas.update(_RUNS)
    by_status: dict[str, int] = {}
    for m in metas.values():
        st = m.get("status", "unknown")
        by_status[st] = by_status.get(st, 0) + 1
    # evidence / tool-call totals from finished states we can cheaply read (in-memory first)
    total_evidence = total_tool_calls = 0
    for rid in metas:
        state = _STATES.get(rid) or artifact_store.load_state(rid)
        if state is not None:
            total_tool_calls += getattr(state, "tool_calls", 0) or 0
            if state.research is not None:
                total_evidence += len(state.research.evidence)
    from aps.infra import cache
    return {
        "total_runs": len(metas),
        "by_status": by_status,
        "in_flight": by_status.get("running", 0),
        "total_evidence": total_evidence,
        "total_tool_calls": total_tool_calls,
        "providers_configured": sum(1 for p in PROVIDERS
                                    if (nvidia_key() if p["id"] == "nim" else gemini_key())),
        "uptime_seconds": round(time.monotonic() - _STARTED, 1),
        # plan §4 observability: surface the concurrency + cache subsystems honestly.
        "queue_depth": _RUN_QUEUE.qsize(),
        "max_concurrent_runs": _MAX_CONCURRENT_RUNS,
        "queued": by_status.get("queued", 0),
        "tool_cache": cache.stats(),
    }


@app.get("/stats")
def stats(x_aps_key: str | None = Header(default=None)):
    """Aggregate stats feeding the Dashboard/System/decorative widgets (honest, derived)."""
    _auth(x_aps_key)
    return _stats()


@app.get("/runs")
def list_runs(x_aps_key: str | None = Header(default=None)):
    """All runs, newest-first — the in-memory runs of this process merged with the durable
    ones on disk (so runs from a previous process still show). Powers the Dashboard list."""
    _auth(x_aps_key)
    merged: dict[str, dict] = {}
    # disk first (older / previous process), then in-memory wins (fresher status)
    for rid in artifact_store.list_runs():
        meta = artifact_store.load_meta(rid)
        if meta is not None:
            merged[rid] = meta
    merged.update(_RUNS)
    runs = list(merged.values())
    runs.sort(key=lambda r: r.get("run_id", ""), reverse=True)
    return {"runs": runs, "count": len(runs)}


@app.get("/runs/{run_id}")
def get_run(run_id: str, x_aps_key: str | None = Header(default=None)):
    _auth(x_aps_key)
    if run_id in _RUNS:
        return _RUNS[run_id]
    meta = artifact_store.load_meta(run_id)   # read-through: run from a previous process
    if meta is not None:
        return meta
    raise HTTPException(404, "no such run")


@app.get("/runs/{run_id}/events")
def stream(run_id: str):
    if run_id not in _BUSES:
        raise HTTPException(404, "no such run")
    bus = _BUSES[run_id]

    async def gen():
        sent = 0
        loop = asyncio.get_event_loop()
        # Push delivery (plan 1.3): block off-loop on the bus condition until new events land
        # (or a 1 s liveness tick) instead of polling every 0.2 s — near-zero event latency.
        deadline = time.monotonic() + 120   # ~2 min safety cap (unchanged)
        while time.monotonic() < deadline:
            new = await loop.run_in_executor(None, bus.wait, run_id, sent, 1.0)
            for ev in new:
                sent += 1
                yield f"event: {ev.type}\ndata: {json.dumps(ev.data, default=str)}\n\n"
                if ev.type in ("run_complete", "run_failed"):
                    return

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/runs/{run_id}/artifacts/{name}")
def artifact(run_id: str, name: str,
             format_: str | None = Query(default=None, alias="format"),
             x_aps_key: str | None = Header(default=None)):
    _auth(x_aps_key)
    if name not in _ARTIFACTS:
        raise HTTPException(404, f"unknown artifact '{name}'")

    # resolve the artifact as a model (in-memory) or dict (file store read-through)
    state = _STATES.get(run_id)
    if state is not None:
        obj = getattr(state, name)
        if obj is None:
            raise HTTPException(404, f"artifact '{name}' not produced")
    else:
        obj = artifact_store.load_artifact(run_id, name)
        if obj is None:
            raise HTTPException(404, "run not finished or unknown")

    # ?format=md → on-demand Markdown render (W6); the default JSON path is unchanged.
    # Rendering is a pure transform over the already-stored typed object; nothing new is
    # persisted (the artifact store still holds JSON only).
    if format_ == "mermaid":
        # interactive architecture diagrams (T2.2) — TRD only
        if name != "trd":
            raise HTTPException(404, "mermaid is only available for the 'trd' artifact")
        from aps.state.models import TRD
        trd = obj if isinstance(obj, TRD) else TRD.model_validate(obj)
        return PlainTextResponse(architecture_mmd.render(trd), media_type="text/markdown")
    if format_ == "md":
        return PlainTextResponse(render_artifact(name, obj), media_type="text/markdown")
    return obj.model_dump() if hasattr(obj, "model_dump") else obj


@app.get("/runs/{run_id}/score")
def score(run_id: str,
          format_: str | None = Query(default=None, alias="format"),
          x_aps_key: str | None = Header(default=None)):
    """Startup Score — a derived 0–10 scorecard computed on demand from the run's research
    (+ PRD). Not stored, not part of StudioState; ?format=md returns a Markdown scorecard."""
    _auth(x_aps_key)
    state = _STATES.get(run_id) or artifact_store.load_state(run_id)
    if state is None or state.research is None:
        raise HTTPException(404, "run not finished or has no research")
    sc = score_startup(state.research, state.prd)
    if format_ == "md":
        return PlainTextResponse(score_md.render(sc), media_type="text/markdown")
    return sc.model_dump()


@app.get("/runs/{run_id}/debate")
def debate(run_id: str,
           format_: str | None = Query(default=None, alias="format"),
           x_aps_key: str | None = Header(default=None)):
    """Autonomous Debate — the studio argues build-vs-don't and returns a verdict. Derived,
    computed on demand from the run's research/PRD; ?format=md returns the debate transcript."""
    _auth(x_aps_key)
    state = _STATES.get(run_id) or artifact_store.load_state(run_id)
    if state is None or state.research is None:
        raise HTTPException(404, "run not finished or has no research")
    d = run_debate(state.research, state.prd)
    if format_ == "md":
        return PlainTextResponse(debate_md.render(d), media_type="text/markdown")
    return d.model_dump()


@app.get("/runs/{run_id}/explain")
def explain(run_id: str,
            format_: str | None = Query(default=None, alias="format"),
            x_aps_key: str | None = Header(default=None)):
    """Explain-Why (T2.5) — per-feature provenance: the pain/competitor it came from, the
    evidence that grounds it, and a confidence score. Derived, computed on demand."""
    _auth(x_aps_key)
    state = _STATES.get(run_id) or artifact_store.load_state(run_id)
    if state is None or state.prd is None:
        raise HTTPException(404, "run not finished or has no PRD")
    x = explain_prd(state.prd, state.research)
    if format_ == "md":
        return PlainTextResponse(explain_md.render(x), media_type="text/markdown")
    return x.model_dump()


@app.post("/runs/{run_id}/launch/github")
def launch(run_id: str, req: LaunchReq, x_aps_key: str | None = Header(default=None)):
    """GitHub Launch Mode (T2.4) — create a REAL repo + README + milestones + issues from the
    run's execution package. With no token (or dry_run) it returns a preview and creates
    nothing; with a PAT it performs the real GitHub API calls and returns the live URLs."""
    _auth(x_aps_key)
    state = _STATES.get(run_id) or artifact_store.load_state(run_id)
    if state is None or state.prd is None:
        raise HTTPException(404, "run not finished or has no PRD")
    plan = build_launch_plan(state.idea, state.prd, state.execution, state.pitch, trd=state.trd)
    result = launch_github(plan, token=req.token, owner=req.owner,
                           private=req.private, dry_run=req.dry_run)
    return result.model_dump()


# The rich "mission control" Frontend Data Contract (docs/backenddatacontract.md) lives behind
# /v1 as an isolated sub-app: JWT auth + {success,data,meta} envelope + WebSockets. It shares
# THIS module's single run engine (_RUNS/_STATES/_BUSES/_run_in_background) via lazy import, so
# both APIs drive the same orchestrator. Mounted last so the engine symbols above already exist.
from aps.api.v1 import v1_app  # noqa: E402

app.mount("/v1", v1_app)

# Billing (Dodo Payments) — server-side hosted checkout + subscriptions at /api/billing.
# Self-contained (aps.billing + aps.api.billing); reuses the bearer-token auth the /v1 API
# accepts. Inert until the DODO_* env vars are set, so it never affects existing behavior.
from aps.api.billing import router as billing_router  # noqa: E402

app.include_router(billing_router)
