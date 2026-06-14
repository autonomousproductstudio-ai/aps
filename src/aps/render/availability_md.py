"""AvailabilityReport → Markdown (Launch Studio Phase 4)."""
from __future__ import annotations

from aps.state.models import AvailabilityReport
from aps.render import base as b

_STATUS = {"available": "✅ available", "registered": "❌ registered", "unknown": "— unknown"}


def render(p: AvailabilityReport) -> str:
    out = [b.front_matter(f"Name Availability — {p.company_name or 'Untitled'}")]
    if p.summary:
        out.append(p.summary.strip() + "\n")
    if p.recommended_domain:
        out.append(f"\n**Recommended domain:** `{p.recommended_domain}`\n")

    out.append(b.h2("Domains"))
    out.append(b.table(
        ["Domain", "Status", "Source"],
        [[d.get("domain"), _STATUS.get(d.get("status"), d.get("status")), d.get("source")]
         for d in p.domains],
    ))

    out.append(b.h2("Trademark (indicative)"))
    out.append(b.table(
        ["Mark", "Jurisdiction", "Status", "Registry", "Search"],
        [[t.get("mark"), t.get("jurisdiction"), t.get("status"), t.get("source"),
          t.get("search_url")] for t in p.trademarks],
    ))
    if p.trademarks:
        notes = [t.get("note") for t in p.trademarks if t.get("note")]
        if notes:
            out.append(b.bullet_list(notes))

    return "".join(out)
