"""ComplianceReport → Markdown (Launch Studio Phase 5)."""
from __future__ import annotations

from aps.state.models import ComplianceReport
from aps.render import base as b


def render(p: ComplianceReport) -> str:
    out = [b.front_matter(f"Compliance — {p.country or 'Unknown jurisdiction'}")]
    if p.degraded and p.note:
        out.append(f"> {p.note}\n")
    if p.summary:
        out.append(p.summary.strip() + "\n")

    out.append(b.h2("Applicable Regimes"))
    for r in p.regimes:
        flag = "applies" if r.get("applicable") else "n/a"
        out.append(b.h3(f"{r.get('name')} ({flag})"))
        if r.get("why"):
            out.append(r["why"].strip() + "\n")
        out.append(b.bullet_list(r.get("obligations", [])))

    out.append(b.h2("Checklist"))
    out.append(b.table(
        ["Item", "Regime", "Status"],
        [[c.get("item"), c.get("regime"), c.get("status")] for c in p.checklist],
    ))

    if p.sources:
        out.append(b.h2("Guidance sources"))
        out.append(b.bullet_list([b.evidence_link(e) for e in p.sources]))

    return "".join(out)
