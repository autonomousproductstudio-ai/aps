"""detect_trend_signal — classify a demand time series as rising / declining / flat.

Takes an interest-over-time series (e.g. from `trends_interest`) and computes a simple
least-squares slope plus percent change, returning a direction and confidence. If no
numeric series is passed, it falls back to parsing numbers out of evidence snippets.
Deterministic math, no LLM, no network.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Evidence
from aps.tools.analysis._text import as_evidence_list, evidence_text

_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _slope(series: list[float]) -> float:
    n = len(series)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(series) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, series)) / denom


class Args(BaseModel):
    series: list[float] = Field(default_factory=list,
                                description="interest/usage values in time order")
    evidence: list[Evidence] = Field(default_factory=list,
                                     description="fallback: parse numbers from snippets")
    flat_band: float = Field(0.05, ge=0, le=1,
                             description="abs percent-change under this counts as flat")


class DetectTrendSignal(BaseTool):
    name = "detect_trend_signal"
    namespace = "analysis"
    description = (
        "Detect whether demand is rising, declining, or flat from an interest-over-time "
        "series (e.g. trends_interest output), via least-squares slope and percent "
        "change. Use to judge market timing — is this category heating up or cooling "
        "off? Falls back to numbers found in evidence if no series is given."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        series = list(args.series)
        ev = as_evidence_list(args.evidence)
        if not series and ev:
            for e in ev:
                series.extend(float(x) for x in _NUM.findall(evidence_text(e)))

        if len(series) < 2:
            return ToolResult(ok=True, payload={
                "direction": "unknown", "slope": 0.0, "change_pct": 0.0,
                "points": len(series), "note": "need >=2 data points",
            }, evidence=ev)

        first = next((v for v in series if v), series[0])
        last = series[-1]
        change = (last - first) / first if first else 0.0
        slope = _slope(series)
        if abs(change) < args.flat_band:
            direction = "flat"
        elif slope > 0:
            direction = "rising"
        else:
            direction = "declining"
        return ToolResult(ok=True, payload={
            "direction": direction,
            "slope": round(slope, 4),
            "change_pct": round(change * 100, 1),
            "first": first, "last": last, "points": len(series),
        }, evidence=ev)


TOOL = DetectTrendSignal()

if __name__ == "__main__":
    import json
    out = TOOL.run(series=[10, 14, 18, 25, 31, 40])
    print(json.dumps(out.model_dump(), indent=2, default=str))
