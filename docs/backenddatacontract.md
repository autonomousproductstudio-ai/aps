# APS Frontend — Backend Data Contract

> **Implementation status:** this rich contract is implemented behind the **`/v1`** prefix as a
> mounted FastAPI sub-app (`src/aps/api/v1/`). Every endpoint below is live; values are real
> where `StudioState` provides them and **deterministic mock** otherwise. See
> [API_V1_STATUS.md](API_V1_STATUS.md) for the per-endpoint real/derived/mock table, the demo
> login, and known deviations. The separate **lean** API (`/`, `X-APS-Key`, SSE) that the
> currently-shipped `frontend/` uses is documented in [API_CONTRACT.md](API_CONTRACT.md).

Complete specification of every API endpoint, data model, field format, WebSocket protocol, and integration rule the frontend requires. A backend developer should be able to implement every endpoint from this document alone.

---

## Table of Contents

0. [API Contract Conventions](#0-api-contract-conventions)
1. [Global / Shared Models](#1-global--shared-models)
2. [Authentication API](#2-authentication-api)
3. [Pipeline Page](#3-pipeline-page)
4. [Dashboard Page](#4-dashboard-page)
5. [Artifacts Page](#5-artifacts-page)
6. [System Page](#6-system-page)
7. [Auth Visualization Telemetry](#7-auth-visualization-telemetry)
8. [WebSocket / Streaming Protocol](#8-websocket--streaming-protocol)
9. [Live Metric Update Intervals](#9-live-metric-update-intervals)
10. [Enum Reference](#10-enum-reference)
11. [Field Format Rules](#11-field-format-rules)
12. [Error Handling](#12-error-handling)

---

## 0. API Contract Conventions

### 0.1 Base URL

```
https://api.aps.io/v1
```

All paths in this document are relative to this base. Example: `GET /agents` → `GET https://api.aps.io/v1/agents`

### 0.2 Content-Type

All requests and responses use:

```
Content-Type: application/json
Accept: application/json
```

The frontend sends `Content-Type: application/json` on every POST/PATCH/PUT. The backend must return `Content-Type: application/json` on every response, including errors.

### 0.3 Authentication

After login, every request includes a JWT Bearer token:

```
Authorization: Bearer <jwt_token>
```

The token is stored in `localStorage` under key `aps_token`. The frontend reads it on every fetch and attaches it automatically. Routes that do NOT require auth: `POST /auth/login`, `POST /auth/signup`, `POST /auth/forgot-password`, `POST /auth/reset-password`.

### 0.4 Standard Response Envelope

Every successful response is wrapped in a consistent envelope:

```json
{
  "success": true,
  "data": { ...payload },
  "meta": {
    "requestId": "req_abc123",
    "timestamp": "2026-06-11T08:30:00.000Z"
  }
}
```

- `success` — always `true` on 2xx responses
- `data` — the actual payload object or array (never null on success)
- `meta.requestId` — unique ID for debugging; frontend logs this on errors
- `meta.timestamp` — server time as ISO-8601 UTC

**List endpoints** additionally include pagination in `meta`:

```json
{
  "success": true,
  "data": [...],
  "meta": {
    "requestId": "req_abc123",
    "timestamp": "2026-06-11T08:30:00.000Z",
    "total": 8,
    "page": 1,
    "pageSize": 50
  }
}
```

The frontend does not currently implement pagination UI — send all records in a single page (`pageSize: 50` default is sufficient for all current lists).

### 0.5 Error Envelope

All 4xx and 5xx responses use this shape:

```json
{
  "success": false,
  "error": {
    "code":    "INVALID_CREDENTIALS",
    "message": "Email or password is incorrect.",
    "field":   "email"
  },
  "meta": {
    "requestId": "req_abc123",
    "timestamp": "2026-06-11T08:30:00.000Z"
  }
}
```

- `error.code` — machine-readable string the frontend switches on (see §12)
- `error.message` — human-readable string; may be shown directly in the UI
- `error.field` — optional; which form field caused the error (used for inline validation)

### 0.6 CORS

The frontend is served from:

```
http://localhost:3000        (development)
https://app.aps.io           (production)
```

The backend must include:

```
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Headers: Authorization, Content-Type
Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
Access-Control-Allow-Credentials: true
```

### 0.7 HTTP Status Codes Used by the Frontend

| Code | Meaning                              | Frontend action                          |
|------|--------------------------------------|------------------------------------------|
| 200  | OK                                   | Parse `data`, render                     |
| 201  | Created                              | Parse `data`, navigate                   |
| 400  | Bad request / validation error       | Show `error.message` on field            |
| 401  | Unauthenticated                      | Clear token, redirect to `/login`        |
| 403  | Forbidden                            | Show "Access denied" toast               |
| 404  | Not found                            | Show empty state or redirect             |
| 422  | Unprocessable (field validation)     | Show `error.field` + `error.message`     |
| 429  | Rate limited                         | Show "Too many requests" toast           |
| 500  | Server error                         | Show generic error toast                 |

### 0.8 Null vs Absent Fields

The frontend reads fields by name — missing fields cause silent `undefined` which breaks renders.

**Rule:** Every field defined in this contract **must** be present in the response. Use these defaults for "not yet available" data:

| Field type     | Not-available value |
|----------------|---------------------|
| `string`       | `""` (empty string) or `"—"` as noted per field |
| `number`       | `0`                 |
| `boolean`      | `false`             |
| `string[]`     | `[]`                |
| `object`       | `null`              |

**Never omit a key.** Send `"size": "—"` not a missing `size` key.

### 0.9 Number Precision

| Field              | Precision        | Example    |
|--------------------|------------------|------------|
| Percentages (0–100)| 1 decimal max    | `94.0`     |
| Cost in USD        | 2 decimals       | `12.40`    |
| Score (0–10)       | 1 decimal        | `8.7`      |
| Uptime %           | 2 decimals       | `99.98`    |
| tokensM (millions) | 3 decimals       | `0.847`    |
| Latency ms         | integer          | `1240`     |
| Count / integer    | integer          | `47`       |

### 0.10 Sorting Rules

| Endpoint                        | Sort order                              |
|---------------------------------|-----------------------------------------|
| `GET /runs/:runId/agents`       | Fixed order: research, product, arch, execution, present |
| `GET /runs/:runId/artifacts`    | By category order: Research → Product → Architecture → Execution → Business |
| `GET /runs/:runId/stream`       | Ascending by timestamp (oldest first)   |
| `GET /system/tools`             | By namespace order: Research → Product → Architecture → Execution |
| `GET /system/memory`            | Fixed order: working, run, artifact, evidence, kg, longterm |
| `GET /system/cost`              | Descending by `value` (highest cost first) |
| `GET /artifacts/:id/versions`   | Ascending (v1 first, current last)      |

---

## 1. Global / Shared Models

### 1.1 Agent

```ts
interface Agent {
  id:         string        // fixed IDs: "research" | "product" | "arch" | "execution" | "present"
  name:       string        // display name: "Research Agent"
  icon:       string        // Material Symbols Outlined icon name: "travel_explore"
  status:     AgentStatus   // see §10
  confidence: number        // integer 0–100; 0 when agent not yet started
  tools:      string[]      // tool names available to this agent, e.g. ["web_search","github_api"]
  toolLog:    string[]      // 2–4 recent action strings rotated in the card, e.g. ["GitHub · 34 repos analyzed"]
  output:     string        // one-line status: "Synthesizing evidence clusters" | "Awaiting Research output" | "Standby" | "Idle"
}
```

**JSON example:**
```json
{
  "id": "research",
  "name": "Research Agent",
  "icon": "travel_explore",
  "status": "running",
  "confidence": 94,
  "tools": ["web_search", "github_api", "reddit_api"],
  "toolLog": [
    "GitHub · 34 repos analyzed",
    "Reddit · 847 posts scraped",
    "Evidence cluster #3 forming…"
  ],
  "output": "Synthesizing evidence clusters"
}
```

### 1.2 StreamEvent

```ts
interface StreamEvent {
  t:     string     // wall-clock display string "HH:MM:SS", e.g. "14:02:01"
  agent: string     // short agent name: "Research" (not "Research Agent")
  icon:  string     // Material Symbol name
  type:  EventType  // see §10
  msg:   string     // full display message, 40–120 chars
  color: "cyan" | "green" | "amber"
}
```

**JSON example:**
```json
{
  "t": "14:02:23",
  "agent": "Research",
  "icon": "star",
  "type": "evidence",
  "msg": "Pain Point Cluster #1 · \"ATS false-negative bias\" formed",
  "color": "green"
}
```

**Color assignment rule:**
- `"green"` → type is `evidence` or `artifact`
- `"amber"` → type is `insight`
- `"cyan"`  → all other types (`start`, `tool`, `model`, `agent`)

### 1.3 User

```ts
interface User {
  id:        string   // "usr_abc123"
  name:      string   // "Rajat Nagda"
  email:     string   // "operator@aps.io"
  avatarUrl: string   // absolute URL to avatar image (served over HTTPS, CORS-open)
  role:      string   // one of the 7 signup roles
}
```

**JSON example:**
```json
{
  "id": "usr_abc123",
  "name": "Rajat Nagda",
  "email": "operator@aps.io",
  "avatarUrl": "https://cdn.aps.io/avatars/usr_abc123.jpg",
  "role": "Founder / CEO"
}
```

### 1.4 Run

```ts
interface Run {
  id:             string   // "RUN_0042" — prefix RUN_ + 4-digit zero-padded number
  label:          string   // "AI SaaS Resume Screening" — user's original prompt, truncated to 40 chars
  phase:          string   // current phase label: "Research Phase"
  progressPct:    number   // integer 0–100, drives the circular completion ring
  startedAt:      string   // ISO-8601 UTC: "2026-06-11T08:25:00.000Z"
  elapsedSec:     number   // integer seconds since startedAt — frontend increments locally after load
  viabilityScore: number   // 0.0–10.0 with 1 decimal, e.g. 8.7; 0 if not computed yet
  status:         "running" | "complete" | "failed" | "paused"
}
```

**JSON example:**
```json
{
  "id": "RUN_0042",
  "label": "AI SaaS Resume Screening",
  "phase": "Research Phase",
  "progressPct": 63,
  "startedAt": "2026-06-11T08:25:00.000Z",
  "elapsedSec": 312,
  "viabilityScore": 8.7,
  "status": "running"
}
```

---

## 2. Authentication API

### 2.1 POST `/auth/login`

**Request body:**
```json
{
  "email":    "operator@aps.io",
  "password": "MyPassword123",
  "remember": true
}
```

| Field      | Type    | Required | Validation                    |
|------------|---------|----------|-------------------------------|
| `email`    | string  | yes      | valid email format            |
| `password` | string  | yes      | min 1 char (server validates) |
| `remember` | boolean | no       | default `false` if absent     |

**Response 200:**
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expiresIn": 86400,
    "user": {
      "id": "usr_abc123",
      "name": "Rajat Nagda",
      "email": "operator@aps.io",
      "avatarUrl": "https://cdn.aps.io/avatars/usr_abc123.jpg",
      "role": "Founder / CEO"
    }
  },
  "meta": { "requestId": "req_001", "timestamp": "2026-06-11T08:30:00.000Z" }
}
```

- `token` — JWT string; frontend stores in `localStorage.aps_token`
- `expiresIn` — seconds until token expiry; frontend uses this to schedule silent refresh

**Response 401:**
```json
{
  "success": false,
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Email or password is incorrect.",
    "field": null
  },
  "meta": { "requestId": "req_001", "timestamp": "2026-06-11T08:30:00.000Z" }
}
```

**Frontend verification overlay sequence** (purely UI, no extra API calls needed):

```
Step 0 — "VERIFYING IDENTITY"          (shown ~0ms after submit)
Step 1 — "Checking Credentials..."     (shown ~360ms)
Step 2 — "Connecting Agents..."        (shown ~720ms)
Step 3 — "Syncing Workspace..."        (shown ~1080ms)
Step 4 — "Loading Intelligence Layer..." (shown ~1440ms)
         → "ACCESS GRANTED"            (shown ~1740ms)
         → navigate to /dashboard      (~2640ms total)
```

The API call happens immediately on submit. The step animation runs in parallel. If the API returns an error before the animation completes, the overlay is dismissed and the error is shown on the form.

---

### 2.2 POST `/auth/signup`

**Request body:**
```json
{
  "name":     "Rajat Nagda",
  "email":    "operator@aps.io",
  "password": "MyPassword123",
  "role":     "Founder / CEO"
}
```

| Field      | Type   | Required | Validation                   |
|------------|--------|----------|------------------------------|
| `name`     | string | yes      | min 2 chars, max 80 chars    |
| `email`    | string | yes      | unique, valid email format   |
| `password` | string | yes      | min 8 chars                  |
| `role`     | string | yes      | must be one of the 7 roles   |

**Valid role values (exact strings):**
```
"Founder / CEO"
"Product Manager"
"Engineering Lead"
"Design Lead"
"Researcher"
"Investor"
"Other"
```

**Response 201:**
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expiresIn": 86400,
    "user": {
      "id": "usr_xyz789",
      "name": "Rajat Nagda",
      "email": "operator@aps.io",
      "avatarUrl": "https://cdn.aps.io/avatars/default.jpg",
      "role": "Founder / CEO"
    }
  },
  "meta": { "requestId": "req_002", "timestamp": "2026-06-11T08:31:00.000Z" }
}
```

**Response 422 (email already exists):**
```json
{
  "success": false,
  "error": {
    "code": "EMAIL_ALREADY_EXISTS",
    "message": "An account with this email already exists.",
    "field": "email"
  },
  "meta": { ... }
}
```

**Frontend provisioning overlay sequence** (5 steps, ~400ms each):
```
"Operator Created"
"Agent Permissions Assigned"
"Workspace Provisioned"
"Memory Initialized"
"Mission Control Ready"
→ navigate to /dashboard
```

---

### 2.3 POST `/auth/forgot-password`

**Request body:**
```json
{ "email": "operator@aps.io" }
```

**Response 200** (always 200 even if email not found — security best practice):
```json
{
  "success": true,
  "data": {
    "message": "Recovery link transmitted",
    "expiresInMinutes": 15
  },
  "meta": { ... }
}
```

Frontend displays: `"Recovery link transmitted to operator@aps.io"` + `"Link expires in 15 minutes."`

---

### 2.4 POST `/auth/reset-password`

**Request body:**
```json
{
  "token":    "pwd_reset_token_from_email_link",
  "password": "NewPassword123"
}
```

| Field      | Type   | Required | Validation   |
|------------|--------|----------|--------------|
| `token`    | string | yes      | valid reset token |
| `password` | string | yes      | min 8 chars  |

**Response 200:**
```json
{
  "success": true,
  "data": { "message": "Password updated successfully." },
  "meta": { ... }
}
```

**Response 400 (token expired or invalid):**
```json
{
  "success": false,
  "error": {
    "code": "INVALID_RESET_TOKEN",
    "message": "This reset link has expired or is invalid.",
    "field": null
  },
  "meta": { ... }
}
```

---

## 3. Pipeline Page

**Route:** `/`

### 3.1 GET `/system/status`

Drives: nav system pill, hero status badge, agent count in pipeline card, metrics cards, footer version.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "status":       "Optimal",
    "agentCount":   5,
    "activeSwarms": 1204,
    "uptimePct":    99.9992,
    "apiStatus":    "Optimal",
    "version":      "4.0.2-STABLE"
  },
  "meta": { ... }
}
```

| Field          | Type   | Unit / Notes                                      |
|----------------|--------|---------------------------------------------------|
| `status`       | string | `"Optimal"` \| `"Degraded"` \| `"Offline"`        |
| `agentCount`   | number | integer — shown as `"5 Agents Available"`         |
| `activeSwarms` | number | integer — shown as `"1,204"` (frontend adds comma)|
| `uptimePct`    | number | 4 decimal float — shown as `"99.9992%"`           |
| `apiStatus`    | string | `"Optimal"` \| `"Degraded"`                       |
| `version`      | string | semver string — shown in footer                   |

---

### 3.2 GET `/agents`

Drives: pipeline card agent readiness list (right panel).

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "id": "research",  "name": "Research Agent",     "icon": "travel_explore", "status": "ready" },
    { "id": "product",   "name": "Product Agent",       "icon": "architecture",   "status": "ready" },
    { "id": "arch",      "name": "Architecture Agent",  "icon": "hub",            "status": "ready" },
    { "id": "execution", "name": "Execution Agent",     "icon": "data_object",    "status": "ready" },
    { "id": "present",   "name": "Presentation Agent",  "icon": "smart_display",  "status": "ready" }
  ],
  "meta": { ... }
}
```

On the Pipeline page all agents always show `"ready"` — this changes only once a run starts.

---

### 3.3 WebSocket `/ws/runs/global/stream`

Drives: live terminal stream (scrolling log) on Pipeline page.

**Each message (newline-delimited JSON):**
```json
{
  "type": "terminal_log",
  "payload": {
    "timestamp": "[12:46:10]",
    "runId":     "RUN_776",
    "message":   "Vector db sync complete.",
    "highlight": false
  }
}
```

| Field       | Type    | Notes                                       |
|-------------|---------|---------------------------------------------|
| `timestamp` | string  | Pre-formatted `"[HH:MM:SS]"` including brackets |
| `runId`     | string  | `"RUN_NNN"` format                          |
| `message`   | string  | log text, 20–80 chars                       |
| `highlight` | boolean | `true` → renders in cyan (`#a5e7ff`), `false` → 50% opacity |

---

### 3.4 POST `/runs`

Triggered when user clicks **"Initiate Startup"** button.

**Request body:**
```json
{ "prompt": "Build an AI SaaS for resume screening..." }
```

| Field    | Type   | Required | Notes                       |
|----------|--------|----------|-----------------------------|
| `prompt` | string | yes      | max 500 chars; the startup idea |

**Response 201:**
```json
{
  "success": true,
  "data": {
    "runId":  "RUN_0042",
    "status": "running"
  },
  "meta": { ... }
}
```

Frontend stores `runId` in state and navigates to `/dashboard?run=RUN_0042`.

---

## 4. Dashboard Page

**Route:** `/dashboard`

### 4.1 GET `/runs/:runId`

Drives: command header (run identity, elapsed timer, completion ring, active agent, system health bars, viability score).

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id":             "RUN_0042",
    "label":          "AI SaaS Resume Screening",
    "phase":          "Research Phase",
    "progressPct":    63,
    "startedAt":      "2026-06-11T08:25:00.000Z",
    "elapsedSec":     312,
    "viabilityScore": 8.7,
    "status":         "running",
    "activeAgentId":  "research",
    "systemHealth": {
      "cpuPct":       24,
      "memPct":       61,
      "apiUptimePct": 99
    }
  },
  "meta": { ... }
}
```

| Field                     | Type   | Frontend display            |
|---------------------------|--------|-----------------------------|
| `progressPct`             | number | SVG circle ring; integer    |
| `elapsedSec`              | number | seed for `MM:SS` counter; integer |
| `viabilityScore`          | number | `"8.7 / 10"` — 1 decimal   |
| `systemHealth.cpuPct`     | number | `"24%"` — integer           |
| `systemHealth.memPct`     | number | `"61%"` — integer           |
| `systemHealth.apiUptimePct` | number | `"99.9%"` — integer, displayed as `{n}.9%` |

---

### 4.2 GET `/runs/:runId/agents`

Drives: Agent Fleet grid (5 cards).

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id":          "research",
      "name":        "Research Agent",
      "icon":        "travel_explore",
      "status":      "running",
      "confidence":  94,
      "tools":       ["web_search", "github_api", "reddit_api"],
      "toolLog":     ["GitHub · 34 repos analyzed", "Reddit · 847 posts scraped", "Evidence cluster #3 forming…"],
      "output":      "Synthesizing evidence clusters",
      "currentTool": "GitHub · 34 repos analyzed"
    },
    {
      "id":          "product",
      "name":        "Product Agent",
      "icon":        "architecture",
      "status":      "queued",
      "confidence":  0,
      "tools":       ["prd_writer", "user_story_gen"],
      "toolLog":     [],
      "output":      "Awaiting Research output",
      "currentTool": null
    },
    {
      "id":          "arch",
      "name":        "Architecture Agent",
      "icon":        "hub",
      "status":      "queued",
      "confidence":  0,
      "tools":       ["diagram_gen", "openapi_spec", "c4_model"],
      "toolLog":     [],
      "output":      "Standby",
      "currentTool": null
    },
    {
      "id":          "execution",
      "name":        "Execution Agent",
      "icon":        "data_object",
      "status":      "queued",
      "confidence":  0,
      "tools":       ["code_gen", "test_runner", "ci_builder"],
      "toolLog":     [],
      "output":      "Standby",
      "currentTool": null
    },
    {
      "id":          "present",
      "name":        "Presentation Agent",
      "icon":        "smart_display",
      "status":      "idle",
      "confidence":  0,
      "tools":       ["deck_builder", "memo_writer", "pitch_scorer"],
      "toolLog":     [],
      "output":      "Idle",
      "currentTool": null
    }
  ],
  "meta": { ... }
}
```

- `toolLog` — array of 2–4 strings rotated every 2.6s in the running agent card; send `[]` for non-running agents
- `currentTool` — the most recently active tool log string; `null` if agent is not running

---

### 4.3 GET `/runs/:runId/stream` (initial seed)

Loads the initial batch of stream events into the Execution Stream panel on page mount. New events arrive via WebSocket (§8).

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "t":     "14:02:01",
      "agent": "Research",
      "icon":  "travel_explore",
      "type":  "start",
      "msg":   "Agent spawned — initializing evidence workspace",
      "color": "cyan"
    },
    {
      "t":     "14:02:23",
      "agent": "Research",
      "icon":  "star",
      "type":  "evidence",
      "msg":   "Pain Point Cluster #1 · \"ATS false-negative bias\" formed",
      "color": "green"
    }
  ],
  "meta": { "total": 10, ... }
}
```

**Query params the frontend may pass:**
- `?limit=50` — max events to return (default 50, always enough for initial load)
- `?type=tool` — filter by event type (when user clicks filter tab; frontend re-fetches)

---

### 4.4 GET `/runs/:runId/artifacts`

Drives: Artifact Factory panel (condensed 8-item list).

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id":         "research-brief",
      "name":       "Research Brief",
      "icon":       "travel_explore",
      "status":     "complete",
      "size":       "42 KB",
      "time":       "3m 12s",
      "confidence": 94,
      "evidence":   47,
      "color":      "green"
    },
    {
      "id":         "prd",
      "name":       "PRD v1.0",
      "icon":       "description",
      "status":     "building",
      "size":       "—",
      "time":       "—",
      "confidence": 0,
      "evidence":   0,
      "color":      "cyan"
    },
    {
      "id":         "openapi",
      "name":       "OpenAPI Spec",
      "icon":       "code",
      "status":     "queued",
      "size":       "—",
      "time":       "—",
      "confidence": 0,
      "evidence":   0,
      "color":      "muted"
    }
  ],
  "meta": { ... }
}
```

| Field        | Type   | Notes                                                    |
|--------------|--------|----------------------------------------------------------|
| `size`       | string | `"42 KB"` when complete; exact string `"—"` otherwise    |
| `time`       | string | `"3m 12s"` when complete; exact string `"—"` otherwise   |
| `confidence` | number | integer 0–100; send `0` when not started                 |
| `evidence`   | number | integer count; send `0` when not started                 |
| `color`      | string | `"green"` (complete) \| `"cyan"` (building) \| `"muted"` (queued) |

---

### 4.5 GET `/runs/:runId/viability`

Drives: Startup Intelligence radar chart and viability score.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "score": 8.7,
    "radarAxes": [
      { "label": "Market Opp.",   "value": 88, "angle": 270 },
      { "label": "Competition",   "value": 62, "angle": 342 },
      { "label": "Monetisation",  "value": 75, "angle": 54  },
      { "label": "Defensibility", "value": 71, "angle": 126 },
      { "label": "Exec. Speed",   "value": 82, "angle": 198 }
    ],
    "scenarios": [
      { "label": "Best Case",  "values": [95, 75, 85, 82, 90], "color": "#79ff5b", "opacity": 0.14 },
      { "label": "Expected",   "values": [88, 62, 75, 71, 82], "color": "#a5e7ff", "opacity": 0.22 },
      { "label": "Worst Case", "values": [60, 40, 50, 45, 55], "color": "#f59e0b", "opacity": 0.11 }
    ]
  },
  "meta": { ... }
}
```

| Field                    | Type     | Notes                                                    |
|--------------------------|----------|----------------------------------------------------------|
| `score`                  | number   | 1 decimal, 0.0–10.0                                      |
| `radarAxes[].value`      | number   | integer 0–100; used for the "Expected" polygon           |
| `radarAxes[].angle`      | number   | SVG angle in degrees; fixed per axis — backend can hardcode these |
| `scenarios[].values`     | number[] | same length and order as `radarAxes`; integer 0–100 each |
| `scenarios[].color`      | string   | hex string including `#`                                 |
| `scenarios[].opacity`    | number   | 2 decimal float                                          |

---

### 4.6 GET `/runs/:runId/debate`

Drives: Debate Chamber panel.

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "side": "Build",        "agent": "Research Agent", "point": "$8.4B TAM with proven pain — ATS false-negatives cost $50K/hire" },
    { "side": "Build",        "agent": "Product Agent",  "point": "No AI-native SMB solution; incumbents bloated & expensive" },
    { "side": "Don't Build",  "agent": "Risk Agent",     "point": "Workday & Greenhouse ship AI features Q3 — 6-month window only" },
    { "side": "Don't Build",  "agent": "Risk Agent",     "point": "Cold-start: need labelled CV corpus before training begins" },
    { "side": "Build",        "agent": "Research Agent", "point": "OSS models (Mistral) eliminate the training-data moat entirely" }
  ],
  "meta": { ... }
}
```

| Field   | Type   | Notes                                          |
|---------|--------|------------------------------------------------|
| `side`  | string | **Exact strings:** `"Build"` or `"Don't Build"` — apostrophe included |
| `agent` | string | Full agent name: `"Research Agent"`, `"Risk Agent"` |
| `point` | string | Argument text, 40–100 chars                    |

---

### 4.7 GET `/runs/:runId/evidence-graph`

Drives: Evidence Hub SVG network graph.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "nodes": [
      { "id": "github", "label": "GitHub",         "x": 200, "y": 55,  "type": "source", "count": 34 },
      { "id": "reddit", "label": "Reddit",         "x": 75,  "y": 130, "type": "source", "count": 12 },
      { "id": "hn",     "label": "HN",             "x": 325, "y": 130, "type": "source", "count": 8  },
      { "id": "ph",     "label": "Prod Hunt",      "x": 75,  "y": 240, "type": "source", "count": 12 },
      { "id": "papers", "label": "Papers",         "x": 325, "y": 240, "type": "source", "count": 3  },
      { "id": "pain1",  "label": "ATS False Neg.", "x": 200, "y": 148, "type": "pain",   "count": 0  },
      { "id": "pain2",  "label": "Keyword Bias",   "x": 130, "y": 210, "type": "pain",   "count": 0  },
      { "id": "pain3",  "label": "5h+ Manual",     "x": 270, "y": 210, "type": "pain",   "count": 0  },
      { "id": "req1",   "label": "Semantic Score", "x": 200, "y": 275, "type": "req",    "count": 0  },
      { "id": "arch1",  "label": "LLM Scoring",    "x": 145, "y": 330, "type": "arch",   "count": 0  },
      { "id": "road1",  "label": "MVP Sprint 1",   "x": 255, "y": 330, "type": "roadmap","count": 0  }
    ],
    "edges": [
      ["github","pain1"], ["reddit","pain2"], ["hn","pain1"], ["ph","pain3"], ["papers","pain1"],
      ["pain1","req1"],   ["pain2","req1"],   ["pain3","req1"],
      ["req1","arch1"],   ["req1","road1"]
    ]
  },
  "meta": { ... }
}
```

