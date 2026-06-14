# PRODUCTION_PLAN.md — turning APS into a production-grade, reviewer-trusted system

> Companion to `docs/plan.md` (the P2 workstream sketch). This document hardens that
> sketch into an execution-ready plan **reconciled against the codebase as it stands
> today** (post-PR #3 + the Phase A–D / fan-out / docs-reconcile merges, `main` @ `371b4cc`,
> 150 tests green). It adds the production concerns `plan.md` leaves implicit: contracts,
> acceptance criteria, test strategy, security, persistence, the frontend, CI/CD, and a
> risk register.

---

## 0. Where we actually are (baseline truth)

What is **real and merged** today — the plan builds on this, it does not re-do it:

| Capability | State | Evidence |
|---|---|---|
| 52 model-callable tools, 6 namespaces, per-agent scoping | done | `tools/registry.py`, `test_registry.py` |
| Deterministic downstream agents (Product→Architecture→Execution→Presentation) | done | `agents/*/agent.py` |
| Full LangGraph orchestrator, all 5 nodes, SSE events | done | `orchestrator/graph.py` |
| Research **fan-out supervisor** (parallel sub-researchers) | done | `agents/research/supervisor.py` |
| **Keyless** deterministic research path (no-key tools) | done | `agents/research/keyless.py` |
| **Honest degradation**: `RunStatus.DEGRADED`, `[fixture]` stamping, fail-fast preflight | done | `graph.py`, `infra/llm.py`, `tools/base.py` |
| LLM RPM rate-limiting + resilient HTTP (retry/rate-limit) | done | `infra/llm.py`, `infra/http.py` |
| File-backed **artifact store** + API read-through | done | `infra/artifact_store.py`, `api/main.py` |
| FastAPI backend (runs, status, SSE, artifacts, `/metrics`) | done | `api/main.py` |
| Eval harness + scorers, gold set (8 ideas) | partial | only `g01` run live |
| Live smoke scripts (NIM verified) | done | `scripts/live_*_smoke.py` |

**Open gaps this plan closes** (verified against the tree):

- **No renderer layer** — `src/aps/render/` does not exist; `?format=md` is not wired
  (`grep format src/aps/api/main.py` → 0). *(plan.md W1, W6)*
- **Gemini tool-calling unvalidated live** — only NIM exercised end-to-end. *(W2)*
- **Thin-PRD risk** — no enforced feature floor; not regression-guarded. *(W3)*
- **Token-gated tools** — `pytrends` not in `requirements`; Reddit OAuth path not wired;
  README key→capability table incomplete. *(W4)*
- **Eval is single-point** — targets rest on `g01` only. *(W5)*
- **No React frontend** — the one explicitly-excluded area; required for a "production" demo.
- **Production hardening** — single-key auth, in-memory run registry, no deploy/runbook.

---

## 1. Goals & non-goals

**Goals (this phase).** Make every artifact human-readable on demand (renderer), de-risk
the default model path (Gemini), guarantee artifact depth (PRD floor), make live tooling
reproducible for a judge with their own keys, broaden the eval to a real metric, build the
React UI, and harden the service for an actual deployment.

**Non-goals (explicitly deferred).** Multi-tenant accounts, billing, a managed database
(file store stays v1 — Redis/Postgres is a documented "more-time" item), and PDF/DOCX
export beyond a stretch goal. The JSON-native pipeline does **not** change.

**Invariant (do not violate).** The pipeline is JSON-native and JSON-only-persisted.
Markdown/PDF are **request-time, pure-function transforms** over already-stored typed
objects. The renderer is **infra, not a tool** — it never enters `registry.py` and never
counts toward the 52. `state/models.py` stays the frozen contract.

---

## 2. Workstreams

Each workstream below carries: **status**, **deliverables (concrete files/interfaces)**,
**acceptance criteria**, **tests**, **risk/mitigation**. Effort: S ≤ ½ day, M ≈ 1–2 days,
L ≈ 3+ days.

