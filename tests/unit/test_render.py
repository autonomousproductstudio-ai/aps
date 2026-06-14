"""Renderer layer (plan.md W1): completeness, empty-input, citation integrity, determinism."""
from __future__ import annotations

import pytest

from aps.state.models import (
    ResearchReturn, PRD, TRD, ExecutionPlan, PitchPackage,
    Evidence, Competitor, PainPoint, Persona, Feature, Severity,
)
from aps.render import render_artifact, base
from aps.render import research_md, prd_md, trd_md, execution_md, pitch_md


# ── fixtures ────────────────────────────────────────────────────────────────
def _evidence():
    return [
        Evidence(source="github", url="https://github.com/x/y/issues/1",
                 title="Parser drops PDFs", snippet="the resume parser drops valid pdf files"),
        Evidence(source="reddit", url="https://reddit.com/r/x/2",
                 title="ranking complaint", snippet="keyword ranking misses good candidates"),
    ]


def _research():
    ev = _evidence()
    return ResearchReturn(
        idea="AI resume screening",
        market_size="TAM ~$3B (cited at https://x.com/report)",
        competitors=[Competitor(name="Acme", url="https://acme.io",
                                features=["PDF export", "Slack"], pricing="$49/mo", notes="incumbent")],
        pain_points=[PainPoint(text="parser drops PDFs", severity=Severity.HIGH,
                               source_evidence=[ev[0]])],
        evidence=ev,
    )


def _prd():
    ev = _evidence()
    return PRD(
        idea="AI resume screening",
        personas=[Persona(name="Recruiter", role="recruiter",
                          goals=["screen faster"], frustrations=["parser drops PDFs"])],
        features=[Feature(title="Reliable PDF parsing", description="handle pdf resumes",
                          priority="Must")],
        mvp_scope="MVP: reliable parsing.",
        requirements=["[Must] Reliable PDF parsing: handle pdf resumes", "Keyword ranking quality"],
        sources=ev,
    )


def _trd():
    return TRD(
        data_model={"entities": {"User": {"fields": {"id": "uuid", "email": "string"}},
                                 "Resume": {"fields": {"id": "uuid", "score": "float"}}},
                    "architecture": {"components": ["API gateway", "worker"],
                                     "data_flow": ["client → api → db"]}},
        api_spec={"openapi": "3.0.3", "info": {"title": "X API", "version": "1.0.0"},
                  "paths": {"/resumes": {"get": {"summary": "List Resumes"},
                                         "post": {"summary": "Create Resume"}}},
                  "components": {"schemas": {}}},
        stack=["Backend: FastAPI", "DB: PostgreSQL"],
        scale_estimate="10k-100k users; p95 < 300ms",
    )


def _execution():
    return ExecutionPlan(
        repo_plan={"dirs": ["backend/app", "frontend/src"], "key_files": ["README.md"]},
        backlog=[{"id": "APS-001", "title": "Parse PDFs", "type": "story",
                  "priority": "Must", "points": 5}],
        sprints=[{"sprint": 1, "items": [{"title": "Parse PDFs"}], "points": 5}],
        roadmap="MVP then Beta.",
        infra_cost="~$235/mo",
    )


def _pitch():
    return PitchPackage(pitch_outline="1. Problem\n5. Ask",
                        demo_script="Demo steps",
                        investor_memo="INVESTOR MEMO\n\n---\nJUDGE BRIEF")


# ── completeness: every field's content appears in the output ───────────────
def test_research_render_is_complete():
    r = _research()
    md = research_md.render(r)
    assert r.market_size in md
    assert "Acme" in md and "$49/mo" in md
    for e in r.evidence:
        assert e.url in md           # citation integrity: every evidence URL linked
    assert "HIGH" in md              # severity badge


def test_prd_render_is_complete_with_citations():
    p = _prd()
    md = prd_md.render(p)
    assert "Recruiter" in md
    assert "Reliable PDF parsing" in md and "[Must]" in md
    assert p.mvp_scope in md
    # requirement citations: the PDF requirement overlaps the github source → linked
    assert "github.com/x/y/issues/1" in md


def test_trd_render_has_tables_and_spec():
    md = trd_md.render(_trd())
    assert "FastAPI" in md and "PostgreSQL" in md
    assert "User" in md and "Resume" in md     # entity tables
    assert "/resumes" in md and "GET" in md     # endpoint summary
    assert "```json" in md and "openapi" in md  # fenced spec


def test_execution_render_is_complete():
    md = execution_md.render(_execution())
    assert "APS-001" in md and "Parse PDFs" in md
    assert "Sprint 1" in md and "~$235/mo" in md


def test_pitch_render_sections():
    md = pitch_md.render(_pitch())
    assert "Pitch Outline" in md and "Demo Script" in md and "Investor Memo" in md
    assert "JUDGE BRIEF" in md


# ── empty / degenerate input: graceful, no exception, no literal None/null ──
@pytest.mark.parametrize("name,obj", [
    ("research", ResearchReturn(idea="x")),
    ("prd", PRD(idea="x")),
    ("trd", TRD()),
    ("execution", ExecutionPlan()),
    ("pitch", PitchPackage()),
])
def test_empty_artifacts_render_gracefully(name, obj):
    md = render_artifact(name, obj)
    assert md and base.PLACEHOLDER in md
    # no raw None/null leaking into the document
    assert "None" not in md
    assert ": null" not in md.lower()


def test_degraded_research_is_flagged():
    r = _research()
    r.degraded = True
    assert "Degraded run" in research_md.render(r)


# ── determinism: render twice → byte-identical ──────────────────────────────
@pytest.mark.parametrize("name,factory", [
    ("research", _research), ("prd", _prd), ("trd", _trd),
    ("execution", _execution), ("pitch", _pitch),
])
def test_render_is_deterministic(name, factory):
    obj = factory()
    assert render_artifact(name, obj) == render_artifact(name, obj)


# ── registry: dict (artifact-store JSON) renders identically to the model ────
def test_render_artifact_accepts_dict():
    p = _prd()
    assert render_artifact("prd", p.model_dump()) == render_artifact("prd", p)


def test_render_artifact_unknown_name_raises():
    with pytest.raises(KeyError):
        render_artifact("bogus", {})


# ── base helpers ────────────────────────────────────────────────────────────
def test_evidence_link_graceful_without_url():
    e = Evidence(source="hn", url="", title="t", snippet="s")
    assert base.evidence_link(e) == "hn · t"           # no broken link
    assert base.citation_refs([]) == base.PLACEHOLDER


def test_table_escapes_pipes_and_handles_empty():
    assert base.table(["A"], []) .strip() == base.PLACEHOLDER
    t = base.table(["A"], [["x|y"]])
    assert "x\\|y" in t
