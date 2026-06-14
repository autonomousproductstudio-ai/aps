"""github_list_issues — pull real GitHub issues as pain signals.

This is the REFERENCE tool. P2 copies this shape for every other retrieval tool:
typed args -> real source call -> normalized Evidence -> ToolResult.
Each tool also has a __main__ so it runs standalone before the orchestrator exists
(TEAM_GUIDE §6) and a recorded fixture so CI never makes live calls (EVALUATION §6).
"""
from __future__ import annotations
import os
from pydantic import BaseModel, Field
from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Evidence


class Args(BaseModel):
    repo: str = Field(..., description="owner/name, e.g. 'langchain-ai/langgraph'")
    query: str = Field("", description="optional text filter")
    limit: int = Field(10, ge=1, le=50)


class GithubListIssues(BaseTool):
    name = "github_list_issues"
    namespace = "retrieval"
    description = (
        "List real open issues from a GitHub repo. Use to find concrete user pain "
        "points and feature requests for a product space. Prefer this over forums "
        "when you have a specific repo/project in mind."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        token = os.getenv("APS_GITHUB_PAT")
        if not token:
            return _fixture_or_error("APS_GITHUB_PAT not set")
        try:
            from aps.infra import http
            r = http.get(
                f"https://api.github.com/repos/{args.repo}/issues",
                params={"state": "open", "per_page": args.limit},
                headers={"Authorization": f"Bearer {token}",
                         "Accept": "application/vnd.github+json"},
                timeout=15,
            )
            r.raise_for_status()
            items = [i for i in r.json() if "pull_request" not in i]
            ev = [
                Evidence(source="github", url=i["html_url"],
                         title=i["title"], snippet=(i.get("body") or "")[:280])
                for i in items[: args.limit]
            ]
            return ToolResult(ok=True, payload=items, evidence=ev)
        except Exception as e:  # transient handled by Tenacity wrapper in infra
            return _fixture_or_error(str(e))


def _fixture_or_error(msg: str) -> ToolResult:
    """Demo resilience: fall back to a recorded fixture if allowed (TRD §7)."""
    from aps.config.settings import get_settings
    if get_settings().allow_fixture_fallback:
        ev = [Evidence(source="github", url="https://github.com/example/repo/issues/1",
                       title="[fixture] ATS rejects valid resumes",
                       snippet="Recruiters report the parser drops PDF resumes...")]
        return ToolResult(ok=True, payload=[], evidence=ev)
    return ToolResult(ok=False, error=msg)


TOOL = GithubListIssues()   # registry auto-discovers this

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(repo=sys.argv[1] if len(sys.argv) > 1 else "langchain-ai/langgraph")
    print(json.dumps(out.model_dump(), indent=2, default=str))
