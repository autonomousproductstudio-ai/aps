# ADR-0001: LangGraph as the orchestration framework

## Status
Accepted

## Context
We need a multi-agent orchestrator with: typed shared state, deterministic routing,
fan-out to subagents, recursion control, and a clean place to fork Open Deep
Research's research loop. Candidates: LangGraph, CrewAI, custom asyncio, Claude Agent SDK.

## Decision
Use **LangGraph**. It is a framework (not a template): typed `StateGraph`, prebuilt
supervisor, `Send` API for fan-out, built-in recursion limits, and first-class
LangChain `bind_tools` for model-driven tool selection. Open Deep Research is built
on LangGraph, so forking its research loop is direct.

## Consequences
- (+) Typed state matches our Pydantic spine; ODR fork is low-friction.
- (+) `Send`/supervisor cover the orchestration we'd otherwise hand-roll.
- (+) Model-agnostic — works with free Gemini/NIM.
- (−) Learning curve on graph semantics; some boilerplate per node.

## Alternatives considered
- **CrewAI:** higher-level role abstractions but less control over state/recursion;
  harder to prove genuine model-driven selection. Rejected.
- **Claude Agent SDK:** excellent built-in subagents/tools, but Claude-only and
  governed by commercial terms — conflicts with the free-model requirement. Rejected
  for v1 (see project notes correcting the "Agent SDK + free Gemini" misconception).
- **Custom asyncio:** maximal control, maximal time cost. Rejected for a 5-day build.
