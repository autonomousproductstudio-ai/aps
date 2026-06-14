# HLD — High-Level Design (Autonomous Product Studio)

**Status:** Draft v1 · **Owner:** P1 · Derived from: [TRD.md](TRD.md)

System architecture, agent topology, data flow, and the runtime sequence. Low-level
class/schema detail lives in `src/aps/state/models.py` and each agent's module.

---

## 1. System context

```
                         ┌────────────────────────────┐
        idea string ───▶ │        React Frontend       │  (P3)
                         │  run console · timeline ·    │
                         │  evidence panel · artifacts  │
                         └──────────────┬───────────────┘
                                        │ HTTP + SSE  (API_CONTRACT.md)
                         ┌──────────────▼───────────────┐
                         │        FastAPI service        │  (P3 boundary)
                         │  POST /runs · /runs/{id}/events│
                         └──────────────┬───────────────┘
                                        │ in-process
                         ┌──────────────▼───────────────┐
                         │   APS engine (LangGraph)      │  (P1 + P2)
                         │   CEO orchestrator + agents   │
                         └──────────────┬───────────────┘
                                        │
            ┌───────────────────────────┼───────────────────────────┐
            ▼                           ▼                            ▼
     free LLM (Gemini)          tool layer (52 tools)        infra (logs/metrics)
                                 │  retrieval → live sources
                                 │  (GitHub, HN, Reddit, ...)
```

---

## 2. Agent topology

```
CEO / Orchestrator   (typed StudioState; no domain tools)
│
├── Research Agent          scoped tools: retrieval(20) + analysis(10)
│       returns ResearchReturn { market_size, competitors[], pain_points[], evidence[] }
│
├── Product Agent           scoped tools: product(6)
│       consumes ResearchReturn → returns PRD { personas[], features[], mvp_scope, requirements[], sources[] }
│
├── Architecture Agent      scoped tools: architecture(6)   [thin-but-real in v1]
│       consumes PRD → returns TRD { data_model, api_spec(OpenAPI), stack, scale_estimate }
│
├── Execution Agent         scoped tools: execution(6)      [thin in v1]
│       consumes TRD → returns ExecutionPlan { repo_plan, backlog[], sprints[], roadmap, infra_cost }
│
└── Presentation Agent      scoped tools: presentation(4)   [thin in v1]
        consumes all → returns PitchPackage { pitch_outline, demo_script, investor_memo }
```

**Coherence guarantee:** no agent's model ever sees more than ~20 tools. The global
registry clears 50, but selection stays a real choice within a bounded set — the
direct answer to "coherent at fifty tools rather than fifty conditional dispatches."

---

## 3. Research Agent internals (forked from Open Deep Research)

```
            ┌──────────────────────────────────────────────┐
   idea ───▶│  PLAN: model proposes what to investigate      │
            └───────────────────┬──────────────────────────┘
                                ▼
            ┌──────────────────────────────────────────────┐
            │  TOOL LOOP (model ↔ scoped tools)              │
            │   model emits tool calls from descriptions;    │◀─┐ loop until
            │   each call hits a real source, returns        │  │ done or cap
            │   ToolResult{payload, evidence[]}              │──┘ (C2/C3)
            └───────────────────┬──────────────────────────┘
                                ▼
            ┌──────────────────────────────────────────────┐
            │  COMPRESSION node                              │
            │   dedupe_and_rank_evidence → validate_with_    │
            │   sources → tight, cited brief                 │
            └───────────────────┬──────────────────────────┘
                                ▼
                      ResearchReturn (typed)
```

ODR mapping: its **supervisor → researcher → compression** spine is forked directly;
its **report writer** is *replaced* by the downstream typed-handoff chain.

---

## 4. Data flow (composition — Req 5)

```
Research.return.pain_points + target_users
      → Product.assemble_prd → PRD.requirements
      → Architecture.design_data_model / design_api_contract → TRD
      → Execution.generate_backlog → ExecutionPlan.sprints
      → Presentation.* → PitchPackage
```

Every arrow is a **typed handoff**, never a re-prompt. The orchestrator holds only
the structured returns, so context stays small across the long horizon.

---

## 5. Runtime sequence (one run)

```
Frontend         API           Orchestrator      Research      Tools/LLM
   │  POST /runs   │                 │               │             │
   │──────────────▶│  start(idea)    │               │             │
   │  {run_id}     │────────────────▶│               │             │
   │◀──────────────│                 │  invoke       │             │
   │  GET /events  │                 │──────────────▶│             │
   │═════════════▶ │  (SSE open)     │               │ tool loop   │
   │  event: agent_start             │               │────────────▶│
   │◀════════ event: tool_call(github_list_issues) ◀─│◀────────────│
   │◀════════ event: tool_call(hn_search)                          │
   │◀════════ event: artifact_ready(research_brief)                │
   │                                 │  → Product     │             │
   │◀════════ event: artifact_ready(prd)                           │
   │◀════════ event: run_complete    │               │             │
```

The SSE event stream is both the live UI and the audit trace (NFR-3).

---

## 6. Deployment view (v1)

- Single process: FastAPI + LangGraph engine in one Python service.
- Frontend served separately (Vite dev / static build).
- State in-memory per process; runs also written to JSON for replay/fixtures.
- Optional: containerize for the demo; AMD Developer Cloud / any VM works (see
  `amd-cloud-setup-alternative` notes in project docs) but a laptop suffices on free LLM tiers.

---

## 7. Cross-cutting concerns

- **Config:** one `config/settings.py` (Pydantic settings) reads `.env`; selects model
  provider, search backend, limits. One switch flips Gemini ↔ NIM.
- **Registry:** `tools/registry.py` auto-loads tools by directory scan; agents request
  tools by **namespace** (`retrieval`, `analysis`, `product`, ...).
- **Events:** an in-process pub/sub the orchestrator publishes to and the API subscribes to.
- **Resilience:** Tenacity on tool I/O; rate limiter per keyed source; fixture fallback in demo mode.

---

## 8. Key risks & mitigations (HLD level)

| Risk | Mitigation |
|------|------------|
| Tool loop runs away | Per-agent recursion cap + global call budget (TRD C2/C3) |
| Source rate-limited mid-demo | Rate limiter + in-run cache + fixture fallback |
| 50-tool registry confuses the model | Per-agent scoping (≤20 visible) — the core design bet |
| Three people block each other | Folder-disjoint ownership + two frozen contracts (TEAM_GUIDE §2) |
| Over-building in 5 days | One deep vertical (Research→PRD), rest thin, honest MEMO |
