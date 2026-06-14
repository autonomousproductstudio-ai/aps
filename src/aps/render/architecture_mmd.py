"""TRD → Mermaid architecture diagrams (remaining.md T2.2).

Pure, deterministic. Emits a Markdown doc with two fenced ```mermaid blocks — a system
**flowchart** (components + data flow) and an **ER diagram** (entities + relationships) —
so it renders on GitHub immediately and a frontend can lift the raw blocks for mermaid.js.
"""
from __future__ import annotations

import re

from aps.state.models import TRD
from aps.render import base as b

_ARROWS = re.compile(r"\s*(?:->|→|↔|<->|=>)\s*")
_PAREN = re.compile(r"\([^)]*\)")


def _node_id(label: str) -> str:
    core = _PAREN.sub("", label).strip()
    sid = re.sub(r"[^A-Za-z0-9]+", "_", core).strip("_") or "node"
    if sid[0].isdigit():
        sid = "n_" + sid
    return sid[:40]


def _clean_label(label: str) -> str:
    return _PAREN.sub("", label).strip().replace('"', "'")[:48] or "node"


def _flowchart(data_model: dict) -> str:
    arch = (data_model or {}).get("architecture", {}) or {}
    components = arch.get("components", []) or []
    data_flow = arch.get("data_flow", []) or []

    nodes: dict[str, str] = {}      # id -> label (insertion-ordered, deterministic)
    edges: list[tuple[str, str]] = []
    seen_edges: set[tuple[str, str]] = set()

    def ensure(label: str) -> str:
        nid = _node_id(label)
        nodes.setdefault(nid, _clean_label(label))
        return nid

    for comp in components:
        ensure(comp)
    for line in data_flow:
        segs = [s for s in _ARROWS.split(str(line)) if s.strip()]
        chain = [ensure(s) for s in segs]
        for a, c in zip(chain, chain[1:]):
            if a != c and (a, c) not in seen_edges:
                seen_edges.add((a, c))
                edges.append((a, c))

    if not nodes:
        return ""
    lines = ["flowchart TD"]
    for nid, label in nodes.items():
        lines.append(f'    {nid}["{label}"]')
    for a, c in edges:
        lines.append(f"    {a} --> {c}")
    return "\n".join(lines)


def _er(data_model: dict) -> str:
    entities = (data_model or {}).get("entities", {}) or {}
    if not entities:
        return ""
    names_lc = {n.lower(): n for n in entities}
    lines = ["erDiagram"]
    for name, spec in entities.items():
        fields = (spec or {}).get("fields", {}) or {}
        lines.append(f"    {name} {{")
        for fname, ftype in fields.items():
            t = re.sub(r"[^A-Za-z0-9_]", "_", str(ftype)) or "string"
            lines.append(f"        {t} {fname}")
        lines.append("    }")
    # relationships from <x>_id foreign keys (owner_id -> User)
    rels: set[tuple[str, str, str]] = set()
    for name, spec in entities.items():
        for fname in ((spec or {}).get("fields", {}) or {}):
            if fname.endswith("_id") and fname != "id":
                base = fname[:-3]
                target = "User" if base == "owner" else names_lc.get(base)
                if target and target != name:
                    rels.add((target, name, base))
    for target, name, base in sorted(rels):
        lines.append(f'    {target} ||--o{{ {name} : "{base}"')
    return "\n".join(lines)


def render(t: TRD) -> str:
    out = [b.front_matter("Architecture Diagram")]

    out.append(b.h2("System Architecture"))
    flow = _flowchart(t.data_model)
    out.append(b.fenced(flow, "mermaid") if flow else b.PLACEHOLDER + "\n")

    out.append(b.h2("Data Model (ER)"))
    er = _er(t.data_model)
    out.append(b.fenced(er, "mermaid") if er else b.PLACEHOLDER + "\n")

    out.append(b.h2("Tech Stack"))
    out.append(b.bullet_list(t.stack))
    return "".join(out)
