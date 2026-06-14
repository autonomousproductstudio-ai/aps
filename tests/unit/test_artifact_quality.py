"""Artifact-quality cascade fix: clean labels, domain-noun entities, competitor deny-list."""
from __future__ import annotations

from aps.tools.analysis._text import clean_label
from aps.tools.analysis import build_competitor_matrix as cm
from aps.tools.architecture import design_data_model as ddm
from aps.tools.architecture import design_api_contract as dac
from aps.state.models import Evidence, Feature


def test_clean_label_strips_boilerplate_and_markdown():
    out = clean_label("Solve: ## Feature Request: Scheduled Auto-Export for integrations…Please descr")
    assert out == "Scheduled Auto-Export for integrations"
    assert "##" not in out and "solve" not in out.lower()
    assert "descr" not in out.lower()       # no mid-word fragment leaks


def test_clean_label_is_short_and_capitalized():
    out = clean_label("the parser is broken and keeps dropping data and lots more text follows here")
    assert 0 < len(out.split()) <= 8
    assert out[0].isupper()


def test_competitor_deny_excludes_integrations_and_categories():
    ev = [
        Evidence(source="web", url="https://zapier.com/apps", title="Zapier", snippet="integrates apps"),
        Evidence(source="web", url="https://productivity.com/blog", title="p", snippet="productivity tips"),
        Evidence(source="web", url="https://api.github.io/x", title="gh", snippet="code sample"),
        Evidence(source="web", url="https://habitbox.com", title="Habitbox",
                 snippet="A habit tracker that supports reminders and shared goals. $5/mo."),
    ]
    names = {c.name.lower() for c in
             cm.TOOL.run(evidence=[e.model_dump() for e in ev]).payload}
    assert "habitbox" in names                                  # real product kept
    assert names.isdisjoint({"zapier", "productivity", "github"})  # noise excluded


def test_entities_are_domain_nouns_no_fragments():
    dm = ddm.TOOL.run(
        idea="a privacy-first habit tracker for couples",
        features=[Feature(title="Scheduled export for integrations", description="x", priority="Should").model_dump(),
                  Feature(title="Reminder notifications", description="x", priority="Must").model_dump()],
    ).payload
    names = {n.lower() for n in dm["entities"]}
    assert "habit" in names                                     # clean domain noun from the idea
    for bad in ("descr", "scheduled", "external", "tool", "integration", "export"):
        assert bad not in names
    paths = list(dac.TOOL.run(data_model=dm, idea="x").payload["paths"].keys())
    assert not any(p.endswith("ss") for p in paths)             # sane pluralization
