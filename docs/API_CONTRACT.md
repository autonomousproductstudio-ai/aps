# API_CONTRACT.md — Backend ⇄ Frontend contract

> **Two contracts exist.** This is the **lean root API** (`/`, `X-APS-Key`, SSE, raw JSON)
> that the shipped `frontend/` consumes. The separate, richer "mission control" contract lives
> in [backenddatacontract.md](backenddatacontract.md) and is implemented behind **`/v1`** (JWT +
> `{success,data,meta}` envelope + WebSockets) — see [API_V1_STATUS.md](API_V1_STATUS.md) for
> its per-endpoint real/derived/mock status. Both APIs share one orchestrator engine.

**Owner:** P1 (defines) · **Consumes:** P3 (frontend). This revision reconciles the contract
with the **shipped** backend (`src/aps/api/main.py`, post-`front-architect`). It is the single
reference P3 wires against; pair it with [WIREFRAMES.md](WIREFRAMES.md) (widget→endpoint map).

Base URL: `/` · Auth: header `X-APS-Key: <APS_API_KEY>` on every request **except** the SSE
`/events` stream. Status values: `queued | running | complete | degraded | failed` — note
**`degraded`** (ran on the labeled stub fixture; never reported as `complete`).

> Each endpoint is tagged **[live]** (implemented now) or **[planned]** (the UI should leave the
> dependent widget in its empty state until P1 ships it — see §12).

---

## 1. Start a run — [live]

```
POST /runs
{
  "idea": "Build an AI SaaS for resume screening",
  "config": { "provider": "nim", "model": "openai/gpt-oss-120b" }   // optional, per-run
}
→ 202
{ "run_id": "run_a1b2c3", "idea": "...", "status": "running",
  "artifacts": [], "provider": "nim", "model": "openai/gpt-oss-120b" }
```

- `config.provider` ∈ providers from `GET /models` (`nim` | `gemini`). `config.model` is any
  `id` from that provider's list. **Honored for this run only** (per-run override).
- `config.max_tool_calls` — **[planned]**, ignored today.

---

## 2. List runs — [live]

```
GET /runs
→ 200 { "runs": [ { "run_id","idea","status","artifacts":[...names],
                    "provider","model","degrade_reason"? } ... ], "count": N }
```
Newest-first; merges in-memory runs with the durable store. Powers Dashboard recent-runs.

---

## 3. Get one run (snapshot) — [live, shape differs from legacy]

```
GET /runs/{run_id}
→ 200 { "run_id","idea","status","artifacts":[ "research","prd",... ],
        "provider","model","degrade_reason"?, "error"? }
```
> **Note:** today this is a flat record; `artifacts` is a **list of ready names** (fetch each
> via §5). Legacy contract fields `current_agent`, `started_at`, `finished_at`, and `artifacts`
> as a nested object are **[planned]**. Use the SSE stream (§4) for live agent/progress state.

---

## 4. Live event stream (SSE) — [live] — the timeline UI

```
GET /runs/{run_id}/events        Accept: text/event-stream
```
Frame: `event: <type>\ndata: <json>\n\n`. **Event types emitted today:**

| event | data (keys) | use |
|---|---|---|
| `run_start` | `idea` | run begins |
| `agent_start` / `agent_end` | `agent` | flip the 5-stage rail/nodes |
| `research_plan` | `subtopics[]` | the fan-out plan |
| `research_unit_start` / `research_unit_end` | `focus`, `provider`, `evidence` | the 3 parallel sub-researchers |
| `research_diversified` | `providers[]` | which providers each unit used |
| `research_keyless` | `evidence`, `reason` | no-key fallback path |
| `tool_calls_total` | `n` | aggregate tool-call count for the run |
| `composition` | `research.pain_points`, `prd.features`, … (counts) | research→PRD handoff |
| `artifact_ready` | `name` | refetch that artifact (§5) |
| `error` | `agent`/`focus`/`error`, or `fallback` | non-fatal; run continues |
| `run_degraded` | `reason` | degraded outcome + why |
| `run_complete` / `run_failed` | `status`, `degraded`, `reason` | terminal |

**[planned] — not emitted yet** (blocks the per-tool live stream + live evidence list):
```
event: tool_call    data: { agent, tool, args, ts }
event: tool_result  data: { tool, ok, evidence_count, duration_ms, ts }
```

Client: `new EventSource('/runs/'+id+'/events')` (no auth header on SSE). Note named events —
parse the `event:` line (the shipped frontend uses a fetch-stream parser to catch every type).

---

## 5. Fetch one artifact — [live]

```
GET /runs/{run_id}/artifacts/{name}              name ∈ research|prd|trd|execution|pitch
→ 200  { ...typed object... }                    (JSON; shapes in §9)

GET /runs/{run_id}/artifacts/{name}?format=md    → text/markdown   (human render / download)
GET /runs/{run_id}/artifacts/trd?format=mermaid  → text/markdown   (Mermaid diagram source; TRD only)
```

