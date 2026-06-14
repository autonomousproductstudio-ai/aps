# ADR-0007: React + Vite + TypeScript frontend

## Status
Accepted

## Context
P3 needs to ship a run console, live timeline, evidence panel, and artifact viewer
fast, decoupled from the backend, and typed against the API contract.

## Decision
**React + Vite + TypeScript + Tailwind.** Vite for instant dev server; TS types
generated from / hand-mirrored to API_CONTRACT.md shapes; `EventSource` for SSE.
P3 develops entirely against the mock API until the real orchestrator lands.

## Consequences
- (+) Fast iteration; strong typing against the contract; large ecosystem.
- (+) Fully decoupled — frontend is buildable Day 1 on the mock.
- (−) Type drift risk if API_CONTRACT.md changes silently — mitigated by `contract:` PRs.

## Alternatives considered
- **Plain HTML/JS:** less overhead but weaker for a live, stateful pipeline UI. Rejected.
- **Next.js:** SSR we don't need for a single-page demo console. Rejected.