### W1 — Renderer layer (typed artifact → Markdown) · **must · M · not started**

**Goal.** Every artifact renders to a clean, complete, deterministic Markdown document,
on demand, without touching the pipeline.

**Deliverables.**
```
src/aps/render/
  __init__.py
  base.py          # helpers: h1/h2/h3, table(), bullet/numbered_list,
                   #          evidence_link(ev), citation_refs(evs), front_matter(), placeholder()
  research_md.py   # render(r: ResearchReturn) -> str
  prd_md.py        # render(p: PRD) -> str   (requirements carry inline citations)
  trd_md.py        # render(t: TRD) -> str   (endpoint summary table + fenced OpenAPI yaml)
  execution_md.py  # render(e: ExecutionPlan) -> str
  pitch_md.py      # render(p: PitchPackage) -> str
  registry.py      # RENDERERS: dict[str, Callable[[BaseModel], str]]; render_artifact(name, obj)
```
Contract for every renderer: `render(obj) -> str`, **pure** (no I/O, no LLM, no network),
**total** (every field in the typed object appears in output), **graceful** (missing
optional → `_ none identified _`, never raw `None`/`null`), **deterministic** (sort where
dict/set ordering could vary).

**Acceptance.**
- `render_artifact("prd", prd)` returns Markdown containing every persona name, every
  feature title, the MVP scope, every requirement, and one citation link per `Evidence`.
