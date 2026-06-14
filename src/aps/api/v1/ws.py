"""WebSocket live stream (docs §8). Token via query param (WS can't set headers).

Two endpoints:
  /ws/runs/{alias}/stream  — run-scoped: seed events, then metric_tick + new EventBus events
                             reshaped to StreamEvents, plus ping keepalive.
  /ws/runs/global/stream   — global terminal log feed for the Pipeline page.

Frames are JSON envelopes {type, payload} (§8.2). Close codes per §8.8. All "live" values are
deterministic (mockdata.jitter) so behavior is reproducible. Sends are paced but the FIRST
seed + metric frames go out immediately so a client (and tests) see data at once.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from aps.api.v1 import engine, mappers, mockdata
from aps.api.v1 import tokens, firebase_auth

router = APIRouter()

_TICK_SECONDS = 1.0   # internal loop granularity; frames pace themselves off counters


def _authed(websocket: WebSocket) -> bool:
    token = websocket.query_params.get("token", "")
    if not token:
        return False
    # Accept the demo JWT or a Firebase ID token (same dual-auth as the HTTP current_user).
    return bool(tokens.decode(token)) or bool(firebase_auth.verify(token))


async def _send(ws: WebSocket, type_: str, payload) -> None:
    await ws.send_json({"type": type_, "payload": payload})


@router.websocket("/ws/runs/global/stream")
async def global_stream(websocket: WebSocket):
    await websocket.accept()
    if not _authed(websocket):
        await websocket.close(code=1008)
        return
    try:
        i = 0
        while websocket.application_state == WebSocketState.CONNECTED:
            i += 1
            await _send(websocket, "terminal_log", {
                "timestamp": f"[14:{(i // 60) % 60:02d}:{i % 60:02d}]",
                "runId": f"RUN_{mockdata.jitter(f'gl:{i}', 1, 999):03d}",
                "message": _global_message(i),
                "highlight": i % 4 == 0,
            })
            if i % 30 == 0:
                await _send(websocket, "ping", None)
            await asyncio.sleep(_TICK_SECONDS * 3)
    except WebSocketDisconnect:
        pass


@router.websocket("/ws/runs/{alias}/stream")
async def run_stream(websocket: WebSocket, alias: str):
    await websocket.accept()
    if not _authed(websocket):
        await websocket.close(code=1008)
        return
    # Run-not-found → contract close code 4004.
    from aps.api.v1 import idmap
    if not idmap.known_alias(alias):
        await websocket.close(code=4004)
        return

    try:
        # 1) immediate seed: replay existing events as `event` frames. Read the history ONCE
        #    and derive the cursor from that same snapshot — this closes the double-read race
        #    (events arriving between the two reads were silently skipped before).
        hist = engine.bus_history(alias)
        for ev in mappers.stream_events(hist, limit=50):
            await _send(websocket, "event", ev)
        sent = len(hist)

        # 2) immediate first metric tick so the header populates at once.
        i = 0
        await _send(websocket, "metric_tick", _metric_payload(alias, i))

        # 3) live loop: PUSH new events (plan 1.3) — block off-loop on the bus condition until
        #    events land or a 1 s liveness tick; metric_tick/ping stay on a wall-clock cadence
        #    so they don't speed up just because events are flowing.
        loop = asyncio.get_event_loop()
        last_metric = last_ping = asyncio.get_event_loop().time()
        while websocket.application_state == WebSocketState.CONNECTED:
            new = await loop.run_in_executor(None, engine.bus_wait, alias, sent, _TICK_SECONDS)
            if new:
                for ev in mappers.stream_events(new, limit=50):
                    await _send(websocket, "event", ev)
                sent += len(new)
            now = loop.time()
            if now - last_metric >= 5.0:
                i += 1
                await _send(websocket, "metric_tick", _metric_payload(alias, i))
                last_metric = now
            if now - last_ping >= 30.0:
                await _send(websocket, "ping", None)
                last_ping = now
    except WebSocketDisconnect:
        pass


def _metric_payload(alias: str, i: int) -> dict:
    return {
        "cpuPct": mockdata.jitter(f"wscpu:{alias}:{i // 5}", 18, 46),
        "memPct": mockdata.jitter(f"wsmem:{alias}:{i // 5}", 40, 78),
        "apiUptimePct": 99,
        "tokensUsed": 200000 + i * 1200,
        "activeAgents": 1,
    }


def _global_message(i: int) -> str:
    msgs = ["Vector db sync complete.", "Evidence cluster committed.",
            "Sub-researcher spawned.", "Compression pass finished.",
            "Artifact persisted to store.", "Tool call returned 200."]
    return msgs[i % len(msgs)]
