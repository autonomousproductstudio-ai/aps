"""The orchestrator-driven eval runner scores gold ideas end-to-end (offline)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_RUN_EVAL = Path(__file__).resolve().parents[1] / "evals" / "run_eval.py"
_spec = importlib.util.spec_from_file_location("aps_run_eval", _RUN_EVAL)
run_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_eval)


GOLD = [
    {"id": "g01", "idea": "Build an AI SaaS for resume screening", "min_evidence": 1},
    {"id": "g02", "idea": "A marketplace for renting camera gear", "min_evidence": 1},
]


def test_evaluate_runs_each_gold_item_through_the_graph():
    rows = run_eval.evaluate(GOLD)
    assert len(rows) == 2
    for r in rows:
        assert r["e2e"] is True            # all five artifacts produced
        assert r["prd_valid"] is True      # PRD validates against the contract
        assert 0.0 <= r["coverage"] <= 1.0
        assert r["evidence"] >= 1
        # W5: the feature-count regression guard is recorded per idea
        assert isinstance(r["features"], int)
        assert isinstance(r["feature_floor_met"], bool)


def test_report_markdown_renders():
    md = run_eval.to_markdown(run_eval.evaluate(GOLD))
    assert md.startswith("# Eval report")
    assert "g01" in md and "g02" in md
