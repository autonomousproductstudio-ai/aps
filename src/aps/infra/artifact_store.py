"""File-backed artifact store (Req-4, ADR-0003). NOT a counted tool — platform capability.

A minimal durable store so runs survive a process restart and every artifact is inspectable
on disk. This is the v1 stand-in for Redis-backed cross-run memory (a "more time would add"
item in the MEMO). Pure stdlib json + pathlib; one directory per run under APS_ARTIFACT_DIR
(default .artifacts/).

Layout:
    {dir}/{run_id}/meta.json    -> {run_id, idea, status, artifacts:[...]}
    {dir}/{run_id}/state.json   -> full StudioState dump
    {dir}/{run_id}/{name}.json  -> each produced artifact (research, prd, trd, ...)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from aps.state.models import StudioState

_ARTIFACTS = ("research", "prd", "trd", "execution", "pitch", "brand", "legal", "funding",
              "availability", "compliance")


def _root() -> Path:
    d = Path(os.getenv("APS_ARTIFACT_DIR", ".artifacts"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_run(run_id: str, state: StudioState) -> Path:
    """Persist a finished run's state + each produced artifact to disk. Returns the dir."""
    d = _root() / run_id
    d.mkdir(parents=True, exist_ok=True)
    produced = [a for a in _ARTIFACTS if getattr(state, a, None) is not None]
    (d / "state.json").write_text(state.model_dump_json(indent=2), encoding="utf-8")
    for name in produced:
        obj = getattr(state, name)
        (d / f"{name}.json").write_text(
            json.dumps(obj.model_dump(), default=str, indent=2), encoding="utf-8")
    status = state.status.value if hasattr(state.status, "value") else str(state.status)
    # Surface WHY a run degraded right in meta.json, so `GET /runs/{id}` and a glance at disk
    # explain a degraded/failed run without parsing the full event trace.
    degrade_reason = getattr(state.research, "degrade_reason", None) if state.research else None
    (d / "meta.json").write_text(
        json.dumps({"run_id": run_id, "idea": state.idea, "status": status,
                    "degrade_reason": degrade_reason, "artifacts": produced}, indent=2),
        encoding="utf-8")
    return d


def load_meta(run_id: str) -> dict | None:
    p = _root() / run_id / "meta.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def load_artifact(run_id: str, name: str) -> dict | None:
    p = _root() / run_id / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def load_state(run_id: str) -> StudioState | None:
    p = _root() / run_id / "state.json"
    return StudioState.model_validate_json(p.read_text(encoding="utf-8")) if p.exists() else None


def list_runs() -> list[str]:
    root = _root()
    return sorted(p.name for p in root.iterdir()
                  if p.is_dir() and (p / "meta.json").exists())
