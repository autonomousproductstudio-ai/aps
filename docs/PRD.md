# PRD — Autonomous Product Studio

**Status:** Draft v1 · **Owner:** P1 · **Last updated:** Day 0
**Downstream dependents:** TRD, HLD, Evaluation Plan, all agent specs.

---

## 1. Problem & opportunity

Founders and hackathon builders spend days doing the same cold-start work for every
idea: scanning the market, finding real user pain, sizing demand, scoping an MVP,
drafting product and technical specs, and preparing pitch materials. Most AI tools
either *answer questions* (chatbots) or *write code* (coding agents). None behave
like a **small startup team** that takes an idea and returns a coherent, evidence-
grounded execution package.

**Opportunity:** an autonomous multi-agent "studio" that produces that package in a
single run, grounded in live data (not hallucinated), with traceable evidence.

---

## 2. Goals & non-goals

### Goals
- G1. From a single idea string, produce a complete **startup execution package**:
  market brief, validated pain points, PRD, TRD, architecture, execution plan, pitch.
- G2. Ground every major claim in **real, cited evidence** from live sources.
- G3. Demonstrate **genuine model-driven tool selection** across distinct sources.
- G4. Run end to end on **free model + free data tiers** so anyone can reproduce it.
- G5. Be **observable**: every agent, tool call, and artifact is inspectable in the UI.

### Non-goals
- NG1. Generating production application code (we produce a *plan*, not the app).
- NG2. Multi-tenant SaaS, billing, auth beyond a demo key.
- NG3. Fine-tuning or training models.
- NG4. Deep build-out of all five agents in v1 — Research→PRD is deep; the rest is thin-but-real.

---

## 3. Users & personas

| Persona | Need | Success looks like |
|---------|------|--------------------|
| **Hackathon builder** ("Ravi") | Stand out from generic coding-agent submissions; satisfy the assignment's 5 requirements. | A reproducible system that visibly does real research and composes typed artifacts. |
| **Solo founder** ("Mara") | Validate an idea before committing weeks. | A cited market brief + PRD she can act on or discard in an hour. |
| **Reviewer / judge** ("Dr. Okafor") | Verify *something real happens* behind the artifacts. | Can open any artifact, see the tool calls and evidence that produced it. |

Primary persona for v1 scope = **Ravi** (the assignment context). Mara/Okafor define
the bar for "is this real."

---

## 4. User stories (v1)

- **US-1** As a builder, I enter one idea string and get a full execution package, so I don't cold-start by hand. *(P1)*
- **US-2** As a founder, I see *which sources* produced each finding, so I can trust the market brief. *(P2 evidence + P3 citation panel)*
- **US-3** As a reviewer, I watch the pipeline run live (agents, tool calls), so I can confirm real work happens. *(P3 timeline)*
- **US-4** As a builder, I can download each artifact (PRD/TRD/OpenAPI/pitch) as a file. *(P3)*
- **US-5** As an operator, I can re-run with my own free API keys and get the same shape of output. *(P1 config)*
- **US-6** As a builder, when a source is rate-limited, the run degrades gracefully and tells me. *(P2 infra + P3 error state)*

Each story maps to an owner so the team can claim work directly.

---

## 5. Scope — MVP vs later

### MVP (must ship)
- **M1.** CEO orchestrator that routes an idea through agents and holds typed state.
- **M2.** Research Agent with **≥12 real retrieval tools live** + compression to a typed brief.
- **M3.** Analysis tools sufficient for pain points, competitor matrix, market size, evidence grounding.
- **M4.** Product Agent producing a schema-valid **PRD** from the research brief (the composition proof).
- **M5.** Registry of **52 model-callable tools**, scoped per agent (Req-1 proof).
- **M6.** FastAPI surface + React UI: start a run, watch it live, view & download artifacts.
- **M7.** Evaluation harness with a small gold set and the metrics in `docs/EVALUATION.md`.

### Should (if time)
- S1. Thin-but-real Architecture Agent emitting valid **OpenAPI**.
- S2. Thin Execution Agent (backlog, sprints, roadmap, cost from real pricing).
- S3. Thin Presentation Agent (pitch outline, demo script, investor memo).

### Later (explicitly cut in v1, stated in MEMO)
- L1. Redis-backed cross-run memory. L2. Broader retrieval sources. L3. Deep
  Architecture/Execution/Presentation. L4. Human-in-the-loop edits to artifacts.

---

## 6. Functional requirements

- **FR-1.** Accept an idea string (≤500 chars) and optional config (model, max tool calls).
- **FR-2.** Orchestrator spawns specialist subagents, each in isolated context, each
  returning a typed Pydantic object.
- **FR-3.** Research Agent selects tools via the model (function-calling), not a
  dispatch table; it may call any of its scoped retrieval/analysis tools in any order.
- **FR-4.** Every retrieval tool returns both a raw payload and normalized `Evidence`
  (source, url, snippet, retrieved_at) for grounding.
- **FR-5.** Product Agent consumes `ResearchReturn` and emits a schema-valid `PRD`;
  `assemble_prd` validates, it does not re-generate from scratch.
- **FR-6.** The system streams lifecycle events (agent start/stop, tool call, artifact
  ready) to the API as they happen.
- **FR-7.** All artifacts are downloadable (JSON + a human-readable rendering).
- **FR-8.** A run is reproducible given the same idea, keys, and seed/config.

---

## 7. Non-functional requirements

- **NFR-1 (cost):** a full run completes within free tiers (≤~5k tokens-equivalent budget; see TRD).
- **NFR-2 (latency):** a Research→PRD run completes in ≤ ~5 min on free tier; UI shows progress throughout.
- **NFR-3 (observability):** structured logs (Structlog), per-tool metrics (Prometheus), full event stream.
- **NFR-4 (resilience):** transient source failures retried (Tenacity); permanent failures degrade gracefully and are reported.
- **NFR-5 (reproducibility):** judges run it with their own free keys; no paid dependency.
- **NFR-6 (coherence):** no agent's model is exposed to more than ~20 tools at once.

---

## 8. Success metrics (tie to Evaluation Plan)

| Metric | Target (v1) |
|--------|-------------|
| Tool-selection validity (model picks a runnable tool with valid args) | ≥ 90% |
| Distinct sources touched in a typical run | ≥ 6 |
| Evidence coverage (PRD claims with ≥1 citation) | ≥ 80% |
| PRD schema validity | 100% |
| End-to-end run success rate (Idea→PRD, no crash) | ≥ 90% |
| Tool calls per run | 25–35 |

Full definitions, harness, and gold set in **[EVALUATION.md](EVALUATION.md)**.

---

## 9. Assumptions & risks

- **A1.** Free tiers (Gemini / NIM, GitHub PAT, Tavily, Algolia HN) remain available. → *Risk:* rate limits. *Mitigation:* rate limiter + caching + fixtures.
- **A2.** Model tool-calling is reliable enough for 25–35 calls/run. → *Risk:* drift/loops. *Mitigation:* recursion cap, per-agent tool scoping.
- **A3.** Five-day window. → *Risk:* over-building. *Mitigation:* one deep vertical, rest thin, honest MEMO.

---

## 10. Open questions

- Q1. Which free model is the daily driver — Gemini Flash vs NIM Nemotron? (See ADR-0002; default Gemini.)
- Q2. Do we persist runs across sessions in v1? (Default: in-memory + JSON fixtures; Redis is *later*.)
- Q3. How much of Architecture/Execution/Presentation is "real" by demo? (Default: OpenAPI real, rest thin.)
