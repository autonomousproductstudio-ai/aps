"""Live single-idea eval (gold g01) for the real MEMO numbers.

Runs the full orchestrator once (research fan-out + downstream agents) against a live
model, scores it with the eval scorers, writes tests/evals/report.md, and prints the
numbers to paste into MEMO.md. One idea on purpose — the full 8-idea gold set runs offline
in CI (test_eval_runner.py); running all 8 live would burn ~240 model calls.

    python scripts/eval_g01_live.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests", "evals"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _tool_counts() -> dict[str, float]:
    from aps.infra.metrics import TOOL_CALLS
    out: dict[str, float] = {}
    collect = getattr(TOOL_CALLS, "collect", None)
    if not collect:
        return out
    for fam in collect():
        for s in fam.samples:
            if s.name.endswith("_total") and s.value:
                out[s.labels.get("tool")] = out.get(s.labels.get("tool"), 0.0) + s.value
    return out


def main() -> int:
    # `--model NAME` overrides the NIM model for a verification run; set BEFORE importing
    # settings/run_eval (get_settings is lru_cached at import).
    argv = sys.argv[1:]
    if "--model" in argv:
        i = argv.index("--model")
        if i + 1 < len(argv):
            os.environ["APS_NIM_MODEL"] = argv[i + 1]

    from aps.config.settings import describe_runtime
    print(f"runtime: {describe_runtime()}")

    import run_eval  # tests/evals/run_eval.py

    g01 = [{"id": "g01", "idea": "Build an AI SaaS for resume screening",
            "expect_sources": ["github", "hackernews", "reddit"], "min_evidence": 5}]
    rows = run_eval.evaluate(g01)
    report = Path(__file__).resolve().parents[1] / "tests" / "evals" / "report.md"
    report.write_text(run_eval.to_markdown(rows), encoding="utf-8")

    tools = _tool_counts()
    r = rows[0]
    print("=== g01 LIVE eval ===")
    print(json.dumps(r, indent=2))
    print("distinct tools called :", len(tools))
    print("total tool calls      :", int(sum(tools.values())))
    print("report.md written     :", report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
