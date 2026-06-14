# TRD — Autonomous Product Studio

**Status:** Draft v1 · **Owner:** P1 · Derived from: [PRD.md](PRD.md)
**Dependents:** HLD, ADRs, all implementation.

This converts the PRD into technical requirements, constraints, interfaces, and the
concrete free-tier mapping the team builds against.

---

## 1. Technology stack (and why — full rationale in ADRs)

| Concern | Choice | ADR |
|---------|--------|-----|
| Agent orchestration | **LangGraph** (typed `StateGraph`, `Send` fan-out, prebuilt supervisor) | ADR-0001 |
| LLM (daily driver) | **Google Gemini** free tier via `langchain-google-genai`; NIM as fallback | ADR-0002 |
| Typed state / validation | **Pydantic v2** | — |
| API | **FastAPI** + SSE (event stream) | ADR-0006 |
| Frontend | **React + Vite + TypeScript**, Tailwind | ADR-0007 |
| Persistence (v1) | In-memory + JSON; **PostgreSQL** as the documented target, Redis = later | ADR-0003 |
| Logging | **Structlog** (JSON logs) | — |
| Metrics | **Prometheus** client (`/metrics`) | — |
| Retries | **Tenacity** | — |
| Tests / evals | **Pytest** | EVALUATION.md |

---

## 2. Component responsibilities

### 2.1 Orchestrator (CEO) — P1
- A LangGraph `StateGraph` over a typed `StudioState`.
- Holds only **structured returns** from each agent (this is the context-management strategy, Req 3).
- Routes Idea → Research → Product → (Architecture → Execution → Presentation).
- Emits lifecycle events to an event bus the API subscribes to.
- No domain tools of its own.

### 2.2 Research Agent — P1 (forked from Open Deep Research)
- Subgraph: a tool-calling loop (model ↔ scoped tools) + a **compression node**.
- Scoped to retrieval (20) + analysis (10) tools.
- Returns `ResearchReturn { market_size, competitors[], pain_points[], evidence[] }`.
- Compression node = `dedupe_and_rank_evidence` + `validate_with_sources`: collapses
  noisy tool output into a tight, cited brief before handing up.

### 2.3 Tool layer — P2
- Each tool implements the `Tool` protocol (`name`, `description`, `args_schema`, `run`).
- Retrieval tools return `ToolResult { payload, evidence[] }`.
- Registry auto-discovers tools by scanning `tools/retrieval/` and `tools/analysis/`,
  so adding a tool never edits a shared list (kills the merge-conflict hotspot).
- Tools are bound to a model via LangChain `bind_tools`; the **model emits the calls**.

### 2.4 Downstream agents — P2
- Product / Architecture / Execution / Presentation, each scoped to its 4–6 tools,
  each consuming the upstream typed object and returning its own typed object.

### 2.5 API — P3 boundary
- `POST /runs` starts a run (async), returns `run_id`.
- `GET /runs/{id}` returns status + artifacts so far.
- `GET /runs/{id}/events` is an **SSE stream** of lifecycle events.
- `GET /runs/{id}/artifacts/{name}` returns one artifact (JSON or rendered).
- Full shapes in [API_CONTRACT.md](API_CONTRACT.md).

### 2.6 Frontend — P3
- Run console (enter idea, start), live pipeline timeline, evidence/citation panel,
  artifact viewer + download. Builds against the mock API from Day 1.

---

## 3. Tool registry (52 model-callable tools)

> Counted tools = things the **model selects**. Infra is **not** counted.

**Research & Retrieval (20)** — each a distinct real source, the Req-1 proof:
`web_search`, `fetch_page`, `github_search_repos`, `github_repo_stats`,
`github_search_code`, `github_list_issues`, `hn_search`, `hn_thread_comments`,
`reddit_search`, `reddit_subreddit_top`, `reddit_comments`, `stackexchange_search`,
`producthunt_search`, `trends_interest`, `arxiv_search`, `wikipedia_summary`,
`pypi_package_info`, `npm_package_info`, `jobs_search`, `pricing_page_extract`.

**Analysis (10)** — operate on retrieved data:
`extract_pain_points`, `cluster_themes`, `sentiment_breakdown`,
`extract_competitor_features`, `build_competitor_matrix`, `estimate_market_size`,
`rank_opportunities`, `detect_trend_signal`, `validate_with_sources`,
`dedupe_and_rank_evidence`.

**Product (6):** `generate_personas`, `generate_user_stories`, `prioritize_features`,
`define_mvp_scope`, `acceptance_criteria`, `assemble_prd`.

**Architecture (6):** `design_data_model`, `design_api_contract`, `choose_tech_stack`,
`estimate_scale`, `design_architecture`, `assemble_trd`.

