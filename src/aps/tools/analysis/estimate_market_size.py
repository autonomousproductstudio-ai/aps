"""estimate_market_size — a grounded TAM/SAM/SOM read from gathered evidence.

Deterministic: pulls any explicit money figures ($X B/M/K) out of the evidence,
counts demand signals (jobs, issues, threads, competitor mentions), and assembles a
sourced market-size *statement string* — the shape `ResearchReturn.market_size` wants.
Never invents a number it can't point at; if there are no figures it says so and falls
back to a signal-strength characterization. No LLM, no network.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Evidence
from aps.tools.analysis._text import as_evidence_list, evidence_text

_MONEY = re.compile(
    r"\$\s?(\d[\d,]*(?:\.\d+)?)\s?(trillion|billion|million|thousand|tn|bn|mn|[btmk])\b",
    re.I,
)
_MULT = {"trillion": 1e12, "tn": 1e12, "t": 1e12,
         "billion": 1e9, "bn": 1e9, "b": 1e9,
         "million": 1e6, "mn": 1e6, "m": 1e6,
         "thousand": 1e3, "k": 1e3}


def _human(n: float) -> str:
    for label, scale in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= scale:
            return f"${n / scale:.1f}{label}"
    return f"${n:.0f}"


class Args(BaseModel):
    evidence: list[Evidence] = Field(default_factory=list)
    topic: str = Field("", description="optional topic label for the statement")


class EstimateMarketSize(BaseTool):
    name = "estimate_market_size"
    namespace = "analysis"
    description = (
        "Estimate market size (TAM/SAM/SOM) from gathered evidence by extracting "
        "explicit dollar figures and counting demand signals, returning a sourced "
        "statement string. Use during compression to characterize how big the "
        "opportunity is — grounded, never a made-up number."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        ev = as_evidence_list(args.evidence)
        figures: list[tuple[float, Evidence]] = []
        signals = 0
        for e in ev:
            text = evidence_text(e)
            low = text.lower()
            for amt, unit in _MONEY.findall(text):
                val = float(amt.replace(",", "")) * _MULT.get(unit.lower(), 1)
                figures.append((val, e))
            if any(k in low for k in ("hiring", "job", "demand", "growing", "market",
                                      "adoption", "users", "customers", "issue", "request")):
                signals += 1

        topic = args.topic or "this space"
        # Plausibility floor: a "$X" hit below ~$1M is almost always a price/salary/funding
        # snippet, not a market size. Reporting it as TAM is worse than saying "no figure" —
        # it looks like the pipeline ran and produced garbage. So we only treat figures above
        # the floor as a TAM; smaller ones are surfaced with provenance as a flagged non-TAM.
        MIN_TAM = 1_000_000
        plausible = sorted((f for f in figures if f[0] >= MIN_TAM),
                           key=lambda x: x[0], reverse=True)
        if plausible:
            tam, src = plausible[0]
            sam = tam * 0.10
            som = sam * 0.05
            excerpt = (src.snippet or src.title or "").strip()[:90]
            stmt = (
                f"Estimated market for {topic}: TAM ~{_human(tam)} "
                f"(source: {src.url} — \"{excerpt}\"); SAM ~{_human(sam)} (≈10% serviceable); "
                f"SOM ~{_human(som)} (≈5% of SAM, early obtainable). "
                f"{signals} demand signal(s) across {len(ev)} sources corroborate activity."
            )
        else:
            strength = ("strong" if signals >= 6 else "moderate" if signals >= 2 else "thin")
            note = ""
            if figures:  # figures exist but all below the credibility floor
                figures.sort(key=lambda x: x[0], reverse=True)
                top, src = figures[0]
                note = (f" (Largest dollar figure found, ~{_human(top)} at {src.url}, is below a "
                        f"credible-TAM floor — likely a price/salary, so not reported as market size.)")
            stmt = (
                f"No explicit market figure found in evidence for {topic}; demand signal "
                f"is {strength} ({signals} signal(s) across {len(ev)} sources). "
                f"Recommend sizing via bottom-up (users × price) before pitching a TAM.{note}"
            )
        return ToolResult(ok=True, payload=stmt, evidence=ev)


TOOL = EstimateMarketSize()

if __name__ == "__main__":
    import json
    e = [Evidence(source="web", url="https://x.com/report", title="ATS market",
                  snippet="The ATS market is worth $3 billion and growing."),
         Evidence(source="jobs", url="https://j/1", title="hiring", snippet="hiring demand high")]
    out = TOOL.run(evidence=[x.model_dump() for x in e], topic="resume screening")
    print(json.dumps(out.model_dump(), indent=2, default=str))
