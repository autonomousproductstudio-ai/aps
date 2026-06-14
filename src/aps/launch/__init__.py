"""aps.launch — turn the execution package into a REAL GitHub project (remaining.md T2.4).

`build_launch_plan` is pure/deterministic (repo name, README, milestones, issues from the
PRD + ExecutionPlan). `launch_github` performs the **real** GitHub REST API calls (create
repo, push README, open milestones + issues) when a PAT is provided; with no token it
returns a clearly-labeled **preview** (no network) so nothing is created by accident.

This is an ACTION, not a research tool — it is NOT in the registry and NOT counted in the 52.
"""
from aps.launch.github_launch import (
    LaunchIssue, LaunchPlan, LaunchResult, build_launch_plan, launch_github,
)

__all__ = [
    "LaunchIssue", "LaunchPlan", "LaunchResult", "build_launch_plan", "launch_github",
]
