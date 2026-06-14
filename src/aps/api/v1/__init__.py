"""aps.api.v1 — the rich "mission control" Frontend Data Contract (docs/backenddatacontract.md).

A self-contained FastAPI **sub-application** mounted at /v1 by aps.api.main. It is deliberately
isolated from the lean root API (X-APS-Key + SSE + raw JSON): /v1 speaks the frontend contract's
{success,data,meta} envelope, JWT Bearer auth, and a WebSocket live stream. Real values are
derived from StudioState wherever they exist; everything the backend has no source for
(per-model cost/latency, memory layers, observability, graph layouts) is DETERMINISTIC mock
data so the contract's "never omit a key" rule holds and unit tests stay hermetic.

Import `v1_app` and mount it; nothing here mutates the root API's behavior.
"""
from aps.api.v1.app import v1_app

__all__ = ["v1_app"]
