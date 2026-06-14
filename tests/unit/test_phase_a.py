"""Phase-A credibility fixes: idea-agnostic stub + noun entities / correct pluralization."""
from __future__ import annotations

from aps.agents.research.stub import stub_research
from aps.tools.architecture import design_data_model, design_api_contract
from aps.state.models import Feature


def test_stub_is_idea_agnostic_and_degraded():
    r = stub_research("a privacy-first habit tracker")
    assert r.degraded is True
    # the fixture references the actual idea and never claims a different domain (no ATS bleed)
    blob = (r.market_size + " " + " ".join(p.text for p in r.pain_points)
            + " " + " ".join(e.snippet for e in r.evidence)).lower()
    assert "ats" not in blob and "resume" not in blob
    assert "habit tracker" in blob
    assert r.evidence and all(e.source == "stub_fallback" for e in r.evidence)


def test_arch_entities_are_domain_nouns_not_verbs():
    # idea is the clean source; the feature title is raw pain text that used to mint
    # verb/adjective entities (`Rejects`, `Great`) and `/rejectss`.
    dm = design_data_model.TOOL.run(
        idea="a privacy-first habit tracker for couples",
        features=[Feature(title="Solve: ATS rejects qualified candidates",
                          description="x", priority="High").model_dump()],
    ).payload
    names = {n.lower() for n in dm["entities"]}
    assert "habit" in names or "tracker" in names          # clean domain noun from the idea
    for bad in ("rejects", "great", "inconvenient", "solve", "resolve", "qualified"):
        assert bad not in names                              # no verbs/adjectives/filler
    assert len(dm["entities"]) >= 2


def test_api_contract_pluralization_has_no_double_s():
    dm = {"entities": {"Class": {"fields": {"id": "uuid"}},
                       "Category": {"fields": {"id": "uuid"}}}}
    doc = design_api_contract.TOOL.run(data_model=dm, idea="x").payload
    paths = list(doc["paths"].keys())
    assert "/classes" in paths and "/categories" in paths
    assert not any(p.endswith("ss") for p in paths)
    assert doc["paths"]["/classes"]["get"]["operationId"] == "listClasses"


def test_keyless_research_returns_real_evidence_not_stub(monkeypatch):
    # Phase C: with no LLM key, the no-key tools are called directly and compressed into a
    # REAL ResearchReturn (degraded=False) — not the labeled stub. Tools are monkeypatched
    # so the unit test stays offline/hermetic.
    import importlib
    from aps.agents.research import keyless
    from aps.state.models import ToolResult, Evidence

    def fake_run(**kwargs):
        return ToolResult(ok=True, evidence=[Evidence(
            source="hackernews", url="https://news.ycombinator.com/item?id=1",
            title="habit tracker friction",
            snippet="people say existing habit trackers are broken and hard to stick with")])

    for mod_path, _extra in keyless._KEYLESS_TOOLS:
        monkeypatch.setattr(importlib.import_module(mod_path).TOOL, "run", fake_run)

    r = keyless.keyless_research("a privacy-first habit tracker")
    assert r.idea == "a privacy-first habit tracker"
    assert r.degraded is False     # genuine evidence, not the stub fallback
    assert r.evidence              # compressed from the no-key tools' output
