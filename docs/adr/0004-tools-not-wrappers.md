# ADR-0004: Fine-grained real tools, not LLM wrappers

## Status
Accepted

## Context
The original design had `generate_prd` / `generate_trd` / `generate_pitch` — a row of
near-identical LLM wrappers. To the model these are indistinguishable, so no real
selection happens, and Req 1 ("model-driven, not hand-routed") effectively fails.

## Decision
**Tools are fine-grained real operations; artifact-writing lives in agent reasoning.**
Replace `generate_prd` with small distinct verbs (`generate_personas`,
`prioritize_features`, `define_mvp_scope`) plus a schema-enforcing `assemble_prd`. The
bulk of the registry (~20 retrieval + 10 analysis) touches genuinely different live
sources, so the model must actually choose between meaningfully different capabilities.

## Consequences
- (+) Tool selection is genuinely model-driven (the Req-1 proof).
- (+) Honest tool count from distinct real operations, not padded wrappers.
- (+) A reviewer probing "does anything real happen?" finds live data behind artifacts.
- (−) More tools to implement than four generators — mitigated by P2 parallelism +
  a shared tool interface (each tool ~15 lines behind the protocol).

## Alternatives considered
- **Keep the generators:** fastest to write, but collapses Req 1. Rejected.
