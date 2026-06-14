# Autonomous Product Studio — Improved Design

This revision fixes the one requirement that was a pass/fail risk (Req 1: 50+ model-driven tools) and tightens the architecture around it. The product thesis is unchanged: an organization of subagents that turns an idea into a startup execution package.

---

## What was broken, and the fix

**The problem.** The original registry came to ~34 items, several of which (`artifact_storage`, `memory_retrieval`, `logging`, `retry`, `metrics`) are *infrastructure*, not tools a model selects. Worse, the generation layer was a row of near-identical LLM wrappers — `generate_prd`, `generate_trd`, `generate_pitch`, `generate_investor_memo` — which to the model are almost indistinguishable. When tools look alike, the model isn't *choosing*, so "selection driven by the model rather than routed by hand" fails, and a reviewer probing "does anything real happen?" finds nothing behind the artifacts.

**Three principles that fix it:**

1. **Tools are fine-grained, real operations. Artifacts are written by agents, not by wrapper tools.** Instead of one `generate_prd` tool that asks an LLM to write a PRD, the Product agent *reasons over real upstream data* and uses small, distinct tools (`generate_personas`, `prioritize_features`, `define_mvp_scope`) plus a schema-enforcing `assemble_prd`. The writing is the agent's job; the tools are the verbs.

2. **The bulk of the registry is real retrieval.** ~20 tools each hit a *different real data source* (web, GitHub, Hacker News, Reddit, Stack Exchange, Google Trends, arXiv, package registries). These are genuinely distinct, so the model has to actually choose ("GitHub issues vs Reddit vs HN for this pain point?"). This is what makes selection real — and it pads the count honestly.

3. **Selection is model-driven and scoped per agent.** No `if intent == "market": call search_market()` dispatch table. All of an agent's tools are bound to the model via function-calling; the model emits tool calls from their descriptions. Globally the registry is 50+, but **each subagent only ever sees the ~10–20 tools for its bounded context** — that is the concrete answer to "remain coherent at fifty tools rather than collapsing into fifty conditional dispatches."

---

## Redesigned tool registry (52 model-callable tools)

### Research & Retrieval — real external data (20)
Each is a distinct real source; this layer is the proof of Req 1.

| Tool | What it really does | Free source |
|------|--------------------|-------------|
| `web_search` | General web query | Tavily / Brave / Serper free tier |
| `fetch_page` | Fetch + extract readable content from a URL | — |
| `github_search_repos` | Find repos by topic/keyword | GitHub API |
| `github_repo_stats` | Stars, forks, last commit, open-issue count | GitHub API |
| `github_search_code` | Find real usage patterns in code | GitHub API |
| `github_list_issues` | Pull real issues = pain signals | GitHub API |
| `hn_search` | Hacker News stories/comments | Algolia HN API (no key) |
| `hn_thread_comments` | Comment tree for a story | Algolia HN API |
| `reddit_search` | Search posts across subreddits | Reddit API |
| `reddit_subreddit_top` | Top/hot posts in a subreddit | Reddit API |
| `reddit_comments` | Comments for a post | Reddit API |
| `stackexchange_search` | Questions/answers, tag activity | Stack Exchange API |
| `producthunt_search` | Product launches / competitors | PH API or web |
| `trends_interest` | Search-interest time series | pytrends (free) |
| `arxiv_search` | Technical/research depth | arXiv API (free) |
| `wikipedia_summary` | Background / definitions | free |
| `pypi_package_info` | Python ecosystem maturity | PyPI (free) |
| `npm_package_info` | JS ecosystem maturity | npm registry (free) |
| `jobs_search` | Job posts reveal demand + stacks | web |
| `pricing_page_extract` | Pull competitor pricing tiers | fetch + parse |

### Analysis — operate on retrieved data (10)
| Tool | Operation |
|------|-----------|
| `extract_pain_points` | Mine complaints/requests from a corpus |
| `cluster_themes` | Group findings into themes |
| `sentiment_breakdown` | Sentiment over reviews/comments |
| `extract_competitor_features` | Feature lists from competitor content |
| `build_competitor_matrix` | Comparison matrix across competitors |
| `estimate_market_size` | TAM/SAM/SOM from signals, with sources |
| `rank_opportunities` | Score gaps/opportunities |
| `detect_trend_signal` | Rising/declining from trends data |
| `validate_with_sources` | Attach evidence/citations to a claim (grounding) |
| `dedupe_and_rank_evidence` | Consolidate findings |

### Product (6)
`generate_personas` · `generate_user_stories` · `prioritize_features` (RICE/MoSCoW) · `define_mvp_scope` · `acceptance_criteria` · `assemble_prd` (schema validation, not re-generation)

