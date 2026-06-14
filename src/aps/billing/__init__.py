"""Billing subsystem — Dodo Payments hosted checkout (test/sandbox mode) for APS.

Kept fully isolated from the orchestrator/agents: a small JSON file store for per-user
subscription state (store.py) and a thin Dodo Payments SDK wrapper (dodo_service.py). The
FastAPI surface lives in aps.api.billing and mounts at /api/billing.
"""
