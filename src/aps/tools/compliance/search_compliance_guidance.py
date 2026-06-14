"""search_compliance_guidance — best-effort live regulator guidance (cached 24h).

For the applicable regimes, fetch the official regulator's guidance page so the report carries
real source citations. Regulations change slowly → 24h cache TTL → repeat runs are free. Goes
through aps.infra.http (rate-limited + circuit-broken) and falls back to labelled fixtures
offline/keyless, so it never blocks a no-key run.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error, USER_AGENT, DEFAULT_TIMEOUT
from aps.state.models import ToolResult, Evidence

# Regime keyword → official guidance URL. Kept small and authoritative.
_GUIDANCE = {
    "dpdp": ("DPDP Act (India)", "https://www.meity.gov.in/data-protection-framework"),
    "gdpr (eu)": ("GDPR (EU)", "https://gdpr.eu/"),
    "uk gdpr": ("UK GDPR (ICO)", "https://ico.org.uk/for-organisations/"),
    "ccpa": ("CCPA/CPRA", "https://oag.ca.gov/privacy/ccpa"),
    "soc 2": ("SOC 2 / ISO 27001", "https://www.iso.org/isoiec-27001-information-security.html"),
    "pci-dss": ("PCI-DSS", "https://www.pcisecuritystandards.org/"),
    "health": ("Health-data rules", "https://www.hhs.gov/hipaa/for-professionals/index.html"),
}


def _match(regime_name: str):
    n = (regime_name or "").lower()
    for key, rec in _GUIDANCE.items():
        if key in n:
            return rec
    return None


class Args(BaseModel):
    regimes: list[str] = Field(default_factory=list, description="applicable regime names")


class SearchComplianceGuidance(BaseTool):
    name = "search_compliance_guidance"
    namespace = "compliance"
    cache_ttl = 86400  # 24h — regulatory guidance changes slowly
    description = (
        "Fetch official regulator guidance pages for the applicable compliance regimes so the "
        "report carries real source citations. Cached 24h; falls back to fixtures offline. "
        "Returns Evidence citations."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        from aps.infra import http
        from aps.infra.breaker import CircuitOpen

        targets = []
        for name in args.regimes:
            rec = _match(name)
            if rec and rec not in targets:
                targets.append(rec)
        if not targets:
            targets = [_GUIDANCE["soc 2"]]

        evidence: list[Evidence] = []
        any_live = False
        for label, url in targets:
            try:
                r = http.get(url, headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT)
                ok = 200 <= r.status_code < 400
                if ok:
                    any_live = True
                evidence.append(Evidence(
                    source="compliance", url=url, title=f"{label} — official guidance",
                    snippet=f"Official guidance for {label} (HTTP {r.status_code})."))
            except (CircuitOpen, Exception):
                evidence.append(Evidence(
                    source="compliance", url=url, title=f"{label} — official guidance",
                    snippet=f"Official guidance for {label} (reference link)."))

        if not any_live:
            # offline / all failed → labelled fixture, but keep the real reference links
            return fixture_or_error("compliance guidance offline",
                                    payload={"live": False}, evidence=evidence)
        return ToolResult(ok=True, payload={"live": True}, evidence=evidence)


TOOL = SearchComplianceGuidance()

if __name__ == "__main__":
    import json
    out = TOOL.run(regimes=["DPDP Act (India)", "SOC 2 / ISO 27001"])
    print(json.dumps(out.model_dump(), indent=2, default=str))
