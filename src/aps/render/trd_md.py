"""TRD → Markdown (plan.md W1).

The data model and OpenAPI spec render as human tables (entity/field, endpoint summary)
with the full spec in a fenced block below — not a raw JSON dump. The spec is fenced as
JSON (dependency-free) rather than YAML; see decision.md D16.
"""
from __future__ import annotations

import json

from aps.state.models import TRD
from aps.render import base as b

_VERBS = ("get", "post", "put", "patch", "delete")


def _stack_table(stack: list[str]) -> str:
    rows = []
    for item in stack:
        if ":" in item:
            concern, choice = item.split(":", 1)
            rows.append([concern.strip(), choice.strip()])
        else:
            rows.append(["—", item.strip()])
    return b.table(["Concern", "Choice"], rows)


def _entities(data_model: dict) -> str:
    entities = (data_model or {}).get("entities", {})
    if not entities:
        return b.PLACEHOLDER + "\n"
    out = []
    for name, spec in entities.items():
        out.append(b.h3(name))
        fields = (spec or {}).get("fields", {})
        out.append(b.table(["Field", "Type"], [[f, t] for f, t in fields.items()]))
    return "".join(out)


def _endpoint_table(api_spec: dict) -> str:
    paths = (api_spec or {}).get("paths", {})
    rows = []
    for path, ops in paths.items():
        for verb in _VERBS:
            if verb in ops:
                rows.append([verb.upper(), path, ops[verb].get("summary", "")])
    return b.table(["Method", "Path", "Summary"], rows)


def render(t: TRD) -> str:
    out = [b.front_matter("Technical Requirements Document")]

    out.append(b.h2("Tech Stack"))
    out.append(_stack_table(t.stack))

    out.append(b.h2("Scale Estimate"))
    out.append((t.scale_estimate or b.PLACEHOLDER) + "\n")

    out.append(b.h2("Data Model"))
    out.append(_entities(t.data_model))

    arch = (t.data_model or {}).get("architecture")
    if isinstance(arch, dict):
        out.append(b.h3("Components"))
        out.append(b.bullet_list(arch.get("components", [])))
        out.append(b.h3("Data Flow"))
        out.append(b.numbered_list(arch.get("data_flow", [])))

    out.append(b.h2("API Contract"))
    out.append(_endpoint_table(t.api_spec))
    if t.api_spec:
        out.append(b.h3("OpenAPI Specification"))
        out.append(b.fenced(json.dumps(t.api_spec, indent=2, sort_keys=True), "json"))
    return "".join(out)
