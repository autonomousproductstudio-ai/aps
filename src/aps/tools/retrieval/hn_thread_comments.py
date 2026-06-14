"""hn_thread_comments — pull the comment tree for one HN item (Algolia, no key).

Use after hn_search to read what people actually said in a high-signal thread.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error, USER_AGENT, DEFAULT_TIMEOUT
from aps.state.models import ToolResult, Evidence


class Args(BaseModel):
    item_id: str = Field(..., description="HN story id, e.g. '12345' (from hn_search url)")
    limit: int = Field(15, ge=1, le=100)


def _flatten(node, out, cap):
    for child in node.get("children", []) or []:
        if child.get("text"):
            out.append(child)
        if len(out) >= cap:
            return
        _flatten(child, out, cap)


class HnThreadComments(BaseTool):
    name = "hn_thread_comments"
    namespace = "retrieval"
    description = (
        "Fetch the comment tree of a specific Hacker News thread (no key). Use to read "
        "concrete user opinions, complaints, and feature wishes once hn_search found a "
        "relevant story. Returns flattened comment text as evidence."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        try:
            from aps.infra import http
            import re
            r = http.get(
                f"https://hn.algolia.com/api/v1/items/{args.item_id}",
                headers={"User-Agent": USER_AGENT},
                timeout=DEFAULT_TIMEOUT,
            )
            r.raise_for_status()
            root = r.json()
            flat: list = []
            _flatten(root, flat, args.limit)
            ev = [
                Evidence(
                    source="hackernews",
                    url=f"https://news.ycombinator.com/item?id={c.get('id')}",
                    title=(root.get("title") or "HN comment"),
                    snippet=re.sub("<[^>]+>", " ", c.get("text") or "")[:280],
                )
                for c in flat[: args.limit]
            ]
            return ToolResult(ok=True, payload=flat, evidence=ev)
        except Exception as e:
            return fixture_or_error(str(e), evidence=[
                Evidence(source="hackernews",
                         url="https://news.ycombinator.com/item?id=2",
                         title="[fixture] thread",
                         snippet="The parser keeps dropping my bullet points, super annoying.")
            ])


TOOL = HnThreadComments()

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(item_id=sys.argv[1] if len(sys.argv) > 1 else "1")
    print(json.dumps(out.model_dump(), indent=2, default=str))
