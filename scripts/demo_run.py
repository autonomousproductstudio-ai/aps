"""demo_run.py — clean full-vertical demo on any idea (Phase 6 defense / repro entry point).

Runs Idea -> Research(fan-out) -> Product -> Architecture -> Execution -> Presentation,
persists every artifact to the file store (.artifacts/<run_id>/), and prints a human
summary. With an LLM key + free source keys it runs fully live; with no keys it degrades to
the fixture brief and still completes end-to-end (so a judge can reproduce either way).

    python scripts/demo_run.py "a privacy-first personal finance tracker for couples"
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _parse_args(argv: list[str]) -> tuple[str, str | None]:
    """Return (idea, model). `--model NAME` overrides the NIM model for verification runs
    (e.g. qwen3.5-122b-a10b / glm-5.1); the positional arg is the idea."""
    idea, model, rest = None, None, []
    it = iter(argv)
    for a in it:
        if a == "--model":
            model = next(it, None)
        elif a.startswith("--model="):
            model = a.split("=", 1)[1]
        else:
            rest.append(a)
    if rest:
        idea = rest[0]
    return (idea or "a privacy-first personal finance tracker for couples", model)


def main() -> int:
    idea, model = _parse_args(sys.argv[1:])
    # Must set the model env BEFORE importing settings (get_settings is lru_cached at import).
    if model:
        os.environ["APS_NIM_MODEL"] = model

    from aps.orchestrator.events import EventBus
    from aps.orchestrator.graph import run_sync
    from aps.infra import artifact_store
    from aps.config.settings import describe_runtime

    run_id = "demo"
    print(f"{describe_runtime()} fanout={os.getenv('APS_RESEARCH_FANOUT', 'true')}")
    print(f">>> {idea!r}\n")

    bus = EventBus()
    state = run_sync(idea, bus, run_id=run_id)
    path = artifact_store.save_run(run_id, state)

    ev_types = [e.type for e in bus.history(run_id)]
    produced = [a for a in ("research", "prd", "trd", "execution", "pitch")
                if getattr(state, a) is not None]

    # W6: drop a human-readable Markdown render of each artifact beside its JSON, so a judge
    # running the demo gets readable documents (the pipeline still persists JSON only).
    from aps.render import render_artifact
    for name in produced:
        (path / f"{name}.md").write_text(
            render_artifact(name, getattr(state, name)), encoding="utf-8")
    # T2.2: drop the TRD's Mermaid architecture diagrams alongside the JSON/MD
    if state.trd is not None:
        from aps.render import architecture_mmd
        (path / "trd.mermaid.md").write_text(
            architecture_mmd.render(state.trd), encoding="utf-8")
    r, prd, trd, ex = state.research, state.prd, state.trd, state.execution

    print(f"status        : {state.status.value}")
    print(f"artifacts     : {', '.join(produced)}")
    print(f"events        : {len(ev_types)}  (fan-out: "
          f"{ev_types.count('research_unit_start')} sub-researchers)")
    if r:
        print(f"research      : {len(r.evidence)} evidence, {len(r.competitors)} competitors, "
              f"{len(r.pain_points)} pains")
        print(f"market_size   : {(r.market_size or '')[:90]}")
    if prd:
        print(f"prd           : {len(prd.personas)} personas, {len(prd.features)} features, "
              f"{len(prd.requirements)} requirements, {len(prd.sources)} sources")
    if trd:
        print(f"trd           : OpenAPI {trd.api_spec.get('openapi')}, "
              f"{len(trd.api_spec.get('paths', {}))} paths, stack {trd.stack[:4]}")
    if ex:
        print(f"execution     : {len(ex.backlog)} backlog items, {len(ex.sprints)} sprints")
    print(f"pitch         : {'yes' if state.pitch else 'no'}")

    if state.research:
        from aps.scoring import score_startup
        sc = score_startup(state.research, state.prd)
        print(f"\nStartup Score : {sc.overall}/10 — {sc.verdict}")
        for d in sc.dimensions:
            print(f"  {d.name:24} {d.score:>4}/10  ({d.rationale})")

        from aps.debate import run_debate
        dbt = run_debate(state.research, state.prd)
        print(f"\nDebate verdict: {dbt.verdict}  (confidence {int(dbt.confidence * 100)}%)")
        print(f"  FOR : {len(dbt.build_case)} point(s) · AGAINST: {len(dbt.risk_case)} risk(s)")

    if state.prd:
        from aps.explain import explain_prd
        ex = explain_prd(state.prd, state.research)
        print(f"\nExplain-Why   : {int(ex.overall_confidence * 100)}% avg confidence "
              f"across {len(ex.features)} feature(s) (every feature traced to its evidence)")

    if state.prd:
        # GitHub Launch preview (dry-run — creates nothing; set APS_GITHUB_PAT + run the
        # live smoke / POST /launch/github to create the repo for real).
        from aps.launch import build_launch_plan, launch_github
        plan = build_launch_plan(state.idea, state.prd, state.execution, state.pitch)
        prev = launch_github(plan, dry_run=True)
        print(f"\nGitHub Launch : repo '{plan.repo_name}' — {len(plan.issues)} issues, "
              f"{len(plan.milestones)} milestones (preview; set APS_GITHUB_PAT to create)")

    print(f"\nartifacts saved to: {path}")

    ok = state.status.value == "complete" and len(produced) == 5
    print("\n" + ("PASS — full vertical reproduced end-to-end." if ok else "INCOMPLETE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
