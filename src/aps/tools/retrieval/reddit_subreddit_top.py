"""reddit_subreddit_top — top posts of a specific subreddit over a time window.

Use when you know the community (e.g. r/recruiting) and want its highest-signal
discussions. Auth via REDDIT_CLIENT_ID/SECRET when set; public JSON otherwise.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error
from aps.state.models import ToolResult, Evidence
from aps.tools.retrieval._reddit import reddit_get, posts_to_evidence


class Args(BaseModel):
    subreddit: str = Field(..., description="subreddit name without r/, e.g. 'recruiting'")
    limit: int = Field(10, ge=1, le=50)
    time: str = Field("year", description="hour | day | week | month | year | all")


class RedditSubredditTop(BaseTool):
    name = "reddit_subreddit_top"
    namespace = "retrieval"
    description = (
        "Get the top posts of a specific subreddit over a time window. Use when you "
        "already know the relevant community and want its most-upvoted discussions "
        "(durable pain points / wishes). Use reddit_search when you don't know the sub."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        try:
            data = reddit_get(f"/r/{args.subreddit}/top",
                              {"limit": args.limit, "t": args.time})
            ev = posts_to_evidence(data, args.limit)
            return ToolResult(ok=True, payload=data, evidence=ev)
        except Exception as e:
            return fixture_or_error(str(e), evidence=[
                Evidence(source="reddit",
                         url="https://www.reddit.com/r/recruiting/comments/2",
                         title="[fixture] What ATS do you all actually like?",
                         snippet="Megathread: recruiters compare ATS tools and their gripes...")
            ])


TOOL = RedditSubredditTop()

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(subreddit=sys.argv[1] if len(sys.argv) > 1 else "python")
    print(json.dumps(out.model_dump(), indent=2, default=str))