| Field          | Type              | Notes                                             |
|----------------|-------------------|---------------------------------------------------|
| `nodes[].x/y`  | number            | SVG viewport coordinates (viewBox 0 0 400 400); backend can hardcode these layout constants |
| `nodes[].type` | string            | `"source"` \| `"pain"` \| `"req"` \| `"arch"` \| `"roadmap"` — drives node color |
| `nodes[].count`| number            | integer; shown inside source nodes; 0 for derived nodes |
| `edges`        | `[string,string][]`| `[fromId, toId]` pairs; `fromId` and `toId` must exist in `nodes` |

---

### 4.8 GET `/runs/:runId/dna`

Drives: Company DNA radial graph.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "nodes": [
      { "id": "core",     "label": "AI SaaS",       "x": 200, "y": 170, "r": 28, "core": true  },
      { "id": "market",   "label": "Market",         "x": 200, "y": 60,  "r": 19, "core": false },
      { "id": "users",    "label": "Users",          "x": 315, "y": 115, "r": 17, "core": false },
      { "id": "compete",  "label": "Competitors",    "x": 315, "y": 225, "r": 17, "core": false },
      { "id": "mono",     "label": "Revenue",        "x": 200, "y": 282, "r": 17, "core": false },
      { "id": "arch",     "label": "Architecture",   "x": 85,  "y": 225, "r": 17, "core": false },
      { "id": "features", "label": "Features",       "x": 85,  "y": 115, "r": 17, "core": false }
    ],
    "edges": [
      { "a": "core", "b": "market"   },
      { "a": "core", "b": "users"    },
      { "a": "core", "b": "compete"  },
      { "a": "core", "b": "mono"     },
      { "a": "core", "b": "arch"     },
      { "a": "core", "b": "features" },
      { "a": "market", "b": "users"  },
      { "a": "users",  "b": "features" }
    ]
  },
  "meta": { ... }
}
```

| Field         | Type    | Notes                                      |
|---------------|---------|--------------------------------------------|
| `nodes[].r`   | number  | SVG circle radius; `core` node is larger   |
| `nodes[].core`| boolean | `true` for exactly one central node        |
| `edges[].a/b` | string  | node `id` values; order doesn't matter     |

---

### 4.9 GET `/runs/:runId/timeline`

Drives: Company Replay horizontal timeline bar.

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "label": "Research",     "icon": "travel_explore", "start": 0,  "end": 30  },
    { "label": "Product",      "icon": "architecture",   "start": 30, "end": 50  },
    { "label": "Architecture", "icon": "hub",            "start": 50, "end": 70  },
    { "label": "Execution",    "icon": "data_object",    "start": 70, "end": 90  },
    { "label": "Presentation", "icon": "smart_display",  "start": 90, "end": 100 }
  ],
  "meta": { ... }
}
```

