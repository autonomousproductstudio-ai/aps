# TEAM_GUIDE.md — How three people build APS in one repo without colliding

This is the most important doc for execution. The architecture is deliberately
split so that **the three of you touch mostly disjoint folders**, and where you
must meet, you meet at **typed contracts** that are frozen on Day 1.

---

## 1. Roles

| Person | Role | Owns | Skill fit |
|--------|------|------|-----------|
| **P1 — You** | Orchestration & complex tasks | CEO graph, routing, typed state, Research Agent (forked ODR loop), config, composition chain | Hardest, most interdependent work; the "brain" |
| **P2** | Tool & agent builder (Claude-Code-executable) | All 20 retrieval tools, 10 analysis tools, Product/Architecture/Execution/Presentation agents, infra (logging/retry/metrics), unit tests for tools | Highly parallel, well-bounded, spec-driven → ideal for delegating to Claude Code |
| **P3** | Frontend & API surface | FastAPI app, streaming endpoints, the entire `frontend/` React app, wireframes → working UI | Independent once the API contract is frozen |

### Why this split works
- **P2's work is "embarrassingly parallel":** every tool is a self-contained function
  behind one interface (`Tool` protocol). P2 can hand each tool spec to Claude Code
  one at a time and they never conflict, because each is a new file in
  `tools/retrieval/` or `tools/analysis/`.
- **P3 never imports agent code.** P3 codes against `docs/API_CONTRACT.md` only.
  Until P1's orchestrator is real, P3 runs against the **mock server** (see §6).
- **P1 owns the contracts.** Everyone else depends on `src/aps/state/models.py` and
  `docs/API_CONTRACT.md`. P1 freezes both on Day 1; changes go through a PR + ping.

---

## 2. The two frozen contracts (Day 1, non-negotiable)

Everything parallel depends on these. Freeze them first, change them only by PR.

1. **`src/aps/state/models.py`** — the Pydantic types every agent returns and
   consumes (`ResearchReturn`, `PRD`, `TRD`, `ExecutionPlan`, `PitchPackage`, and the
   `Evidence`/`Competitor`/`Persona`/... building blocks). This is the spine of Req 5.
2. **`docs/API_CONTRACT.md`** — the HTTP/streaming surface between backend and
   frontend (`POST /runs`, `GET /runs/{id}`, `GET /runs/{id}/events` SSE, artifact
   shapes). P3 builds the whole UI against this whether or not P1 is done.

If a contract must change: open a PR titled `contract:`, tag all three, merge only
after a 👍 from each. No silent edits to these two files.

---

## 3. Folder ownership (who can edit what)

```
src/aps/
├── state/          ← P1 owns. Others READ, never edit (PR + ping to change).
├── config/         ← P1
├── orchestrator/   ← P1
├── agents/research/← P1
├── agents/product/ ─┐
├── agents/architecture/ │
├── agents/execution/    ├← P2
├── agents/presentation/ │
├── tools/          ─────┘  (retrieval/ + analysis/ + registry.py)
├── infra/          ← P2
└── api/            ← P3
frontend/           ← P3
tests/evals/        ← shared, but P1 curates the gold set
tests/unit/         ← whoever wrote the code writes its unit test
docs/               ← author owns their doc; PRs reviewed by one other
```

**Rule of thumb:** if a change forces an edit outside your folder, it touches a
contract — open a PR and tag the others.

---

## 4. Git workflow

- **Default branch:** `main`, protected. No direct pushes.
- **Branches:** `p1/orchestrator-fanout`, `p2/tool-github-issues`, `p3/run-console`.
  Prefix with your initial so it's obvious who's working where.
- **PRs:** small and frequent. One tool = one PR for P2. Required: 1 review.
- **CI (GitHub Actions):** `ruff` + `pytest tests/unit` must pass before merge.
- **Conflict-avoidance by construction:** because ownership is folder-disjoint, the
  only realistic conflict points are `tools/registry.py` (P2-internal) and
  `pyproject.toml`. Keep the registry as a directory-scan auto-loader (see
  `tools/registry.py`) so adding a tool doesn't edit a shared list.

