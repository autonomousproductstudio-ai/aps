"""Shared, deterministic finance primitives for the funding tools (Launch Studio Phase 3).

Leading underscore ⇒ the registry never mistakes this for a TOOL module. Pure stdlib, no
network, no LLM. Parses money figures out of the research market-size statement and builds an
illustrative 3-year model on clearly-labelled assumptions (never presented as a forecast).
"""
from __future__ import annotations

import re
from typing import Any

# Largest "$X B/M/K" figure in a free-text market-size statement (e.g. "~$3B ATS market").
_MONEY = re.compile(
    r"\$\s?(\d[\d,]*(?:\.\d+)?)\s?(trillion|billion|million|thousand|tn|bn|mn|[btmk])?\b",
    re.IGNORECASE,
)
_MULT = {
    "trillion": 1e12, "tn": 1e12, "t": 1e12,
    "billion": 1e9, "bn": 1e9, "b": 1e9,
    "million": 1e6, "mn": 1e6, "m": 1e6,
    "thousand": 1e3, "k": 1e3, "": 1.0, None: 1.0,
}


def parse_tam(market_size: str) -> float | None:
    """Return the largest dollar figure (absolute USD) found in a market-size string, or None."""
    best: float | None = None
    for num, unit in _MONEY.findall(market_size or ""):
        try:
            val = float(num.replace(",", "")) * _MULT.get((unit or "").lower(), 1.0)
        except ValueError:
            continue
        if best is None or val > best:
            best = val
    return best


def fmt_usd(amount: float) -> str:
    """Compact human dollar string: $3.0B / $4.5M / $120K / $900."""
    a = float(amount)
    for thresh, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(a) >= thresh:
            return f"${a / thresh:.1f}{suffix}"
    return f"${a:,.0f}"


# Default illustrative assumptions — every one is surfaced in the output so a reader knows
# exactly what drives the numbers (and can challenge them). Deterministic.
DEFAULTS = {
    "arpu_annual": 600,        # $50/mo per paying customer
    "y1_customers": 120,
    "growth_y2": 3.0,
    "growth_y3": 2.5,
    "gross_margin": 0.80,
    "headcount": [4, 8, 16],   # y1, y2, y3
    "cost_per_head": 90000,    # fully-loaded annual
    "marketing_pct": 0.25,     # of revenue
}


def annual_infra(infra_cost: str) -> float:
    """Best-effort annual infra spend from the execution infra_cost string. Detects a $ figure
    and whether it is monthly (×12) vs already annual; defaults to a small annual floor."""
    val = parse_tam(infra_cost or "")
    if val is None:
        return 6000.0  # modest cloud floor when nothing parseable
    s = (infra_cost or "").lower()
    monthly = any(t in s for t in ("/mo", "per month", "month", "monthly", "/ month"))
    return val * (12 if monthly else 1)


def project(market_size: str, infra_cost: str, assumptions: dict | None = None) -> dict[str, Any]:
    """Build the 3-year illustrative model. Returns {assumptions, years:[...], tam, notes}."""
    a = {**DEFAULTS, **(assumptions or {})}
    infra = annual_infra(infra_cost)
    tam = parse_tam(market_size)

    customers = [
        a["y1_customers"],
        round(a["y1_customers"] * a["growth_y2"]),
        round(a["y1_customers"] * a["growth_y2"] * a["growth_y3"]),
    ]
    years = []
    for i, cust in enumerate(customers):
        revenue = cust * a["arpu_annual"]
        cogs = revenue * (1 - a["gross_margin"])
        team = a["headcount"][i] * a["cost_per_head"]
        marketing = revenue * a["marketing_pct"]
        opex = team + marketing + infra
        net = revenue - cogs - opex
        years.append({
            "year": f"Y{i + 1}",
            "customers": cust,
            "revenue": round(revenue),
            "gross_profit": round(revenue - cogs),
            "opex": round(opex),
            "net": round(net),
            "headcount": a["headcount"][i],
        })

    notes = [
        "Illustrative model on the assumptions below — NOT a forecast or guarantee.",
        f"ARPU ${a['arpu_annual']}/yr; Y1 {a['y1_customers']} customers; growth "
        f"{a['growth_y2']}x then {a['growth_y3']}x; gross margin {int(a['gross_margin']*100)}%.",
        f"Infra ≈ {fmt_usd(infra)}/yr (from execution estimate); marketing "
        f"{int(a['marketing_pct']*100)}% of revenue; fully-loaded cost/head "
        f"{fmt_usd(a['cost_per_head'])}.",
    ]
    if tam:
        notes.append(f"TAM reference from research: {fmt_usd(tam)}. Y3 revenue implies "
                     f"{(years[-1]['revenue']/tam*100):.2f}% TAM penetration.")
    return {"assumptions": a, "years": years, "tam": tam, "notes": notes}