| Field   | Type   | Notes                                                        |
|---------|--------|--------------------------------------------------------------|
| `start` | number | integer 0–100 — percentage offset from left for CSS `left:` |
| `end`   | number | integer 0–100 — `width = end - start` percent               |
| Phases must cover exactly 0–100 with no gaps or overlaps     |

---

## 5. Artifacts Page

**Route:** `/artifacts`

### 5.1 GET `/runs/:runId/artifacts` (full detail)

Drives: left navigator list + center viewer header.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id":            "research-brief",
      "name":          "Research Brief",
      "icon":          "travel_explore",
      "category":      "Research",
      "status":        "complete",
      "confidence":    94,
      "quality":       9.1,
      "size":          "42 KB",
      "genTime":       "3m 12s",
      "agents":        ["Research Agent"],
      "evidenceCount": 47,
      "sourceCount":   8,
      "versions":      2,
      "generatedAt":   "14:03:12",
      "summary":       "Confirmed $8.4B TAM. 47 evidence nodes. ATS false-negative rate 75%. No AI-native SMB solution."
    },
    {
      "id":            "trd",
      "name":          "Technical Design",
      "icon":          "hub",
      "category":      "Architecture",
      "status":        "building",
      "confidence":    72,
      "quality":       0,
      "size":          "—",
      "genTime":       "—",
      "agents":        ["Architecture Agent"],
      "evidenceCount": 0,
      "sourceCount":   0,
      "versions":      0,
      "generatedAt":   "—",
      "summary":       "Generating system architecture, API design, and database schema."
    }
  ],
  "meta": { ... }
}
```

| Field          | Type     | Not-started value | Notes                                       |
|----------------|----------|-------------------|---------------------------------------------|
| `confidence`   | number   | `0`               | integer 0–100                               |
| `quality`      | number   | `0`               | 1 decimal 0.0–10.0                          |
| `size`         | string   | `"—"`             | e.g. `"42 KB"`, `"18 KB"`, `"127 MB"`      |
| `genTime`      | string   | `"—"`             | `"3m 12s"` format: `{m}m {s}s`             |
| `evidenceCount`| number   | `0`               | integer                                     |
| `sourceCount`  | number   | `0`               | integer                                     |
| `versions`     | number   | `0`               | integer                                     |
| `generatedAt`  | string   | `"—"`             | `"HH:MM:SS"` wall-clock string              |
| `agents`       | string[] | `[]`              | full agent names in creation order          |
| `summary`      | string   | `"Awaiting..."`   | 1–2 sentences shown under artifact name     |

---

### 5.2 GET `/artifacts/:artifactId/content`

Drives: center panel rich viewer (rendered as markdown).

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id":     "research-brief",
    "format": "markdown",
    "body":   "# Research Brief\n\n## Market Size\n\nTotal Addressable Market: **$8.4B**..."
  },
  "meta": { ... }
}
```

