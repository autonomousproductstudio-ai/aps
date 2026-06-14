"""Authentication API (docs/backenddatacontract.md §2) — in-memory, mock-grade.

Seeded with a demo operator so the frontend can log in immediately:
    email=operator@aps.io  password=demo1234
Signup adds users to the same in-process dict (lost on restart, by design). Tokens are the
stdlib HMAC JWTs from tokens.py. `current_user` is the dependency every protected /v1 route uses.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Header
from pydantic import BaseModel

from aps.api.v1 import tokens, firebase_auth
from aps.api.v1.envelope import V1Error, ok

router = APIRouter()

VALID_ROLES = (
    "Founder / CEO", "Product Manager", "Engineering Lead", "Design Lead",
    "Researcher", "Investor", "Other",
)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TOKEN_TTL = 86400  # seconds (advertised via expiresIn)

# email → {id, name, email, password_hash, role, avatarUrl}
_USERS: dict[str, dict] = {}
_RESET_TOKENS: dict[str, str] = {}  # reset-token → email
_user_seq = 0


def _next_user_id() -> str:
    global _user_seq
    _user_seq += 1
    return f"usr_{_user_seq:06d}"


def _seed() -> None:
    if "operator@aps.io" not in _USERS:
        _USERS["operator@aps.io"] = {
            "id": "usr_000001", "name": "Rajat Nagda", "email": "operator@aps.io",
            "password_hash": tokens.hash_password("demo1234"), "role": "Founder / CEO",
            "avatarUrl": "https://cdn.aps.io/avatars/usr_000001.jpg",
        }


_seed()


def _public(user: dict) -> dict:
    return {k: user[k] for k in ("id", "name", "email", "avatarUrl", "role")}


def _issue(user: dict) -> dict:
    token = tokens.encode({"sub": user["id"], "email": user["email"], "role": user["role"]})
    return {"token": token, "expiresIn": _TOKEN_TTL, "user": _public(user)}


# --------------------------------------------------------------------------- #
# Dependency
# --------------------------------------------------------------------------- #
def current_user(authorization: str | None = Header(default=None)) -> dict:
    """Parse `Authorization: Bearer <jwt>` → the user dict, or 401 in the error envelope.

    Accepts EITHER the built-in demo JWT (tokens.py) OR a Firebase ID token (when
    APS_FIREBASE_PROJECT_ID is set) — so social/email logins via the frontend's Firebase SDK
    authenticate against the same API.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise V1Error("UNAUTHORIZED", "Authentication required.")
    raw = authorization.split(" ", 1)[1].strip()
    payload = tokens.decode(raw)
    if payload:
        user = _USERS.get(payload.get("email", ""))
        if user:
            return user
    # Fall back to a Firebase ID token (no-op unless APS_FIREBASE_PROJECT_ID is configured).
    fb = firebase_auth.verify(raw)
    if fb:
        return _USERS.setdefault(fb["email"], fb)   # auto-provision the Firebase user once
    raise V1Error("UNAUTHORIZED", "Token missing or expired.")


# --------------------------------------------------------------------------- #
# Request bodies
# --------------------------------------------------------------------------- #
class LoginReq(BaseModel):
    email: str
    password: str
    remember: bool = False


class SignupReq(BaseModel):
    name: str
    email: str
    password: str
    role: str


class ForgotReq(BaseModel):
    email: str


class ResetReq(BaseModel):
    token: str
    password: str


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@router.post("/auth/login")
def login(req: LoginReq):
    user = _USERS.get(req.email.strip().lower()) or _USERS.get(req.email.strip())
    if not user or not tokens.verify_password(req.password, user["password_hash"]):
        raise V1Error("INVALID_CREDENTIALS", "Email or password is incorrect.")
    return ok(_issue(user))


@router.post("/auth/signup", status_code=201)
def signup(req: SignupReq):
    name = req.name.strip()
    email = req.email.strip()
    if len(name) < 2 or len(name) > 80:
        raise V1Error("VALIDATION_ERROR", "Name must be 2–80 characters.", field="name")
    if not _EMAIL_RE.match(email):
        raise V1Error("VALIDATION_ERROR", "Invalid email format.", field="email")
    if len(req.password) < 8:
        raise V1Error("VALIDATION_ERROR", "Password must be at least 8 characters.",
                      field="password")
    if req.role not in VALID_ROLES:
        raise V1Error("VALIDATION_ERROR", "Pick a valid role.", field="role")
    if email in _USERS:
        raise V1Error("EMAIL_ALREADY_EXISTS", "An account with this email already exists.",
                      field="email")
    user = {
        "id": _next_user_id(), "name": name, "email": email,
        "password_hash": tokens.hash_password(req.password), "role": req.role,
        "avatarUrl": "https://cdn.aps.io/avatars/default.jpg",
    }
    _USERS[email] = user
    return ok(_issue(user))


@router.post("/auth/forgot-password")
def forgot_password(req: ForgotReq):
    # Always 200 (don't leak which emails exist). Mint a reset token only if the user is real.
    email = req.email.strip()
    if email in _USERS:
        _RESET_TOKENS[tokens.encode({"reset": email})] = email
    return ok({"message": "Recovery link transmitted", "expiresInMinutes": 15})


@router.post("/auth/reset-password")
def reset_password(req: ResetReq):
    email = _RESET_TOKENS.get(req.token)
    payload = tokens.decode(req.token)
    if not email or not payload or payload.get("reset") != email:
        raise V1Error("INVALID_RESET_TOKEN", "This reset link has expired or is invalid.")
    if len(req.password) < 8:
        raise V1Error("VALIDATION_ERROR", "Password must be at least 8 characters.",
                      field="password")
    _USERS[email]["password_hash"] = tokens.hash_password(req.password)
    _RESET_TOKENS.pop(req.token, None)
    return ok({"message": "Password updated successfully."})


# Used by the auth-page telemetry panel (kept here so the seed stays one place).
def user_count() -> int:
    return len(_USERS)
