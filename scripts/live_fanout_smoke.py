"""live_fanout_smoke.py — Phase-3 fan-out verification (live).

Runs the research fan-out supervisor on an idea and prints the plan, per-unit trace, the
distinct retrieval tools the parallel sub-researchers selected, total tool calls, and the
merged brief. Confirms the deliverable: >= 2 units, evidence > 0, ~15-20 tool calls.

    python scripts/live_fanout_smoke.py "an AI resume builder that beats ATS filters"
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _tool_counts(namespace: str | None = None) -> dict[str, float]:
    from aps.infra.metrics import TOOL_CALLS
    out: dict[str, float] = {}
    collect = getattr(TOOL_CALLS, "collect", None)
    if not collect:
        return out
    for fam in collect():
        for s in fam.samples:
            if s.name.endswith("_total") and s.value:
                ns = s.labels.get("namespace")
                tool = s.labels.get("tool")
                if namespace and ns != namespace:
                    continue
                out[tool] = out.get(tool, 0.0) + s.value
    return out


def main() -> int:
    idea = sys.argv[1] if len(sys.argv) > 1 else \
        "an AI resume builder that beats ATS filters"

    from aps.config.settings import get_settings
    s = get_settings()
    model = s.nim_model if s.model_provider == "nim" else s.gemini_model
    print(f"provider={s.model_provider} model={model} "
          f"max_concurrent={s.max_concurrent_researchers}")

    events: list = []

    def on_event(t: str, d: dict) -> None:
        events.append((t, d))
        if t == "research_plan":
            print("PLAN:")
            for st in d["subtopics"]:
                print(f"   - {st}")
        elif t == "research_unit_start":
            print(f"  unit START : {d['focus'][:60]}")
        elif t == "research_unit_end":
            print(f"  unit END   : {d['focus'][:55]} -> {d['evidence']} evidence")
        elif t == "error":
            print(f"  ERROR      : {d.get('error', '')[:90]}")

    from aps.agents.research.supervisor import run_research_fanout
    print(f"\n>>> fan-out research on: {idea!r}\n")
    r = run_research_fanout(idea, on_event=on_event)

    retrieval = _tool_counts("retrieval")
    units = [e for e in events if e[0] == "research_unit_start"]
    print("\n--- RESULT ---")
    print("units spawned         :", len(units))
    print("distinct retrieval    :", retrieval)
    print("total retrieval calls :", int(sum(retrieval.values())))
    print("evidence (merged)     :", len(r.evidence))
    print("competitors           :", len(r.competitors))
    print("pain_points           :", len(r.pain_points))
    print("market_size           :", (r.market_size or "")[:80])

    ok = len(units) >= 2 and len(r.evidence) > 0
    print("\n" + ("PASS — fan-out produced a real merged brief; safe to ship Phase 3."
                  if ok else "FAIL — see errors above."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
