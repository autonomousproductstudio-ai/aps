"""live_research_smoke.py — foundation check for the p1/orchestrator-fanout branch.

Runs the REAL research tool-loop against a LIVE model (no stubs) and asserts the
foundation that Send fan-out will sit on top of:

  1. the model selects >= 2 DISTINCT retrieval tools  (model-driven selection, Req-1),
  2. the loop terminates cleanly and returns a typed ResearchReturn,
  3. real evidence was collected.

Why retrieval-tool count is the right signal: the compression step only ever calls
ANALYSIS tools deterministically, so any RETRIEVAL call must have come from the model
choosing it. Distinct retrieval tools > 1 ⇒ the model is genuinely selecting.

This is meaningful even with NO source API keys: the no-key tools (HN, arXiv, Wikipedia,
PyPI, npm, Stack Exchange, jobs) return real data — you only need the LLM key.

Recommended dev model: NIM `nvidia/nvidia-nemotron-nano-9b-v2` (free, agentic, cheap).

Usage:
    # .env:  APS_MODEL_PROVIDER=nim   NVIDIA_API_KEY=nvapi-...
    python scripts/live_research_smoke.py "an AI resume builder that beats ATS filters"

Exit code 0 = PASS (safe to build fan-out), 1 = FAIL (fix on the linear base first).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _tool_counts(namespace: str | None = None) -> dict[str, float]:
    """Distinct tools with >0 calls this process, from the Prometheus counter."""
    from aps.infra.metrics import TOOL_CALLS
    out: dict[str, float] = {}
    collect = getattr(TOOL_CALLS, "collect", None)
    if collect is None:  # prometheus_client absent -> metrics are no-ops
        return out
    for fam in collect():
        for s in fam.samples:
            if not s.name.endswith("_total"):
                continue
            ns = s.labels.get("namespace")
            tool = s.labels.get("tool")
            if namespace and ns != namespace:
                continue
            if s.value and s.value > 0:
                out[tool] = out.get(tool, 0.0) + s.value
    return out


def main() -> int:
    idea = sys.argv[1] if len(sys.argv) > 1 else \
        "an AI resume builder that beats ATS filters"

    from aps.config.settings import get_settings
    s = get_settings()
    model = s.nim_model if s.model_provider == "nim" else s.gemini_model
    print(f"provider = {s.model_provider}")
    print(f"model    = {model}")
    print(f"tool-call cap/agent = {s.max_tool_calls_per_agent}")

    # fail fast on a missing key rather than a confusing 401 mid-loop
    if s.model_provider == "nim" and not os.getenv("NVIDIA_API_KEY"):
        print("\nFAIL: APS_MODEL_PROVIDER=nim but NVIDIA_API_KEY is not set.")
        return 1
    if s.model_provider == "gemini" and not (os.getenv("GEMINI_API_KEY")
                                             or os.getenv("GOOGLE_API_KEY")):
        print("\nFAIL: APS_MODEL_PROVIDER=gemini but GEMINI_API_KEY/GOOGLE_API_KEY not set.")
        return 1

    from aps.agents.research.agent import run_research
    print(f"\nrunning live research loop on: {idea!r}\n")
    try:
        research = run_research(idea)
    except Exception as e:  # the loop should never raise; if it does, that's the finding
        print(f"FAIL: research loop raised {type(e).__name__}: {e}")
        return 1

    retrieval = _tool_counts("retrieval")
    analysis = _tool_counts("analysis")
    print("model-selected retrieval tools :", retrieval or "(none)")
    print("analysis tools fired (compress):", analysis or "(none)")
    print("evidence collected             :", len(research.evidence))
    print("pain points                    :", len(research.pain_points))
    print("competitors                    :", len(research.competitors))
    print("market_size                    :", (research.market_size or "")[:80])

    ok = True
    if len(retrieval) < 2:
        print("\nFAIL: model selected <2 distinct retrieval tools — selection unproven.")
        print("      check: tools bound, descriptions specific, temperature not too low.")
        ok = False
    if not research.evidence:
        print("\nFAIL: no evidence collected.")
        ok = False

    print()
    if ok:
        print("PASS — linear research loop works against a live model. "
              "Safe to build Send fan-out on this engine.")
        return 0
    print("FAIL — fix the linear loop before layering fan-out on it.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
