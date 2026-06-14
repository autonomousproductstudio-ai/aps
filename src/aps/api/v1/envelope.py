"""Response envelope + error model for the /v1 contract (docs/backenddatacontract.md §0.4–0.5).

Every success is wrapped `{success:true, data, meta:{requestId,timestamp,...}}`; every error is
`{success:false, error:{code,message,field}, meta:{...}}`. `requestId` is a deterministic
per-process counter (not random) so tests can assert it; `timestamp` comes from a single helper
that tests can monkeypatch. List endpoints add `total/page/pageSize` to meta.
"""
from __future__ import annotations

import itertools
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

# Deterministic, monotonic request ids (avoids Math.random/uuid nondeterminism in tests).
_REQ_COUNTER = itertools.count(1)


def _request_id() -> str:
    return f"req_{next(_REQ_COUNTER):06d}"


def _timestamp() -> str:
    """ISO-8601 UTC. Isolated so a test can monkeypatch a fixed clock."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def meta(**extra: Any) -> dict:
    return {"requestId": _request_id(), "timestamp": _timestamp(), **extra}


def ok(data: Any, **extra_meta: Any) -> dict:
    """Wrap a success payload. `extra_meta` carries list pagination (total/page/pageSize)."""
    return {"success": True, "data": data, "meta": meta(**extra_meta)}


def page_meta(items: list, page: int = 1, page_size: int = 50) -> dict:
    return {"total": len(items), "page": page, "pageSize": page_size}


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
# code → default HTTP status (docs §12.1)
ERROR_STATUS = {
    "INVALID_CREDENTIALS": 401,
    "EMAIL_ALREADY_EXISTS": 422,
    "INVALID_RESET_TOKEN": 400,
    "VALIDATION_ERROR": 422,
    "RUN_NOT_FOUND": 404,
    "ARTIFACT_NOT_FOUND": 404,
    "UNAUTHORIZED": 401,
    "RATE_LIMITED": 429,
    "SERVER_ERROR": 500,
}


class V1Error(Exception):
    """Raised inside /v1 routes; rendered into the error envelope by the registered handler."""

    def __init__(self, code: str, message: str, *, field: str | None = None,
                 status: int | None = None, fields: list[dict] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
        self.fields = fields
        self.status = status or ERROR_STATUS.get(code, 400)


def error_body(code: str, message: str, *, field: str | None = None,
               fields: list[dict] | None = None) -> dict:
    err: dict[str, Any] = {"code": code, "message": message, "field": field}
    if fields is not None:
        err["fields"] = fields
    return {"success": False, "error": err, "meta": meta()}


def register_error_handlers(app) -> None:
    """Attach the three handlers that keep every /v1 error in the contract's envelope."""
    from fastapi import HTTPException
    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(V1Error)
    async def _v1(_: Request, exc: V1Error):
        return JSONResponse(
            status_code=exc.status,
            content=error_body(exc.code, exc.message, field=exc.field, fields=exc.fields),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        fields = [{"field": ".".join(str(p) for p in e.get("loc", [])[1:]) or "body",
                   "message": e.get("msg", "Invalid value.")} for e in exc.errors()]
        return JSONResponse(
            status_code=422,
            content=error_body("VALIDATION_ERROR", "Please correct the highlighted fields.",
                               field=None, fields=fields),
        )

    @app.exception_handler(HTTPException)
    async def _http(_: Request, exc: HTTPException):
        code = {401: "UNAUTHORIZED", 403: "UNAUTHORIZED", 404: "RUN_NOT_FOUND",
                429: "RATE_LIMITED"}.get(exc.status_code, "SERVER_ERROR")
        msg = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(status_code=exc.status_code, content=error_body(code, msg))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        return JSONResponse(status_code=500,
                            content=error_body("SERVER_ERROR", "Something went wrong."))
