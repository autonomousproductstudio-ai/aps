"""github_search_code — search code across public GitHub (requires PAT).

Use to find how widely an API/library/pattern is actually used in real codebases —
an adoption signal. GitHub's code-search API requires authentication.
"""
from __future__ import annotations

import os

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error, USER_AGENT, DEFAULT_TIMEOUT
from aps.state.models import ToolResult, Evidence


class Args(BaseModel):
    query: str = Field(..., description="code search, e.g. 'import langgraph language:python'")
    limit: int = Field(10, ge=1, le=30)


class GithubSearchCode(BaseTool):
    name = "github_search_code"
    namespace = "retrieval"
    description = (
        "Search source code across public GitHub (needs PAT). Use to measure real "
        "adoption of a library/API/pattern by counting and inspecting actual usages in "
        "code. Distinct from github_search_repos, which finds projects, not usages."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        token = os.getenv("APS_GITHUB_PAT")
        if not token:
            return fixture_or_error("APS_GITHUB_PAT not set (code search requires auth)",
                                    evidence=[_fix()])
        try:
            from aps.infra import http
            r = http.get(
                "https://api.github.com/search/code",
                params={"q": args.query, "per_page": args.limit},
                headers={"User-Agent": USER_AGENT,
                         "Accept": "application/vnd.github+json",
                         "Authorization": f"Bearer {token}"},
                timeout=DEFAULT_TIMEOUT,
            )
            r.raise_for_status()
            items = r.json().get("items", [])
            ev = [
                Evidence(source="github", url=i.get("html_url", ""),
                         title=f"{i.get('repository', {}).get('full_name', '')}/{i.get('name', '')}",
                         snippet=f"match in {i.get('path', '')}"[:280])
                for i in items[: args.limit]
            ]
            return ToolResult(ok=True, payload={"total": r.json().get("total_count"),
                                                "items": items}, evidence=ev)
        except Exception as e:
            return fixture_or_error(str(e), evidence=[_fix()])


def _fix() -> Evidence:
    return Evidence(source="github", url="https://github.com/example/repo/blob/main/app.py",
                    title="[fixture] example/repo/app.py",
                    snippet="match in app.py")


TOOL = GithubSearchCode()

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(query=sys.argv[1] if len(sys.argv) > 1 else "import langgraph language:python")
    print(json.dumps(out.model_dump(), indent=2, default=str))
