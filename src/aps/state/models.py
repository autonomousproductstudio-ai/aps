"""
aps.state.models — THE CONTRACT.

Every agent returns and consumes these types. This file is owned by P1 and frozen on
Day 1. Changing anything here is a `contract:` PR that all three people approve
(see docs/TEAM_GUIDE.md §2). Mirror of the shapes in docs/API_CONTRACT.md §5.

Pydantic v2.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Building blocks
# --------------------------------------------------------------------------- #
class Severity(str, Enum):
    LOW = "low"
    MED = "med"
    HIGH = "high"


class Evidence(BaseModel):
    """A single grounded fact from a real source. Returned by every retrieval tool."""
    source: str = Field(..., description="e.g. 'github', 'hackernews', 'reddit'")
    url: str
    title: str | None = None
    snippet: str
    retrieved_at: datetime = Field(default_factory=_now)
    # Relevance of this evidence to the run's product idea, 0–1 (deterministic lexical overlap,
    # set by the research relevance gate during compression). None = never scored. Additive/
    # backward-compatible: absent on older records, ignored by everything that doesn't read it.
    relevance: float | None = None


class Competitor(BaseModel):
    name: str
    url: str | None = None
    features: list[str] = []
    pricing: str | None = None
    notes: str | None = None


class PainPoint(BaseModel):
    text: str
    severity: Severity = Severity.MED
    source_evidence: list[Evidence] = []


class Persona(BaseModel):
    name: str
    role: str
    goals: list[str] = []
    frustrations: list[str] = []


class Feature(BaseModel):
    title: str
    description: str
    priority: str = "med"  # High/Med/Low or RICE/MoSCoW label


# --------------------------------------------------------------------------- #
# Agent return types (the composition chain — Req 5)
# --------------------------------------------------------------------------- #
class ResearchReturn(BaseModel):
    idea: str
    market_size: str = ""
    competitors: list[Competitor] = []
    pain_points: list[PainPoint] = []
    evidence: list[Evidence] = []
    degraded: bool = False  # True when this is the stub fixture (no live research ran)
    tool_calls: int = 0     # actual LLM-side tool invocations that produced this brief
    degrade_reason: str | None = None  # WHY a run degraded (no_llm_key / llm_auth_401 / ...)
    evidence_relevance: float = 0.0  # mean idea-relevance (0–1) of the kept evidence after the gate


class PRD(BaseModel):
    idea: str
    personas: list[Persona] = []
    features: list[Feature] = []
    mvp_scope: str = ""
    requirements: list[str] = []
    sources: list[Evidence] = []


class TRD(BaseModel):
    data_model: dict[str, Any] = {}
    api_spec: dict[str, Any] = {}      # OpenAPI document
    stack: list[str] = []
    scale_estimate: str = ""


class ExecutionPlan(BaseModel):
    repo_plan: dict[str, Any] = {}
    backlog: list[dict[str, Any]] = []
    sprints: list[dict[str, Any]] = []
    roadmap: str = ""
    infra_cost: str = ""


class PitchPackage(BaseModel):
    pitch_outline: str = ""
    demo_script: str = ""
    investor_memo: str = ""


class BrandPackage(BaseModel):
    """Brand identity + launch campaign. Deterministic, SVG-native, no image model.

    Additive to the contract (Launch Studio Phase 1): produced by the Brand agent in a
    parallel graph branch behind APS_ENABLE_BRAND. Existing consumers ignore it.
    """
    name: str = ""                 # the derived brand/product name
    logo_svg: str = ""             # mark + wordmark lockup
    logo_mark_svg: str = ""        # mark only (favicon/app-icon use)
    brand_sheet_svg: str = ""      # shareable card: lockup + palette + taglines
    palette: list[str] = []        # [primary, accent, ink]
    taglines: list[str] = []
    positioning: str = ""
    value_props: list[str] = []
    brand_voice: str = ""
    channels: list[dict[str, Any]] = []
    launch_sequence: list[dict[str, Any]] = []
    sample_posts: list[dict[str, Any]] = []


class LegalDocument(BaseModel):
    """One generated legal document. A deterministic template, NOT legal advice."""
    title: str = ""
    kind: str = ""              # privacy_policy | tos | nda | founders_agreement | employment
    body: str = ""             # Markdown
    placeholders: list[str] = []   # party-specific fields a lawyer must still fill in


class LegalPackage(BaseModel):
    """Founder-grade legal scaffolding (Launch Studio Phase 2). Deterministic templates from
    jurisdiction + company facts already in state — no LLM, no network. Additive to the
    contract; produced by the Legal agent in a parallel branch behind APS_ENABLE_LEGAL.

    These are templates only — every document carries a NOT-LEGAL-ADVICE disclaimer.
    """
    company_name: str = ""
    jurisdiction: str = ""
    governing_law: str = ""
    disclaimer: str = ""
    documents: list[LegalDocument] = []


class FundingPackage(BaseModel):
    """Investor-facing funding pack (Launch Studio Phase 3). Deterministic, assembled from the
    Research/PRD/Execution artifacts already in state — no LLM, no network. Additive to the
    contract; produced by the Funding agent in a parallel branch behind APS_ENABLE_FUNDING.

    Financials are an illustrative model built on clearly-labelled assumptions, not a forecast.
    """
    company_name: str = ""
    ask: str = ""                              # headline current raise
    deck_slides: list[dict[str, Any]] = []     # [{title, bullets:[...]}] — pitch deck outline
    financials: dict[str, Any] = {}            # {assumptions, years:[...], notes}
    use_of_funds: list[dict[str, Any]] = []    # [{area, pct, detail}]
    rounds: list[dict[str, Any]] = []          # [{round, amount, timing, milestones}]


class AvailabilityReport(BaseModel):
    """Name availability check (Launch Studio Phase 4): domains + trademark. The first agent
    with live retrieval — domain status is real (RDAP); trademark is indicative. Additive to
    the contract; produced by the Availability agent in a parallel branch behind
    APS_ENABLE_TRADEMARK.
    """
    company_name: str = ""
    domains: list[dict[str, Any]] = []         # [{domain, status, source}] available|registered|unknown
    trademarks: list[dict[str, Any]] = []      # [{mark, jurisdiction, status, source, note}]
    recommended_domain: str = ""
    summary: str = ""


class ComplianceReport(BaseModel):
    """Regulatory-compliance scaffolding (Launch Studio Phase 5, gated hard). Deterministic
    applicability + checklist from the TRD data model + country, plus best-effort cached live
    guidance citations. Additive; produced by the Compliance agent ONLY when APS_ENABLE_COMPLIANCE
    is set (default off). Scaffolding, not legal/compliance advice.
    """
    country: str = ""
    regimes: list[dict[str, Any]] = []     # [{name, applicable, why, obligations:[...]}]
    checklist: list[dict[str, Any]] = []   # [{item, regime, status}]
    sources: list[Evidence] = []           # live citations when enrichment ran
    summary: str = ""
    degraded: bool = False                 # True when only the deterministic core ran (no live evidence)
    note: str = ""


# --------------------------------------------------------------------------- #
# Tool I/O
# --------------------------------------------------------------------------- #
class ToolResult(BaseModel):
    """Every tool returns this. `payload` is raw; `evidence` is normalized for grounding."""
    ok: bool = True
    payload: Any = None
    evidence: list[Evidence] = []
    error: str | None = None


# --------------------------------------------------------------------------- #
# Orchestrator state + events
# --------------------------------------------------------------------------- #
class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    DEGRADED = "degraded"   # ran to the end but on the stub fixture (no live evidence)
    FAILED = "failed"
    CANCELLED = "cancelled"  # cooperatively stopped (user cancel or deadline) — honest terminal


class Event(BaseModel):
    """One lifecycle event. Streamed over SSE (API_CONTRACT §3) and persisted as the trace."""
    type: str            # agent_start | tool_call | tool_result | artifact_ready | agent_end | error | run_complete
    ts: datetime = Field(default_factory=_now)
    data: dict[str, Any] = {}


class StudioState(BaseModel):
    """The orchestrator's typed state. Holds ONLY structured returns (context strategy, Req 3)."""
    idea: str
    status: RunStatus = RunStatus.QUEUED
    current_agent: str | None = None
    research: ResearchReturn | None = None
    prd: PRD | None = None
    trd: TRD | None = None
    execution: ExecutionPlan | None = None
    pitch: PitchPackage | None = None
    brand: BrandPackage | None = None
    legal: LegalPackage | None = None
    funding: FundingPackage | None = None
    availability: AvailabilityReport | None = None
    compliance: ComplianceReport | None = None
    tool_calls: int = 0
    events: list[Event] = []
