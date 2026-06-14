"""aps.api.mock — replays tests/evals/fixtures/sample_run.json over the REAL SSE
contract so P3 builds the whole UI on Day 1 without the orchestrator (TEAM_GUIDE §6).

Run: uvicorn aps.api.mock:app --reload
"""
from __future__ import annotations
import asyncio
import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI(title="APS mock")
FIXTURE = Path(__file__).resolve().parents[3] / "tests/evals/fixtures/sample_run.json"


@app.post("/runs", status_code=202)
def start():
    return {"run_id": "run_mock1", "status": "running"}


@app.get("/runs/{run_id}/events")
def events(run_id: str):
    data = json.loads(FIXTURE.read_text()) if FIXTURE.exists() else {"events": []}

    async def gen():
        for ev in data.get("events", []):
            yield f"event: {ev['type']}\ndata: {json.dumps(ev.get('data', {}))}\n\n"
            await asyncio.sleep(0.4)   # realistic pacing
    return StreamingResponse(gen(), media_type="text/event-stream")
