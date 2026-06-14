"""stackexchange_search — search Stack Overflow / Stack Exchange questions (no key).

Use to find concrete technical problems people hit in a domain — high-signal pain
points phrased as questions. Optional STACKEXCHANGE_KEY raises the quota.
"""
from __future__ import annotations

import os

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error, USER_AGENT, DEFAULT_TIMEOUT
from aps.state.models import ToolResult, Evidence


class Args(BaseModel):
    query: str = Field(..., description="problem terms, e.g. 'pdf resume parsing python'")
    site: str = Field("stackoverflow", description="SE site, e.g. 'stackoverflow', 'serverfault'")
    limit: int = Field(10, ge=1, le=50)


class StackexchangeSearch(BaseTool):
    name = "stackexchange_search"
    namespace = "retrieval"
    description = (
        "Search Stack Exchange (default Stack Overflow) questions on a topic (no key, "
        "low volume). Use to find concrete technical problems and unmet needs phrased "
        "as developer questions. Prefer over hn_search when the pain is implementation-level."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        try:
            from aps.infra import http
            params = {
                "order": "desc", "sort": "relevance", "q": args.query,
                "site": args.site, "pagesize": args.limit,
            }
            key = os.getenv("STACKEXCHANGE_KEY")
            if key:
                params["key"] = key
            r = http.get(
                "https://api.stackexchange.com/2.3/search/advanced",
                params=params, headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT,
            )
            r.raise_for_status()
            items = r.json().get("items", [])
            ev = [
                Evidence(
                    source="stackexchange",
                    url=i.get("link", ""),
                    title=i.get("title", ""),
                    snippet=(f"score {i.get('score', 0)}, "
                             f"{i.get('answer_count', 0)} answers, "
                             f"tags: {', '.join(i.get('tags', [])[:5])}")[:280],
                )
                for i in items[: args.limit]
            ]
            return ToolResult(ok=True, payload=items, evidence=ev)
        except Exception as e:
            return fixture_or_error(str(e), evidence=[
                Evidence(source="stackexchange",
                         url="https://stackoverflow.com/q/1",
                         title="[fixture] How to reliably parse PDF resumes in Python?",
                         snippet="score 42, 5 answers, tags: python, pdf, nlp")
            ])


TOOL = StackexchangeSearch()

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(query=sys.argv[1] if len(sys.argv) > 1 else "rate limiting fastapi")
    print(json.dumps(out.model_dump(), indent=2, default=str))
