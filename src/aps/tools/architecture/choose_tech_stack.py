"""choose_tech_stack — pick a justified stack from requirements + scale.

Deterministic rules: start from a sane Python/Postgres/React baseline, then add
components when requirement/scale keywords call for them (ML, realtime, search, queue,
high scale). Returns a list of '<component>: <choice> — <why>' strings. No LLM.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult


def _has(blob: str, *cues: str) -> bool:
    """Match each cue at a WORD START (leading boundary), not as an internal substring.
    This keeps prefix/stem matching ('stream'→'streaming', 'notif'→'notification') while
    killing false positives — 'ai' must not fire on 'blockch-ai-n'/'em-ai-l', 'ml' not on 'ht-ml'."""
    return any(re.search(r"\b" + re.escape(c), blob) for c in cues)


class Args(BaseModel):
    requirements: list[str] = Field(default_factory=list)
    scale_estimate: str = ""


class ChooseTechStack(BaseTool):
    name = "choose_tech_stack"
    namespace = "architecture"
    description = (
        "Choose a justified tech stack from the requirements and scale estimate. Starts "
        "from a proven baseline and adds ML/search/realtime/queue/cache components only "
        "when the requirements warrant — each choice carries a one-line justification."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        blob = (" ".join(args.requirements) + " " + args.scale_estimate).lower()
        stack = [
            "Backend: FastAPI (async Python) — fast to build, typed, great for AI tool I/O",
            "DB: PostgreSQL — relational integrity for the core entities",
            "Frontend: React + Vite — matches the existing frontend (ADR-0007)",
            "Hosting: containerized (Docker) on a managed platform — simple ops at MVP",
        ]
        if _has(blob, "ml", "model", "ai", "score", "nlp", "predict", "embedding", "llm",
                "recommend", "classif"):
            stack.append("ML serving: a hosted LLM/ML endpoint + a thin inference service "
                         "— avoids GPU ops at MVP")
        if _has(blob, "search", "match", "rank", "similar"):
            stack.append("Search: pgvector / OpenSearch — semantic matching over the corpus")
        if _has(blob, "realtime", "real-time", "live", "stream", "notif", "collab"):
            stack.append("Realtime: WebSocket/SSE layer — push live updates to clients")
        if _has(blob, "queue", "batch", "async job", "background", "high", "scale", "millions"):
            stack.append("Async: Redis + a worker queue — offload long/batch jobs")
        if _has(blob, "cache", "high", "scale", "latency"):
            stack.append("Cache: Redis — cut read latency on hot paths")
        return ToolResult(ok=True, payload=stack)


TOOL = ChooseTechStack()

if __name__ == "__main__":
    import json
    out = TOOL.run(requirements=["AI scoring of resumes", "search/match candidates"],
                   scale_estimate="high")
    print(json.dumps(out.model_dump(), indent=2, default=str))