- TRD render contains an endpoint table (`method · path · summary`) **and** the OpenAPI in a
  fenced ```yaml block.
- Rendering an empty/degenerate artifact produces placeholders, never an exception, never a
  literal `None`/`null`.

**Tests** (`tests/unit/test_render_*.py`, one per renderer): round-trip completeness,
empty-input, citation integrity, byte-determinism (render twice → identical). These run
offline with zero new deps.

**Risk.** Scope creep into "pretty" formatting. *Mitigation:* the test asserts content
presence, not aesthetics — ship correct, iterate on polish.

### W2 — Validate Gemini tool-calling live · **must · S · open**

**Goal.** The documented default (`APS_MODEL_PROVIDER=gemini`, ADR-0002) provably selects
tools, so a judge using their own `GEMINI_API_KEY` does not hit an unverified path.

**Deliverables.** Extend `scripts/live_research_smoke.py` to assert the contract under
Gemini; record numbers (distinct tools, tool calls, evidence count) in `docs/MEMO.md`
beside the NIM numbers. If Gemini returns empty `tool_calls`, fix at the source: verify
`bind_tools` binding, tighten any tool `args_schema` Gemini rejects (no unsupported JSON-
schema types), and check temperature isn't suppressing tool use.

**Acceptance.** A fresh checkout + `GEMINI_API_KEY` reproduces a run that selects ≥2
distinct retrieval tools, terminates, and collects real evidence; MEMO cites both
providers. **Done-gate for the whole phase** (highest-risk unknown — do it first).

**Tests.** A `@pytest.mark.live` test (skipped without a key) asserting ≥2 distinct tools
+ non-empty evidence; never runs in CI.

**Risk.** Gemini free-tier 429s during fan-out. *Mitigation:* `infra/llm.acquire_llm()`
already throttles; verify `llm_rpm` matches Gemini's quota.

### W3 — Guarantee PRD depth (thin-PRD fix) · **must · M · open**

**Goal.** The deep vertical never emits a 1-feature PRD when richer signal exists.

**Deliverables.**
1. Diagnose with several diverse ideas: count `PainPoint`s from `extract_pain_points` and
   their severity spread; locate the bottleneck (sparse evidence vs. over-collapsing
   clustering vs. `prioritize_features`/`assemble_prd` dropping low-severity pains).
2. Apply the minimal fix: loosen clustering so distinct pains don't merge, and/or add a
   **feature floor** in `assemble_prd` — when ≥N pains exist, derive ≥N features (mirrors
   the existing TAM floor-fix in `estimate_market_size`). When evidence is genuinely sparse,
   let the fan-out plan one extra angle rather than the PRD silently thinning.

**Acceptance.** PRD emits **≥3 features** on every gold idea where ≥3 distinct pains exist.

**Tests.** Unit test on `assemble_prd`/`prioritize_features` asserting the floor; plus the
W5 gold-set regression assertion so it can't regress unnoticed.

**Risk.** A floor that fabricates filler features. *Mitigation:* the floor only promotes
**already-extracted** lower-severity pains into features — never invents content; if pains
< floor, the PRD is honestly short and the eval records why.

### W4 — Harden token-gated / optional-dependency tools · **high · S–M · partial**

**Goal.** Anyone with keys gets live capability; every fallback is loud; the README maps
each key to what it unlocks.

**Deliverables.**
- Add `pytrends` to a `[trends]` optional extra in `pyproject.toml` + `requirements.txt`,
  documented; `trends_interest` is real on that install instead of fixture-only.
- Wire the Reddit OAuth path (`REDDIT_CLIENT_ID`/`SECRET` in `tools/retrieval/_reddit.py`)
  so it runs live with credentials (public JSON 429s server-side).
- Audit every token-gated tool (GitHub PAT, Tavily, ProductHunt): the fixture-fallback
  branch must **log that it fell back** (so a judge knows it's fixture data), and the
  README gets a **key → env var → unlocks** table.

**Acceptance.** `pip install` (with the extra) pulls everything the live paths need; README
table is complete; a keyless run logs every fallback explicitly.

**Tests.** Unit test that a token-gated tool with no key returns `[fixture]`-stamped
evidence and logs the fallback (assert via caplog / the stamp).

### W5 — Broaden the eval beyond one gold item · **high · M · open**

**Goal.** Metrics rest on ≥4 ideas across domains, not just `g01`.

**Deliverables.** The gold set already has 8 ideas; run ≥4 live across domains (consumer
app, dev tool, vertical SaaS, research-heavy), record per-idea numbers in
`tests/evals/report.md`, add the **W3 regression scorer** (`prd_feature_count ≥ 3`) to
`tests/evals/scorers.py`, and update the MEMO success-metrics table with aggregates.

**Acceptance.** MEMO cites metrics averaged across ≥4 ideas; the thin-PRD guard is part of
the harness; `EVALUATION.md` targets (≥90% selection validity, ≥6 sources, ≥80% coverage,
100% schema validity) are measured, not asserted.

**Tests.** `evaluate()` over a multi-idea slice asserts e2e + `prd_valid` + feature-floor on
each (offline, stub research); the live run is a documented manual step.

### W6 — Wire the renderer + close loose ends · **high · S · open**

**Goal.** `?format=md` works through the real API; the demo emits readable docs.

**Deliverables.**
- `GET /runs/{id}/artifacts/{name}?format=md` in `api/main.py`: load stored JSON →
  `render.registry.render_artifact(name, obj)` → `text/markdown`. Plain `GET` stays JSON,
  unchanged. **No change to what is persisted.** This is a **`contract:` change** —
  update `docs/API_CONTRACT.md` and ping P3.
- `scripts/demo_run.py` drops each artifact's rendered Markdown next to its JSON.
- Confirm the WIREFRAMES Screen-3 `[⬇ md]` button targets the new endpoint (coordinate P3).

**Acceptance.** `curl ".../artifacts/prd?format=md"` returns Markdown with `Content-Type:
text/markdown`; `?format` absent or `=json` returns JSON identical to today.

**Tests.** API test (TestClient): run → `GET ?format=md` is 200 + `text/markdown` +
contains the idea; plain `GET` is unchanged JSON.

### W7 — React frontend (the excluded area, brought in for production) · **high · L · not started**

> Required for a "production" demo even though prior rounds excluded it. Build against the
> **frozen `docs/API_CONTRACT.md`**, never importing `src/aps`. Until the renderer/contract
> land, develop against `aps.api.mock`.

**Deliverables** (`frontend/`, React + Vite per ADR-0007):
1. **Run console** — one-string idea → `POST /runs`; shows `run_id` + status badge
   (running / **degraded** / complete / failed — the honest states must be visible).
2. **Live pipeline timeline** — subscribe to `GET /runs/{id}/events` (SSE); render
   `agent_start/tool/artifact_ready/composition/research_unit_*` as a streaming timeline.
   This is the Req-1 proof on screen.
3. **Artifact viewer** — fetch typed JSON; render PRD/TRD/etc.; **citation panel** linking
   every finding to its source; **download** (JSON + `?format=md`).
4. **Empty/loading/error/degraded states** — first-class, not afterthoughts.

**Acceptance.** From a clean `npm install && npm run dev` against a live backend, a user
drives a full run from one idea string and sees the streaming timeline + every artifact with
clickable citations. Degraded runs are visibly labeled.

**Tests.** Component tests for the SSE timeline reducer and artifact rendering; a Playwright
smoke (optional) driving one full run against the mock API.

**Risk.** SSE handling/back-pressure in the browser. *Mitigation:* the backend already
replays history on subscribe, so a late/reconnecting client recovers the full trace.

### W8 — Production hardening (service-level) · **must-for-prod · M · open**

`plan.md` is feature-focused; production also needs:

- **Auth.** Replace the single shared `X-APS-Key` with per-client keys or short-lived
  tokens; rate-limit `POST /runs` per key (an idea string triggers ~25–35 live tool calls —
  abuse vector). Document the threat model.
- **Secrets.** All keys via env only (already the pattern); add a `.env.example` audit and a
  README "never commit keys" note; ensure no key is logged (the structured logger must
  redact `Authorization`).
- **Persistence & lifecycle.** The in-memory `_RUNS/_STATES/_BUSES` dicts grow unbounded and
  die on restart. Back them with the existing `artifact_store` read-through (already partial
  for status/artifacts) and add TTL/eviction for buses; document Redis as the scale path.
- **Concurrency limits.** Cap concurrent in-flight runs (a thread pool / semaphore) so N
  simultaneous `POST /runs` can't exhaust the box or the LLM quota.
- **Observability.** Confirm `/metrics` exposes the tool/agent counters; add run-level
  counters (runs by terminal status: complete/degraded/failed) and a request log; wire a
  basic dashboard or at least documented PromQL.
- **Deploy.** A `Dockerfile` + `docker-compose.yml` (api + optional redis), a `/healthz`
  endpoint, and a `RUNBOOK.md` (env vars, how to run, how to read degraded vs failed).
- **CI/CD.** Extend the existing workflow: add a `@pytest.mark.live` job gated on a repo
  secret (manual/scheduled, not PR), and a build job for the frontend.

**Acceptance.** A single `docker compose up` serves the API with `/healthz` green; load of K
concurrent runs degrades gracefully (queues, never crashes); no secret appears in logs.

### W9 — Differentiator features (from plan.md grid) · **post-must · phased**

Build only after W1–W3 + W6 are solid. Each reuses existing analysis tools — they are
**new agents/tools inside the existing scoping model**, not pipeline rewrites:

| Feature | Reuses | Note |
|---|---|---|
| **Startup Score** (demand/competition/risk/monetization 0–10) | `rank_opportunities`, `sentiment_breakdown`, `estimate_market_size` | A scorer over the research brief; renders as a badge row |
| **"Roast My Startup"** skeptic agent | research + PRD | Adversarial agent; memorable demo; its own scoped tools |
| **Judge Mode** (innovation/execution/difficulty) | all artifacts | The hackathon-meta differentiator |
| **Artifact dependency graph** | composition events | Visualizes Req-5; frontend-side from the `composition` events already emitted |
| **Investor Mode** (TAM/SAM/SOM + readiness) | `estimate_market_size` | Extends existing market tooling |

Each must keep the 52-tool count honest (new tools are added to a namespace and counted, or
declared infra) and ship with a unit test + a renderer section.

---

## 3. Sequencing & milestones

> Pull **W2 first** (de-risks the default path; one afternoon) and **W1 in parallel** (the
> highest-visibility win). Frontend (W7) starts as soon as the `?format=md` contract is
> frozen (end of W6).

| Milestone | Contents | Exit gate |
|---|---|---|
| **M1 — Trustworthy core** (days 1–2) | W2 (Gemini verified) · W1 `base.py`+`research_md`+`prd_md` | Gemini numbers in MEMO; PRD/Research render with citations; renderer tests green |
| **M2 — Readable everywhere** (days 2–3) | W1 finish (trd/execution/pitch) · W6 (`?format=md` + demo docs) · W3 (PRD floor) | `?format=md` live; PRD ≥3 features on gold; API test green |
| **M3 — Reproducible & measured** (days 3–4) | W4 (tool hardening + README table) · W5 (multi-idea eval + regression guard) | `pip install` runs live paths; MEMO aggregate metrics across ≥4 ideas |
| **M4 — Shippable product** (days 4–7) | W7 (frontend) · W8 (hardening: auth/persistence/deploy/runbook) | `docker compose up` serves API + UI; full run drivable from the browser; degraded states visible |
| **M5 — Differentiators** (stretch) | W9 (Startup Score, Roast, Judge Mode) · PDF/DOCX export | At least one differentiator live behind a renderer + test |

---

## 4. Definition of Done (release gate)

- [ ] Every artifact renders to clean, complete, deterministic Markdown (W1); reclassified
      as **infra-not-a-tool** in the MEMO (52 count stays honest).
- [ ] `?format=md` returns those docs through the real endpoint; JSON path unchanged (W6).
- [ ] Renderer tests cover completeness / empty / citation-integrity / determinism.
- [ ] Gemini runs a real tool-selecting loop; numbers in MEMO beside NIM (W2).
- [ ] PRD reliably ≥3 features across gold ideas; regression-guarded in eval (W3, W5).
- [ ] `requirements`/extras install every live tool path; README key→capability table (W4).
- [ ] Eval across ≥4 ideas; aggregate numbers in MEMO (W5).
- [ ] Frontend drives a full run from one idea, streams the timeline, shows cited artifacts,
      labels degraded runs (W7).
- [ ] `docker compose up` serves API (+`/healthz`); per-key auth + run rate-limit; no secret
      logged; RUNBOOK written (W8).
- [ ] `pytest` green (current 150 + renderer/eval/api/frontend additions); whole tree
      `ruff`-clean; CI runs the real stack and a gated live job.

---

## 5. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Gemini emits zero tool calls for a judge | Med | **High** (Req-1 collapses for that reviewer) | W2 first; fix binding/schema; document NIM as a verified fallback provider |
| Free-tier 429s mid-demo (fan-out burst) | Med | Med | `infra/llm.acquire_llm()` throttle + `with_retry`; tune `llm_rpm`; keyless path as floor |
| Thin PRD undercuts the depth story | Med | Med | W3 feature floor + W5 regression guard |
| Renderer scope-creeps into design polish | Med | Low | Tests assert content, not aesthetics; ship correct then iterate |
| Contract drift breaks the frontend | Low | High | `?format=md` is a `contract:` PR; freeze `API_CONTRACT.md`; P3 builds on mock until merged |
| In-memory run registry leaks / dies on restart | High (at scale) | Med | artifact_store read-through (partly done) + TTL eviction; Redis documented as scale path |
| Shared API key abused (each run = ~30 live calls) | Med | Med | per-key auth + per-key run rate-limit (W8) |

---

## 6. Ownership & guardrails (unchanged)

- **Frozen:** `src/aps/state/models.py` (typed contract), `docs/API_CONTRACT.md` (change only
  via a `contract:` PR with all-party 👍).
- **Renderer is infra**, never a tool — keep it out of `registry.py`; restate in MEMO.
- **JSON stays the source of truth**; Markdown/PDF are derived, never persisted.
- Small, frequent PRs; one workstream per PR; `ruff` + `pytest` green before merge; commits
  authored by the implementer (no AI co-author).