### Commit cadence
- P1: commit when a graph node compiles and the typed state round-trips.
- P2: commit per tool, each with its unit test and a docstring the model will read.
- P3: commit per UI view.

---

## 5. The interface contracts P2 and P3 code against

### P2 — every tool implements this protocol
```python
# Conceptual contract (see src/aps/tools/base.py)
class Tool(Protocol):
    name: str                      # snake_case, what the model calls
    description: str               # the model reads THIS to decide — write it well
    args_schema: type[BaseModel]   # typed inputs
    def run(self, **kwargs) -> ToolResult: ...   # returns evidence + raw payload
```
A tool is "done" when: it has a typed args schema, a real call to its source (or a
documented fixture if the key isn't issued yet), a unit test with a recorded
fixture, and a description good enough that the model picks it for the right job.

### P3 — every UI view consumes API_CONTRACT.md shapes only
P3 imports nothing from `src/aps`. The only coupling is JSON over HTTP/SSE.

---

## 6. Unblocking: how to work before P1's orchestrator exists

Parallelism only works if P2 and P3 aren't blocked waiting on P1.

- **P2 runs tools standalone:** `python -m aps.tools.retrieval.github_issues --query "..."`.
  Each tool has a `__main__` for manual runs. No orchestrator needed.
- **P3 runs against the mock API:** `uvicorn aps.api.mock:app`. The mock replays a
  recorded run from `tests/evals/fixtures/sample_run.json` over the real SSE
  contract, so the whole UI is buildable on Day 1.
- **P1 stubs agents:** the CEO graph routes to stub agents that return fixture
  `ResearchReturn`/`PRD` objects until the real ones land. Typed state flows end to
  end before any tool is real.

---

## 7. Five-day plan (mapped to people)

| Day | P1 (Orchestration) | P2 (Tools/Agents) | P3 (Frontend/API) |
|-----|--------------------|--------------------|--------------------|
| **1** | Freeze `state/models.py` + `API_CONTRACT.md`. CEO graph routes to stub agents; typed state round-trips. `config/` → Gemini. | `tools/base.py` + `registry.py` auto-loader. First 3 retrieval tools: `web_search`, `github_list_issues`, `hn_search` (each with fixture + test). | Scaffold React app. Build run console + live event log **against mock API**. |
| **2** | Fork ODR researcher loop into Research Agent; bind P2's 3 tools; add compression → `dedupe_and_rank_evidence`. Research returns real typed brief. | Finish retrieval tools 4–12 (Reddit, StackExchange, arXiv, trends, pypi, npm, ...). | Artifact viewer (renders PRD/TRD JSON). Wire run console to real `POST /runs`. |
| **3** | Wire Research→Product handoff; orchestrator holds typed returns; recursion/limits. | Remaining retrieval + all 10 analysis tools. Start Product Agent tools. | Pipeline timeline view (per-agent status, tool-call stream). Evidence/citation panel. |
| **4** | Composition chain real end to end (Research→PRD). Eval harness wired; run gold set. | Finish Product Agent (`assemble_prd`). Thin Architecture (real OpenAPI), Execution, Presentation. | Polish: download artifacts, error states, empty/loading states. |
| **5** | MEMO.md (deep vs thin, infra≠tools, defended tradeoff). Final eval run + numbers. | Infra: Structlog, Tenacity, Prometheus, rate limiter. Fill unit-test gaps. | Demo flow, deploy/share build, record walkthrough. |

---

## 8. Definition of Done (per layer)

- **A tool:** typed args, real source call, fixture-backed unit test, model-grade description.
- **An agent:** scoped tool set bound, runs its loop, returns its typed Pydantic object, has one eval case.
- **The orchestrator:** runs Idea→PRD end to end on the gold set, streams events to the API.
- **The frontend:** drives a full run from one idea string and renders every artifact.
- **The system:** `pytest` green, eval numbers in `docs/EVALUATION.md`, MEMO written.
