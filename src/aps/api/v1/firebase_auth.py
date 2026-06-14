"""Verify Firebase ID tokens so Firebase-authenticated users (Google / GitHub / email via the
frontend's Firebase SDK) are accepted by the /v1 API — alongside the built-in demo JWT (tokens.py).

Gated on APS_FIREBASE_PROJECT_ID: when it's unset (e.g. under pytest, or when Firebase isn't
configured) NO Firebase verification is attempted, so the test suite stays hermetic/offline and the
demo-JWT path is unaffected. Verification uses google-auth (already a dependency): it checks
Google's public RS256 signature + the audience (the Firebase project id) + issuer/expiry. No
service-account JSON is required — only the project id, which matches the frontend's
VITE_FIREBASE_PROJECT_ID.
"""
from __future__ import annotations

import os


def project_id() -> str:
    return (os.getenv("APS_FIREBASE_PROJECT_ID") or "").strip()


def configured() -> bool:
    return bool(project_id())


def verify(token: str) -> dict | None:
    """A valid Firebase ID token → a user dict; else None (not configured / invalid / not Firebase).

    Never raises — a non-Firebase token (e.g. the demo HMAC JWT) just returns None so the caller
    falls through. The cert fetch + signature check are handled by google-auth and cached.
    """
    proj = project_id()
    if not proj or not token or token.count(".") != 2:
        return None
    try:
        from google.auth.transport import requests as g_requests
        from google.oauth2 import id_token as gid
        claims = gid.verify_firebase_token(token, g_requests.Request(), audience=proj)
    except Exception:
        return None
    if not claims:
        return None
    uid = claims.get("user_id") or claims.get("sub") or ""
    email = (claims.get("email") or "").strip().lower()
    if not (uid or email):
        return None
    return {
        "id": uid or email,
        "name": claims.get("name") or (email.split("@")[0] if email else "User"),
        "email": email or f"{uid}@firebase.local",
        "avatarUrl": claims.get("picture", ""),
        "role": "Founder / CEO",          # default role for a Firebase-authenticated operator
        "password_hash": "",              # Firebase owns the credential; no local password
    }
