"""Eval harness — run each gold idea through the orchestrator and score it.

Usage: python tests/evals/run_eval.py --gold tests/evals/gold --out tests/evals/report.md

Runs the real LangGraph pipeline (Idea → Research → … → Pitch). With LLM keys the
Research step hits live sources; without them it degrades to the fixture brief, so this
harness still runs end-to-end offline (the deterministic downstream agents are always
real). Scores come from scorers.py. `evaluate()` is importable for unit tests.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# make `import aps` and `import scorers` work whether run as a script or imported
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))                       # tests/evals  -> scorers
sys.path.insert(0, str(_HERE.parents[1] / "src"))    # repo/src     -> aps

import scorers  # noqa: E402


def evaluate(gold: list[dict]) -> list[dict]:
    """Run each gold item through the orchestrator and return a scored row per item."""
    from aps.orchestrator.events import EventBus
    from aps.orchestrator.graph import run_sync

    rows: list[dict] = []
    for g in gold:
        bus = EventBus()
        state = run_sync(g["idea"], bus, run_id=g["id"])
        research, prd = state.research, state.prd
        ev = list(research.evidence) if research else []
        trace = [{"tool": "research",
                  "evidence": [e.model_dump() for e in ev]}]
        rows.append({
            "id": g["id"],
            "idea": g["idea"],
            "e2e": all([state.research, state.prd, state.trd, state.execution, state.pitch]),
            "prd_valid": scorers.prd_schema_valid(prd) if prd else False,
            "coverage": scorers.evidence_coverage(prd) if prd else 0.0,
            "diversity": scorers.source_diversity(trace),
            "evidence": len(ev),
            "min_evidence_met": len(ev) >= g.get("min_evidence", 0),
            "features": scorers.prd_feature_count(prd) if prd else 0,
            "feature_floor_met": scorers.meets_feature_floor(prd) if prd else False,
            "relevance_rate": scorers.evidence_relevance_rate(g["idea"], ev),   # E12
            "relevance_met": scorers.evidence_relevance_rate(g["idea"], ev) >= g.get("min_relevance", 0.8),
            "titles_clean": scorers.feature_titles_clean(prd) if prd else False,  # E14
        })
    return rows


def to_markdown(rows: list[dict]) -> str:
    head = ("# Eval report\n\n"
            "| id | idea | e2e (E7) | prd_valid (E6) | coverage (E4) | sources (E3) "
            "| evidence | features (E11) | relevance (E12) | titles (E14) |\n"
            "|---|---|---|---|---|---|---|---|---|---|\n")
    body = "\n".join(
        f"| {r['id']} | {r['idea'][:40]} | {'✓' if r['e2e'] else '✗'} | "
        f"{'✓' if r['prd_valid'] else '✗'} | {r['coverage']} | {r['diversity']} | "
        f"{r['evidence']}{'' if r['min_evidence_met'] else ' (below min)'} | "
        f"{r['features']}{' ✓' if r['feature_floor_met'] else ' (<3)'} | "
        f"{r['relevance_rate']}{' ✓' if r['relevance_met'] else ' (<0.8)'} | "
        f"{'✓' if r['titles_clean'] else '✗ fragment'} |"
        for r in rows
    )
    return head + body + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default=str(_HERE / "gold"))
    ap.add_argument("--out", default=str(_HERE / "report.md"))
    a = ap.parse_args()
    gold = json.loads((Path(a.gold) / "gold.json").read_text())
    rows = evaluate(gold)
    Path(a.out).write_text(to_markdown(rows), encoding="utf-8")
    passed = sum(1 for r in rows if r["e2e"] and r["prd_valid"])
    print(f"wrote {a.out}: {passed}/{len(rows)} items passed e2e+prd_valid")


if __name__ == "__main__":
    main()
