"""ResearchReturn → Markdown (plan.md W1)."""
from __future__ import annotations

from aps.state.models import ResearchReturn
from aps.render import base as b


def render(r: ResearchReturn) -> str:
    out = [b.front_matter("Research Brief", r.idea)]
    if r.degraded:
        out.append("\n> ⚠️ **Degraded run** — this brief is the labeled fallback fixture, "
                   "not live idea-specific evidence. Set an LLM key to research for real.\n")

    out.append(b.h2("Market Size"))
    out.append((r.market_size or b.PLACEHOLDER) + "\n")

    out.append(b.h2(f"Competitors ({len(r.competitors)})"))
    rows = [[
        f"[{c.name}]({c.url})" if c.url else c.name,
        c.pricing, ", ".join(c.features), c.notes,
    ] for c in r.competitors]
    out.append(b.table(["Name", "Pricing", "Features", "Notes"], rows))

    out.append(b.h2(f"Pain Points ({len(r.pain_points)})"))
    if r.pain_points:
        for p in r.pain_points:
            out.append(f"- {b.severity_badge(p.severity)} — {p.text} "
                       f"({b.citation_refs(p.source_evidence)})\n")
    else:
        out.append(b.PLACEHOLDER + "\n")

    out.append(b.h2(f"Evidence ({len(r.evidence)})"))
    out.append(b.numbered_list([b.evidence_link(e) for e in r.evidence]))
    return "".join(out)
