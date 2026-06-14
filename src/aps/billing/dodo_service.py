"""Thin wrapper around the Dodo Payments SDK — the only module that talks to Dodo.

Design:
  * Server-side only. Secrets (DODO_API_KEY, DODO_WEBHOOK_SECRET) are read from the environment
    here and never returned to the client.
  * Environment-based config: DODO_ENVIRONMENT=sandbox|test|test_mode -> Dodo "test_mode"
    (the only mode this integration uses); anything else -> "live_mode".
  * Env validation: missing/blank required vars raise BillingConfigError, which the API layer
    turns into a clean 503 instead of a 500 stack trace.
  * Resilient to SDK response shape: every Dodo object is normalized via _to_dict so we read
    fields off plain dicts regardless of pydantic model version.

Docs: https://docs.dodopayments.com  ·  SDK: https://github.com/dodopayments/dodopayments-python
"""
from __future__ import annotations

import os
from typing import Any

# Plan id (used across the app / frontend) -> the env var holding its Dodo product id.
PLAN_PRODUCT_ENV: dict[str, str] = {
    "operator": "DODO_OPERATOR_PRODUCT_ID",
    "command": "DODO_COMMAND_PRODUCT_ID",
}
# Display price (USD/mo) — informational only; the real amount lives on the Dodo product.
PLAN_PRICE_USD: dict[str, int] = {"operator": 29, "command": 99}

PAID_PLANS = tuple(PLAN_PRODUCT_ENV.keys())


class BillingConfigError(RuntimeError):
    """Dodo is not configured (missing key/product id). API layer -> 503."""


class BillingError(RuntimeError):
    """A Dodo API call failed at runtime. API layer -> 502."""


# --------------------------------------------------------------------------- #
# Configuration / validation
# --------------------------------------------------------------------------- #
def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def dodo_environment() -> str:
    """Map DODO_ENVIRONMENT to the SDK's value. This integration is test-mode only."""
    raw = _env("DODO_ENVIRONMENT").lower() or "sandbox"
    return "live_mode" if raw in ("live", "live_mode", "production", "prod") else "test_mode"


def is_configured() -> bool:
    """True when at least the API key is present (the minimum to create a checkout)."""
    return bool(_env("DODO_API_KEY"))


def product_id_for(plan: str) -> str:
    env_name = PLAN_PRODUCT_ENV.get(plan)
    if not env_name:
        raise BillingConfigError(f"'{plan}' is not a paid plan")
    pid = _env(env_name)
    if not pid:
        raise BillingConfigError(f"{env_name} is not set — cannot create checkout for '{plan}'")
    return pid


def plan_for_product(product_id: str | None) -> str | None:
    """Reverse map a Dodo product id back to our plan id (used by webhooks)."""
    if not product_id:
        return None
    for plan, env_name in PLAN_PRODUCT_ENV.items():
        if _env(env_name) and _env(env_name) == product_id:
            return plan
    return None


def _require_api_key() -> str:
    key = _env("DODO_API_KEY")
    if not key:
        raise BillingConfigError(
            "DODO_API_KEY is not set. Add it to the backend .env (test-mode key)."
        )
    return key


# --------------------------------------------------------------------------- #
# SDK client
# --------------------------------------------------------------------------- #
def _client():
    key = _require_api_key()
    try:
        from dodopayments import DodoPayments
    except ImportError as e:  # pragma: no cover - dependency guard
        raise BillingConfigError(
            "The 'dodopayments' package is not installed. Run: pip install dodopayments"
        ) from e
    return DodoPayments(bearer_token=key, environment=dodo_environment())


