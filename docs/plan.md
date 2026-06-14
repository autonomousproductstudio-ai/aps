# plan.md — P2 Implementation Plan

**Build state:** Phases 0–6 complete, 146 tests green, one deep vertical (Research → PRD) real.
**Fan-out:** 3 parallel sub-researchers, 11 distinct tools, 60 merged evidence — verified live on NIM.
**This plan:** the next layer of work that turns a technically correct system into one a human
reviewer trusts on sight, plus the loose ends the project notes already flag.

---

## Design principle — JSON stays default, Markdown is opt-in

The system is JSON-native. JSON is the source of truth and the default response everywhere.
The typed handoff between agents, the frontend's structured rendering, schema validation, and
eval scoring all keep consuming JSON unchanged.

The renderer is a **request-time, on-demand transform**:

```
GET /runs/{id}/artifacts/{name}             → typed JSON      (DEFAULT — machines, frontend)
GET /runs/{id}/artifacts/{name}?format=md   → text/markdown   (OPT-IN — humans, downloads)
```

Markdown is computed only when a human explicitly requests it via `?format=md`.
**Only JSON is persisted** — the artifact store holds JSON and only JSON. Markdown is derived
fresh per request and discarded. Nothing in the pipeline changes.

This decoupling makes the MEMO claim airtight: the renderer is platform infra, not a tool,
not part of the pipeline, and not counted in the 52.

---

## Priority order

| # | Workstream | Why it ranks here | Effort |
|---|---|---|---|
| **W1** | Renderer layer — typed artifact → Markdown | Highest visible payoff; every artifact becomes human-readable; satisfies the `?format=md` contract promise | M |
| **W2** | Gemini tool-calling validated live | Biggest correctness risk: default model path is unexercised; a judge's run could produce zero tool calls | S |
| **W3** | Thin-PRD fix (pain extraction → richer features) | The one deep vertical sometimes emits a 1-feature PRD; undercuts the depth story | M |
| **W4** | Token-gated / optional-dep tools hardened | Several tools silently fall back to fixtures; cheap to make them real | S |
| **W5** | Eval broadened beyond one gold item | Targets proven only on `g01`; catches W3 regressions systematically | M |
| **W6** | Wire renderer into API + commit loose ends | Reproducibility for judges; closes the loop | S |

W1, W2, W3 are the must tier. W4–W6 are high-value polish.

---

## W1 — The renderer layer

### Where it lives

```
src/aps/render/
  __init__.py
  base.py            # Renderer protocol + shared helpers
  research_md.py     # ResearchReturn  → Markdown
  prd_md.py          # PRD             → Markdown
  trd_md.py          # TRD             → Markdown (incl. OpenAPI pretty-print)
  execution_md.py    # ExecutionPlan   → Markdown
  pitch_md.py        # PitchPackage    → Markdown
  registry.py        # artifact name → renderer function
```

### Non-negotiable design constraints

- **On-demand only.** The renderer fires exclusively on the `?format=md` request path.
  A normal run never invokes it, and only JSON is persisted in the artifact store.
- **Pure functions.** `render(obj: PRD) -> str`. No I/O, no network, no LLM. Deterministic
  output for a given input — unit-testable, reproducible, safe to recompute on every request.
- **Not a tool.** Does not go in the registry; not counted toward the 52. Infra, like
  `artifact_store`. State this in the MEMO alongside the other infra-not-tools calls.
- **Total over the typed object.** Every field in `state/models.py` for that artifact appears
  somewhere in the rendered doc, or the renderer test fails.
- **Graceful on empty.** A missing optional field renders as `— none identified —`, never a
  crash and never a raw `None`/`null`.

### Shared helpers (`base.py`)

Build once; every renderer uses them:

- `h1/h2/h3(text)` → headings.
- `table(headers, rows)` → GitHub-flavored Markdown table.
- `bullet_list(items)` / `numbered_list(items)`.
- `evidence_link(ev: Evidence)` → `[source · title](url)` with graceful fallback when
  `url`/`title` are absent. This is the credibility primitive — every citation flows through it.
- `citation_refs(evidence: list[Evidence])` → compact inline string like
  `[GitHub #214](...) · [HN](...)` for attaching to a requirement or pain point.
- `front_matter(title, idea, generated_at)` → small header at the top of each doc so a
  downloaded file is self-describing.

