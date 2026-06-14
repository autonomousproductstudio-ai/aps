# ADR-0002: Gemini free tier as the daily-driver LLM

## Status
Accepted

## Context
The system makes 25–35 tool-calling round-trips per run and must run on free tiers so
judges reproduce it with their own keys. Candidates: Google Gemini (AI Studio free),
NVIDIA NIM free credits, OpenAI/Anthropic (paid).

## Decision
Use **Gemini free tier** (`langchain-google-genai`, `ChatGoogleGenerativeAI`) as the
default; keep **NVIDIA NIM** as a one-switch fallback. Both are OpenAI-compatible for
tool calling and integrate with LangGraph.

## Consequences
- (+) Very high free token/request quota — comfortably covers many tool-call round-trips.
- (+) Native function-calling + structured output; LangChain integration is mature.
- (+) Judges plug in their own free key.
- (−) Rate/quota limits vary by region → rate limiter + caching required.
- (−) Do NOT use Gemini's built-in Google Search grounding for Req 1; we must ship our
  own distinct-tool registry. Stated explicitly so no one shortcuts it.

## Alternatives considered
- **NIM:** strong agentic models, but tighter credit budget (1k–5k, 40 RPM). Kept as fallback.
- **Paid OpenAI/Anthropic:** breaks the free-reproducibility requirement. Rejected for v1.
