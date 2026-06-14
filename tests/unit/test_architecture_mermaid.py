"""T2.2 — TRD → Mermaid architecture diagrams: valid, complete, graceful, deterministic."""
from __future__ import annotations

from aps.state.models import TRD
from aps.render import architecture_mmd


def _trd():
    return TRD(
        data_model={
            "entities": {
                "User": {"fields": {"id": "uuid", "email": "string"}},
                "Resume": {"fields": {"id": "uuid", "owner_id": "uuid", "score": "float"}},
            },
            "architecture": {
                "components": ["API gateway", "App service", "PostgreSQL", "Inference service"],
                "services": ["auth", "scoring"],
                "data_flow": ["Client → API gateway → App service (authn)",
                              "App service → Inference service → result persisted"],
            },
        },
        api_spec={"openapi": "3.0.3", "paths": {"/resumes": {"get": {"summary": "List"}}}},
        stack=["Backend: FastAPI", "DB: PostgreSQL"],
    )


def test_emits_two_mermaid_blocks():
    md = architecture_mmd.render(_trd())
    assert md.count("```mermaid") == 2
    assert "flowchart TD" in md and "erDiagram" in md


def test_flowchart_has_components_and_edges():
    md = architecture_mmd.render(_trd())
    assert "API gateway" in md and "Inference service" in md
    assert "-->" in md            # at least one data-flow edge


def test_er_has_entities_fields_and_relationship():
    md = architecture_mmd.render(_trd())
    assert "User {" in md and "Resume {" in md
    assert "uuid id" in md
    # owner_id foreign key becomes a User--Resume relationship
    assert "User ||--o{ Resume" in md


def test_node_ids_are_mermaid_safe():
    md = architecture_mmd.render(_trd())
    flow = md.split("flowchart TD", 1)[1].split("```", 1)[0]
    for line in flow.splitlines():
        line = line.strip()
        if line.startswith(("%", "")) and "[" in line and "-->" not in line:
            nid = line.split("[", 1)[0]
            assert nid.replace("_", "").isalnum(), f"unsafe node id: {nid!r}"


def test_empty_trd_is_graceful():
    md = architecture_mmd.render(TRD())
    assert md and "None" not in md
    assert "_— none identified —_" in md


def test_deterministic():
    t = _trd()
    assert architecture_mmd.render(t) == architecture_mmd.render(t)
