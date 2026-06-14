"""Eval scorers (tests/evals/scorers.py) — deterministic, run against real artifacts."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from aps.state.models import Evidence
from aps.agents.research.stub import stub_research
from aps.agents.product.agent import run_product

# scorers.py lives under tests/evals (not importable as a package) — load by path.
_SPEC = importlib.util.spec_from_file_location(
    "aps_eval_scorers",
    Path(__file__).resolve().parents[1] / "evals" / "scorers.py",
)
scorers = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(scorers)


def _trace():
    return [
        {"tool": "github_list_issues", "namespace": "retrieval",
         "evidence": [Evidence(source="github", url="https://github.com/x/1",
                               title="t", snippet="parser drops PDFs").model_dump()]},
        {"tool": "hn_search", "namespace": "retrieval",
         "evidence": [Evidence(source="hackernews", url="https://h/2",
                               title="t", snippet="ranking misses people").model_dump()]},
        {"tool": "not_a_real_tool", "namespace": "retrieval", "evidence": []},
    ]


def test_selection_validity_counts_known_tools():
    # 2 of 3 calls are real registry tools
    assert scorers.selection_validity(_trace()) == round(2 / 3, 3)
    assert scorers.selection_validity([]) == 0.0


def test_source_diversity_counts_distinct_sources():
    assert scorers.source_diversity(_trace()) == 2  # github + hackernews


def test_prd_schema_valid_true_for_real_prd():
    prd = run_product(stub_research("resume screening"))
    assert scorers.prd_schema_valid(prd) is True
    assert scorers.prd_schema_valid({"idea": ""}) is False


def test_evidence_coverage_in_unit_range():
    prd = run_product(stub_research("resume screening"))
    cov = scorers.evidence_coverage(prd)
    assert 0.0 <= cov <= 1.0


def test_prd_feature_count_and_floor():
    from aps.state.models import PRD, Feature
    prd = PRD(idea="x", requirements=["r"],
              features=[Feature(title=f"f{i}", description="d") for i in range(3)])
    assert scorers.prd_feature_count(prd) == 3
    assert scorers.meets_feature_floor(prd) is True
    assert scorers.meets_feature_floor(PRD(idea="x")) is False
    # works on a plain dict too (artifact-store JSON)
    assert scorers.prd_feature_count(prd.model_dump()) == 3


def test_evidence_coverage_detects_overlap():
    from aps.state.models import PRD, Feature
    prd = PRD(idea="x",
              features=[Feature(title="resume parser fix", description="handle pdf")],
              requirements=["r"],
              sources=[Evidence(source="github", url="https://g/1", title="parser",
                                snippet="the resume parser drops pdf files")])
    assert scorers.evidence_coverage(prd) == 1.0
