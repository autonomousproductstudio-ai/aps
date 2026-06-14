"""github_repo_stats — fetch stars/forks/issues/language for one GitHub repo.

Use to quantify an incumbent's traction. Works unauthenticated (rate-limited);
APS_GITHUB_PAT raises the limit.
"""
from __future__ import annotations

import os

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error, USER_AGENT, DEFAULT_TIMEOUT
from aps.state.models import ToolResult, Evidence


class Args(BaseModel):
    repo: str = Field(..., description="owner/name, e.g. 'langchain-ai/langgraph'")


class GithubRepoStats(BaseTool):
    name = "github_repo_stats"
    namespace = "retrieval"
    description = (
        "Get traction metrics for a specific GitHub repo: stars, forks, open issues, "
        "primary language, description. Use to quantify how established a competitor or "
        "incumbent tool is. Pair with github_search_repos (which finds the repos)."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        try:
            from aps.infra import http
            headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
            token = os.getenv("APS_GITHUB_PAT")
            if token:
                headers["Authorization"] = f"Bearer {token}"
            r = http.get(f"https://api.github.com/repos/{args.repo}",
                             headers=headers, timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            d = r.json()
            snippet = (f"{d.get('stargazers_count', 0)}★ "
                       f"{d.get('forks_count', 0)} forks, "
                       f"{d.get('open_issues_count', 0)} open issues, "
                       f"lang {d.get('language')}: {(d.get('description') or '')[:120]}")
            ev = [Evidence(source="github", url=d.get("html_url", ""),
                           title=d.get("full_name", args.repo), snippet=snippet[:280])]
            return ToolResult(ok=True, payload={
                "stars": d.get("stargazers_count"), "forks": d.get("forks_count"),
                "open_issues": d.get("open_issues_count"), "language": d.get("language"),
            }, evidence=ev)
        except Exception as e:
            return fixture_or_error(str(e), evidence=[
                Evidence(source="github", url="https://github.com/example/repo",
                         title="[fixture] example/repo",
                         snippet="12000★ 800 forks, 230 open issues, lang Python: an example tool")
            ])


TOOL = GithubRepoStats()

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(repo=sys.argv[1] if len(sys.argv) > 1 else "langchain-ai/langgraph")
    print(json.dumps(out.model_dump(), indent=2, default=str))
