"""Thin accessor over the root API's single run engine (aps.api.main).

The /v1 sub-app shares ONE orchestrator engine with the lean root API instead of standing up
a second one. Imports are done lazily inside functions so mounting /v1 from main.py doesn't
create an import cycle. Also bridges the RUN_NNNN ↔ backend run_id alias and 404s cleanly.
"""
from __future__ import annotations

from aps.api.v1 import idmap
from aps.api.v1.envelope import V1Error


def _main():
    from aps.api import main  # lazy: avoids cycle (main mounts v1 at import time)
    return main


def start_run(idea: str, config: dict | None = None,
              idempotency_key: str | None = None, user: dict | None = None) -> str:
    """Start a real orchestrator run via the shared engine; return its RUN_NNNN alias.

    Routes through the single admission path (queue + worker pool + idempotency, plan §2) so
    /v1 and the lean API share one set of concurrency guards rather than two run spawners.

    When a `user` is supplied (the authenticated /v1 caller), the run is registered in that
    user's personal History archive at admission time. Best-effort: a history hiccup never
    blocks starting the run."""
    m = _main()
    rec = m.submit_run(idea, config, idempotency_key=idempotency_key)
    alias = idmap.alias_for(rec["run_id"])
    if user:
        try:
            from aps.infra import history_store
            cfg = config or {}
            history_store.record_start(
                rec["run_id"], alias=alias,
                user_email=user.get("email"), user_id=user.get("id"),
                idea=idea, provider=cfg.get("provider"), model=cfg.get("model"),
                created_at=m._now_iso(),
            )
        except Exception:
            pass
    return alias


def cancel_run(alias: str) -> bool:
    """Cooperatively cancel the run behind an alias (plan 2.2)."""
    m = _main()
    return m.cancel_run(resolve(alias))


def resolve(alias: str) -> str:
    """RUN_NNNN → backend run_id, or 404 in the contract's error envelope."""
    bid = idmap.backend_id(alias)
    if bid is None:
        raise V1Error("RUN_NOT_FOUND", "Run ID does not exist.", status=404)
    return bid


def state_for(alias: str):
    """The live or on-disk StudioState behind an alias (None if the run hasn't produced one)."""
    m = _main()
    bid = resolve(alias)
    st = m._STATES.get(bid)
    if st is not None:
        return st
    return m.artifact_store.load_state(bid)


def meta_for(alias: str) -> dict | None:
    m = _main()
    bid = resolve(alias)
    return m._RUNS.get(bid) or m.artifact_store.load_meta(bid)


def bus_history(alias: str) -> list:
    m = _main()
    bid = resolve(alias)
    bus = m._BUSES.get(bid)
    return bus.history(bid) if bus else []


def bus_wait(alias: str, seen: int, timeout: float) -> list:
    """Block (off the event loop) until the run's history grows past `seen`, then return the
    new tail — the push primitive (plan 1.3) the WebSocket stream uses instead of polling."""
    m = _main()
    bid = resolve(alias)
    bus = m._BUSES.get(bid)
    return bus.wait(bid, seen, timeout) if bus else []


def launch_github(alias: str, *, dry_run: bool = True, token: str | None = None) -> dict:
    """GitHub Launch Mode for a run — preview (no token / dry_run) or create the real repo.
    Reshaped into the frontend contract; the REAL action lives in aps.launch."""
    from aps.launch import build_launch_plan, launch_github as do_launch
    st = state_for(alias)
    if st is None or st.prd is None:
        raise V1Error("RUN_NOT_FOUND", "Run not finished or has no PRD yet.", status=404)
    plan = build_launch_plan(st.idea, st.prd, st.execution, st.pitch, trd=st.trd)
    res = do_launch(plan, dry_run=dry_run, token=token)
    return {
        "created": res.created, "dryRun": res.dry_run, "repoUrl": res.repo_url,
        "fullName": res.full_name, "issueUrls": res.issue_urls,
        "milestonesCreated": res.milestones_created, "message": res.message,
        "repoName": plan.repo_name, "issueCount": len(plan.issues),
        "milestoneCount": len(plan.milestones),
        "filesCreated": res.files_created, "fileCount": len(plan.files),
    }


def stats() -> dict:
    return _main()._stats()


def tool_names_by_namespace() -> dict[str, list[str]]:
    """Real registry tool names grouped into the contract's 4 display namespaces."""
    try:
        from aps.tools.registry import all_tools
        names_by_ns: dict[str, list[str]] = {}
        for t in all_tools():
            ns = getattr(t, "namespace", "")
            label = {"retrieval": "Research", "analysis": "Research", "product": "Product",
                     "architecture": "Architecture", "execution": "Execution",
                     "presentation": "Execution"}.get(ns, "Research")
            names_by_ns.setdefault(label, []).append(getattr(t, "name", "tool"))
        # keep the panel readable: cap each namespace to 6 tools
        return {k: sorted(set(v))[:6] for k, v in names_by_ns.items()}
    except Exception:
        return {"Research": ["web_search", "github_api", "reddit_api"],
                "Architecture": ["diagram_gen", "openapi_spec"]}
