"""Phase 5 — lock the research-quality work with an eval that runs in CI (hermetic).

Three guards so the relevance gate / pain validation / feature synthesis can never silently
regress: (E12) on-topic evidence stays >= 0.8, (E13) known junk fixtures are all rejected, and
(E14) no PRD feature title is a raw fragment.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from aps.state.models import Evidence, PainPoint, Severity, PRD, Feature, Persona
from aps.agents.research.agent import _compress
from aps.agents.product.agent import run_product
from aps.agents.research.stub import stub_research

# scorers.py lives under tests/evals (not an importable package) — load by path.
_SPEC = importlib.util.spec_from_file_location(
    "aps_eval_scorers", Path(__file__).resolve().parents[1] / "evals" / "scorers.py")
scorers = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(scorers)

_FIX = json.loads((Path(__file__).resolve().parents[1] / "evals" / "fixtures" / "offtopic.json").read_text())


# ── E13: off-topic rejection — the headline guard ────────────────────────────
def test_all_known_junk_is_rejected():
    rate = scorers.off_topic_rejection_rate(_FIX["idea"], _FIX["junk"])
    assert rate == 1.0, f"junk leaked through the gate: rejection rate {rate}"


def test_relevant_fixtures_score_above_threshold():
    rate = scorers.evidence_relevance_rate(_FIX["idea"], _FIX["relevant"])
    assert rate >= 0.8, f"on-topic evidence relevance rate too low: {rate}"


def test_gate_drops_junk_from_pains_end_to_end():
    # mix junk + a real complaint through the real compression gate → no junk in pains
    evidence = [Evidence(url=f"https://x/{i}", **j) for i, j in enumerate(_FIX["junk"])]
    evidence.append(Evidence(source="reddit", url="https://r/1", title="rant",
                             snippet="the activity tracker is broken and keeps crashing on sync"))
    research = _compress(_FIX["idea"], evidence)
    joined = " ".join(p.text.lower() for p in research.pain_points)
    for bad in ("stake", "bonus", "sales", "freelance", "sun position", "youtube"):
        assert bad not in joined, f"junk term {bad!r} reached the pains: {joined!r}"


# ── E12: evidence relevance rate ─────────────────────────────────────────────
def test_relevance_rate_is_high_for_clean_set_low_for_dirty():
    clean = scorers.evidence_relevance_rate(_FIX["idea"], _FIX["relevant"])
    dirty = scorers.evidence_relevance_rate(_FIX["idea"], _FIX["junk"])
    assert clean >= 0.8 and dirty <= 0.2 and clean > dirty


# ── E14: feature-title sanity ────────────────────────────────────────────────
def _prd_with_titles(titles):
    return PRD(idea="x", personas=[Persona(name="P", role="r")],
               features=[Feature(title=t, description="d", priority="Should") for t in titles],
               requirements=["r"], mvp_scope="m")


def test_feature_titles_clean_flags_fragments():
    assert scorers.feature_titles_clean(_prd_with_titles(["Resume Parser", "Export"])) is True
    for bad in ["However about a week", "When following a Google", "Maintainer]",
                "Implement: bulk delete", "Feature request: offline mode", "API that gives..."]:
        assert scorers.feature_titles_clean(_prd_with_titles([bad])) is False, bad


def test_real_product_agent_yields_clean_titles():
    # the actual pipeline (stub research → product agent) must produce only clean feature titles
    research = stub_research("a privacy-first activity tracker")
    research.pain_points = [
        PainPoint(text="However the activity tracker keeps crashing", severity=Severity.HIGH),
        PainPoint(text="no way to self-host the data", severity=Severity.MED),
    ]
    prd = run_product(research)
    assert prd.features, "expected synthesized features"
    assert scorers.feature_titles_clean(prd), [f.title for f in prd.features]
