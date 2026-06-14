# WIREFRAMES.md — Frontend ⇄ Backend wiring spec (P3)

**Audience:** P3 (frontend). **Goal:** wire the **existing** `front-architect` design
(`frontend/` — 4 pages, the dark "instrument-panel" look + animations) to the live backend
**without redesigning**. This doc names every widget on every page and the exact endpoint /
SSE event / field that feeds it, plus the handful of backend additions you should *request*
(don't build them in React).

> Design is locked. The shipped UI is the 4-page React/Vite/Tailwind app from branch
> [`front-architect`](https://github.com/ashwini-361/aps/tree/front-architect) (merged to
> `main` as `b3177b9`). **Keep its layout, glass panels, glow, stagger/flow animations.** This
> spec only tells you which data to drop into each existing slot.

Backend contract & shapes: [API_CONTRACT.md](API_CONTRACT.md). Run it: `uvicorn aps.api.main:app`
(:8000) + `cd frontend && npm run dev` (:5173, dev-proxies the API).

**Status legend:** ✅ live now (endpoint exists, just bind) · 🟡 small backend add needed
(ask P1) · 🔴 larger backend work (ask P1; don't fake it in the UI).

---

## 0. Data flow (one read)

```
Pipeline ─POST /runs {idea, config:{provider,model}}─► run_id
        ─GET /runs/{id}/events (SSE)─► drive timeline/terminal/agent rail
on run_complete ─► Artifacts ─GET /runs/{id}/artifacts/{name}[?format=md|mermaid]
                            ─GET /runs/{id}/score|debate|explain[?format=md]
Dashboard/System ─GET /runs · /stats · /health · /providers · /models (poll 5s)
```

Auth: header `X-APS-Key: <APS_API_KEY>` on every request **except** the SSE `/events` stream.
Selected model is **per-run** — pass it in `config.model`; it's honored for that run only.

---

## 1. Page: **Pipeline** (`/`) — run console + live run

Existing sections: hero "Startup Creation Protocol" card (idea input, Expected Deliverables,
"Agent Readiness" rail, Initiate button), "The Swarm Pipeline" 5-node strip, "Core Engine"
marketing block, "LIVE_RUN_STREAM" terminal + metrics cards.

| Widget (existing) | Bind to | Field / detail | Status |
|---|---|---|---|
| Idea `<input>` | local state → `POST /runs` | `{ idea }` | ✅ |
| **Model selector** (add to the card; design has room next to input) | `GET /models` → `<select>` | `providers[].models[].{id,label}`; send as `config.{provider,model}` | ✅ |
| `max tool calls` control (wireframe extra) | `POST /runs` `config.max_tool_calls` | — | 🟡 not honored yet |
| "Initiate Startup" button | `POST /runs` | → `run_id`; then open SSE | ✅ |
| Agent Readiness rail (5 rows `Ready`) | SSE `agent_start`/`agent_end` | flip `idle→running→done` per agent | ✅ |
| Swarm Pipeline 5 nodes (Research…Presentation) | SSE `agent_start`/`agent_end` | node state + `node-active` glow on running | ✅ |
| LIVE_RUN_STREAM terminal | SSE all events | render `event.type` + `data.agent/focus/tool` per line | ✅ (coarse) |
| ‣ per-tool lines (`▸ github_list_issues ✓ 7 evidence`) | SSE `tool_call`/`tool_result` | tool, args, `evidence_count`, ok/warn | 🔴 **backend emits none yet** |
| "Active Swarms / System Load" metric card | `GET /stats` | `total_runs`, `in_flight`, `total_evidence` | ✅ |
| "Uptime 99.99%" card | `GET /health` / `/stats` | `uptime_seconds`, `total_tool_calls` | ✅ |
| 3 parallel sub-researchers callout | SSE `research_unit_start/end`, `research_diversified` | show the 3 units firing | 🟡 events exist; design a 3-lane view |

**Animations to keep:** `flow` connector between nodes, `fadeInUp` stagger, `node-active` glow,
terminal auto-scroll. Just swap the data source; don't touch the CSS.

---

## 2. Page: **Dashboard** — Mission Control

Existing widgets (labels from the design): Live Autonomous Run, Autonomous Agent Fleet (Active
Agent / Research Phase / Reasoning / Progress / Awaiting predecessor), Startup Viability +
Best/Expected/Worst case scores + Confidence, Agent Debate, Startup DNA, Evidence Intelligence,
Execution Stream, Artifact Factory, Company Replay, System Health, Living Network.

| Widget | Bind to | Field | Status |
|---|---|---|---|
| Live Autonomous Run / Active Agent / Progress | `GET /runs` + active run's SSE | `runs[]`, `current_agent`, stage states | ✅ (use SSE for the active one) |
| Autonomous Agent Fleet rows | SSE `agent_*` of the active run | per-agent status | ✅ |
| **Startup Viability** + score | `GET /runs/{id}/score` | `overall` (0–10), `verdict`, `grounded` | ✅ |
| Best / Expected / Worst case scores | `GET /runs/{id}/score` | `dimensions[].{name,score}` (5 dims) — map to the 3 cards or replace with the 5 dims | ✅ (5 dims, not 3 cases) |
| Confidence | `GET /runs/{id}/debate` | `confidence` (0–1) | ✅ |
| **Agent Debate** | `GET /runs/{id}/debate` | `verdict`, `build_case[]`, `risk_case[]`, `rationale` | ✅ |
| Startup DNA / Evidence Intelligence | `GET /runs/{id}/explain` + research | `explain.overall_confidence`, `features[]`; `research.evidence` | ✅ |
| Execution Stream | `GET /runs/{id}/artifacts/execution` | `backlog[]`, `sprints[]`, `roadmap` | ✅ |
| Artifact Factory tiles | `GET /runs/{id}` | `artifacts[]` (which are ready) | ✅ |
| System Health | `GET /health` / `/stats` | `status`, `by_status`, `uptime_seconds` | ✅ |
| Recent runs / status badges | `GET /runs` | `runs[].{run_id,idea,status,model}` | ✅ |
| **Company Replay** | replay a finished run's stored events | scrub persisted `events` | 🔴 `GET /runs/{id}/replay` not built (T1.5) |
| **Living Network** (graph) | traceability edges | source→pain→requirement→arch | 🔴 Evidence Graph not built (T2.1) |

> The "Best/Expected/Worst case" framing in the mock is decorative — back it with the **5 real
> Startup-Score dimensions** (Market Opportunity, Competitive Whitespace, Technical Feasibility,
> Monetization, Founder Velocity). Keep the 3-card visual or add two cards; your call, no redesign.

---

## 3. Page: **Artifacts** — Intelligence Vault

Existing panels: artifact rail (Research Brief, Market Analysis, PRD, Technical Design, Roadmap,
Investor Memo, Pitch Deck) with status + confidence + quality; center tabs (Overview / Evidence /
Versions); panels for Executive Summary, Key Intelligence Findings, Validated Pain Points, Market
Sizing, Competitor Matrix, Feature Priority Matrix, User Stories, Product Goals, Execution
Timeline, "Why This Exists", Evidence Traceability, Startup DNA Contribution, Agent Contributors,
Version History.

| Panel | Bind to | Field | Status |
|---|---|---|---|
| Artifact rail items | `GET /runs/{id}` | `artifacts[]` ready-state; badge unbuilt as `Queued` | ✅ |
| Render any artifact (Markdown) | `GET /runs/{id}/artifacts/{name}?format=md` | `react-markdown` | ✅ |
| Render any artifact (typed) | `GET /runs/{id}/artifacts/{name}` | JSON shapes in API_CONTRACT §5 | ✅ |
| **Validated Pain Points** | `…/artifacts/research` | `pain_points[].{text,severity,source_evidence[]}` | ✅ |
| **Competitor Matrix** | `…/artifacts/research` | `competitors[].{name,url,features,pricing}` | ✅ |
| **Market Sizing** | `…/artifacts/research` | `market_size` (string) | ✅ |
| **Feature Priority Matrix** / User Stories / Product Goals | `…/artifacts/prd` | `features[].{title,priority,description}`, `requirements[]`, `personas[]` | ✅ |
| **Execution Timeline** | `…/artifacts/execution` | `backlog[]`, `sprints[]`, `roadmap` | ✅ |
| Technical Design + **architecture diagram** | `…/artifacts/trd` + `?format=mermaid` | `data_model`, `api_spec`, `stack`; Mermaid text | 🟡 text returns; **render with mermaid.js** (not just show source) |
| **Startup DNA Contribution / Quality / Confidence badges** | `GET /runs/{id}/score` | `dimensions[]`, `overall` | ✅ |
| **"Why This Exists"** (per artifact/feature) | `GET /runs/{id}/explain` | `features[].{why,inspired_by,confidence,evidence[]}` | ✅ |
| **Evidence Traceability** / inline citations | `explain.features[].evidence[]` + `prd.sources` + `research.evidence` | render each claim's `Evidence.{source,url,title}` as a **clickable link** | 🟡 data is there; build the citation link component (typed render, not md) |
| Agent Debate panel | `GET /runs/{id}/debate` | as §2 | ✅ |
| Download MD / JSON buttons | `?format=md` + plain JSON | wire two buttons | 🟡 endpoints exist; add buttons |
| Version History | — | only one version persisted today | 🔴 versioning not in backend |
| Active Trace / "Living network" graph | traceability edges | — | 🔴 Evidence Graph (T2.1) |

> **Citations are the "real work" proof** (WIREFRAMES original intent). All the data exists
> (`Evidence` on pains, `PRD.sources`, `explain.features[].evidence`). Render the **typed JSON**
> for at least PRD requirements + Explain so each claim links to `Evidence.url`. This is the
> highest-value bind on this page.

---

## 4. Page: **System** — runtime & providers

Existing widgets: Provider Access, model name, System Health / "All checks passed", Current Run
Cost, Efficiency Score, Latency Distribution, Memory Usage, Tool Activity Heatmap, Activity 24h,
Audit Log, Compliance, Live dependency graph, Overall Assessment.

| Widget | Bind to | Field | Status |
|---|---|---|---|
| Runtime banner / model in use | `GET /health` / `GET /models` | `runtime`, `default.{provider,model}` | ✅ |
| **Provider Access** | `GET /providers` | `providers[].{label,enabled,key_env}`, `resolved` | ✅ |
| Model catalog | `GET /models` | `providers[].models[]` (+ `tools` flag) | ✅ |
| System Health / "All checks passed" | `GET /health` | `status`, `uptime_seconds` | ✅ |
| Run stats (totals, by-status) | `GET /stats` | `total_runs`, `by_status`, `in_flight`, `total_evidence`, `total_tool_calls` | ✅ |
| Prometheus link | `/metrics` | raw Prometheus text | ✅ |
| **Current Run Cost** | — | token/credit cost per run | 🔴 not tracked (ask P1 for a cost field) |
| **Latency Distribution / Memory Usage / Efficiency** | — | per-call latency, RSS | 🔴 not exposed (ask P1 to add to `/stats` or `/metrics`) |
| **Tool Activity Heatmap** | needs per-tool counts | `aps_tool_calls_total{tool}` exists in Prometheus | 🟡 parse `/metrics`, or ask P1 for a JSON `/stats/tools` |
| Audit Log / Compliance | — | structured audit trail | 🔴 not built |
| Live dependency graph | traceability edges | — | 🔴 Evidence Graph (T2.1) |

---

## 5. Backend additions to **request from P1** (don't build in React)

Ordered by demo value (see `remaining.md`). These are the only things blocking the design from
being fully live:

1. 🔴 **`tool_call` / `tool_result` SSE events** — per-tool, with `tool`, `args`,
   `evidence_count`, `duration_ms`, ok/warn. Unblocks the Pipeline **live tool stream** and live
   counters. (Contract already specifies them — see API_CONTRACT §3 "promised but not emitted".)
2. 🔴 **Live evidence event** (or evidence on `tool_result`) — so the Pipeline **evidence list**
   fills during the run, not only after `artifact_ready`.
3. 🔴 **Traceability edges** on the `composition` event (source→pain→requirement→arch) — unblocks
   **Evidence Graph / Living Network / Live dependency graph** (3 widgets across pages).
4. 🔴 **`GET /runs/{id}/replay`** (stream stored events at a speed) — unblocks **Company Replay**.
5. 🟡 **`GET /runs/{id}` to match the contract** — add `current_agent`, `started_at`/`finished_at`,
   `artifacts` as a nested object (today it's a flat record; you currently fetch artifacts
   separately, which works but isn't the contract).
6. 🟡 **`config.max_tool_calls`** honored in `POST /runs`.
7. 🔴 **Cost / latency / memory / per-tool metrics** in `/stats` (or a `/stats/tools`) for the
   System page's cost/heatmap/latency widgets.

Until each lands, leave that widget in its **empty/loading state** (the design already has
`Awaiting predecessor` / `No evidence generated yet` / `No tasks executed yet` placeholders —
use them; never hardcode fake numbers).

---

## 6. SSE events the backend emits **today** (bind these now)

`run_start` · `agent_start` · `agent_end` · `artifact_ready` · `composition` (counts) ·
`research_plan` · `research_unit_start` · `research_unit_end` · `research_diversified` ·
`research_keyless` · `tool_calls_total` · `error` · `run_degraded` · `run_complete` ·
`run_failed`. (Not yet: `tool_call`, `tool_result` — see §5.1.)

Honest run states to surface as badges: **complete** (real/keyless evidence) · **degraded**
(ran on the labeled stub — show `degrade_reason`) · **failed** (invalid key, fail-fast). A
degraded run must never render as "complete".

---

## 7. Visual / animation notes (unchanged — preserve)

- Instrument-panel aesthetic: monospace tool/agent names, status dots (green ok / amber warn /
  grey idle / blue running), glass panels, generous whitespace. Credibility = **visible live
  data**, not decoration.
- Keep the existing keyframes: `flow` (pipeline connector), `fadeInUp` (stagger), `node-active`
  (running glow), terminal mask/scroll.
- Every panel keeps an **empty / loading / error** state (graceful degradation NFR).
- Mobile: stack the two-column views vertically; timeline first.
- Colour is status-only. No new theme.

---

## 8. Component inventory (unchanged target)

```
<App> (BrowserRouter)
 ├ /          <PipelinePage>   run console + live SSE (§1)
 ├ /dashboard <DashboardPage>  mission control (§2)
 ├ /artifacts <ArtifactsPage>  intelligence vault (§3)
 └ /system    <SystemPage>     runtime & providers (§4)
shared: lib/api.ts (fetch + SSE parser + X-APS-Key), lib/types.ts, store.ts (zustand)
```
