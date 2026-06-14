"""design_architecture — component/service decomposition from stack + data model.

Deterministic: lays out the standard service components (API gateway, app service,
worker, datastore, plus any optional ones implied by the stack) and the data flow.
Returns {components: [...], services: [...], data_flow: [...]}. No LLM, no network.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult


class Args(BaseModel):
    stack: list[str] = Field(default_factory=list)
    data_model: dict = Field(default_factory=dict)


class DesignArchitecture(BaseTool):
    name = "design_architecture"
    namespace = "architecture"
    description = (
        "Decompose the system into components and services (gateway, app, workers, "
        "datastore, plus ML/search/cache when the stack includes them) and describe the "
        "request/data flow. Use after the stack is chosen to give the TRD its shape."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        blob = " ".join(args.stack).lower()
        components = ["API gateway / load balancer", "FastAPI application service",
                      "PostgreSQL primary datastore"]
        services = ["auth", "core-crud"]
        if "redis" in blob or "queue" in blob or "worker" in blob:
            components.append("Redis + background worker pool")
            services.append("async-jobs")
        if "ml" in blob or "inference" in blob or "llm" in blob:
            components.append("Inference service (hosted model endpoint)")
            services.append("scoring")
        if "search" in blob or "pgvector" in blob or "opensearch" in blob:
            components.append("Vector/search index")
            services.append("search-match")
        entities = list((args.data_model or {}).get("entities", {}).keys())
        data_flow = [
            "Client → API gateway → app service (authn/authz)",
            "App service ↔ PostgreSQL for " + (", ".join(entities[:5]) or "core entities"),
        ]
        if "scoring" in services:
            data_flow.append("App service → inference service → result persisted")
        return ToolResult(ok=True, payload={
            "components": components, "services": services, "data_flow": data_flow,
        })


TOOL = DesignArchitecture()

if __name__ == "__main__":
    import json
    out = TOOL.run(stack=["ML serving: hosted endpoint", "Async: Redis + worker queue"],
                   data_model={"entities": {"Resume": {}, "User": {}}})
    print(json.dumps(out.model_dump(), indent=2, default=str))
