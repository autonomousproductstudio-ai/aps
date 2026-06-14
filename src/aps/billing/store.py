"""Per-user subscription store — a tiny, durable JSON "database".

APS has no managed database (runs persist as JSON via infra.artifact_store), so subscription
state follows the same convention: one JSON file per user under APS_BILLING_DIR (default
`.billing/`). This is the database the requirements ask for — swap _root()/get/save for a real
datastore later without touching callers.

Each record holds exactly the fields the spec requires:
    user_id · customer_id · subscription_id · plan_name · billing_status · renewal_date ·
    provider_name (+ subscription_start, email, updated_at for completeness).
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.Lock()

# Free tier (Scout) is the implicit default for any user we've never charged.
FREE_PLAN = "free"
PROVIDER = "dodo"


def _root() -> Path:
    d = Path(os.getenv("APS_BILLING_DIR", ".billing"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_id(user_id: str) -> str:
    """Filesystem-safe filename for an arbitrary user id (Firebase uid or email)."""
    return hashlib.sha256(user_id.encode()).hexdigest()[:32]


def _path(user_id: str) -> Path:
    return _root() / f"{_safe_id(user_id)}.json"


def default_record(user_id: str, email: str = "") -> dict:
    return {
        "user_id": user_id,
        "email": email,
        "plan": FREE_PLAN,                 # plan_name: free | operator | command
        "status": "none",                  # billing_status: none|active|on_hold|cancelled|failed|expired
        "customer_id": None,               # Dodo customer id
        "subscription_id": None,           # Dodo subscription id
        "subscription_start": None,        # ISO-8601 (UTC)
        "renewal_date": None,              # ISO-8601 (UTC) — next billing date
        "provider": PROVIDER,              # provider_name
        "pending_session_id": None,        # last checkout session awaiting confirmation
        "pending_plan": None,              # plan the pending session is buying
        "updated_at": None,
    }


def get(user_id: str, email: str = "") -> dict:
    """Current subscription for a user; a default FREE record if none stored yet."""
    p = _path(user_id)
    if not p.exists():
        return default_record(user_id, email)
    try:
        data = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return default_record(user_id, email)
    rec = default_record(user_id, email)          # layer onto default so old files stay valid
    rec.update({k: v for k, v in data.items() if k in rec})
    return rec


def save(user_id: str, patch: dict) -> dict:
    """Merge `patch` into the user's record and persist atomically. Returns the new record."""
    with _LOCK:
        rec = get(user_id, patch.get("email", ""))
        rec.update({k: v for k, v in patch.items() if k in rec})
        rec["updated_at"] = datetime.now(timezone.utc).isoformat()
        p = _path(user_id)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(rec, indent=2))
        tmp.replace(p)
        return rec


def find_by(field: str, value: str) -> dict | None:
    """Reverse lookup (e.g. by customer_id or subscription_id) for webhook events that only
    carry a Dodo id, not our user id."""
    if not value:
        return None
    for f in _root().glob("*.json"):
        try:
            data = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if data.get(field) == value:
            return data
    return None


def public_view(rec: dict) -> dict:
    """The shape returned to the frontend — exactly the spec's DATABASE fields, plus display
    helpers. No secrets ever live in this record, so it's safe to serialize wholesale."""
    return {
        "userId": rec.get("user_id"),
        "customerId": rec.get("customer_id"),
        "subscriptionId": rec.get("subscription_id"),
        "plan": rec.get("plan") or FREE_PLAN,
        "planName": (rec.get("plan") or FREE_PLAN).upper(),
        "status": rec.get("status") or "none",
        "subscriptionStart": rec.get("subscription_start"),
        "renewalDate": rec.get("renewal_date"),
        "provider": rec.get("provider") or PROVIDER,
        "providerName": "Dodo Payments",
    }
