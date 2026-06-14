"""Health/ping lane (plan 2.6): cheap dependency-free liveness, separate from /system/health."""
from __future__ import annotations

from fastapi.testclient import TestClient

from aps.api.main import app

client = TestClient(app)


def test_v1_ping_needs_no_auth_and_is_trivial():
    r = client.get("/v1/system/ping")
    assert r.status_code == 200
    assert r.json()["data"] == {"ok": True}


def test_root_health_is_dependency_free():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
