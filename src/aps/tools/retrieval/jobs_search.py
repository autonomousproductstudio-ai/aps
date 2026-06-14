"""jobs_search — search remote job postings via the Remotive API (no key).

Hiring demand is a market signal: lots of companies hiring for a skill/role implies a
growing space. Remotive's public API needs no credentials.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error, USER_AGENT, DEFAULT_TIMEOUT
from aps.state.models import ToolResult, Evidence


class Args(BaseModel):
    query: str = Field(..., description="role/skill terms, e.g. 'machine learning engineer'")
    limit: int = Field(10, ge=1, le=50)


class JobsSearch(BaseTool):
    name = "jobs_search"
    namespace = "retrieval"
    description = (
        "Search remote job postings (Remotive, no key). Use hiring volume for a "
        "role/skill as a demand signal: many openings ⇒ a growing, well-funded space. "
        "Complements trends_interest (search demand) with employer demand."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        try:
            from aps.infra import http
            r = http.get(
                "https://remotive.com/api/remote-jobs",
                params={"search": args.query, "limit": args.limit},
                headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT,
            )
            r.raise_for_status()
            jobs = r.json().get("jobs", [])
            ev = [
                Evidence(source="jobs", url=j.get("url", ""),
                         title=f"{j.get('title', '')} @ {j.get('company_name', '')}",
                         snippet=(f"{j.get('candidate_required_location', '')} | "
                                  f"{j.get('job_type', '')} | "
                                  f"{', '.join(j.get('tags', [])[:5])}")[:280])
                for j in jobs[: args.limit]
            ]
            return ToolResult(ok=True, payload={"count": len(jobs), "jobs": jobs}, evidence=ev)
        except Exception as e:
            return fixture_or_error(str(e), payload={"count": 1}, evidence=[
                Evidence(source="jobs", url="https://remotive.com/job/1",
                         title="[fixture] ML Engineer @ ExampleCo",
                         snippet="Worldwide | full_time | python, ml, nlp")
            ])


TOOL = JobsSearch()

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(query=sys.argv[1] if len(sys.argv) > 1 else "data engineer")
    print(json.dumps(out.model_dump(), indent=2, default=str))