| Field    | Type   | Notes                                                    |
|----------|--------|----------------------------------------------------------|
| `format` | string | `"markdown"` \| `"json"` \| `"yaml"` — frontend uses `react-markdown` for markdown |
| `body`   | string | raw content string; not pre-escaped; may contain newlines, headers, bold |

---

### 5.3 GET `/artifacts/:artifactId/evidence-traces`

Drives: right panel Evidence Trace tab — expandable claim list with sources.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "claimId": "tam",
      "label":   "$8.4B total addressable market",
      "sources": [
        {
          "platform": "Market Reports",
          "icon":     "bar_chart",
          "count":    4,
          "examples": [
            "Gartner HRTech 2024 Report",
            "IDC Recruitment Software Forecast",
            "Grand View Research ATS Market",
            "Allied Market Research HR Tech"
          ]
        },
        {
          "platform": "GitHub",
          "icon":     "code",
          "count":    12,
          "examples": [
            "OSS ATS repos: combined star growth +340% YoY",
            "hiring-tools: 12k stars",
            "+10 more"
          ]
        }
      ]
    }
  ],
  "meta": { ... }
}
```

| Field               | Type     | Notes                                                    |
|---------------------|----------|----------------------------------------------------------|
| `claimId`           | string   | slug, used as React key                                  |
| `label`             | string   | full claim sentence shown as accordion header            |
| `sources[].platform`| string   | display name shown as badge                              |
| `sources[].icon`    | string   | Material Symbol name                                     |
| `sources[].count`   | number   | integer — shown as `"{n} sources"`                       |
| `sources[].examples`| string[] | 2–4 strings shown in expanded view; last item can be `"+N more"` |

---

### 5.4 GET `/artifacts/:artifactId/versions`

Drives: right panel Versions tab.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "label":   "v1 — Initial Draft",
      "time":    "14:03:12",
      "note":    "First pass from raw evidence",
      "current": false
    },
    {
      "label":   "v2 — Refined",
      "time":    "14:06:45",
      "note":    "Competitor data cross-validated",
      "current": true
    }
  ],
  "meta": { ... }
}
```

