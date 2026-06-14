"""arxiv_search — search arXiv papers (Atom API, no key).

Use to find research backing or prior art for a technical product idea.
Parses the Atom feed with stdlib xml (no extra dependency).
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error, USER_AGENT, DEFAULT_TIMEOUT
from aps.state.models import ToolResult, Evidence

_ATOM = "{http://www.w3.org/2005/Atom}"


class Args(BaseModel):
    query: str = Field(..., description="topic terms, e.g. 'retrieval augmented generation'")
    limit: int = Field(8, ge=1, le=30)


class ArxivSearch(BaseTool):
    name = "arxiv_search"
    namespace = "retrieval"
    description = (
        "Search arXiv for academic papers on a topic (no key). Use to ground a "
        "technical idea in research / find prior art and state-of-the-art methods. "
        "Prefer over web_search when you need credible scientific sources."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        try:
            from aps.infra import http
            import urllib.parse
            import xml.etree.ElementTree as ET
            q = urllib.parse.quote(args.query)
            r = http.get(
                f"http://export.arxiv.org/api/query?search_query=all:{q}"
                f"&start=0&max_results={args.limit}",
                headers={"User-Agent": USER_AGENT},
                timeout=DEFAULT_TIMEOUT,
            )
            r.raise_for_status()
            root = ET.fromstring(r.text)
            ev = []
            for entry in root.findall(f"{_ATOM}entry")[: args.limit]:
                title = (entry.findtext(f"{_ATOM}title") or "").strip()
                summary = (entry.findtext(f"{_ATOM}summary") or "").strip()
                link = (entry.findtext(f"{_ATOM}id") or "").strip()
                ev.append(Evidence(source="arxiv", url=link, title=title,
                                   snippet=summary[:280]))
            return ToolResult(ok=True, payload=r.text, evidence=ev)
        except Exception as e:
            return fixture_or_error(str(e), evidence=[
                Evidence(source="arxiv", url="https://arxiv.org/abs/0000.00000",
                         title="[fixture] A Survey of Resume Parsing Methods",
                         snippet="We review NLP approaches to structured resume extraction...")
            ])


TOOL = ArxivSearch()

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(query=sys.argv[1] if len(sys.argv) > 1 else "large language models")
    print(json.dumps(out.model_dump(), indent=2, default=str))
