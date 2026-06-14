"""CLI: python -m aps.orchestrator.run "Build an AI SaaS for resume screening"

Runs the full orchestrator and prints a summary + the typed StudioState as JSON.
Set APS_USE_STUBS=true to force the Research fixture (no keys/network).
"""
from __future__ import annotations

import sys

from aps.orchestrator.events import EventBus
from aps.orchestrator.graph import run_sync


def main() -> None:
    idea = sys.argv[1] if len(sys.argv) > 1 else "Build an AI SaaS for resume screening"
    bus = EventBus()
    state = run_sync(idea, bus, run_id="run_cli")

    produced = [a for a in ("research", "prd", "trd", "execution", "pitch")
                if getattr(state, a) is not None]
    status = state.status.value
    print(f"\n# Run finished - status={status}", file=sys.stderr)
    if status == "degraded":
        print("# [DEGRADED] no live evidence -- ran on the stub fixture. Set an LLM key "
              "(APS_MODEL_PROVIDER + NVIDIA_API_KEY / GEMINI_API_KEY) for real research.",
              file=sys.stderr)
    elif status == "failed":
        print("# [FAILED] LLM preflight/auth failed -- check the run_failed event "
              "(likely a wrong/expired key).", file=sys.stderr)
    print(f"# Artifacts: {', '.join(produced)}", file=sys.stderr)
    print(f"# Events: {len(state.events)}", file=sys.stderr)
    if state.trd:
        print(f"# API paths: {len(state.trd.api_spec.get('paths', {}))} | "
              f"backlog: {len(state.execution.backlog) if state.execution else 0} items",
              file=sys.stderr)
    print(state.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
