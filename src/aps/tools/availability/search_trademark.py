"""search_trademark — indicative trademark check + official-registry search links.

There is no clean, free, keyless trademark API (esp. for the India default), so this is
deliberately INDICATIVE: it returns the jurisdiction's official registry search URL (so a
founder can confirm in one click) and a clearly-labelled best-effort status. Never presented
as a clearance opinion — confirm with a registry / attorney.

Slow-changing → long cache TTL (6h).
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Evidence

# Jurisdiction → (registry name, search URL template with {q}). Loose-matched like _legal.
_REGISTRIES = {
    "india": ("India IP Office (IPindiaonline)",
              "https://tmrsearch.ipindia.gov.in/tmrpublicsearch/"),
    "european union": ("EUIPO eSearch",
                       "https://euipo.europa.eu/eSearch/#advanced/trademarks/1/100/n1=MarkVerbalElementText&v1={q}"),
    "united kingdom": ("UK IPO",
                       "https://www.gov.uk/search-for-trademark?q={q}"),
    "delaware": ("USPTO Trademark Search",
                 "https://tmsearch.uspto.gov/search/search-information?query={q}"),
}
_DEFAULT = "india"


def _registry(jurisdiction: str) -> tuple[str, str]:
    j = (jurisdiction or "").strip().lower()
    for key, rec in _REGISTRIES.items():
        if key in j or j in key:
            return rec
    if any(t in j for t in ("usa", "united states", "u.s", "america")):
        return _REGISTRIES["delaware"]
    if any(t in j for t in ("eu", "europe")):
        return _REGISTRIES["european union"]
    if any(t in j for t in ("uk", "britain", "england")):
        return _REGISTRIES["united kingdom"]
    return _REGISTRIES[_DEFAULT]


class Args(BaseModel):
    mark: str = Field(..., description="the brand name / mark to check")
    jurisdiction: str = "India"


class SearchTrademark(BaseTool):
    name = "search_trademark"
    namespace = "availability"
    cache_ttl = 21600  # 6h
    description = (
        "Indicative trademark check for a brand name in a jurisdiction: returns the official "
        "registry's search link and a best-effort status. Indicative only — confirm registrability "
        "with the registry or an attorney; not a clearance opinion."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        registry_name, url_tmpl = _registry(args.jurisdiction)
        q = (args.mark or "").strip()
        search_url = url_tmpl.replace("{q}", q.replace(" ", "+"))
        note = (f"Indicative only — search '{q}' on {registry_name} to confirm. A registered "
                f"mark in this class would block use; consult an attorney before filing.")
        tm = {
            "mark": q,
            "jurisdiction": args.jurisdiction,
            "status": "check_required",
            "source": registry_name,
            "search_url": search_url,
            "note": note,
        }
        ev = [Evidence(source="trademark", url=search_url,
                       title=f"{registry_name}: search '{q}'",
                       snippet=note)]
        return ToolResult(ok=True, payload={"trademarks": [tm]}, evidence=ev)


TOOL = SearchTrademark()

if __name__ == "__main__":
    import json
    print(json.dumps(TOOL.run(mark="Habitly", jurisdiction="India").payload, indent=2))
