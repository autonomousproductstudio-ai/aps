"""PRD → Markdown (plan.md W1).

Requirements carry inline citations: for each requirement we surface the source evidence
whose text overlaps it (deterministic token overlap), realizing the WIREFRAMES Screen-3
"real pain → written requirement" link without inventing a mapping that isn't there.
"""
from __future__ import annotations

import re

from aps.state.models import PRD, Evidence
from aps.render import base as b


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{4,}", (text or "").lower())}


def _matching_sources(requirement: str, sources: list[Evidence], limit: int = 3) -> list[Evidence]:
    req = _tokens(requirement)
    if not req:
        return []
    scored = []
    for e in sources:
        overlap = len(req & _tokens(f"{e.title or ''} {e.snippet or ''}"))
        if overlap:
            scored.append((overlap, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:limit]]


def render(p: PRD) -> str:
    out = [b.front_matter("Product Requirements Document", p.idea)]

    out.append(b.h2(f"Personas ({len(p.personas)})"))
    if p.personas:
        for persona in p.personas:
            out.append(b.h3(f"{persona.name} — {persona.role}"))
            out.append("**Goals:**\n" + b.bullet_list(persona.goals))
            out.append("\n**Frustrations:**\n" + b.bullet_list(persona.frustrations))
    else:
        out.append(b.PLACEHOLDER + "\n")

    out.append(b.h2(f"Features ({len(p.features)})"))
    out.append(b.numbered_list([
        f"**{f.title}** `[{f.priority}]` — {f.description}" for f in p.features
    ]))

    out.append(b.h2("MVP Scope"))
    out.append((p.mvp_scope or b.PLACEHOLDER) + "\n")

    out.append(b.h2(f"Requirements ({len(p.requirements)})"))
    if p.requirements:
        for i, req in enumerate(p.requirements, 1):
            cites = _matching_sources(req, p.sources)
            tail = f"  \n  ↳ {b.citation_refs(cites)}" if cites else ""
            out.append(f"{i}. {req}{tail}\n")
    else:
        out.append(b.PLACEHOLDER + "\n")

    out.append(b.h2(f"Sources ({len(p.sources)})"))
    out.append(b.numbered_list([b.evidence_link(e) for e in p.sources]))
    return "".join(out)
