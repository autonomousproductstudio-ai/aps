"""Assemble the /v1 sub-application: routers + CORS + envelope error handlers.

Mounted by aps.api.main via `app.mount("/v1", v1_app)`. Because it is a separate FastAPI
instance, its exception handlers (which produce the {success:false,error} envelope) and CORS
are fully scoped to /v1 and never touch the lean root API.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aps.api.v1 import auth, routes_history, routes_runs, routes_system, ws
from aps.api.v1.envelope import register_error_handlers
from aps.config.settings import get_settings


def build_app() -> FastAPI:
    app = FastAPI(title="APS Frontend Data Contract (v1)", docs_url="/docs")

    # CORS: the rich frontend dev/prod origins (§0.6) plus whatever the lean API allows.
    origins = {o.strip() for o in get_settings().cors_origins.split(",") if o.strip()}
    origins.update({"http://localhost:3000", "https://app.aps.io"})
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    register_error_handlers(app)

    app.include_router(auth.router, tags=["auth"])
    app.include_router(routes_runs.router, tags=["runs"])
    app.include_router(routes_history.router, tags=["history"])
    app.include_router(routes_system.router, tags=["system"])
    app.include_router(ws.router)
    return app


v1_app = build_app()
