"""sentiment_breakdown — coarse positive/negative/neutral split over evidence.

Lexicon-based polarity count (no model). Gives the agent a quick read on whether the
discussion around a space is mostly frustrated (opportunity) or satisfied (saturated).
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Evidence
from aps.tools.analysis._text import as_evidence_list, evidence_text

_POS = ("love", "great", "excellent", "amazing", "best", "easy", "fast", "reliable",
        "helpful", "intuitive", "solid", "recommend", "works well", "fantastic")
_NEG = ("hate", "broken", "slow", "buggy", "terrible", "awful", "confusing", "useless",
        "frustrat", "annoying", "expensive", "worst", "lacks", "missing", "crash")


class Args(BaseModel):
    evidence: list[Evidence] = Field(default_factory=list)


class SentimentBreakdown(BaseTool):
    name = "sentiment_breakdown"
    namespace = "analysis"
    description = (
        "Classify evidence into positive / negative / neutral by lexicon and return the "
        "counts and net sentiment. Use to judge whether a space is full of frustrated "
        "users (opportunity) or happy ones (hard to displace). Coarse, not per-aspect."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        ev = as_evidence_list(args.evidence)
        pos = neg = neu = 0
        for e in ev:
            low = evidence_text(e).lower()
            p = sum(low.count(w) for w in _POS)
            n = sum(low.count(w) for w in _NEG)
            if p > n:
                pos += 1
            elif n > p:
                neg += 1
            else:
                neu += 1
        total = pos + neg + neu
        net = round((pos - neg) / total, 3) if total else 0.0
        return ToolResult(ok=True, payload={
            "positive": pos, "negative": neg, "neutral": neu,
            "total": total, "net_sentiment": net,
        }, evidence=ev)


TOOL = SentimentBreakdown()

if __name__ == "__main__":
    import json
    e = [Evidence(source="reddit", url="https://r/1", title="t", snippet="I love this, works well"),
         Evidence(source="reddit", url="https://r/2", title="t", snippet="buggy and slow, hate it")]
    out = TOOL.run(evidence=[x.model_dump() for x in e])
    print(json.dumps(out.model_dump(), indent=2, default=str))
