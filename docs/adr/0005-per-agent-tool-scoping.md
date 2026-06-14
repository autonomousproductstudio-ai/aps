# ADR-0005: Per-agent tool scoping (≤20 visible to any model)

## Status
Accepted

## Context
A 50+ tool registry handed to one model degrades selection quality and invites
"fifty conditional dispatches." The requirement wants coherence at fifty tools.

## Decision
Bind tools to models **per agent, per bounded context**. The registry is global and
clears 50, but each subagent's model sees only its namespace (~10–20 tools): Research
sees retrieval+analysis, Product sees product, etc. Selection is via LangChain
`bind_tools` (function-calling), never an `if intent == ...` dispatch table.

## Consequences
- (+) Selection stays a real, coherent choice within a small set.
- (+) Directly answers the "coherent at fifty tools" requirement.
- (+) Namespacing also organizes the codebase and team ownership.
- (−) The orchestrator must route to the right agent so the right tools are in scope.

## Alternatives considered
- **All tools to one ReAct agent:** simplest wiring, worst selection at scale. Rejected.
