"""Idea-agnostic fixture Research return — used ONLY when live research can't run
(no LLM key, or a transient failure). It is deliberately generic and clearly labeled so a
degraded run is never mistaken for real, idea-specific evidence (the old fixture hardcoded
ATS/resume data, which made a 'habit tracker' run look like an ATS product). The run that
uses this is marked RunStatus.DEGRADED upstream; `degraded=True` is the signal for that.
"""
from aps.state.models import ResearchReturn, Competitor, PainPoint, Evidence, Severity


def stub_research(idea: str, *, reason: str | None = None) -> ResearchReturn:
    """Labeled, idea-agnostic fixture brief. `reason` (e.g. 'llm_auth_401', 'no_llm_key')
    records WHY live research could not run, so a degraded artifact is self-diagnosing
    rather than a mysterious '[stub] no live research'."""
    why = f" reason: {reason}" if reason else ""
    ev = Evidence(
        source="stub_fallback",
        url="https://example.com/stub",
        title="[stub fixture] no live research",
        snippet=(f"No live research was run for: {idea}.{why} "
                 "Set a valid LLM key to gather real evidence."),
    )
    return ResearchReturn(
        idea=idea,
        market_size="[stub] no live evidence gathered — set an LLM key to research this idea",
        competitors=[Competitor(name="Example Competitor",
                                notes="[stub] placeholder — not real evidence")],
        pain_points=[PainPoint(text="[stub] users report friction with existing solutions",
                               severity=Severity.MED, source_evidence=[ev])],
        evidence=[ev],
        degraded=True,
        degrade_reason=reason,
    )