| Field     | Type    | Notes                                                |
|-----------|---------|------------------------------------------------------|
| `label`   | string  | `"v{n} — {description}"` format                      |
| `time`    | string  | `"HH:MM:SS"` wall-clock string                       |
| `current` | boolean | exactly one item must have `current: true`; rest `false` |

---

## 6. System Page

**Route:** `/system`

### 6.1 GET `/system/health`

Drives: global status bar (8 stat tiles + uptime + run info).

**Response 200:**
```json
{
  "success": true,
  "data": {
    "agentsActive":  "5/5",
    "toolsOnline":   "84/84",
    "memoryLoad":    "2.4 GB",
    "modelsReady":   "4/4",
    "evidenceItems": "2,841",
    "runsToday":     12,
    "tokensUsed":    230400,
    "runtimeSec":    312,
    "uptimePct":     99.98,
    "systemVersion": "4.0.2-STABLE",
    "statusLabel":   "ALL SYSTEMS OPERATIONAL",
    "activeRunId":   "RUN_0042"
  },
  "meta": { ... }
}
```

| Field           | Type   | Notes                                                           |
|-----------------|--------|-----------------------------------------------------------------|
| `agentsActive`  | string | Pre-formatted `"active/total"` string — frontend renders as-is |
| `toolsOnline`   | string | Pre-formatted `"online/total"` string                           |
| `memoryLoad`    | string | Pre-formatted with unit: `"2.4 GB"`                            |
| `modelsReady`   | string | Pre-formatted `"ready/total"` string                           |
| `evidenceItems` | string | Pre-formatted with comma separator: `"2,841"`                  |
| `runsToday`     | number | integer                                                         |
| `tokensUsed`    | number | raw integer — frontend displays as `"{n}K"` by dividing by 1000 |
| `runtimeSec`    | number | integer — frontend seeds the live MM:SS timer from this         |
| `uptimePct`     | number | 2 decimal float — displayed as `"99.98"`                       |

---

### 6.2 GET `/system/agents`

Drives: Agent Fleet panel + inspection drawer.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id":             "research",
      "name":           "Research Agent",
      "icon":           "travel_explore",
      "status":         "running",
      "confidence":     94,
      "tools":          ["web_search", "github_api", "reddit_api"],
      "toolLog":        ["GitHub · 34 repos analyzed", "Reddit · 847 posts scraped"],
      "output":         "Synthesizing evidence clusters",
      "memPct":         72,
      "tasksCompleted": 47,
      "currentJob":     "Evidence synthesis — cluster #3",
      "latencyMs":      230,
      "successRate":    97.4,
      "lastExec":       "14:03:12",
      "tokensUsed":     128400
    },
    {
      "id":             "product",
      "name":           "Product Agent",
      "icon":           "architecture",
      "status":         "queued",
      "confidence":     0,
      "tools":          ["prd_writer", "user_story_gen"],
      "toolLog":        [],
      "output":         "Awaiting Research output",
      "memPct":         18,
      "tasksCompleted": 12,
      "currentJob":     "Awaiting Research output",
      "latencyMs":      0,
      "successRate":    98.1,
      "lastExec":       "13:58:44",
      "tokensUsed":     42100
    }
  ],
  "meta": { ... }
}
```

| Field            | Type   | Notes                                                       |
|------------------|--------|-------------------------------------------------------------|
| `memPct`         | number | integer 0–100 — memory utilization %                        |
| `tasksCompleted` | number | integer — cumulative tasks across all runs                  |
| `latencyMs`      | number | integer ms; send `0` for non-running agents                 |
| `successRate`    | number | 1 decimal, e.g. `97.4`; includes all-time history          |
| `lastExec`       | string | `"HH:MM:SS"` of last task completion                        |
| `tokensUsed`     | number | integer raw token count for this run                        |

---

### 6.3 GET `/system/models`

Drives: Model Orchestration panel (4 model cards).

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id":          "claude",
      "name":        "Claude Sonnet 4.6",
      "provider":    "Anthropic",
      "icon":        "psychology",
      "available":   true,
      "latencyMs":   1240,
      "tokensM":     0.847,
      "costUSD":     12.40,
      "successRate": 99.2,
      "primary":     true,
      "color":       "#a5e7ff"
    },
    {
      "id":          "gpt4o",
      "name":        "GPT-4o",
      "provider":    "OpenAI",
      "icon":        "smart_toy",
      "available":   true,
      "latencyMs":   1820,
      "tokensM":     0.243,
      "costUSD":     4.86,
      "successRate": 98.7,
      "primary":     false,
      "color":       "#79ff5b"
    },
    {
      "id":          "gemini",
      "name":        "Gemini 1.5 Pro",
      "provider":    "Google",
      "icon":        "auto_awesome",
      "available":   true,
      "latencyMs":   2140,
      "tokensM":     0.091,
      "costUSD":     1.37,
      "successRate": 97.3,
      "primary":     false,
      "color":       "#bbc9cf"
    },
    {
      "id":          "local",
      "name":        "Mistral 7B",
      "provider":    "Local",
      "icon":        "memory",
      "available":   true,
      "latencyMs":   380,
      "tokensM":     0.412,
      "costUSD":     0.00,
      "successRate": 94.1,
      "primary":     false,
      "color":       "#f59e0b"
    }
  ],
  "meta": { ... }
}
```

