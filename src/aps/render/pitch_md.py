"""PitchPackage → Markdown (plan.md W1)."""
from __future__ import annotations

from aps.state.models import PitchPackage
from aps.render import base as b


def _section(title: str, body: str) -> str:
    return b.h2(title) + ((body.strip() + "\n") if body and body.strip() else b.PLACEHOLDER + "\n")


def render(p: PitchPackage) -> str:
    out = [b.front_matter("Pitch Package")]
    out.append(_section("Pitch Outline", p.pitch_outline))
    out.append(_section("Demo Script", p.demo_script))
    # investor_memo carries the judge brief folded in (decision.md D4)
    out.append(_section("Investor Memo", p.investor_memo))
    return "".join(out)
