"""hn_search — search Hacker News stories via the Algolia API (no key required).

Use to gauge developer/early-adopter interest and discussion volume for a topic.
Shape mirrors github_issues.py: typed args -> real source call -> Evidence -> ToolResult.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error, USER_AGENT, DEFAULT_TIMEOUT
from aps.state.models import ToolResult, Evidence


class Args(BaseModel):
    query: str = Field(..., description="search terms, e.g. 'resume parser ATS'")
    limit: int = Field(10, ge=1, le=50)


class HnSearch(BaseTool):
    name = "hn_search"
    namespace = "retrieval"
    description = (
        "Search Hacker News stories (Algolia, no key) for discussion of a topic. "
        "Use to measure technical/early-adopter interest and surface opinionated "
        "threads. Prefer over Reddit when the audience is developers/founders."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        try:
            from aps.infra import http
            r = http.get(
                "https://hn.algolia.com/api/v1/search",
                params={"query": args.query, "tags": "story", "hitsPerPage": args.limit},
                headers={"User-Agent": USER_AGENT},
                timeout=DEFAULT_TIMEOUT,
            )
            r.raise_for_status()
            hits = r.json().get("hits", [])
            ev = [
                Evidence(
                    source="hackernews",
                    url=h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
                    title=h.get("title") or h.get("story_title"),
                    snippet=(h.get("story_text") or
                             f"{h.get('points', 0)} points, {h.get('num_comments', 0)} comments")[:280],
                )
                for h in hits[: args.limit]
            ]
            return ToolResult(ok=True, payload=hits, evidence=ev)
        except Exception as e:
            return fixture_or_error(str(e), evidence=[
                Evidence(source="hackernews",
                         url="https://news.ycombinator.com/item?id=1",
                         title="[fixture] Show HN: a better resume parser",
                         snippet="Discussion: existing ATS parsers mishandle PDFs...")
            ])


TOOL = HnSearch()

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(query=sys.argv[1] if len(sys.argv) > 1 else "vector database")
    print(json.dumps(out.model_dump(), indent=2, default=str))
