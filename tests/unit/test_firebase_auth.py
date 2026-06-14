"""The /v1 API accepts Firebase ID tokens (Google/GitHub/email login via the frontend's Firebase
SDK) in addition to the built-in demo JWT — the 'proper fix' for the frontend↔backend token
mismatch that made the Start button 401. Network verification is gated on APS_FIREBASE_PROJECT_ID
(off by default → suite stays hermetic) and mocked here for the accept path.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from aps.api.main import app
from aps.api.v1 import firebase_auth, auth as auth_mod

client = TestClient(app)


def _demo_token() -> str:
    return client.post("/v1/auth/login",
                       json={"email": "operator@aps.io", "password": "demo1234"}).json()["data"]["token"]


def test_firebase_disabled_by_default_is_hermetic(monkeypatch):
    # No APS_FIREBASE_PROJECT_ID → verify() returns None immediately (no network, no google-auth).
    monkeypatch.delenv("APS_FIREBASE_PROJECT_ID", raising=False)
    assert firebase_auth.configured() is False
    assert firebase_auth.verify("a.b.c") is None


def test_non_firebase_token_returns_none_even_when_configured(monkeypatch):
    monkeypatch.setenv("APS_FIREBASE_PROJECT_ID", "demo-proj")
    # the demo HMAC JWT is not a Firebase token → google verify raises/returns None → None
    assert firebase_auth.verify(_demo_token()) is None
    assert firebase_auth.verify("not-a-jwt") is None


def test_demo_jwt_still_authenticates():
    r = client.get("/v1/system/status", headers={"Authorization": f"Bearer {_demo_token()}"})
    assert r.status_code == 200


def test_firebase_token_is_accepted(monkeypatch):
    # simulate a verified Firebase user (Google login) — current_user must accept it + provision.
    fake = {"id": "fb_uid_1", "name": "Ada", "email": "ada@gmail.com", "avatarUrl": "",
            "role": "Founder / CEO", "password_hash": ""}
    monkeypatch.setattr(firebase_auth, "verify", lambda tok: fake if tok == "FIREBASE_TOK" else None)
    r = client.get("/v1/system/status", headers={"Authorization": "Bearer FIREBASE_TOK"})
    assert r.status_code == 200
    assert auth_mod._USERS.get("ada@gmail.com", {}).get("id") == "fb_uid_1"   # auto-provisioned


def test_bad_token_still_401(monkeypatch):
    monkeypatch.setattr(firebase_auth, "verify", lambda tok: None)
    r = client.get("/v1/system/status", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


def test_ws_accepts_firebase_token(monkeypatch):
    from aps.api.v1 import ws
    monkeypatch.setattr(ws.firebase_auth, "verify", lambda tok: {"email": "x@y.z"} if tok == "FB" else None)

    class _WS:
        query_params = {"token": "FB"}
    assert ws._authed(_WS()) is True
    _WS.query_params = {"token": "nope"}
    assert ws._authed(_WS()) is False
