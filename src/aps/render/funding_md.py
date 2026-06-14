"""FundingPackage → Markdown (Launch Studio Phase 3).

The pitch-deck outline (slide by slide), the illustrative financial model as a table with its
assumptions, use-of-funds, and the fundraising round ladder. Pure and deterministic.
"""
from __future__ import annotations

from aps.state.models import FundingPackage
from aps.render import base as b
from aps.tools.funding._finance import fmt_usd


def render(p: FundingPackage) -> str:
    out = [b.front_matter(f"Funding Pack — {p.company_name or 'Untitled'}")]
    if p.ask:
        out.append(f"**Current ask:** {p.ask}\n")

    out.append(b.h2("Pitch Deck Outline"))
    for i, slide in enumerate(p.deck_slides, 1):
        out.append(b.h3(f"{i}. {slide.get('title', 'Slide')}"))
        out.append(b.bullet_list(slide.get("bullets", [])))

    out.append(b.h2("Financial Projections (illustrative)"))
    years = p.financials.get("years", [])
    if years:
        out.append(b.table(
            ["Year", "Customers", "Revenue", "Gross profit", "Opex", "Net", "Headcount"],
            [[y.get("year"), y.get("customers"), fmt_usd(y.get("revenue", 0)),
              fmt_usd(y.get("gross_profit", 0)), fmt_usd(y.get("opex", 0)),
              fmt_usd(y.get("net", 0)), y.get("headcount")] for y in years],
        ))
    else:
        out.append(b.PLACEHOLDER + "\n")
    notes = p.financials.get("notes", [])
    if notes:
        out.append(b.h3("Assumptions & notes"))
        out.append(b.bullet_list(notes))

    out.append(b.h2("Use of Funds"))
    out.append(b.table(
        ["Area", "%", "Detail"],
        [[u.get("area"), f"{u.get('pct')}%", u.get("detail")] for u in p.use_of_funds],
    ))

    out.append(b.h2("Fundraising Roadmap"))
    out.append(b.table(
        ["Round", "Amount", "Timing", "Milestones"],
        [[r.get("round"), r.get("amount"), r.get("timing"), r.get("milestones")]
         for r in p.rounds],
    ))

    return "".join(out)
