"""design_api_contract — emit a VALID OpenAPI 3.0 document from the data model.

This is the architecture agent's must-be-real output (MEMO). For every entity it emits
REST CRUD paths and a component schema, producing a document with `openapi`, `info`,
`paths`, and `components.schemas` — valid enough to load in Swagger UI / openapi tooling.
Deterministic, no LLM, no network.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult
from aps.tools.analysis._inflect import pluralize

_TYPE_MAP = {"uuid": "string", "string": "string", "datetime": "string",
             "int": "integer", "integer": "integer", "bool": "boolean",
             "boolean": "boolean", "float": "number", "number": "number"}


def _schema_for(fields: dict) -> dict:
    props = {}
    for fname, ftype in fields.items():
        prop = {"type": _TYPE_MAP.get(str(ftype), "string")}
        if ftype in ("uuid",):
            prop["format"] = "uuid"
        if ftype == "datetime":
            prop["format"] = "date-time"
        if ftype == "email":
            prop["format"] = "email"
        props[fname] = prop
    return {"type": "object", "properties": props}


class Args(BaseModel):
    data_model: dict = Field(default_factory=dict, description="output of design_data_model")
    idea: str = ""
    version: str = "1.0.0"


class DesignApiContract(BaseTool):
    name = "design_api_contract"
    namespace = "architecture"
    description = (
        "Generate a valid OpenAPI 3.0 contract (paths + component schemas) from the data "
        "model: list/create/get/update/delete per entity. Use after design_data_model — "
        "this is the concrete, loadable API spec the TRD carries."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        entities = (args.data_model or {}).get("entities", {}) or {"Item": {"fields": {"id": "uuid"}}}
        title = (args.idea or "Product").strip()[:60] or "Product"
        paths: dict = {}
        schemas: dict = {}
        for name, spec in entities.items():
            fields = spec.get("fields", {"id": "uuid"})
            schemas[name] = _schema_for(fields)
            plural = pluralize(name)                 # 'Reject'->'Rejects', never '/rejectss'
            coll = "/" + plural.lower()
            item = coll + "/{id}"
            ref = {"$ref": f"#/components/schemas/{name}"}
            paths[coll] = {
                "get": {"summary": f"List {plural}", "operationId": f"list{plural}",
                        "responses": {"200": {"description": "OK",
                            "content": {"application/json": {"schema": {"type": "array", "items": ref}}}}}},
                "post": {"summary": f"Create {name}", "operationId": f"create{name}",
                         "requestBody": {"required": True,
                            "content": {"application/json": {"schema": ref}}},
                         "responses": {"201": {"description": "Created",
                            "content": {"application/json": {"schema": ref}}}}},
            }
            paths[item] = {
                "parameters": [{"name": "id", "in": "path", "required": True,
                                "schema": {"type": "string"}}],
                "get": {"summary": f"Get {name}", "operationId": f"get{name}",
                        "responses": {"200": {"description": "OK",
                            "content": {"application/json": {"schema": ref}}},
                                      "404": {"description": "Not found"}}},
                "put": {"summary": f"Update {name}", "operationId": f"update{name}",
                        "requestBody": {"required": True,
                            "content": {"application/json": {"schema": ref}}},
                        "responses": {"200": {"description": "Updated",
                            "content": {"application/json": {"schema": ref}}}}},
                "delete": {"summary": f"Delete {name}", "operationId": f"delete{name}",
                           "responses": {"204": {"description": "Deleted"}}},
            }

        doc = {
            "openapi": "3.0.3",
            "info": {"title": f"{title} API", "version": args.version,
                     "description": f"Auto-generated REST contract for {title}."},
            "paths": paths,
            "components": {"schemas": schemas},
        }
        return ToolResult(ok=True, payload=doc)


TOOL = DesignApiContract()

if __name__ == "__main__":
    import json
    dm = {"entities": {"Resume": {"fields": {"id": "uuid", "score": "float"}}}}
    out = TOOL.run(data_model=dm, idea="resume screening")
    print(json.dumps(out.payload, indent=2, default=str)[:800])
