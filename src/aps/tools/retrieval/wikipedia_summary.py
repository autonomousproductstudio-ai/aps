"""wikipedia_summary — search Wikipedia and return intro extracts (no key).

Use for neutral background / definitions / market category framing for an idea.
One call: generator=search feeds prop=extracts so we get intros for top hits.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error, USER_AGENT, DEFAULT_TIMEOUT
from aps.state.models import ToolResult, Evidence


class Args(BaseModel):
    query: str = Field(..., description="topic or category, e.g. 'applicant tracking system'")
    limit: int = Field(3, ge=1, le=10)


class WikipediaSummary(BaseTool):
    name = "wikipedia_summary"
    namespace = "retrieval"
    description = (
        "Search Wikipedia and return neutral intro extracts for the top matching "
        "articles (no key). Use to define a market category or get unbiased background "
        "before diving into opinionated sources. Not for user pain points."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        try:
            from aps.infra import http
            r = http.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query", "format": "json",
                    "prop": "extracts", "exintro": 1, "explaintext": 1,
                    "generator": "search", "gsrsearch": args.query,
                    "gsrlimit": args.limit,
                },
                headers={"User-Agent": USER_AGENT},
                timeout=DEFAULT_TIMEOUT,
            )
            r.raise_for_status()
            pages = (r.json().get("query", {}) or {}).get("pages", {}) or {}
            ev = []
            for p in list(pages.values())[: args.limit]:
                title = p.get("title", "")
                ev.append(Evidence(
                    source="wikipedia",
                    url="https://en.wikipedia.org/wiki/" + title.replace(" ", "_"),
                    title=title,
                    snippet=(p.get("extract") or "")[:280],
                ))
            return ToolResult(ok=True, payload=pages, evidence=ev)
        except Exception as e:
            return fixture_or_error(str(e), evidence=[
                Evidence(source="wikipedia",
                         url="https://en.wikipedia.org/wiki/Applicant_tracking_system",
                         title="[fixture] Applicant tracking system",
                         snippet="An ATS is software that handles recruitment and hiring needs...")
            ])


TOOL = WikipediaSummary()

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(query=sys.argv[1] if len(sys.argv) > 1 else "vector database")
    print(json.dumps(out.model_dump(), indent=2, default=str))
