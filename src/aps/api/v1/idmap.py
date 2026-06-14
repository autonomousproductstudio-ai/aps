"""RUN_NNNN ⇄ backend run_id aliasing (docs uses "RUN_0042"; the engine uses "run_a1b2c3").

v1's POST /runs starts a real orchestrator run, gets its backend id, and registers a "RUN_NNNN"
alias. Runs created via the legacy root API (or loaded from disk) are given aliases lazily on
first listing, so they still appear on the /v1 dashboard.

Durability (fix): the map is **persisted to disk** (alongside the artifact store) and reloaded on
startup. The run STATE already survives a restart via artifact_store; without persisting this
mapping too, a browser holding a `RUN_NNNN` (localStorage active-run, a History/Launch deep link)
would 404 after any backend restart/redeploy — the run would appear "lost" and Launch would fail.
Persisting it means a stored alias keeps resolving to its on-disk state across restarts.
"""
from __future__ import annotations

import itertools
import json
import os
import threading
from pathlib import Path

_LOCK = threading.RLock()
_alias_to_backend: dict[str, str] = {}
_backend_to_alias: dict[str, str] = {}
_seq: "itertools.count | None" = None   # initialized on first use, after loading the saved map


def _path() -> Path:
    return Path(os.getenv("APS_ARTIFACT_DIR", ".artifacts")) / "idmap.json"


def _ensure_loaded() -> None:
    """Load the persisted map once, and seed the counter past the highest existing alias."""
    global _seq
    if _seq is not None:
        return
    try:
        p = _path()
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            for alias, bid in data.items():
                _alias_to_backend[alias] = bid
                _backend_to_alias[bid] = alias
    except Exception:
        pass
    highest = 0
    for alias in _alias_to_backend:
        try:
            highest = max(highest, int(alias.split("_")[1]))
        except Exception:
            pass
    _seq = itertools.count(highest + 1)


def _save() -> None:
    try:
        p = _path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(_alias_to_backend, indent=2), encoding="utf-8")
        tmp.replace(p)   # atomic swap so a crash mid-write never corrupts the map
    except Exception:
        pass


def alias_for(backend_id: str) -> str:
    """Stable RUN_NNNN for a backend run id, minting (and persisting) one on first sight."""
    with _LOCK:
        _ensure_loaded()
        existing = _backend_to_alias.get(backend_id)
        if existing:
            return existing
        alias = f"RUN_{next(_seq):04d}"
        _alias_to_backend[alias] = backend_id
        _backend_to_alias[backend_id] = alias
        _save()
        return alias


def backend_id(alias: str) -> str | None:
    with _LOCK:
        _ensure_loaded()
        return _alias_to_backend.get(alias)


def known_alias(alias: str) -> bool:
    with _LOCK:
        _ensure_loaded()
        return alias in _alias_to_backend
