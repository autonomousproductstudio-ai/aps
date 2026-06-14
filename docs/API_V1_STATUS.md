# API v1 — Implementation Status (the rich Frontend Data Contract)

This maps every endpoint in [backenddatacontract.md](backenddatacontract.md) to its actual
implementation in `src/aps/api/v1/`, and marks the **data provenance** of each:

- **real** — derived from live `StudioState` / an existing deterministic computation
  (`score_startup`, `run_debate`, `explain_prd`, `render_artifact`, `_stats()`).
- **derived** — real values reshaped + some fields filled deterministically.
- **mock** — deterministic fabricated data (seeded, never random) because the backend has no
  source for it. Honors the contract's §0.8 "never omit a key", §0.9 precision, §11 formats.

## How the two contracts relate

There are **two** API surfaces, intentionally:

| | Lean root API ([API_CONTRACT.md](API_CONTRACT.md)) | Rich v1 API (this doc) |
|---|---|---|
| Base | `/` | `/v1` |
| Auth | `X-APS-Key` header | JWT `Authorization: Bearer` (`POST /v1/auth/login`) |
| Envelope | raw JSON | `{success, data, meta}` |
| Streaming | SSE `/runs/{id}/events` | WebSocket `/v1/ws/runs/{id}/stream` |
| Consumed by | the shipped `frontend/` | the "mission control" frontend this contract targets |

The v1 app is a **mounted FastAPI sub-app** (`aps.api.v1.app:v1_app`, mounted at `/v1` by
`aps.api.main`). It shares the **single** orchestrator run engine with the root API, so a run
started via `POST /v1/runs` is the same real run the lean API would produce. The lean API and
the shipped frontend are unchanged.

Login for the seeded demo operator: `operator@aps.io` / `demo1234`.

## Endpoint status

| Endpoint | Status | Provenance | Notes |
|---|---|---|---|
| `POST /v1/auth/login` | ✅ | real | HMAC-SHA256 JWT (stdlib), in-memory users |
| `POST /v1/auth/signup` | ✅ | real | 7 roles validated; in-memory |
| `POST /v1/auth/forgot-password` | ✅ | real | always 200; mints reset token if user exists |
| `POST /v1/auth/reset-password` | ✅ | real | validates reset token |
| `GET /v1/system/status` | ✅ | mock | static platform pill |
| `GET /v1/agents` | ✅ | real | 5 fixed agents, all "ready" |
| `POST /v1/runs` | ✅ | real | starts a real orchestrator run; returns `RUN_NNNN` |
| `GET /v1/runs/{id}` | ✅ | derived | status/phase/progress/viability from `StudioState`; cpu/mem mock |
| `GET /v1/runs/{id}/agents` | ✅ | derived | status from artifacts produced; vitals mock |
| `GET /v1/runs/{id}/stream` | ✅ | real | seed from the run's `EventBus` history |
| `GET /v1/runs/{id}/artifacts` | ✅ | derived | real artifact/evidence/source counts; size/time mock |
| `GET /v1/runs/{id}/viability` | ✅ | derived | radar axes from `score_startup().dimensions` |
| `GET /v1/runs/{id}/debate` | ✅ | real | reshaped from `run_debate()` |
| `GET /v1/runs/{id}/evidence-graph` | ✅ | derived | source counts real; SVG layout fixed |
| `GET /v1/runs/{id}/dna` | ✅ | mock | fixed radial layout; core label from idea |
| `GET /v1/runs/{id}/timeline` | ✅ | mock | fixed 5-phase 0–100 |
| `GET /v1/artifacts/{id}/content` | ✅ | real | `render_artifact()` markdown. **Needs `?run=RUN_NNNN`** |
| `GET /v1/artifacts/{id}/evidence-traces` | ✅ | real | from `PainPoint.source_evidence`. **Needs `?run=`** |
| `GET /v1/artifacts/{id}/versions` | ✅ | mock | v1/v2 placeholder. **Needs `?run=`** |
| `GET /v1/system/health` | ✅ | derived | uptime/run/evidence/tool counts real; rest mock |
| `GET /v1/system/agents` | ✅ | mock | fleet vitals against empty state |
| `GET /v1/system/models` | ✅ | mock | 4 cards, deterministic latency/cost/tokens |
| `GET /v1/system/tools` | ✅ | derived | tool names from the real registry; metrics mock |
| `GET /v1/system/memory` | ✅ | derived | evidence layer node count real; rest fixed |
| `GET /v1/system/knowledge-graph` | ✅ | mock | fixed chain layout |
| `GET /v1/system/quality` | ✅ | mock | fixed quality rows |
| `GET /v1/system/cost` | ✅ | mock | fixed cost center |
| `GET /v1/system/observability` | ✅ | mock | 4×20 deterministic sparklines |
| `GET /v1/system/activity-heatmap` | ✅ | mock | 168 deterministic cells |
| `GET /v1/system/events` | ✅ | real | empty seed (WS pushes live events) |
| `GET /v1/system/telemetry/live` | ✅ | mock | no auth; memoryIndex grows per call |
| `WS /v1/ws/runs/{id}/stream` | ✅ | derived | seed + live events real; metric_tick mock |
| `WS /v1/ws/runs/global/stream` | ✅ | mock | terminal log feed |

## Known deviations from the literal contract

- **Artifact endpoints take `?run=RUN_NNNN`.** The contract's `/artifacts/:artifactId/...`
  has no run in the path, but artifacts only exist within a run, so the run id is passed as a
  query param.
- **Auth/users/mock telemetry are in-memory.** Lost on restart (by design — mock-grade).
- **Tokens are HMAC, not RS256 JWT**, and don't expire server-side (the advertised `expiresIn`
  is informational). Adequate for the mock surface; swap in a real IdP for production.
- **Live agent vitals, cost, memory layers, graph coordinates are fabricated** — the
  orchestrator does not track per-agent CPU/memory/cost/latency. Values are deterministic so
  the UI is stable and tests can assert them.

Tests: `tests/unit/test_api_v1.py` (26 cases — envelope, auth flow, key-presence per endpoint,
deterministic mocks, websocket).
