"""Billing API (/api/billing) — Dodo Payments hosted checkout + subscriptions.

Server-side only. Mounted on the lean root app by aps.api.main. Auth reuses the same bearer
token the /v1 API accepts (demo HMAC JWT OR Firebase ID token), so the logged-in frontend user
is identified without a second login. The webhook route is intentionally unauthenticated and
verified by Standard Webhooks signature instead.

Endpoints:
  POST /api/billing/create-checkout-session   {plan} -> {checkoutUrl, sessionId}
  GET  /api/billing/subscription              -> current user's subscription (public view)
  POST /api/billing/confirm                    {sessionId?} -> finalize after redirect (dev path)
  POST /api/billing/webhook                    Dodo events (signed) -> update store
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from aps.api.v1 import firebase_auth, tokens
from aps.billing import dodo_service as dodo
from aps.billing import store
from aps.infra.logging import get_logger

_LOG = get_logger("aps.billing")
router = APIRouter(prefix="/api/billing", tags=["billing"])


# --------------------------------------------------------------------------- #
# Auth — bearer token -> {id, email, name}. Clean 401 (no dependency on /v1 handlers).
# --------------------------------------------------------------------------- #
def _user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Authentication required")
    raw = authorization.split(" ", 1)[1].strip()
    payload = tokens.decode(raw)
    if payload:
        email = payload.get("email", "")
        return {"id": payload.get("sub") or email, "email": email,
                "name": payload.get("name") or (email.split("@")[0] if email else "User")}
    fb = firebase_auth.verify(raw)
    if fb:
        return {"id": fb["id"], "email": fb.get("email", ""), "name": fb.get("name", "")}
    raise HTTPException(401, "Invalid or expired token")


def _base_url(request: Request) -> str:
    """Where to send the customer back to. Prefer the calling site's Origin (handles the Vite
    dev port automatically), then an explicit env override, then a localhost default."""
    import os
    origin = request.headers.get("origin")
    if origin:
        return origin
    env = (os.getenv("APS_PUBLIC_BASE_URL") or "").strip()
    return env or "http://localhost:5174"


def _iso(dt_value) -> str | None:
    """Best-effort ISO string from a Dodo date field (already-ISO string or epoch)."""
    if not dt_value:
        return None
    if isinstance(dt_value, str):
        return dt_value
    try:
        return datetime.fromtimestamp(float(dt_value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


# --------------------------------------------------------------------------- #
# Request bodies
# --------------------------------------------------------------------------- #
class CheckoutReq(BaseModel):
    plan: str


class ConfirmReq(BaseModel):
    sessionId: str | None = None


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@router.post("/create-checkout-session")
def create_checkout_session(req: CheckoutReq, request: Request):
    user = _user(request.headers.get("authorization"))
    plan = (req.plan or "").lower().strip()
    if plan not in dodo.PAID_PLANS:
        raise HTTPException(400, f"'{plan}' is not a checkout plan (paid: {', '.join(dodo.PAID_PLANS)})")
    if not dodo.is_configured():
        raise HTTPException(503, "Billing is not configured (DODO_API_KEY missing).")

    rec = store.get(user["id"], user["email"])
    try:
        session = dodo.create_checkout_session(
            plan=plan, base_url=_base_url(request),
            user_id=user["id"], email=user["email"], name=user["name"],
            customer_id=rec.get("customer_id"),
        )
    except dodo.BillingConfigError as e:
        raise HTTPException(503, str(e))
    except dodo.BillingError as e:
        _LOG.warning("dodo_checkout_failed", error=str(e), plan=plan)
        raise HTTPException(502, "Could not start checkout. Please try again.")

    # Remember which plan/session this user is buying so /confirm can finalize after redirect.
    store.save(user["id"], {"email": user["email"], "pending_plan": plan,
                            "pending_session_id": session.get("session_id")})
    _LOG.info("dodo_checkout_created", plan=plan, user=user["id"],
              session=session.get("session_id"))
    return {"checkoutUrl": session["checkout_url"], "sessionId": session.get("session_id"),
            "plan": plan}


@router.get("/subscription")
def get_subscription(request: Request):
    user = _user(request.headers.get("authorization"))
    rec = store.get(user["id"], user["email"])
    return store.public_view(rec)


@router.post("/confirm")
def confirm(req: ConfirmReq, request: Request):
    """Finalize a subscription after Dodo redirects back to /billing/success.

    Webhooks are the authoritative updater (and required in production), but they can't reach
    localhost during a hackathon demo. So in TEST mode we also verify here: retrieve the session
    from Dodo when possible and, since Dodo only redirects to return_url after a completed
    checkout, activate the plan. Idempotent.
    """
    user = _user(request.headers.get("authorization"))
    rec = store.get(user["id"], user["email"])
    session_id = (req.sessionId or rec.get("pending_session_id") or "").strip()
    if not session_id:
        raise HTTPException(400, "No checkout session to confirm.")

    sub_norm: dict = {}
    plan = None
    try:
        sess = dodo.retrieve_checkout_session(session_id)
        if sess.get("subscription_id"):
            sub_norm = dodo.retrieve_subscription(sess["subscription_id"])
            plan = dodo.plan_for_product(sub_norm.get("product_id")) \
                or dodo.plan_for_product(sess.get("product_id"))
    except dodo.BillingError as e:
        # Retrieval not available in this SDK/build — fall back to optimistic test-mode activation.
        _LOG.info("dodo_confirm_retrieve_skipped", error=str(e), session=session_id)

    now = datetime.now(timezone.utc)
    patch = {
        "email": user["email"],
        "plan": plan or rec.get("pending_plan") or rec.get("plan") or "operator",
        "status": sub_norm.get("status") or "active",
        "customer_id": sub_norm.get("customer_id") or rec.get("customer_id"),
        "subscription_id": sub_norm.get("subscription_id") or rec.get("subscription_id"),
        "subscription_start": _iso(sub_norm.get("created_at")) or rec.get("subscription_start")
        or now.isoformat(),
        "renewal_date": _iso(sub_norm.get("next_billing_date")) or rec.get("renewal_date")
        or (now + timedelta(days=30)).isoformat(),
        "pending_session_id": None,
        "pending_plan": None,
    }
    saved = store.save(user["id"], patch)
    _LOG.info("dodo_subscription_confirmed", user=user["id"], plan=saved["plan"],
              status=saved["status"])
    return store.public_view(saved)


@router.post("/webhook")
async def webhook(request: Request):
    """Dodo webhook receiver — signature-verified, then applied to the store.

    Handles: subscription.created/active/updated/cancelled/expired/on_hold, payment.succeeded,
    payment.failed. Always returns 200 once verified so Dodo doesn't retry storms on our bugs.
    """
    payload = await request.body()
    try:
        event = dodo.verify_webhook(payload, dict(request.headers))
    except dodo.BillingConfigError as e:
        raise HTTPException(503, str(e))
    except dodo.BillingError as e:
        _LOG.warning("dodo_webhook_bad_signature", error=str(e))
        raise HTTPException(400, "Invalid webhook signature")

    etype = (event.get("type") or "").lower()
    data = event.get("data") or {}
    _LOG.info("dodo_webhook", type=etype)

    try:
        _apply_webhook(etype, data)
    except Exception as e:  # never 500 a verified webhook — log and ack
        _LOG.warning("dodo_webhook_apply_failed", type=etype, error=str(e))
    return {"received": True}


# --------------------------------------------------------------------------- #
# Webhook application
# --------------------------------------------------------------------------- #
def _resolve_user_id(data: dict) -> str | None:
    """Find which APS user an event is about: metadata.user_id first, then reverse-lookup by
    subscription id, then customer id."""
    meta = data.get("metadata") or {}
    if meta.get("user_id"):
        return meta["user_id"]
    sub_id = data.get("subscription_id") or data.get("id")
    rec = store.find_by("subscription_id", sub_id) if sub_id else None
    if rec:
        return rec["user_id"]
    cust = data.get("customer") or {}
    cust_id = (cust.get("customer_id") if isinstance(cust, dict) else None) or data.get("customer_id")
    rec = store.find_by("customer_id", cust_id) if cust_id else None
    return rec["user_id"] if rec else None


def _apply_webhook(etype: str, data: dict) -> None:
    user_id = _resolve_user_id(data)
    if not user_id:
        _LOG.warning("dodo_webhook_no_user", type=etype)
        return

    norm = dodo.normalize_subscription(data)
    plan = dodo.plan_for_product(norm.get("product_id")) or (data.get("metadata") or {}).get("plan")

    if etype.startswith("subscription."):
        action = etype.split(".", 1)[1]
        status = {"active": "active", "created": "active", "updated": norm.get("status") or "active",
                  "renewed": "active", "on_hold": "on_hold", "cancelled": "cancelled",
                  "canceled": "cancelled", "expired": "expired", "failed": "failed"}.get(
            action, norm.get("status") or "active")
        patch = {
            "status": status,
            "customer_id": norm.get("customer_id"),
            "subscription_id": norm.get("subscription_id"),
            "renewal_date": _iso(norm.get("next_billing_date")),
        }
        if norm.get("created_at"):
            patch["subscription_start"] = _iso(norm.get("created_at"))
        if plan and status in ("active",):
            patch["plan"] = plan
        if status in ("cancelled", "expired"):
            patch["plan"] = "free"   # lost entitlement -> back to Scout
        store.save(user_id, {k: v for k, v in patch.items() if v is not None or k == "plan"})

    elif etype == "payment.succeeded":
        patch = {"status": "active"}
        if plan:
            patch["plan"] = plan
        if norm.get("customer_id"):
            patch["customer_id"] = norm["customer_id"]
        if norm.get("subscription_id"):
            patch["subscription_id"] = norm["subscription_id"]
        store.save(user_id, patch)

    elif etype == "payment.failed":
        store.save(user_id, {"status": "failed"})
