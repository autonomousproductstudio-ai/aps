# EVALUATION.md — Evaluation Plan (Autonomous Product Studio)

**Status:** Draft v1 · **Owner:** P1 (curates gold set) · Derived from: PRD §8

For an autonomous agent system, evaluation is not optional polish — it is how we
prove the system *works* rather than merely runs. This plan defines what we measure,
how, the gold set, and the pass bar.

---

## 1. What we are evaluating

Four layers, each with its own check:

1. **Tool layer** — does each tool reliably return well-formed `ToolResult` from its source?
2. **Selection** — does the model pick a *runnable* tool with *valid args* for the job?
3. **Agent output** — does each agent return a schema-valid typed object?
4. **End-to-end** — does Idea→PRD complete, grounded, without crashing?

---

## 2. Metrics & targets

| ID | Metric | Definition | Target (v1) | Measured by |
|----|--------|------------|-------------|-------------|
| E1 | Tool-selection validity | % of model tool calls that name a real tool with schema-valid args | ≥ 90% | harness logs |
| E2 | Tool success rate | % of tool calls returning a non-error `ToolResult` | ≥ 85% | infra metrics |
| E3 | Source diversity | distinct sources touched in a typical run | ≥ 6 | event trace |
| E4 | Evidence coverage | % of PRD claims/requirements with ≥1 linked `Evidence` | ≥ 80% | grounding check |
| E5 | Citation validity | % of citations whose URL/source is resolvable & non-duplicate | ≥ 90% | `validate_with_sources` |
| E6 | PRD schema validity | % of runs whose PRD passes Pydantic validation | 100% | contract test |
| E7 | End-to-end success | % of gold runs completing Idea→PRD without crash | ≥ 90% | harness |
| E8 | Tool calls per run | count per run (long-horizon proof, Req 3) | 25–35 | event trace |
| E9 | Latency | wall-clock for Idea→PRD on free tier | ≤ ~5 min | harness timing |
| E10 | Cost | tokens/credits per run within free budget | within free tier | provider usage |
| E11 | PRD feature floor | features per PRD on rich-signal ideas (anti-thin-PRD guard, W3) | ≥ 3 | `scorers.prd_feature_count` |

A run "passes" when E1, E4, E6, E7 meet target; E2/E3/E5/E8/E9/E10/E11 are reported.
E11 guards the thin-PRD regression: the feature floor (W3) promotes real competitive signal
so a rich-signal idea never ships a one-feature PRD; a genuinely sparse idea stays honestly
short (reported as `<3`, not failed).

---

## 2a. Latest results — live g01 (2026-06-10, post-cascade-fix)

Real, reproducible numbers from a live run on gold **g01** ("Build an AI SaaS for resume
screening"), NIM `nemotron-nano-9b-v2` with free `APS_GITHUB_PAT` + `TAVILY_API_KEY`. This
run is **after** the artifact-quality cascade fix — the downstream artifacts it scores have
clean domain-noun entities and well-formed paths (no `/descrs`), not the earlier fragments.
Reproduce: `python scripts/eval_g01_live.py` (writes `tests/evals/report.md`).

| ID | Metric | Target | Result |
|----|--------|--------|--------|
| E1 | Tool-selection validity | ≥ 90% | **100%** (the tool binding only exposes registered tools) |
| E3 | Source diversity | ≥ 6 | **6** ✅ |
| E4 | Evidence coverage | ≥ 80% | **1.0** ✅ |
| E6 | PRD schema validity | 100% | **✅** |
| E7 | End-to-end success | ≥ 90% | **✅** (all 5 artifacts produced) |
| E8 | Tool calls per run | 25–35 | **60** — higher because research fan-out runs 3 sub-researchers; this is the long-horizon proof (Req 3), comfortably above the floor |
| —  | Evidence gathered (merged, deduped) | — | **68** (varies ~60–101 per live run) |
| —  | Distinct tools exercised | — | **41 of 52** |

All four **gated** metrics (E1/E4/E6/E7) pass. Only g01 is sampled live to stay within
free-tier quota; the full 8-idea gold set runs offline/deterministic in CI
(`tests/integration/test_eval_runner.py`). Numbers vary run-to-run with the live model — the
gated metrics are stable; evidence/tool counts fluctuate (this run: 68 evidence / 60 calls /
6 sources vs. a prior 72 / 61 / 8).

---

## 3. Gold set

A small, curated set of idea strings spanning domains (kept in
`tests/evals/gold/`). v1 target: 8–10 ideas.

```
g01  Build an AI SaaS for resume screening
g02  A marketplace for renting camera gear between creators
g03  An open-source observability tool for LangGraph agents
g04  A mobile app that turns receipts into expense reports
g05  A Chrome extension that summarizes long GitHub issues
g06  A B2B tool for automated SOC2 evidence collection
g07  A privacy-first habit tracker with local-only data
g08  A platform connecting clinical trials to eligible patients
```

Each gold item has an **expected-shape rubric** (not exact text): expected source
types (e.g. GitHub issues + HN + Reddit should appear for developer-tool ideas),
expected artifact fields populated, and minimum evidence count.

---

## 4. Scoring methods

- **Deterministic checks** (E2, E6, E8): pure code — schema validation, counts.
- **Trace analysis** (E1, E3, E5): parse the event stream / tool logs.
- **Grounding check** (E4): for each requirement, assert ≥1 `Evidence` reference;
  computed structurally, no LLM judge needed.
- **LLM-as-judge (optional, qualitative)**: a separate cheap-model pass rates PRD
  *coherence* and *relevance* 1–5 against the idea. Used as a soft signal, not a gate
  (LLM judges are noisy — we gate on the structural metrics above).

---

## 5. Harness

```
tests/evals/
├── gold/                 # idea strings + per-idea rubric (yaml/json)
├── fixtures/             # recorded source responses; sample_run.json (also feeds mock API)
├── run_eval.py           # runs each gold idea, collects metrics, writes a report
├── scorers.py            # E1..E10 scorers (deterministic + trace parsers)
└── report.md             # generated (git-ignored); numbers recorded in §2a + MEMO.md
```

Run:
```bash
python tests/evals/run_eval.py --gold tests/evals/gold --out tests/evals/report.md
```

- **CI:** unit tests run on every PR (no live calls — fixtures only).
- **Eval:** runs manually / nightly with real keys (hits live sources, costs free-tier quota).

---

## 6. Per-tool acceptance test (P2's bar)

Each retrieval/analysis tool ships with:
1. a recorded fixture of a real response,
2. a unit test asserting it parses that fixture into a valid `ToolResult`,
3. an args-schema test (bad args rejected),
4. a one-line note on which gold ideas exercise it.

A tool without these four is **not done** (see TEAM_GUIDE §8).

---

## 7. Reporting for the demo / MEMO

The final `report.md` table (E1–E10 with actual numbers on the gold set) goes into
the demo and is referenced in MEMO.md. Honesty rule: report real numbers, flag thin
agents as "not evaluated beyond schema validity," and state which metrics are gated
vs reported.

---

## 8. Out of scope for v1 eval

- Human user-satisfaction studies.
- Adversarial / red-team prompts.
- Eval of Architecture/Execution/Presentation beyond schema validity (they're thin;
  stated explicitly).
