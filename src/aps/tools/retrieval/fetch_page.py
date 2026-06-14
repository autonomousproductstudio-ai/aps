"""fetch_page — fetch a URL and return readable text (no key).

Use to read a specific page another tool surfaced (a blog post, docs, a landing
page). Strips HTML to text with stdlib only (no bs4 dependency).
"""
from __future__ import annotations

import re
import html as _html

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error, USER_AGENT, DEFAULT_TIMEOUT
from aps.state.models import ToolResult, Evidence

_SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def html_to_text(raw: str) -> str:
    raw = _SCRIPT_STYLE.sub(" ", raw)
    raw = _TAG.sub(" ", raw)
    return _WS.sub(" ", _html.unescape(raw)).strip()


class Args(BaseModel):
    url: str = Field(..., description="full http(s) URL to fetch")
    max_chars: int = Field(2000, ge=100, le=20000)


class FetchPage(BaseTool):
    name = "fetch_page"
    namespace = "retrieval"
    description = (
        "Fetch a specific URL and return its readable text content (no key). Use to "
        "actually read a page a search tool pointed you to — docs, a blog post, an "
        "about page. Not a search tool: you must already have the URL."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        if not args.url.startswith(("http://", "https://")):
            return ToolResult(ok=False, error="url must start with http:// or https://")
        try:
            from aps.infra import http
            r = http.get(args.url, headers={"User-Agent": USER_AGENT},
                             timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            text = html_to_text(r.text)[: args.max_chars]
            ev = [Evidence(source="web", url=args.url,
                           title=args.url, snippet=text[:280])]
            return ToolResult(ok=True, payload={"text": text}, evidence=ev)
        except Exception as e:
            return fixture_or_error(str(e), evidence=[
                Evidence(source="web", url=args.url, title="[fixture] page",
                         snippet="Page content unavailable; recorded sample text.")
            ])


TOOL = FetchPage()

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(url=sys.argv[1] if len(sys.argv) > 1 else "https://example.com")
    print(json.dumps(out.model_dump(), indent=2, default=str))