---

## 6. Derived analysis endpoints — [live] (computed on demand, not stored)

```
GET /runs/{run_id}/score[?format=md]
→ { idea, dimensions:[{name,score(0–10),rationale}], overall(0–10), verdict, grounded }
GET /runs/{run_id}/debate[?format=md]
→ { idea, build_case[], risk_case[], startup_score, risk_score, verdict, confidence(0–1), rationale }
GET /runs/{run_id}/explain[?format=md]
→ { idea, features:[{feature_title, priority, why, inspired_by?, evidence[], confidence(0–1)}],
    overall_confidence(0–1) }
```
`?format=md` returns a Markdown card for each. Require the run to have research/PRD (404 otherwise).

---

## 7. GitHub Launch Mode — [live]

```
POST /runs/{run_id}/launch/github
{ "token"?: "...", "owner"?: "...", "private"?: false, "dry_run"?: true }
→ 200 { dry_run, created, message, repo_url?, issues_created?, ... }
```
No token (or `dry_run:true`) → **preview**, creates nothing. With a PAT → real repo + README +
milestones + issues. The "tangible action" for the demo (wire a button on Artifacts).

---

## 8. Platform endpoints (Dashboard / System) — [live]

```
GET /models      → { providers:[{id,label,key_env,models:[{id,label,tools}]}],
                     default:{provider,model}, runtime }            // model selector source
GET /stats       → { total_runs, by_status:{...}, in_flight, total_evidence,
                     total_tool_calls, providers_configured, uptime_seconds }
GET /health      → { status, uptime_seconds, runtime }             // no auth
GET /providers   → { providers:[{id,label,key_env,enabled}], resolved }
GET /metrics     → Prometheus text (when prometheus_client installed)
```

---

## 9. Artifact body shapes (mirror of `state/models.py`)

```ts
type Evidence   = { source:string; url:string; title?:string; snippet:string; retrieved_at:string };
type Competitor = { name:string; url?:string; features:string[]; pricing?:string; notes?:string };
type PainPoint  = { text:string; severity:"low"|"med"|"high"; source_evidence:Evidence[] };
type Persona    = { name:string; role:string; goals:string[]; frustrations:string[] };
type Feature    = { title:string; description:string; priority:string };

type ResearchReturn = { idea:string; market_size:string; competitors:Competitor[];
                        pain_points:PainPoint[]; evidence:Evidence[];
                        degraded:boolean; tool_calls:number; degrade_reason?:string };
type PRD = { idea:string; personas:Persona[]; features:Feature[];
             mvp_scope:string; requirements:string[]; sources:Evidence[] };
type TRD          = { data_model:object; api_spec:object/*OpenAPI*/; stack:string[]; scale_estimate:string };
type ExecutionPlan= { repo_plan:object; backlog:object[]; sprints:object[]; roadmap:string; infra_cost:string };
type PitchPackage = { pitch_outline:string; demo_script:string; investor_memo:string };
```

> **Citations:** evidence is on `PainPoint.source_evidence`, `PRD.sources`, and
> `explain.features[].evidence` — render each `Evidence.url` as a clickable link (the "real work"
> proof; see WIREFRAMES §3).

---

## 10. Errors

```
4xx/5xx → FastAPI default { "detail": "..." }   (e.g. 401 bad api key, 404 unknown run/artifact)
```
A single tool error does **not** fail the run — it surfaces as `event: error` in the stream and
the run continues (degrades honestly if nothing was gathered).

---

## 11. Mock server (P3 unblock) — [live]

`uvicorn aps.api.mock:app` replays `tests/evals/fixtures/sample_run.json` over the SSE contract
with realistic timing — buildable before the real orchestrator. The **real** API
(`aps.api.main`) is what production/demo uses and is what §1–§8 document.

---

## 12. Implementation status (what P3 can bind today vs. wait on)

| Capability | Status | Widget it feeds |
|---|---|---|
| Start run + per-run model · list/get runs · SSE agent timeline | ✅ live | Pipeline, Dashboard |
| Artifacts JSON + `?format=md` + TRD `?format=mermaid` | ✅ live | Artifacts |
| Score / Debate / Explain / Launch · /models /stats /health /providers | ✅ live | Artifacts, Dashboard, System |
| Per-tool `tool_call`/`tool_result` events + live evidence | 🔴 planned | Pipeline live tool stream + evidence list |
| Traceability edges (Evidence Graph) | 🔴 planned | Living Network / dependency graph |
| `GET /runs/{id}/replay` | 🔴 planned | Company Replay |
| `GET /runs/{id}` legacy fields · `config.max_tool_calls` | 🟡 planned | minor |
| Cost / latency / memory / per-tool metrics | 🔴 planned | System cost/heatmap/latency |

Change this contract via a `contract:` PR; keep the shipped backend and WIREFRAMES.md in sync.