### Per-artifact layout

**Research brief (`research_md.py`):**
- Title + idea + generated-at header.
- Market size paragraph with inline source citation.
- Competitors table: name · pricing · features · notes, name linked to URL.
- Pain points list, each with severity badge and `citation_refs` — every pain shows its source.
- Evidence appendix: full deduped list, numbered, each a clickable source. This is the
  "real work" proof a reviewer can click through.

**PRD (`prd_md.py`):**
- Header + idea.
- Personas table or per-persona subsections: name · role · goals · frustrations.
- Features, prioritized, numbered, each with title · description · priority badge.
- MVP scope paragraph.
- Requirements (R1, R2, …) **each with inline citations back to the evidence that motivated
  it.** This is the visible link from "we found this real pain" → "so we wrote this
  requirement." It directly realizes the WIREFRAMES.md Screen-3 sketch.
- Sources appendix.

**TRD (`trd_md.py`):**
- Stack as a table: concern · choice.
- Data model as entity/field tables (not a raw JSON dump).
- OpenAPI spec: pretty-printed in a fenced ```yaml block, plus a human summary table of
  endpoints (method · path · summary) above it.
- Scale estimate paragraph.

**Execution plan (`execution_md.py`):**
- Repo plan as a directory tree in a fenced block.
- Backlog as a table: id · title · estimate · priority.
- Sprints as grouped subsections.
- Roadmap + infra-cost paragraphs.

**Pitch package (`pitch_md.py`):**
- Pitch outline, demo script, investor memo, judge brief — each as its own headed section.

### Tests (`tests/unit/test_render_*.py`)

For each renderer:

1. **Round-trip completeness:** build the typed object from a fixture, render it, assert every
   field's content appears in output (every persona name, every feature title, every evidence URL).
2. **Empty/degenerate input:** empty competitor list, zero pain points, missing optional URL
   → renders the graceful placeholder, no exception, no literal `None`/`null` in output.
3. **Citation integrity:** every `Evidence` in the object produces a link in the rendered doc;
   no requirement with source evidence renders without its citation refs.
4. **Determinism:** render twice, assert byte-identical (sort where needed to prevent
   dict-ordering nondeterminism).

### Stretch: PDF / DOCX export

Once Markdown renderers exist and are tested, export is a thin conversion step, not new
content logic:

- **PDF:** `render/export.py::to_pdf(markdown: str) -> bytes` via `markdown` + `weasyprint`,
  or equivalent.
- **DOCX:** via `pandoc` if available, else a minimal `python-docx` writer.
- Expose as `?format=pdf` / `?format=docx` on the artifact endpoint. Flag as a `contract:`
  change so P3 knows the new formats exist. Mark as stretch — Markdown alone closes the
  human-readability gap.

---

## W2 — Validate Gemini tool-calling live

**The risk:** only the NIM nemotron path has been exercised end-to-end. Gemini is the
documented default daily-driver (ADR-0002, PRD Q1), so a judge running with their own
`GEMINI_API_KEY` hits an unverified code path. If `ai.tool_calls` comes back empty, the
Req-1 proof silently collapses for that reviewer.

**Steps:**

1. Run `scripts/live_research_smoke.py` with `APS_MODEL_PROVIDER=gemini` + live `GEMINI_API_KEY`.
2. Assert the same contract as the NIM smoke: model selects ≥2 distinct retrieval tools, loop
   terminates, real evidence collected, exit 0.
3. If tool calls come back empty, check: (a) tools are bound via `bind_tools` on the Gemini
   model, (b) tool descriptions are specific enough for Gemini's function-calling, (c)
   temperature isn't suppressing tool use (`IMPLEMENTATION.md §4`). Gemini is stricter than NIM
   about schema shape — verify `args_schema` JSON schemas have no unsupported types.
4. Record the run's numbers (distinct tools, evidence count, tool calls) and add them next to
   the NIM numbers in `MEMO.md` so both providers are documented.

**Done when:** a fresh checkout + `GEMINI_API_KEY` reproduces a real tool-selecting run, and
the MEMO cites Gemini numbers alongside NIM numbers.

---

## W3 — Fix the thin-PRD problem

**The symptom:** on some ideas the PRD emits a single feature, because pain extraction returns
too few distinct, high-signal pains for the prioritization step to build on. Since Research → PRD
is the one deep vertical reviewers probe hardest, a 1-feature PRD undercuts the depth story.

**Diagnosis path:**

1. Run several diverse ideas through `gather_evidence` and inspect how many `PainPoint` objects
   `extract_pain_points` yields and their severity spread.
2. Identify whether the bottleneck is (a) too little evidence on certain ideas, (b)
   `extract_pain_points` over-collapsing distinct complaints into one, or (c) `prioritize_features`
   / `assemble_prd` dropping low-severity pains before they become features.

**Likely fixes (choose based on diagnosis):**

- Loosen the clustering threshold in `extract_pain_points` / `cluster_themes` so distinct pains
  aren't merged into one mega-pain.
- Ensure `assemble_prd` derives at least N features when ≥N pains exist (a floor, mirroring
  the TAM floor-fix from the analysis tooling — never assert a thin result when richer signal
  is present).
- When evidence is genuinely sparse, let the research fan-out plan an extra angle rather than
  the PRD silently thinning.

**Guardrail:** add a regression case to the eval (W5) asserting PRD feature-count ≥ 3 on the
gold ideas so this can't regress unnoticed.

---

## W4 — Harden token-gated and optional-dependency tools

Several tools silently degrade to fixtures, which is fine for keyless judges but wastes real
capability for anyone with keys:

- **Reddit:** public JSON 429s server-side. Document and wire the OAuth path
  (`REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` via `tools/retrieval/_reddit.py`) so it runs
  real with credentials.
- **`trends_interest`:** needs `pytrends`, which is not in `requirements`. Add it (or a
  `[trends]` optional extra) and document the install. Right now it is fixture-only on a clean
  install even though the implementation is real.
- **General audit:** for every token-gated tool (GitHub PAT, Tavily, ProductHunt), confirm the
  fixture-fallback path logs clearly that it fell back — so a judge knows it is fixture data,
  not live — and the README documents which env var unlocks live mode.

**Done when:** `requirements`/extras install everything the live paths need, and a table in the
README maps each token-gated tool → its env var → what it unlocks.

---

## W5 — Broaden the eval beyond one gold item

Only `g01` has been run live, so the `EVALUATION.md` targets (≥90% selection validity, ≥6
distinct sources, ≥80% evidence coverage, 100% PRD schema validity) rest on a single data point.

**Steps:**

1. Add 3–5 more gold ideas spanning different domains (consumer app, dev tool, vertical SaaS,
   research-heavy topic) so tool-selection diversity is actually exercised across the set.
2. Run the gold set live and record per-idea numbers in `tests/evals/report.md`.
3. Add the W3 regression scorer: **PRD feature-count ≥ 3** as a gold-set assertion.
4. Update the MEMO success-metrics table (`PRD.md §8`) with aggregate numbers, not just `g01`.

**Done when:** the MEMO cites metrics averaged across ≥4 ideas, and the thin-PRD regression
guard is part of the eval harness.

---

## W6 — Wire the renderer + commit loose ends

- **Wire `?format=md` into the API.** Implement `?format=md` on
  `GET /runs/{id}/artifacts/{name}` by reading the stored JSON, dispatching through
  `render/registry.py`, and returning `text/markdown`. The plain `GET` stays JSON, unchanged.
  No change to what gets stored — the artifact store still holds JSON only; the renderer runs
  at request time on the already-stored typed object.
- **Frontend download buttons.** Confirm the `[⬇ md]` button in `WIREFRAMES.md` Screen 3 hits
  the new endpoint (coordinate with P3; the contract already promises it).
- **Commit `scripts/run_research.py`** (currently untracked) so the standalone runner survives
  and is reproducible for judges.
- **Demo polish.** Have `scripts/demo_run.py` drop the rendered Markdown of each artifact next
  to the JSON in the output folder, so a judge running the demo gets readable documents, not
  just JSON.

---

## Features — priority grid

The build targets two audiences: **Solo Founders / Hackathon Builders** (primary users) and
**Judges / Reviewers** (secondary users, but the real v1 audience).

### Must-have (non-negotiable for the assignment)

| Feature | Requirement |
|---|---|
| 50+ model-callable tools across 4+ namespaces, scoped per agent | Req 1 / M5 |
| Real subagent orchestration — isolated context + typed returns | Req 2 / M1, FR-2 |
| Model-driven tool selection (function-calling, not dispatch table) | Req 3 / FR-3 |
| Context management via structured handoffs (orchestrator holds typed returns only) | Req 3 |
| Real composition: Research → PRD with typed handoff | Req 5 / M4, FR-5 |
| Evidence grounding — every retrieval tool returns normalized `Evidence` | FR-4 |
| Live observability — SSE event stream of agents / tools / artifacts | Req 4 / M6, FR-6 |
| Graceful degradation on tool failure — never crashes the pipeline | FR-8, US-6 |
| Eval harness with gold set + metrics | M7 |
| Schema-valid artifacts, every run | FR-5 |

### Most-used (core loop — every run)

1. One-string idea → full execution package.
2. Live pipeline timeline (agents + tool calls streaming) — the Req-1 proof on screen.
3. Evidence / citation panel — every finding linked to its source.
4. Artifact viewer with inline citations on requirements.
5. Download artifacts (JSON + on-demand Markdown).

### Audience-attracting differentiators

1. **Genuine model-driven tool selection across 20+ distinct live sources.** Most submissions
   fake diversity with near-identical LLM wrappers; this system has the model choosing between
   GitHub issues, HN, Reddit, Stack Exchange, arXiv, package registries, and trends.
2. **Studio behaves like a startup team.** CEO → Research → Product → Architecture → Execution
   → Presentation org — not a chatbot, not a coding agent.
3. **Traceable evidence grounding.** Every claim has a clickable source. Rare and immediately
   credible.
4. **Reproducible on free tiers with the judge's own keys.** A judge who can clone, drop in a
   `GEMINI_API_KEY`, and reproduce the numbers trusts you far more than a hosted demo.
5. **Honest depth-over-breadth story (the MEMO).** Openly stating "Research → PRD is deep, the
   rest is thin-but-real, here's why" attracts sophisticated reviewers — it shows judgment.
6. **On-demand human-readable rendering.** Flip any artifact to a polished document — persona
   tables, cited requirements — without altering the underlying JSON-native pipeline.

### High-value additions (build after must-haves are solid)

| Feature | Persona | Notes |
|---|---|---|
| Startup Score (demand / competition / risk / monetization, 0–10) | Founders, Judges | People love scores; maps cleanly to existing analysis tools |
| "Roast My Startup" skeptic agent | Founders, Judges | Memorable; demonstrates adversarial-agent design |
| Judge Mode (innovation / execution / technical difficulty scores) | Judges | Unique differentiator for a hackathon submission about hackathon builders |
| Artifact dependency graph (Research → PRD → TRD → …) | Judges | Visualizes composition; proves Req 5 at a glance |
| Investor Mode (TAM/SAM/SOM + funding readiness) | Founders | Extends market-size tooling already present |
| Build vs Buy analysis | Founders | Extension of competitor intelligence |

---

## Definition of done

- [ ] Every artifact renders to a clean, complete, deterministic Markdown document (W1).
- [ ] `?format=md` returns those documents through the real API endpoint (W6).
- [ ] Renderer unit tests cover completeness, empty-input, citation integrity, determinism (W1).
- [ ] Gemini path runs a real tool-selecting research loop; numbers in MEMO (W2).
- [ ] PRD reliably emits ≥3 features across the gold ideas; regression-guarded in eval (W3, W5).
- [ ] `requirements`/extras install everything the live tool paths need; README env-var table (W4).
- [ ] Eval run across ≥4 ideas; aggregate numbers in MEMO (W5).
- [ ] `scripts/run_research.py` committed; demo drops rendered docs alongside JSON (W6).
- [ ] Renderer reclassified as infra-not-a-tool in the MEMO (keeps the 52 count honest).
- [ ] `pytest` green (existing 146 + new renderer / eval tests).

---

## Sequencing

| Day | Work |
|---|---|
| 1 | W2 (Gemini smoke — fast, de-risks the default path) + W1 `base.py` + `research_md.py` + `prd_md.py` (the two artifacts judges read most) |
| 2 | Finish W1 (trd / execution / pitch renderers + tests) + W6 wiring (`?format=md` endpoint) |
| 3 | W3 thin-PRD diagnosis + fix; W4 tool hardening |
| 4 | W5 eval broadening + regression guard; MEMO updates; stretch PDF / DOCX export |

Pull W1 and W2 forward regardless — the renderer is the highest-visibility win and the Gemini
check is the highest-risk gap.
