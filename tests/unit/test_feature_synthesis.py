"""Phase 4b — feature SYNTHESIS: cluster pains into themed features, don't paste one-per-pain.

Pins the new behavior of `prioritize_features`: overlapping pains collapse into a single themed
feature (priority = max severity, grounding aggregated), while genuinely distinct pains stay
separate so the W3 feature floor still holds (see also test_thin_prd.py).
"""
from __future__ import annotations

from aps.state.models import PainPoint, Severity
from aps.tools.product.prioritize_features import synthesize_pain_features, TOOL


def _titles(feats):
    return [f.title for f in feats]


def test_overlapping_pains_collapse_into_one_theme():
    pains = [PainPoint(text="export is slow", severity=Severity.LOW),
             PainPoint(text="can't export quickly to csv", severity=Severity.HIGH)]
    feats = synthesize_pain_features(pains)
    assert len(feats) == 1, _titles(feats)
    assert feats[0].title == "Export"                       # the general label wins
    assert feats[0].priority == "Must"                      # MAX severity across the cluster
    assert "2 related user pains" in feats[0].description   # grounded in both


def test_distinct_pains_stay_distinct():
    pains = [PainPoint(text="the parser drops PDFs", severity=Severity.HIGH),
             PainPoint(text="ranking is slow and confusing", severity=Severity.MED),
             PainPoint(text="no way to self-host the data", severity=Severity.MED)]
    feats = synthesize_pain_features(pains)
    assert len(feats) == 3, _titles(feats)


def test_plural_and_inflection_variants_merge():
    pains = [PainPoint(text="the export is broken"), PainPoint(text="exports keep failing")]
    feats = synthesize_pain_features(pains)
    assert len(feats) == 1 and feats[0].title.lower().startswith("export")


def test_single_pain_keeps_the_original_description_format():
    feats = synthesize_pain_features([PainPoint(text="parser drops PDFs", severity=Severity.HIGH)])
    assert len(feats) == 1
    assert feats[0].description == "Addresses the user pain: 'parser drops PDFs'."


def test_floor_still_holds_through_the_tool():
    # three degenerate-but-distinct pains, no competitors → three features (W3 floor preserved)
    pains = [PainPoint(text=f"pain {i}", severity=Severity.HIGH).model_dump() for i in range(3)]
    feats = TOOL.run(pain_points=pains, competitors=[]).payload
    assert len(feats) >= 3


def test_synthesis_titles_are_clean_noun_phrases_not_complaints():
    # the synthesized label is a capability noun phrase, never a complaint sentence/fragment
    feats = synthesize_pain_features([PainPoint(text="However the dashboard keeps crashing badly")])
    assert feats and not feats[0].title.lower().startswith(("however", "the "))
    assert not any(w in feats[0].title.lower() for w in ("crashing", "badly", "keeps"))