### Architecture (6)
`design_data_model` · `design_api_contract` (emits OpenAPI) · `choose_tech_stack` (justified from constraints) · `estimate_scale` · `design_architecture` (component/service spec) · `assemble_trd`

### Execution (6)
`plan_repo_structure` · `generate_backlog` · `plan_sprints` · `estimate_effort` · `generate_roadmap` · `estimate_infra_cost` (uses real pricing data)

### Presentation (4)
`generate_pitch_outline` · `generate_demo_script` · `generate_investor_memo` · `generate_judge_brief`

**Total: 52 tools, of which 30 (retrieval + analysis) are genuinely distinct because they touch real, different data.**

### Platform capabilities — NOT tools, not counted
`artifact_store`, `memory`, `logging` (Structlog), `metrics` (Prometheus), `retry` (Tenacity), `rate_limiter`, `evaluation` (Pytest). These were previously miscounted as tools. Reframing them as infrastructure is itself a point of judgment to call out in the MEMO — it shows you understood the requirement instead of inflating the list.

---

## Revised agent hierarchy

Fold the duplicate generators into the agents. Each subagent runs in its own context, gets a **scoped subset** of the registry, and returns a typed Pydantic result. The parent holds only the structured returns — which is also your context-management strategy (Req 3) made explicit.

```text
CEO / Orchestrator  (no domain tools; routes goals, holds typed state)
│
├── Research Agent        → retrieval (1–20) + analysis (21–30)
│        returns: { market_size, competitors[], pain_points[], evidence[] }
│
├── Product Agent         → product tools (31–36)
│        consumes Research return; returns: { personas[], features[], mvp_scope, prd }
│
├── Architecture Agent    → architecture tools (37–42)
│        consumes PRD; returns: { data_model, api_spec, stack, trd }
│
├── Execution Agent       → execution tools (43–48)
│        consumes TRD; returns: { repo_plan, backlog, sprints, roadmap, cost }
│
└── Presentation Agent    → presentation tools (49–52)
         consumes all artifacts; returns: { pitch, demo_script, memo }
```

No single agent's model sees more than ~20 tools, so selection stays coherent while the global registry clears 50.

---

## Composition chain (Req 5)

The data actually flows — this is one slide:

```text
Research.return.pain_points + target_users
        → Product.assemble_prd → prd.requirements
        → Architecture.design_data_model / design_api_contract → trd
        → Execution.generate_backlog → sprints
```

Each arrow is a typed handoff, not a re-prompt.

---

## Build order — finish one vertical, don't sprawl

The review evaluates **depth, not completion**, so build this end-to-end and make it real:

**Vertical 1 (build completely): Idea → Research → Validation → PRD**
- `CEO → Research Agent → Product Agent`
- ~15–20 real tool calls, all the "does anything actually happen" parts are real (live web/GitHub/HN/Reddit/trends), clean subagent handoff, real composition into the PRD.
- This is the highest-leverage slice: it's both the Req 1 proof *and* the part most likely to be interrogated.

**Then, in order if time allows:** Architecture (shallow but real OpenAPI output) → Execution → Presentation. Implement these thin and **say so in the MEMO** rather than half-building all ten agents.

---

## Free-tier mapping (ties to your model/cloud constraints)

- **LLM:** Gemini free tier is ideal here — many tool-calling round-trips, generous quota. NVIDIA NIM works too. **Build your own tool layer; do not lean on Gemini's built-in Google Search grounding for Req 1** — the requirement wants *your* registry of distinct tools.
- **No-key / free retrieval:** Hacker News (Algolia), Stack Exchange (low volume), arXiv, Wikipedia, PyPI, npm.
- **Free with a token/credentials:** GitHub (PAT), Reddit (script app), web search (Tavily 1k/mo or Brave free tier).
- **Trends:** pytrends (free, unofficial).

The whole real-research layer is buildable inside free quotas, so a judge can run it with their own keys.

---

## MEMO.md framing

- **What I built:** a real Research→PRD vertical; a 52-tool registry scoped per subagent; model-driven function-calling selection.
- **What I cut:** deep Architecture/Execution/Presentation agents are thin — depth over breadth, one finished vertical beats ten at 40%.
- **What more time would add:** make the later agents real, Redis-backed memory, broader retrieval sources.
- **The decision I'd defend:** an organization of subagents with per-agent scoped tools over a monolithic ReAct loop — it improves long-horizon coherence *and* keeps a 50-tool registry coherent (each model sees a small, distinct set), at the cost of coordination complexity. And: tools are fine-grained real operations while artifact-writing lives in agent reasoning — that is precisely what makes selection genuinely model-driven and clears Req 1.
