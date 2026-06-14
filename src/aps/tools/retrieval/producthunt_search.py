"""producthunt_search — find recently launched products on Product Hunt (GraphQL v2).

Use to discover newest competitors and validate that people are shipping in a space.
Needs PRODUCTHUNT_TOKEN (developer token); falls back to a fixture otherwise.
"""
from __future__ import annotations

import os

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error, USER_AGENT, DEFAULT_TIMEOUT
from aps.state.models import ToolResult, Evidence

_QUERY = """
query($q: String!, $n: Int!) {
  posts(order: VOTES, first: $n) {
    edges { node { name tagline url votesCount } }
  }
}
"""


class Args(BaseModel):
    query: str = Field(..., description="topic/keyword to look for in launches")
    limit: int = Field(10, ge=1, le=20)


class ProducthuntSearch(BaseTool):
    name = "producthunt_search"
    namespace = "retrieval"
    description = (
        "Find recently launched products on Product Hunt (needs PRODUCTHUNT_TOKEN). Use "
        "to spot the newest startup competitors in a space and gauge launch momentum via "
        "vote counts. Distinct from github_search_repos (OSS) — this is commercial launches."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        token = os.getenv("PRODUCTHUNT_TOKEN")
        if not token:
            return fixture_or_error("PRODUCTHUNT_TOKEN not set", evidence=[_fix()])
        try:
            from aps.infra import http
            r = http.post(
                "https://api.producthunt.com/v2/api/graphql",
                json={"query": _QUERY, "variables": {"q": args.query, "n": args.limit}},
                headers={"User-Agent": USER_AGENT, "Authorization": f"Bearer {token}"},
                timeout=DEFAULT_TIMEOUT,
            )
            r.raise_for_status()
            edges = (((r.json().get("data") or {}).get("posts") or {}).get("edges")) or []
            q = args.query.lower()
            ev = []
            for e in edges:
                n = e.get("node", {})
                hay = f"{n.get('name','')} {n.get('tagline','')}".lower()
                if q and q not in hay:
                    continue
                ev.append(Evidence(source="producthunt", url=n.get("url", ""),
                                   title=n.get("name", ""),
                                   snippet=(f"{n.get('tagline','')} "
                                            f"({n.get('votesCount',0)} votes)")[:280]))
            return ToolResult(ok=True, payload=edges, evidence=ev[: args.limit])
        except Exception as e:
            return fixture_or_error(str(e), evidence=[_fix()])


def _fix() -> Evidence:
    return Evidence(source="producthunt", url="https://www.producthunt.com/posts/example",
                    title="[fixture] ResumeAI",
                    snippet="AI that rewrites your resume to beat the ATS (320 votes)")


TOOL = ProducthuntSearch()

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(query=sys.argv[1] if len(sys.argv) > 1 else "ai")
    print(json.dumps(out.model_dump(), indent=2, default=str))
