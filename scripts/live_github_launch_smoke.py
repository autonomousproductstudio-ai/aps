"""Live GitHub Launch smoke — creates a REAL repo from a run (needs APS_GITHUB_PAT, repo scope).

    APS_GITHUB_PAT=ghp_xxx python scripts/live_github_launch_smoke.py "your idea"

Runs the full vertical, then launches the execution package to GitHub for real and prints
the repo URL + created issues. This is NOT run in CI (it makes live calls and creates a repo).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def main() -> int:
    idea = sys.argv[1] if len(sys.argv) > 1 else "A privacy-first habit tracker for couples"
    # Importing aps.config loads .env into os.environ (pydantic-settings side effect), so the PAT
    # check below sees a key set in .env — not only one exported in the shell.
    import aps.config.settings  # noqa: F401
    if not os.getenv("APS_GITHUB_PAT"):
        print("FAIL: set APS_GITHUB_PAT (a repo-scoped PAT) to create the repo for real.")
        return 1

    from aps.orchestrator.events import EventBus
    from aps.orchestrator.graph import run_sync
    from aps.launch import build_launch_plan, launch_github

    bus = EventBus()
    state = run_sync(idea, bus, run_id="launch_smoke")
    plan = build_launch_plan(state.idea, state.prd, state.execution, state.pitch)
    print(f">>> launching repo '{plan.repo_name}' "
          f"({len(plan.issues)} issues, {len(plan.milestones)} milestones)...")

    result = launch_github(plan, dry_run=False)
    print(result.message)
    if result.created:
        print("repo:", result.repo_url)
        for u in result.issue_urls[:5]:
            print("  issue:", u)
        print("\nPASS — real GitHub repo created.")
        return 0
    print("\nFAIL — see message above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
