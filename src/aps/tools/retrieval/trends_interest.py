"""trends_interest — Google Trends interest-over-time for terms (via pytrends).

Use to check whether demand for a topic is rising or fading — a market-timing signal.
pytrends is an optional dependency; without it (or on rate-limit) returns a fixture.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error
from aps.state.models import ToolResult, Evidence


class Args(BaseModel):
    terms: list[str] = Field(..., description="1-5 search terms to compare, e.g. ['notion','obsidian']")
    timeframe: str = Field("today 12-m", description="pytrends timeframe, e.g. 'today 12-m'")


class TrendsInterest(BaseTool):
    name = "trends_interest"
    namespace = "retrieval"
    description = (
        "Get Google Trends interest-over-time for one or more terms (pytrends). Use to "
        "tell whether demand for a category is growing, flat, or declining — a timing "
        "signal for the opportunity. Returns the latest value and direction per term."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        terms = args.terms[:5]
        try:
            from pytrends.request import TrendReq  # optional dep
        except Exception:
            return fixture_or_error("pytrends not installed", evidence=[_fix(terms)],
                                    payload={"note": "pip install pytrends to enable"})
        try:
            py = TrendReq(hl="en-US", tz=0)
            py.build_payload(terms, timeframe=args.timeframe)
            df = py.interest_over_time()
            summary = {}
            for t in terms:
                if t in df:
                    series = df[t].tolist()
                    latest = series[-1] if series else 0
                    first = next((v for v in series if v), latest)
                    direction = ("rising" if latest > first else
                                 "falling" if latest < first else "flat")
                    summary[t] = {"latest": latest, "direction": direction}
            snippet = "; ".join(f"{t}: {v['latest']} ({v['direction']})"
                                for t, v in summary.items()) or "no data"
            ev = [Evidence(source="google_trends",
                           url="https://trends.google.com/trends/explore?q=" + ",".join(terms),
                           title="interest over time", snippet=snippet[:280])]
            return ToolResult(ok=True, payload=summary, evidence=ev)
        except Exception as e:
            return fixture_or_error(str(e), evidence=[_fix(terms)])


def _fix(terms) -> Evidence:
    return Evidence(source="google_trends",
                    url="https://trends.google.com/trends/explore?q=" + ",".join(terms),
                    title="[fixture] interest over time",
                    snippet="; ".join(f"{t}: 72 (rising)" for t in terms))


TOOL = TrendsInterest()

if __name__ == "__main__":
    import json
    out = TOOL.run(terms=["notion", "obsidian"])
    print(json.dumps(out.model_dump(), indent=2, default=str))
