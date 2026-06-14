"""StartupScore → Markdown scorecard (remaining.md T1.4). Pure, deterministic."""
from __future__ import annotations

from aps.scoring.startup_score import StartupScore
from aps.render import base as b


def _bar(score: float) -> str:
    filled = int(round(score))
    return "█" * filled + "░" * (10 - filled)


def render(s: StartupScore) -> str:
    out = [b.front_matter("Startup Score", s.idea)]
    if not s.grounded:
        out.append("\n> ⚠️ Scored from a **degraded** (stub) research brief — set an LLM key "
                   "for an evidence-grounded score.\n")
    out.append(f"\n## Overall: {s.overall} / 10 — {s.verdict}\n")
    rows = [[d.name, f"{d.score}", _bar(d.score), d.rationale] for d in s.dimensions]
    out.append(b.table(["Dimension", "Score", "", "Why"], rows))
    return "".join(out)
