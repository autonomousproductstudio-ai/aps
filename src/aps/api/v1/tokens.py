"""Dependency-free JWT + password hashing (stdlib only — no PyJWT in this project).

A compact HMAC-SHA256 token in the standard `header.payload.signature` base64url shape, signed
with a secret derived from the configured API key. Good enough for the mock /v1 auth surface;
not meant to replace a real IdP. Password hashing uses PBKDF2-HMAC-SHA256.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

from aps.config.settings import get_settings


def _secret() -> bytes:
    # Derive a stable signing key from the API key so tokens survive within a process run.
    return hashlib.sha256(("aps-v1:" + get_settings().api_key).encode("utf-8")).digest()


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def encode(payload: dict[str, Any]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    h = _b64e(json.dumps(header, separators=(",", ":")).encode())
    p = _b64e(json.dumps(payload, separators=(",", ":"), default=str).encode())
    signing_input = f"{h}.{p}".encode()
    sig = hmac.new(_secret(), signing_input, hashlib.sha256).digest()
    return f"{h}.{p}.{_b64e(sig)}"


def decode(token: str) -> dict[str, Any] | None:
    """Return the payload if the signature verifies, else None."""
    try:
        h, p, s = token.split(".")
    except ValueError:
        return None
    expected = hmac.new(_secret(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64d(s), expected):
        return None
    try:
        return json.loads(_b64d(p))
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Password hashing
# --------------------------------------------------------------------------- #
def hash_password(password: str, *, salt: bytes | None = None) -> str:
    salt = salt or hashlib.sha256(password.encode()).digest()[:16]
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return f"{_b64e(salt)}.{_b64e(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_b64, _ = stored.split(".")
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt=_b64d(salt_b64)), stored)
