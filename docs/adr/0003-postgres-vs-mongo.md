# ADR-0003: PostgreSQL as target store; in-memory + JSON for v1

## Status
Accepted

## Context
We need to persist runs, artifacts, and (later) cross-run memory. The PRD scopes
persistence as "later"; v1 must demo without infra overhead. Candidates: PostgreSQL,
MongoDB, SQLite, in-memory.

## Decision
**v1:** in-memory run store + JSON snapshots to disk (also reused as eval/mock
fixtures). **Documented target:** PostgreSQL (typed, relational, fits our structured
artifacts; JSONB for flexible artifact bodies). Redis for cross-run memory is *later*.

## Consequences
- (+) Zero infra to demo; JSON snapshots double as fixtures for P3's mock API and evals.
- (+) Postgres path is clear when we need durability.
- (−) No durability across process restarts in v1 (acceptable; stated in MEMO).

## Alternatives considered
- **MongoDB:** flexible docs, but our artifacts are strongly typed; relational +
  JSONB in Postgres gives both structure and flexibility. Rejected as primary.
- **SQLite for v1:** viable, but in-memory + JSON is even lighter and gives us
  fixtures for free. Chosen instead.
