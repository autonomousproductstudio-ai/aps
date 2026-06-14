"""Frontend-wiring endpoints: /health, /models, /providers, /stats, /runs list, and the
per-run model override plumbing. Hermetic — no live LLM calls, no model construction (which
would need a key/provider package CI lacks); we assert plumbing, not provider I/O.
"""
from __future__ import annotations

import time
import contextvars
from concurrent.futures import ThreadPoolExecutor

import pytest
from starlette.testclient import TestClient

from aps.api.main import app
from aps.config.settings import get_settings, set_run_model, reset_run_model, run_model

KEY = get_settings().api_key
HDR = {"X-APS-Key": KEY}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _wait(client, rid, tries=100):
    for _ in range(tries):
        if client.get(f"/runs/{rid}", headers=HDR).json().get("status") in (
                "complete", "degraded", "failed"):
            return
        time.sleep(0.05)
    raise AssertionError("run did not finish")


# ── read-only metric/catalog endpoints ─────────────────────────────────────
def test_health_no_auth(client):
    b = client.get("/health").json()
    assert b["status"] == "ok" and isinstance(b["uptime_seconds"], (int, float))


def test_models_catalog(client):
    b = client.get("/models", headers=HDR).json()
    ids = [p["id"] for p in b["providers"]]
    assert "nim" in ids and "gemini" in ids
    nim = next(p for p in b["providers"] if p["id"] == "nim")
    assert any(m["id"] == "nvidia/nvidia-nemotron-nano-9b-v2" for m in nim["models"])
    assert b["default"]["provider"] and b["default"]["model"]


def test_providers_requires_auth_and_shape(client):
    assert client.get("/providers").status_code == 401
    b = client.get("/providers", headers=HDR).json()
    assert b["resolved"] and all("enabled" in r for r in b["providers"])


def test_stats_shape(client):
    assert client.get("/stats").status_code == 401
    b = client.get("/stats", headers=HDR).json()
    for k in ("total_runs", "by_status", "in_flight", "total_evidence",
              "total_tool_calls", "uptime_seconds"):
        assert k in b


def test_runs_list_includes_started_run(client):
    rid = client.post("/runs", json={"idea": "x"}, headers=HDR).json()["run_id"]
    _wait(client, rid)
    listing = client.get("/runs", headers=HDR).json()
    assert listing["count"] >= 1
    assert any(r["run_id"] == rid for r in listing["runs"])


def test_post_run_echoes_model_choice(client):
    r = client.post("/runs", json={"idea": "x",
                                   "config": {"provider": "nim", "model": "openai/gpt-oss-120b"}},
                    headers=HDR)
    assert r.status_code == 202
    body = r.json()
    assert body["provider"] == "nim" and body["model"] == "openai/gpt-oss-120b"
    _wait(client, body["run_id"])


# ── per-run override plumbing (the contextvar + fan-out mechanism) ──────────
def test_run_model_contextvar_roundtrip():
    assert run_model() is None
    tok = set_run_model("nim", "openai/gpt-oss-120b")
    assert run_model() == {"provider": "nim", "model": "openai/gpt-oss-120b"}
    reset_run_model(tok)
    assert run_model() is None


def test_override_propagates_into_threadpool_workers():
    """Mirrors the supervisor: copy the context once per unit on this thread, .run() each in a
    worker — the per-run override must be visible inside the worker (ThreadPoolExecutor does not
    inherit context on its own)."""
    tok = set_run_model("nim", "qwen/qwen3.5-122b-a10b")
    try:
        ctxs = [contextvars.copy_context() for _ in range(3)]
        with ThreadPoolExecutor(max_workers=3) as pool:
            seen = list(pool.map(lambda c: c.run(lambda: (run_model() or {}).get("model")), ctxs))
        assert seen == ["qwen/qwen3.5-122b-a10b"] * 3
    finally:
        reset_run_model(tok)
    assert run_model() is None