| Field         | Type    | Notes                                                       |
|---------------|---------|-------------------------------------------------------------|
| `latencyMs`   | number  | integer — p50 response latency for this run                 |
| `tokensM`     | number  | 3 decimal float — millions of tokens; shown as `"847K"` by frontend |
| `costUSD`     | number  | 2 decimal float — USD cost this run                         |
| `successRate` | number  | 1 decimal float — % success over this run                   |
| `primary`     | boolean | exactly one model has `true`; drives "PRIMARY" badge        |
| `color`       | string  | hex with `#` — used for sparkline and accent in card        |

---

### 6.4 GET `/system/tools`

Drives: Tool Ecosystem grouped list.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "ns":    "Research",
      "color": "#a5e7ff",
      "tools": [
        { "name": "web_search",  "inv": 847, "succ": 98.4, "avgMs": 1200, "last": "14:03:09", "health": "healthy" },
        { "name": "github_api",  "inv": 412, "succ": 99.1, "avgMs": 840,  "last": "14:02:58", "health": "healthy" },
        { "name": "reddit_api",  "inv": 231, "succ": 97.8, "avgMs": 620,  "last": "14:02:45", "health": "healthy" },
        { "name": "hn_scraper",  "inv": 89,  "succ": 96.2, "avgMs": 980,  "last": "14:02:31", "health": "healthy" },
        { "name": "paper_fetch", "inv": 34,  "succ": 100,  "avgMs": 1840, "last": "14:02:18", "health": "healthy" }
      ]
    },
    {
      "ns":    "Architecture",
      "color": "#bbc9cf",
      "tools": [
        { "name": "diagram_gen",  "inv": 3, "succ": 100, "avgMs": 3200, "last": "—", "health": "standby" },
        { "name": "openapi_spec", "inv": 2, "succ": 100, "avgMs": 5100, "last": "—", "health": "standby" },
        { "name": "c4_model",     "inv": 1, "succ": 100, "avgMs": 2800, "last": "—", "health": "standby" }
      ]
    }
  ],
  "meta": { ... }
}
```

| Field        | Type   | Not-used value | Notes                                       |
|--------------|--------|----------------|---------------------------------------------|
| `inv`        | number | `0`            | integer invocation count                    |
| `succ`       | number | `0`            | 1 decimal success rate %; `0` if never used |
| `avgMs`      | number | `0`            | integer ms average; `0` if never used       |
| `last`       | string | `"—"`          | `"HH:MM:SS"` or exact string `"—"`          |
| `health`     | string | `"standby"`    | `"healthy"` \| `"standby"` \| `"degraded"` \| `"offline"` |

---

### 6.5 GET `/system/memory`

Drives: Memory Engine panel (6 layer rows).

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "id": "working",  "name": "Working Memory",  "icon": "memory_alt",   "size": "2.4 MB",  "nodes": 127,   "speed": 12,  "pct": 72, "color": "#a5e7ff", "note": "Current run context"    },
    { "id": "run",      "name": "Run Memory",       "icon": "history",      "size": "14.2 MB", "nodes": 847,   "speed": 28,  "pct": 45, "color": "#a5e7ff", "note": "Session history"         },
    { "id": "artifact", "name": "Artifact Memory",  "icon": "inventory_2",  "size": "8.1 MB",  "nodes": 312,   "speed": 18,  "pct": 31, "color": "#79ff5b", "note": "Generated documents"     },
    { "id": "evidence", "name": "Evidence Memory",  "icon": "device_hub",   "size": "31.7 MB", "nodes": 2841,  "speed": 45,  "pct": 88, "color": "#f59e0b", "note": "Source intelligence"     },
    { "id": "kg",       "name": "Knowledge Graph",  "icon": "scatter_plot", "size": "5.6 MB",  "nodes": 493,   "speed": 22,  "pct": 62, "color": "#a5e7ff", "note": "Concept relationships"   },
    { "id": "longterm", "name": "Long-Term Memory", "icon": "cloud_sync",   "size": "127 MB",  "nodes": 18400, "speed": 180, "pct": 15, "color": "#bbc9cf", "note": "Cross-run learnings"     }
  ],
  "meta": { ... }
}
```

| Field   | Type   | Notes                                                     |
|---------|--------|-----------------------------------------------------------|
| `size`  | string | Pre-formatted with unit: `"2.4 MB"`, `"127 MB"` — frontend renders as-is |
| `nodes` | number | integer node/document count                               |
| `speed` | number | integer ms — retrieval latency                            |
| `pct`   | number | integer 0–100 — capacity utilization; drives progress bar |
| `color` | string | hex — drives progress bar fill color                      |
| `note`  | string | one-line description shown as subtext                     |

---

### 6.6 GET `/system/knowledge-graph`

Drives: Knowledge Graph vertical chain visualization.

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "id": "idea",     "label": "Idea",         "y": 48,  "side": [] },
    { "id": "evidence", "label": "Evidence",     "y": 128, "side": [{"label": "GitHub ×34", "dx": 120}, {"label": "Reddit ×24", "dx": -120}] },
    { "id": "insights", "label": "Insights",     "y": 208, "side": [{"label": "TAM $8.4B",  "dx": 120}, {"label": "Pain ×3",    "dx": -110}] },
    { "id": "req",      "label": "Requirements", "y": 288, "side": [{"label": "14 Stories", "dx": 115}, {"label": "7 Features", "dx": -115}] },
    { "id": "arch",     "label": "Architecture", "y": 368, "side": [{"label": "API Design", "dx": 110}, {"label": "DB Schema",  "dx": -110}] },
    { "id": "roadmap",  "label": "Roadmap",      "y": 448, "side": [{"label": "Sprint 1",   "dx": 105}, {"label": "Sprint 2",   "dx": -100}] },
    { "id": "pitch",    "label": "Pitch",        "y": 528, "side": [{"label": "Deck",        "dx": 80},  {"label": "Memo",       "dx": -80}]  }
  ],
  "meta": { ... }
}
```

| Field       | Type   | Notes                                                           |
|-------------|--------|-----------------------------------------------------------------|
| `y`         | number | SVG y coordinate; fixed layout — backend can hardcode          |
| `side`      | array  | satellite label objects; `dx` is horizontal offset from center node |
| `side[].dx` | number | positive = right side, negative = left side                    |

---

### 6.7 GET `/system/quality`

Drives: Quality Evaluation panel (one row per completed artifact).

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "name": "Research Brief",  "score": 9.3, "coverage": 94, "hRisk": 2, "depth": 9.1 },
    { "name": "Market Analysis", "score": 8.8, "coverage": 91, "hRisk": 3, "depth": 8.7 },
    { "name": "PRD v1.0",        "score": 8.4, "coverage": 87, "hRisk": 5, "depth": 8.2 },
    { "name": "Roadmap Q1–Q3",  "score": 8.6, "coverage": 88, "hRisk": 4, "depth": 8.5 }
  ],
  "meta": { ... }
}
```

