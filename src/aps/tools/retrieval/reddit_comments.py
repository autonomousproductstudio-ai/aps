"""reddit_comments — fetch the comment thread for a specific Reddit post.

Use after reddit_search / reddit_subreddit_top to read the actual discussion under a
high-signal post. Auth via REDDIT_CLIENT_ID/SECRET when set; public JSON otherwise.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error
from aps.state.models import ToolResult, Evidence
from aps.tools.retrieval._reddit import reddit_get


class Args(BaseModel):
    subreddit: str = Field(..., description="subreddit without r/, e.g. 'jobs'")
    post_id: str = Field(..., description="the post id from a permalink, e.g. '1ab2cd'")
    limit: int = Field(15, ge=1, le=100)


class RedditComments(BaseTool):
    name = "reddit_comments"
    namespace = "retrieval"
    description = (
        "Read the comments under a specific Reddit post (needs subreddit + post id). "
        "Use to mine concrete opinions and counter-arguments once a relevant post is "
        "found. Returns top-level comment text as evidence."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        try:
            data = reddit_get(f"/r/{args.subreddit}/comments/{args.post_id}",
                              {"limit": args.limit})
            ev: list[Evidence] = []
            # response is [postListing, commentListing]
            if isinstance(data, list) and len(data) > 1:
                children = (data[1].get("data", {}) or {}).get("children", []) or []
                for c in children[: args.limit]:
                    d = c.get("data", {})
                    if not d.get("body"):
                        continue
                    ev.append(Evidence(
                        source="reddit",
                        url="https://www.reddit.com" + (d.get("permalink") or ""),
                        title=f"comment by u/{d.get('author', '?')}",
                        snippet=d.get("body", "")[:280],
                    ))
            return ToolResult(ok=True, payload=data, evidence=ev)
        except Exception as e:
            return fixture_or_error(str(e), evidence=[
                Evidence(source="reddit",
                         url="https://www.reddit.com/r/jobs/comments/1/x/abc",
                         title="comment by u/example",
                         snippet="Honestly the keyword matching is the worst part of every ATS.")
            ])


TOOL = RedditComments()

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(subreddit="jobs", post_id=sys.argv[1] if len(sys.argv) > 1 else "1")
    print(json.dumps(out.model_dump(), indent=2, default=str))