def _to_dict(obj: Any) -> dict:
    """Normalize any SDK response (pydantic model / object / dict) to a plain dict."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    for attr in ("model_dump", "to_dict", "dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return fn()
            except TypeError:
                pass
    return {k: v for k, v in vars(obj).items() if not k.startswith("_")} if hasattr(obj, "__dict__") else {}


# --------------------------------------------------------------------------- #
# Operations
# --------------------------------------------------------------------------- #
def create_checkout_session(
    *, plan: str, base_url: str, user_id: str, email: str, name: str,
    customer_id: str | None = None,
) -> dict:
    """Create a hosted Dodo checkout session for a subscription plan.

    Returns {"checkout_url": str, "session_id": str}. The customer is redirected to
    checkout_url; on completion Dodo redirects to return_url (our /billing/success).
    """
    product_id = product_id_for(plan)
    customer: dict[str, Any] = {"customer_id": customer_id} if customer_id else {
        "email": email, "name": name or (email.split("@")[0] if email else "APS User"),
    }
    # Dodo replaces {CHECKOUT_SESSION_ID} in the return_url with the real id on redirect.
    return_url = f"{base_url.rstrip('/')}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
    try:
        resp = _client().checkout_sessions.create(
            product_cart=[{"product_id": product_id, "quantity": 1}],
            customer=customer,
            return_url=return_url,
            metadata={"user_id": user_id, "plan": plan, "app": "aps"},
        )
    except BillingConfigError:
        raise
    except Exception as e:  # SDK / network / Dodo API error
        raise BillingError(f"Dodo checkout creation failed: {e}") from e
    d = _to_dict(resp)
    checkout_url = d.get("checkout_url") or d.get("url") or d.get("payment_link")
    session_id = d.get("session_id") or d.get("id")
    if not checkout_url:
        raise BillingError("Dodo did not return a checkout_url for the session")
    return {"checkout_url": checkout_url, "session_id": session_id}


def retrieve_checkout_session(session_id: str) -> dict:
    """Normalized view of a checkout session: {status, payment_status, subscription_id,
    customer_id}. Best-effort — returns {} if the SDK/endpoint can't resolve it."""
    if not session_id:
        return {}
    try:
        resp = _client().checkout_sessions.retrieve(session_id)
    except Exception as e:
        raise BillingError(f"Could not retrieve checkout session: {e}") from e
    d = _to_dict(resp)
    cust = d.get("customer") or {}
    return {
        "status": d.get("status"),
        "payment_status": d.get("payment_status") or d.get("status"),
        "subscription_id": d.get("subscription_id"),
        "customer_id": (cust.get("customer_id") if isinstance(cust, dict) else None)
        or d.get("customer_id"),
        "product_id": d.get("product_id"),
        "raw": d,
    }


def retrieve_subscription(subscription_id: str) -> dict:
    """Normalized subscription: {status, customer_id, product_id, created_at, next_billing}."""
    if not subscription_id:
        return {}
    try:
        resp = _client().subscriptions.retrieve(subscription_id)
    except Exception as e:
        raise BillingError(f"Could not retrieve subscription: {e}") from e
    return normalize_subscription(_to_dict(resp))


def normalize_subscription(d: dict) -> dict:
    """Pull the fields we persist out of a Dodo subscription dict (from retrieve or webhook)."""
    cust = d.get("customer") or {}
    return {
        "subscription_id": d.get("subscription_id") or d.get("id"),
        "status": d.get("status"),
        "customer_id": (cust.get("customer_id") if isinstance(cust, dict) else None)
        or d.get("customer_id"),
        "product_id": d.get("product_id"),
        "created_at": d.get("created_at") or d.get("subscription_start"),
        "next_billing_date": d.get("next_billing_date") or d.get("renewal_date")
        or d.get("current_period_end"),
    }


# --------------------------------------------------------------------------- #
# Webhooks — Standard Webhooks signature verification
# --------------------------------------------------------------------------- #
def verify_webhook(payload: bytes, headers: dict[str, str]) -> dict:
    """Verify a Dodo webhook (Standard Webhooks spec) and return the parsed event dict.

    Raises BillingConfigError if no secret is set, BillingError on signature mismatch.
    """
    secret = _env("DODO_WEBHOOK_SECRET")
    if not secret:
        raise BillingConfigError("DODO_WEBHOOK_SECRET is not set — cannot verify webhooks.")
    # Standard Webhooks headers (case-insensitive); normalize the three required ones.
    lower = {k.lower(): v for k, v in headers.items()}
    wh_headers = {
        "webhook-id": lower.get("webhook-id", ""),
        "webhook-signature": lower.get("webhook-signature", ""),
        "webhook-timestamp": lower.get("webhook-timestamp", ""),
    }
    try:
        from standardwebhooks import Webhook
    except ImportError as e:  # pragma: no cover - dependency guard
        raise BillingConfigError(
            "The 'standardwebhooks' package is not installed. Run: pip install standardwebhooks"
        ) from e
    try:
        verified = Webhook(secret).verify(payload, wh_headers)
    except Exception as e:
        raise BillingError(f"Webhook signature verification failed: {e}") from e
    # verify() returns the parsed JSON payload (dict) on success.
    return verified if isinstance(verified, dict) else _to_dict(verified)