| Field      | Type   | Notes                                          |
|------------|--------|------------------------------------------------|
| `score`    | number | 1 decimal 0.0–10.0 — overall quality score     |
| `coverage` | number | integer 0–100 — evidence coverage %            |
| `hRisk`    | number | integer 0–10 — hallucination risk (lower = better) |
| `depth`    | number | 1 decimal 0.0–10.0 — research depth score      |

---

### 6.8 GET `/system/cost`

Drives: Cost Center breakdown list.

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "label": "Claude Sonnet 4.6",  "value": 12.40, "tokens": "847K",  "category": "Model" },
    { "label": "GPT-4o (fallback)",  "value": 4.86,  "tokens": "243K",  "category": "Model" },
    { "label": "Gemini 1.5 Pro",     "value": 1.37,  "tokens": "91K",   "category": "Model" },
    { "label": "API calls · tools",  "value": 0.84,  "tokens": "—",     "category": "Tool"  },
    { "label": "Storage · memory",   "value": 0.12,  "tokens": "—",     "category": "Infra" }
  ],
  "meta": { ... }
}
```

| Field      | Type   | Notes                                              |
|------------|--------|----------------------------------------------------|
| `value`    | number | 2 decimal float USD — frontend displays as `$12.40`|
| `tokens`   | string | Pre-formatted `"847K"` or exact string `"—"`       |
| `category` | string | `"Model"` \| `"Tool"` \| `"Infra"` — used for grouping |

---

### 6.9 GET `/system/observability`

Drives: 4 sparkline charts in Observability panel.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "latency": [1240,1180,1320,1240,1390,1180,1260,1340,1200,1280,1420,1180,1250,1340,1200,1380,1240,1300,1180,1260],
    "tokens":  [12,18,14,22,17,28,21,35,26,42,31,48,37,54,42,61,47,70,53,80],
    "errors":  [0,0,1,0,0,0,1,0,0,0,0,1,0,0,0,0,0,1,0,0],
    "runs":    [1,2,1,3,2,4,3,5,4,6,5,7,6,8,7,9,8,10,9,12]
  },
  "meta": { ... }
}
```

| Field     | Type     | Notes                                                        |
|-----------|----------|--------------------------------------------------------------|
| `latency` | number[] | exactly 20 integers — ms values, time-ordered oldest→newest  |
| `tokens`  | number[] | exactly 20 integers — cumulative K tokens at each checkpoint |
| `errors`  | number[] | exactly 20 integers — error count per checkpoint             |
| `runs`    | number[] | exactly 20 integers — concurrent active runs count           |

The frontend SVG scales automatically to array min/max — no pre-normalization needed.

---

### 6.10 GET `/system/activity-heatmap`

Drives: Activity heatmap (7 rows × 24 columns = 168 cells).

**Response 200:**
```json
{
  "success": true,
  "data": {
    "values": [0.12, 0.08, 0.05, 0.03, 0.02, 0.01, 0.04, 0.18, 0.45, 0.72, 0.81, 0.76, 0.68, 0.73, 0.79, 0.74, 0.65, 0.58, 0.42, 0.31, 0.24, 0.18, 0.14, 0.10]
  },
  "meta": { ... }
}
```

| Field    | Type     | Notes                                                                   |
|----------|----------|-------------------------------------------------------------------------|
| `values` | number[] | exactly 168 float values 0.0–1.0; row-major layout: index = `day*24 + hour` |
|          |          | day 0 = oldest (6 days ago), day 6 = today; hour 0 = midnight, hour 23 = 11pm |

---

### 6.11 GET `/system/events` (initial seed)

Same as §4.3 but for the System page event stream. Returns up to 50 recent events. New events arrive via WebSocket.

---

## 7. Auth Visualization Telemetry

Used on `/login`, `/signup`, `/forgot-password` left panel.

### 7.1 GET `/system/telemetry/live`

Polled by the frontend every ~2.8 seconds to keep the auth page telemetry panel alive.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "activeAgents": 5,
    "toolsOnline":  84,
    "memoryIndex":  329,
    "systemHealth": 99.97
  },
  "meta": { ... }
}
```

| Field           | Type   | Notes                                                            |
|-----------------|--------|------------------------------------------------------------------|
| `activeAgents`  | number | integer — static for now; always `5`                            |
| `toolsOnline`   | number | integer — static for now; always `84`                           |
| `memoryIndex`   | number | integer — should increment slightly each call (simulate growth) |
| `systemHealth`  | number | 2 decimal float 99.94–100.00 — should vary slightly each call   |

**Fallback:** If this endpoint is unreachable, the frontend falls back to locally-simulated values (starting from `{ activeAgents:5, toolsOnline:84, memoryIndex:327, systemHealth:99.98 }`). This endpoint is non-critical.

---

## 8. WebSocket / Streaming Protocol

### 8.1 Connection URL

```
WS:  ws://api.aps.io/v1/ws/runs/:runId/stream    (development)
WSS: wss://api.aps.io/v1/ws/runs/:runId/stream   (production)
```

The frontend connects on Dashboard and System page mount. The JWT token is passed as a query parameter (WebSocket connections cannot set headers):

```
wss://api.aps.io/v1/ws/runs/RUN_0042/stream?token=eyJhbGciOi...
```

### 8.2 Message Format

All messages are newline-terminated JSON strings. The frontend uses `JSON.parse(event.data)`.

**Envelope:**
```json
{
  "type":    "event | artifact_update | agent_update | metric_tick | ping",
  "payload": { ...type-specific object }
}
```

---

### 8.3 `event` message

New stream event to append to the execution stream log.

```json
{
  "type": "event",
  "payload": {
    "t":     "14:04:35",
    "agent": "Research",
    "icon":  "check_circle",
    "type":  "evidence",
    "msg":   "Research Brief finalized · 47 evidence nodes · 94% confidence",
    "color": "green"
  }
}
```

---

### 8.4 `artifact_update` message

Drives real-time artifact card state transitions.

```json
{
  "type": "artifact_update",
  "payload": {
    "artifactId": "prd",
    "status":     "complete",
    "confidence": 87,
    "size":       "31 KB",
    "genTime":    "5m 20s"
  }
}
```

Frontend transitions: `queued` → `building` → `complete`
- `queued → building`: card shows cyan pulse, `size` and `genTime` remain `"—"`
- `building → complete`: card shows green, `size` and `genTime` are populated

---

### 8.5 `agent_update` message

Drives real-time agent card status changes.

```json
{
  "type": "agent_update",
  "payload": {
    "agentId":    "product",
    "status":     "running",
    "confidence": 32,
    "currentJob": "Parsing Research Brief output...",
    "toolLog":    ["Reading Research Brief v2", "Extracting feature requirements"]
  }
}
```

---

### 8.6 `metric_tick` message

Drives live metric updates (command header CPU/MEM/API, system health bar).

```json
{
  "type": "metric_tick",
  "payload": {
    "cpuPct":        26,
    "memPct":        63,
    "apiUptimePct":  99,
    "tokensUsed":    231200,
    "activeAgents":  1
  }
}
```

Send every 5 seconds. The frontend updates the header health bars and token counter in-place.

---

### 8.7 `ping` / `pong`

Server sends every 30 seconds:
```json
{ "type": "ping", "payload": null }
```

Client responds immediately:
```json
{ "type": "pong", "payload": null }
```

If the server doesn't receive a `pong` within 10 seconds, it closes the connection. The frontend auto-reconnects with exponential backoff (1s, 2s, 4s, max 30s).

### 8.8 Connection Close Codes

| Code | Meaning                    | Frontend action               |
|------|----------------------------|-------------------------------|
| 1000 | Normal close (run finished)| Show "Run complete" toast     |
| 1008 | Auth failure               | Redirect to `/login`          |
| 1011 | Server error               | Show error toast, reconnect   |
| 4004 | Run not found              | Redirect to Pipeline page     |

---

## 9. Live Metric Update Intervals

| Component                     | Interval   | Source                        | Notes                             |
|-------------------------------|------------|-------------------------------|-----------------------------------|
| Dashboard elapsed timer       | 1 second   | Local `setInterval`           | Seeded from `Run.elapsedSec`      |
| System runtime timer          | 1 second   | Local `setInterval`           | Seeded from `SystemHealth.runtimeSec` |
| Tokens used counter           | 1 second   | Local derivation              | `tokensUsed + (elapsedSec × 12)` |
| Agent tool log rotation       | 2.6 seconds| Local `setInterval`           | Cycles through `agent.toolLog[]`  |
| Execution stream entries      | ~3.4 seconds | WebSocket `event`            | New events pushed by server       |
| System event stream           | 3–5 seconds | WebSocket `event`            | New events pushed by server       |
| Health bar metrics            | 5 seconds  | WebSocket `metric_tick`       | CPU/MEM/API/tokens                |
| Auth telemetry (left panel)   | 2.8 seconds| `GET /system/telemetry/live`  | Falls back to local simulation    |
| Pipeline terminal logs        | 3 seconds  | WebSocket `terminal_log`      | Global (not run-scoped)           |

---

## 10. Enum Reference

### AgentStatus

| Value     | UI badge    | Badge color                | Dot                  |
|-----------|-------------|----------------------------|----------------------|
| running   | "Running"   | `#79ff5b` (green)          | Green, pulsing       |
| queued    | "Queued"    | white/6% opacity           | Cyan, static         |
| idle      | "Idle"      | white/3% opacity           | None                 |
| completed | "Done"      | `rgba(165,231,255,0.15)`   | Cyan, static         |
| failed    | "Failed"    | `rgba(239,68,68,0.15)`     | Red, static          |

