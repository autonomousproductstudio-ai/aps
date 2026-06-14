# ADR-0006: Server-Sent Events for run streaming

## Status
Accepted

## Context
The UI must show the pipeline live (agents, tool calls, artifacts) — this is how a
reviewer confirms real work happens. Options: polling, WebSocket, SSE.

## Decision
Use **SSE** (`GET /runs/{id}/events`). One-directional server→client streaming is
exactly our need; it's simple over plain HTTP, auto-reconnects, and needs no extra
protocol. WebSocket is reserved for if we later add interactive mid-run controls.

## Consequences
- (+) Trivial server (FastAPI `StreamingResponse`) and client (`EventSource`).
- (+) The event stream doubles as the persisted audit trace.
- (−) Server→client only; no client→server mid-run messages (not needed in v1).

## Alternatives considered
- **Polling:** simplest, but laggy and chatty. Rejected.
- **WebSocket:** bidirectional power we don't need yet; more moving parts. Deferred.
