"""Debate → Markdown (remaining.md T2.3). Pure, deterministic."""
from __future__ import annotations

from aps.debate.debate import Debate
from aps.render import base as b

_EMOJI = {"Build": "✅", "Pivot / de-risk first": "🟡", "Don't build (yet)": "🛑"}


def render(d: Debate) -> str:
    out = [b.front_matter("Autonomous Debate", d.idea)]
    out.append(f"\n## Verdict: {_EMOJI.get(d.verdict, '•')} {d.verdict}  "
               f"(confidence {int(d.confidence * 100)}%)\n")
    out.append(f"\n*Startup Score {d.startup_score}/10 · Risk {d.risk_score}/10 — {d.rationale}*\n")

    out.append(b.h2("🟢 The case FOR (Research agent)"))
    out.append(b.bullet_list(d.build_case))

    out.append(b.h2("🔴 The case AGAINST (Risk agent)"))
    out.append(b.bullet_list(d.risk_case))
    return "".join(out)