**Execution (6):** `plan_repo_structure`, `generate_backlog`, `plan_sprints`,
`estimate_effort`, `generate_roadmap`, `estimate_infra_cost`.

**Presentation (4):** `generate_pitch_outline`, `generate_demo_script`,
`generate_investor_memo`, `generate_judge_brief`.

**Platform capabilities — NOT tools, NOT counted:** `artifact_store`, `memory`,
`logging` (Structlog), `metrics` (Prometheus), `retry` (Tenacity), `rate_limiter`,
`evaluation` (Pytest). Reframing these out of the count is a deliberate point of
judgment to state in the MEMO.

---

## 4. Data contracts (the spine — see `src/aps/state/models.py`)

```
Evidence        { source, url, title, snippet, retrieved_at }
Competitor      { name, url, features[], pricing?, notes }
PainPoint       { text, severity, source_evidence[] }
Persona         { name, role, goals[], frustrations[] }
Feature         { title, description, priority, rice?/moscow? }

ResearchReturn  { idea, market_size, competitors[], pain_points[], evidence[] }
PRD             { idea, personas[], features[], mvp_scope, requirements[], sources[] }
TRD             { data_model, api_spec(OpenAPI), stack, scale_estimate }
ExecutionPlan   { repo_plan, backlog[], sprints[], roadmap, infra_cost }
PitchPackage    { pitch_outline, demo_script, investor_memo }
StudioState     { idea, research?, prd?, trd?, execution?, pitch?, events[] }
```

These types are the **only** coupling between agents. Changing one is a `contract:` PR.

---

## 5. Free-tier mapping (NFR-1, NFR-5)

| Need | Service | Key? | Limit (approx) |
|------|---------|------|----------------|
| LLM (daily) | Gemini free tier | `GEMINI_API_KEY` | very high token/RPD quota |
| LLM (fallback) | NVIDIA NIM | `nvapi-` key | 1k–5k credits, 40 RPM |
| Web search | Tavily / Brave | `TAVILY_API_KEY` | ~1k/mo free |
| GitHub | GitHub API | `GITHUB_PAT` | 5k req/hr authenticated |
| Hacker News | Algolia HN | none | generous |
| Reddit | Reddit script app | id/secret | OAuth, modest |
| Stack Exchange | SE API | optional key | low volume free |
| Trends | pytrends | none | unofficial, throttle |
| arXiv / Wikipedia / PyPI / npm | public APIs | none | generous |

**Build your own tool layer.** Do **not** lean on Gemini's built-in Google Search
grounding for Req 1 — the requirement wants *your* registry of distinct tools.
Each tool ships with a recorded fixture so the system runs (and tests pass) even
when a key isn't issued yet or a source is down.

---

## 6. Constraints & budgets

- **C1.** ≤ ~20 tools visible to any single agent's model (coherence; NFR-6).
- **C2.** Recursion/loop cap per agent (default 12 tool calls) to prevent runaway loops.
- **C3.** Global per-run tool-call budget (default 40) with graceful stop.
- **C4.** Rate limiter in front of every keyed source; respect provider RPM.
- **C5.** Caching of retrieval results by (tool, args) hash within a run.
- **C6.** All times UTC; `retrieved_at` on every Evidence.

---

## 7. Error handling & resilience (NFR-4)

- Transient (HTTP 429/5xx, timeout): Tenacity exponential backoff, max 3 tries.
- Permanent (auth, 4xx): tool returns a typed `ToolError` evidence-less result; the
  agent's model sees the failure and chooses another source. Run does not crash.
- Source outage: fall back to fixture if `APS_ALLOW_FIXTURE_FALLBACK=true` (demo mode).
- Every failure is logged (Structlog) and counted (Prometheus `tool_errors_total`).

---

## 8. Security & secrets

- All keys via env (`.env`, never committed). `.env.example` lists required vars.
- Demo API protected by a single shared `APS_API_KEY` header (no user auth in v1).
- No PII collected; idea strings and public data only.

---

## 9. Observability

- **Logs:** Structlog JSON, one event per node entry/exit and tool call.
- **Metrics:** `tool_calls_total{tool}`, `tool_errors_total{tool}`,
  `agent_duration_seconds{agent}`, `run_total{status}` at `/metrics`.
- **Traces:** the SSE event stream *is* the user-facing trace; events persisted to the run record.

---

## 10. Testing strategy

- **Unit (P2 per tool):** each tool tested against a recorded fixture (no live calls in CI).
- **Contract:** Pydantic models validate; API responses validated against schemas.
- **Eval (P1 curates):** gold-set runs scored on the metrics in EVALUATION.md.
- **CI:** `ruff` + `pytest tests/unit`; eval run is manual/nightly (uses real keys).
