"""Shared pytest fixtures for the APS suite.

Everything here is offline and deterministic: retrieval tools fall back to fixtures
(no API keys), analysis/agent tools are pure functions, agents are deterministic
pipelines. The suite must stay green on py3.10 with only pydantic + pytest installed.
"""
from __future__ import annotations

import os

import pytest

# Force fixture fallback so any retrieval tool that *is* exercised never makes a live call.
os.environ.setdefault("APS_ALLOW_FIXTURE_FALLBACK", "true")

from aps.state.models import (
    Evidence, Competitor, PainPoint, Severity, ResearchReturn,
)


@pytest.fixture
def rich_research() -> ResearchReturn:
    """A realistic ResearchReturn so downstream agents have real data to chew on."""
    ev = [
        Evidence(source="github", url="https://github.com/acme/ats/issues/1",
                 title="Parser drops PDF resumes",
                 snippet="The parser is broken and keeps dropping valid PDF resumes."),
        Evidence(source="reddit", url="https://reddit.com/r/recruiting/abc",
                 title="ATS keyword matching is dumb",
                 snippet="Keyword matching is confusing and misses qualified candidates."),
        Evidence(source="web", url="https://acme.io/pricing",
                 title="Acme pricing",
                 snippet="Acme supports PDF export and integrates with Slack. Pricing $49/mo."),
        Evidence(source="web", url="https://marketreport.example.com/ats",
                 title="ATS market",
                 snippet="The ATS market is worth $3 billion and growing fast."),
    ]
    return ResearchReturn(
        idea="Build an AI SaaS for resume screening",
        market_size="~$3B ATS market, growing",
        competitors=[
            Competitor(name="Acme", url="https://acme.io",
                       features=["PDF export", "Slack integration"], pricing="$49/mo"),
            Competitor(name="ScreenAI", features=["keyword match", "ranking"]),
        ],
        pain_points=[
            PainPoint(text="Parser drops valid PDF resumes", severity=Severity.HIGH,
                      source_evidence=[ev[0]]),
            PainPoint(text="Keyword matching misses qualified candidates",
                      severity=Severity.MED, source_evidence=[ev[1]]),
            PainPoint(text="Pricing is too high for small teams", severity=Severity.LOW),
        ],
        evidence=ev,
    )