### ArtifactStatus

| Value    | UI display       | Card border color           |
|----------|------------------|-----------------------------|
| complete | green checkmark  | `rgba(121,255,91,0.2)`      |
| building | cyan pulsing dot | `rgba(165,231,255,0.2)`     |
| queued   | dash / muted     | `rgba(255,255,255,0.05)`    |

### EventType → color

| type     | color field | hex          | UI meaning                    |
|----------|-------------|--------------|-------------------------------|
| start    | "cyan"      | `#a5e7ff`    | Agent spawned                 |
| tool     | "cyan"      | `#a5e7ff`    | Tool call made                |
| evidence | "green"     | `#79ff5b`    | Evidence committed            |
| insight  | "amber"     | `#f59e0b`    | Insight derived               |
| artifact | "green"     | `#79ff5b`    | Artifact created              |
| model    | "cyan"      | `#a5e7ff`    | LLM call completed            |
| agent    | "cyan"      | `#a5e7ff`    | Agent status changed          |

### ToolHealth

| Value    | UI color       | hex       |
|----------|----------------|-----------|
| healthy  | green          | `#79ff5b` |
| standby  | cyan at 40%    | `#a5e7ff` |
| degraded | amber          | `#f59e0b` |
| offline  | red            | `#ef4444` |

### ArtifactCategory (display order)

```
"Research" → "Product" → "Architecture" → "Execution" → "Business"
```

### Agent IDs (fixed)

```
"research" → "product" → "arch" → "execution" → "present"
```

---

## 11. Field Format Rules

### 11.1 Timestamps

| Where                     | Backend sends         | Frontend displays  |
|---------------------------|-----------------------|--------------------|
| `Run.startedAt`           | ISO-8601 UTC string   | Not shown directly |
| `StreamEvent.t`           | `"HH:MM:SS"` string   | As-is              |
| `Artifact.generatedAt`    | `"HH:MM:SS"` string   | As-is              |
| `SysAgent.lastExec`       | `"HH:MM:SS"` string   | As-is              |
| `ToolMetric.last`         | `"HH:MM:SS"` or `"—"` | As-is              |
| `ArtifactVersion.time`    | `"HH:MM:SS"` string   | As-is              |
| `meta.timestamp`          | ISO-8601 UTC string   | Not shown          |

**Rule:** All display timestamps are wall-clock `HH:MM:SS` strings already formatted by the backend. The frontend renders them verbatim. ISO-8601 is only used in `meta` and for internal date math.

### 11.2 File Sizes

Format: `"{n} {unit}"` where unit is `B`, `KB`, `MB`, `GB`.

```
"42 KB"    ✓
"18 KB"    ✓
"2.4 MB"   ✓
"127 MB"   ✓
"2.4 GB"   ✓
"42kb"     ✗  (wrong case)
"42048"    ✗  (no unit)
```

### 11.3 Durations (genTime)

Format: `"{m}m {s}s"` — always both parts even if minutes is 0.

```
"3m 12s"   ✓
"0m 45s"   ✓
"1m 40s"   ✓
"3:12"     ✗
"3 minutes 12 seconds"  ✗
```

### 11.4 Percentages

- **0–100 range** — backend sends the raw number, NOT a string with `%`
- **Display:** frontend adds `%`  
- **Exception:** `agentsActive`, `toolsOnline`, `modelsReady` in `SystemHealth` are pre-formatted strings like `"5/5"` (fraction, not percentage)

### 11.5 Costs

- Always 2 decimal places as a float: `12.40`, `0.84`, `0.00`
- Frontend prepends `$`: `$12.40`
- Never send as string: `"$12.40"` ✗

### 11.6 Token counts in Cost items

Pre-formatted string with K suffix: `"847K"`, `"91K"`, `"—"`

Backend computes: `Math.round(rawTokens / 1000) + "K"`

### 11.7 Run IDs

Format: `"RUN_"` + 4-digit zero-padded integer: `"RUN_0042"`, `"RUN_0776"`.

### 11.8 Absent/Unknown values for string fields

Use the exact em-dash string `"—"` (U+2014). Not `"-"`, not `"N/A"`, not `""`.

```json
"size":   "—"   ✓
"last":   "—"   ✓
"tokens": "—"   ✓
"size":   "-"   ✗
"size":   ""    ✗
"size":   null  ✗
```

---

## 12. Error Handling

### 12.1 Error Codes Reference

| code                  | HTTP | Trigger                                    | Frontend response                      |
|-----------------------|------|--------------------------------------------|----------------------------------------|
| `INVALID_CREDENTIALS` | 401  | Login: wrong email or password             | Inline message under password field    |
| `EMAIL_ALREADY_EXISTS`| 422  | Signup: email taken                        | Inline message under email field       |
| `INVALID_RESET_TOKEN` | 400  | Reset: token expired or not found          | Toast + redirect to `/forgot-password` |
| `VALIDATION_ERROR`    | 422  | Any field fails validation                 | Inline on `error.field`                |
| `RUN_NOT_FOUND`       | 404  | Run ID does not exist                      | Redirect to Pipeline page              |
| `ARTIFACT_NOT_FOUND`  | 404  | Artifact ID does not exist                 | Empty state in viewer                  |
| `UNAUTHORIZED`        | 401  | Token missing or expired                   | Clear token, redirect to `/login`      |
| `RATE_LIMITED`        | 429  | Too many requests                          | Toast: "Too many requests, slow down"  |
| `SERVER_ERROR`        | 500  | Unhandled backend exception                | Toast: "Something went wrong"          |

### 12.2 Validation Error Format

When multiple fields fail:

```json
{
  "success": false,
  "error": {
    "code":    "VALIDATION_ERROR",
    "message": "Please correct the highlighted fields.",
    "field":   null,
    "fields": [
      { "field": "email",    "message": "Invalid email format." },
      { "field": "password", "message": "Password must be at least 8 characters." }
    ]
  },
  "meta": { ... }
}
```

The frontend iterates `error.fields[]` and shows each `message` beneath the matching form input.

### 12.3 Network / Timeout

The frontend sets a 10-second fetch timeout on all REST calls. On timeout it shows:

> "Connection timeout — check your network and try again."

No special response shape needed — this is handled client-side.
