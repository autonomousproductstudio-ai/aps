# Architecture Decision Records

Each ADR captures one significant decision: context, the options weighed, the
decision, and its consequences. Status is one of: Proposed · Accepted · Superseded.

| # | Decision | Status |
|---|----------|--------|
| [0001](0001-langgraph-over-crewai.md) | LangGraph as orchestration framework | Accepted |
| [0002](0002-gemini-free-tier.md) | Gemini free tier as daily-driver LLM | Accepted |
| [0003](0003-postgres-vs-mongo.md) | PostgreSQL as target store; in-memory+JSON for v1 | Accepted |
| [0004](0004-tools-not-wrappers.md) | Fine-grained real tools, not LLM wrappers | Accepted |
| [0005](0005-per-agent-tool-scoping.md) | Per-agent tool scoping (≤20 visible) | Accepted |
| [0006](0006-sse-streaming.md) | SSE for run event streaming | Accepted |
| [0007](0007-react-vite-frontend.md) | React + Vite + TS frontend | Accepted |

## Template
```
# ADR-NNNN: <title>
## Status
## Context
## Decision
## Consequences (positive / negative / neutral)
## Alternatives considered
```
