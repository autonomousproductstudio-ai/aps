"""github_search_repos — find repos matching a query, ranked by stars.

Use to discover the open-source competitor/landscape in a space. Works
unauthenticated (rate-limited); APS_GITHUB_PAT raises the limit.
"""
from __future__ import annotations

import os

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error, USER_AGENT, DEFAULT_TIMEOUT
from aps.state.models import ToolResult, Evidence


class Args(BaseModel):
    query: str = Field(..., description="search terms, e.g. 'resume parser'")
    limit: int = Field(10, ge=1, le=30)


class GithubSearchRepos(BaseTool):
    name = "github_search_repos"
    namespace = "retrieval"
    description = (
        "Search GitHub repositories by topic, ranked by stars. Use to map the "
        "open-source competitive landscape for an idea and find the leading projects. "
        "Then use github_repo_stats / github_list_issues on the ones that matter."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        try:
            from aps.infra import http
            headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
            token = os.getenv("APS_GITHUB_PAT")
            if token:
                headers["Authorization"] = f"Bearer {token}"
            r = http.get(
                "https://api.github.com/search/repositories",
                params={"q": args.query, "sort": "stars", "order": "desc",
                        "per_page": args.limit},
                headers=headers, timeout=DEFAULT_TIMEOUT,
            )
            r.raise_for_status()
            items = r.json().get("items", [])
            ev = [
                Evidence(source="github", url=i.get("html_url", ""),
                         title=i.get("full_name", ""),
                         snippet=(f"{i.get('stargazers_count', 0)}★ "
                                  f"{(i.get('description') or '')}")[:280])
                for i in items[: args.limit]
            ]
            return ToolResult(ok=True, payload=items, evidence=ev)
        except Exception as e:
            return fixture_or_error(str(e), evidence=[
                Evidence(source="github", url="https://github.com/example/parser",
                         title="[fixture] example/parser",
                         snippet="5000★ An open-source resume parser")
            ])


TOOL = GithubSearchRepos()

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(query=sys.argv[1] if len(sys.argv) > 1 else "vector database")
    print(json.dumps(out.model_dump(), indent=2, default=str))
