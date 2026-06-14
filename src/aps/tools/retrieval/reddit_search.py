"""reddit_search — search Reddit posts across all subreddits.

Use to find candid user complaints, requests, and "is there a tool that..." posts.
Auth via REDDIT_CLIENT_ID/SECRET (script app) when set; public JSON otherwise.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error
from aps.state.models import ToolResult, Evidence
from aps.tools.retrieval._reddit import reddit_get, posts_to_evidence


class Args(BaseModel):
    query: str = Field(..., description="search terms, e.g. 'resume keeps getting rejected'")
    limit: int = Field(10, ge=1, le=50)
    sort: str = Field("relevance", description="relevance | top | new | comments")


class RedditSearch(BaseTool):
    name = "reddit_search"
    namespace = "retrieval"
    description = (
        "Search Reddit posts site-wide for candid user complaints and requests. Use to "
        "hear how non-technical users describe a problem in their own words. Prefer over "
        "hn_search for consumer/prosumer audiences; over stackexchange for non-dev pain."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        try:
            data = reddit_get("/search", {"q": args.query, "limit": args.limit,
                                          "sort": args.sort})
            ev = posts_to_evidence(data, args.limit)
            return ToolResult(ok=True, payload=data, evidence=ev)
        except Exception as e:
            return fixture_or_error(str(e), evidence=[
                Evidence(source="reddit", url="https://www.reddit.com/r/jobs/comments/1",
                         title="[fixture] My resume keeps getting auto-rejected",
                         snippet="Applied to 200 jobs, the ATS rejects me before a human sees it...")
            ])


TOOL = RedditSearch()

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(query=sys.argv[1] if len(sys.argv) > 1 else "best note taking app")
    print(json.dumps(out.model_dump(), indent=2, default=str))
