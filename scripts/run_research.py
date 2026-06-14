"""run_research.py — Phase-2 deliverable: run the Research Agent standalone.

Given an idea string, runs the real research tool-loop (live sources) and prints the
typed, evidence-backed brief: market_size, competitors[], pain_points[], evidence[].

    python scripts/run_research.py "a self-hosted note-taking app for developers"
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Windows consoles default to cp1252 and choke on ★/—/etc. in real evidence text.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main() -> int:
    idea = sys.argv[1] if len(sys.argv) > 1 else \
        "a self-hosted note-taking app for developers"

    from aps.agents.research.agent import run_research
    r = run_research(idea)

    print("\n================ RESEARCH BRIEF ================")
    print(f"idea         : {r.idea}")
    print(f"market_size  : {r.market_size}")
    print(f"competitors  : {len(r.competitors)}")
    for c in r.competitors[:8]:
        price = f" — {c.pricing}" if c.pricing else ""
        print(f"   • {c.name}{price}  ({len(c.features)} features)")
    print(f"pain_points  : {len(r.pain_points)}")
    for p in r.pain_points[:8]:
        print(f"   • [{p.severity.value}] {p.text[:100]}")
    print(f"evidence     : {len(r.evidence)}")
    for e in r.evidence[:12]:
        title = (e.title or "")[:55]
        print(f"   [{e.source}] {title}")
        print(f"       {e.snippet[:110]}")

    print("\n================ TYPED JSON (first 1200 chars) ================")
    print(json.dumps(r.model_dump(), default=str, indent=2)[:1200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
