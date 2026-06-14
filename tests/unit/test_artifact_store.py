"""File artifact store persists a run and serves it read-through (offline, deterministic)."""
from __future__ import annotations

from aps.infra import artifact_store
from aps.agents.research.stub import stub_research
from aps.agents.product.agent import run_product
from aps.state.models import StudioState, RunStatus, PRD


def _state() -> StudioState:
    research = stub_research("Build an AI SaaS for resume screening")
    prd = run_product(research)
    return StudioState(idea=research.idea, status=RunStatus.COMPLETE,
                       research=research, prd=prd)


def test_save_then_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("APS_ARTIFACT_DIR", str(tmp_path))
    state = _state()
    artifact_store.save_run("run_x", state)

    # artifacts written to disk
    assert (tmp_path / "run_x" / "prd.json").exists()
    assert (tmp_path / "run_x" / "meta.json").exists()
    assert (tmp_path / "run_x" / "state.json").exists()

    # read-through (simulates a fresh process: only the files exist)
    meta = artifact_store.load_meta("run_x")
    assert meta["idea"] == state.idea and "prd" in meta["artifacts"]

    prd = artifact_store.load_artifact("run_x", "prd")
    assert PRD.model_validate(prd).idea == state.idea

    reloaded = artifact_store.load_state("run_x")
    assert reloaded.idea == state.idea and reloaded.prd is not None
    assert "run_x" in artifact_store.list_runs()


def test_missing_run_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("APS_ARTIFACT_DIR", str(tmp_path))
    assert artifact_store.load_meta("nope") is None
    assert artifact_store.load_artifact("nope", "prd") is None
    assert artifact_store.load_state("nope") is None
