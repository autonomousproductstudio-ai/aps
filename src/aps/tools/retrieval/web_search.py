"""web_search — general web search via Tavily (free tier ~1k/mo).

The catch-all when no specific source fits. Use sparingly; prefer named sources
(github/hn/reddit/...) when you can. Needs TAVILY_API_KEY.
"""
from __future__ import annotations

import os

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error, USER_AGENT, DEFAULT_TIMEOUT
from aps.state.models import ToolResult, Evidence


class Args(BaseModel):
    query: str = Field(..., description="natural-language web query")
    limit: int = Field(8, ge=1, le=20)


class WebSearch(BaseTool):
    name = "web_search"
    namespace = "retrieval"
    description = (
        "General web search (Tavily). The fallback when no specialized source fits — "
        "e.g. news, blog posts, company pages. Prefer github/hn/reddit/arxiv/wikipedia "
        "when the target is one of those; reach for this only for the long tail."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        key = os.getenv("TAVILY_API_KEY")
        if not key:
            return fixture_or_error("TAVILY_API_KEY not set", evidence=[_fix()])
        try:
            from aps.infra import http
            r = http.post(
                "https://api.tavily.com/search",
                json={"api_key": key, "query": args.query,
                      "max_results": args.limit, "search_depth": "basic"},
                headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT,
            )
            r.raise_for_status()
            results = r.json().get("results", [])
            ev = [
                Evidence(source="web", url=x.get("url", ""), title=x.get("title", ""),
                         snippet=(x.get("content") or "")[:280])
                for x in results[: args.limit]
            ]
            return ToolResult(ok=True, payload=results, evidence=ev)
        except Exception as e:
            return fixture_or_error(str(e), evidence=[_fix()])


def _fix() -> Evidence:
    return Evidence(source="web", url="https://example.com/article",
                    title="[fixture] The state of resume screening in 2025",
                    snippet="Most companies now use automated screening before human review...")


TOOL = WebSearch()

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(query=sys.argv[1] if len(sys.argv) > 1 else "ai note taking market size")
    print(json.dumps(out.model_dump(), indent=2, default=str))
