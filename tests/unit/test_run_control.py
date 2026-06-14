"""Concurrency / cancellation control plane (plan §2): cooperative cancel, deadline plumbing,
idempotency, and the cancel endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aps.api.main import app
from aps.api import main as m
from aps.orchestrator import cancel
from aps.orchestrator.events import EventBus
from aps.orchestrator.graph import run_sync
from aps.state.models import RunStatus

client = TestClient(app)
KEY = {"X-APS-Key": "dev-key"}


# ── cancellation primitive ────────────────────────────────────────────────────
def test_checkpoint_raises_only_when_cancelled():
    assert cancel.is_cancelled() is False          # no check installed
    tok = cancel.set_check(lambda: True)
    try:
        assert cancel.is_cancelled() is True
        with pytest.raises(cancel.RunCancelled):
            cancel.checkpoint()
    finally:
        cancel.reset(tok)
    assert cancel.is_cancelled() is False           # reset restores "never cancelled"


def test_run_cancelled_settles_into_cancelled_terminal_state():
    bus = EventBus()
    # should_cancel is already true → the run unwinds at the first stage boundary, no network.
    st = run_sync("a privacy habit tracker", bus, run_id="cx1", should_cancel=lambda: True)
    assert st.status == RunStatus.CANCELLED
    types = [e.type for e in bus.history("cx1")]
    assert "run_cancelled" in types and "run_complete" in types


# ── cancel signal store ────────────────────────────────────────────────────────
def test_cancel_run_unknown_is_false():
    assert m.cancel_run("run_does_not_exist") is False


# ── idempotency (2.4) ────────────────────────────────────────────────────────────
def test_submit_run_is_idempotent_while_in_flight(monkeypatch):
    monkeypatch.setattr(m, "_ensure_workers", lambda: None)   # don't drain → stays in-flight
    r1 = r2 = None
    try:
        r1 = m.submit_run("dedup-idea-unique-7731", None)
        r2 = m.submit_run("dedup-idea-unique-7731", None)
        assert r1["run_id"] == r2["run_id"]                   # collapsed to one run
        assert r1["status"] == RunStatus.QUEUED.value
    finally:
        # drain the parked queue item + clear state so other tests are unaffected
        while not m._RUN_QUEUE.empty():
            m._RUN_QUEUE.get_nowait()
            m._RUN_QUEUE.task_done()
        if r1:
            for store in (m._RUNS, m._BUSES, m._CANCEL):
                store.pop(r1["run_id"], None)
        m._IDEM.clear()


# ── cancel endpoints ──────────────────────────────────────────────────────────
def test_cancel_endpoint_404_for_unknown_run():
    r = client.post("/runs/run_nope42/cancel", headers=KEY)
    assert r.status_code == 404


def test_cancel_endpoint_accepts_known_run(monkeypatch):
    monkeypatch.setattr(m, "_ensure_workers", lambda: None)
    rec = None
    try:
        rec = m.submit_run("cancel-me-idea-9920", None)
        r = client.post(f"/runs/{rec['run_id']}/cancel", headers=KEY)
        assert r.status_code == 202 and r.json()["cancelling"] is True
        assert m._CANCEL[rec["run_id"]].is_set()              # cooperative flag tripped
    finally:
        while not m._RUN_QUEUE.empty():
            m._RUN_QUEUE.get_nowait()
            m._RUN_QUEUE.task_done()
        if rec:
            for store in (m._RUNS, m._BUSES, m._CANCEL):
                store.pop(rec["run_id"], None)
        m._IDEM.clear()
