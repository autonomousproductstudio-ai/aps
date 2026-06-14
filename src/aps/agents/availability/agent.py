"""Availability Agent (Launch Studio Phase 4, thin/live-retrieval).

Consumes the StudioState, emits an AvailabilityReport: domain availability (real, via RDAP)
and an indicative trademark check for the brand name. A deterministic pipeline over the scoped
`availability` tools (ADR-0005) — same shape as Brand/Legal/Funding — but its tools do live,
cached network I/O (6h TTL) through `aps.infra.http`, falling back to fixtures offline.

The name comes from the Brand package when present (else `derive_name(idea)` — identical value,
since Brand derives it the same way), so the studio checks the name it actually picked.
"""
from __future__ import annotations

from aps.state.models import StudioState, AvailabilityReport
from aps.agents._pipeline import scoped, call
from aps.infra.metrics import AGENT_RUNS
from aps.config.settings import get_settings
from aps.tools.brand._svg import derive_name


def run_availability(state: StudioState) -> AvailabilityReport:
    AGENT_RUNS.labels(agent="availability").inc()
    t = scoped("availability")

    name = (state.brand.name if state.brand and state.brand.name
            else derive_name(state.idea))
    jurisdiction = get_settings().legal_jurisdiction or "India"

    domains = call(t, "check_domain_availability", name=name)["domains"]
    trademarks = call(t, "search_trademark", mark=name, jurisdiction=jurisdiction)["trademarks"]

    available = [d["domain"] for d in domains if d.get("status") == "available"]
    recommended = available[0] if available else (domains[0]["domain"] if domains else "")

    n_avail = len(available)
    summary = (
        f"{name}: {n_avail} of {len(domains)} candidate domains available"
        + (f" (recommended: {recommended})" if recommended else "")
        + f". Trademark: indicative only — confirm on the {jurisdiction} registry."
    )

    return AvailabilityReport(
        company_name=name,
        domains=domains,
        trademarks=trademarks,
        recommended_domain=recommended,
        summary=summary,
    )
