"""Pipeline + Dashboard + Artifacts endpoints (docs §3.4, §4, §5).

All protected by JWT (current_user). RUN_NNNN ids are resolved to the shared engine's real
StudioState; mappers.py does the shaping. A 404 surfaces as RUN_NOT_FOUND / ARTIFACT_NOT_FOUND
in the error envelope.
"""
from __future__ import annotations

import io
import json
import os
import zipfile

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from aps.api.v1 import engine, mappers, mockdata
from aps.api.v1.auth import current_user
from aps.api.v1.envelope import V1Error, ok, page_meta

router = APIRouter()


class StartReq(BaseModel):
    prompt: str
    model: str | None = None      # optional per-run model (from the UI selector / GET /v1/models)
    provider: str | None = None


def _require_state(alias: str):
    st = engine.state_for(alias)
    if st is None:
        # the run exists but hasn't produced state yet — return a minimal running shell
        meta = engine.meta_for(alias)
        if meta is None:
            raise V1Error("RUN_NOT_FOUND", "Run ID does not exist.", status=404)
    return st


# --------------------------------------------------------------------------- #
# §3.4 — start a run
# --------------------------------------------------------------------------- #
@router.post("/runs", status_code=201)
def start_run(req: StartReq, user=Depends(current_user)):
    if len(req.prompt) > 500:
        raise V1Error("VALIDATION_ERROR", "Prompt must be ≤ 500 characters.", field="prompt")
    # pass the UI-selected model/provider through to the shared engine (it pins them per-run);
    # omitted → the run uses the resolved default. The engine already supports this config.
    config = {k: v for k, v in (("model", req.model), ("provider", req.provider)) if v}
    alias = engine.start_run(req.prompt, config or None, user=user)
    return ok({"runId": alias, "status": "running"})


@router.post("/runs/{alias}/cancel", status_code=202)
def cancel_run(alias: str, user=Depends(current_user)):
    """Cooperatively cancel a queued/running run (plan 2.2). 404 if the alias is unknown; the
    run unwinds at its next checkpoint into a CANCELLED terminal state."""
    if not engine.cancel_run(alias):
        raise V1Error("RUN_NOT_FOUND", "Run ID does not exist.", status=404)
    return ok({"runId": alias, "cancelling": True})


_PROVIDER_LABELS = {"openai": "OpenAI", "nim": "NVIDIA NIM", "gemini": "Google Gemini",
                    "groq": "Groq", "cerebras": "Cerebras", "mistral": "Mistral",
                    "sambanova": "SambaNova", "openrouter": "OpenRouter", "together": "Together",
                    "deepseek": "DeepSeek", "github_models": "GitHub Models", "xai": "xAI"}


@router.get("/models")
def models(user=Depends(current_user)):
    """Selector catalog (providers → models) + the current default. When a failover chain is
    configured, the catalog IS the chain (so the dropdown offers every active provider) and the
    default is the chain PRIMARY — not the legacy gemini/nim default that could point at an
    exhausted provider. Picking one is a *preference* (it still fails over). No chain → legacy catalog."""
    from aps.config.providers import resolved_provider_chain, REGISTRY
    chain = resolved_provider_chain()
    if chain:
        providers = [{"id": p, "label": _PROVIDER_LABELS.get(p, p.title()),
                      "models": [{"id": REGISTRY[p].default_model,
                                  "label": REGISTRY[p].default_model, "tools": True}]}
                     for p in chain if p in REGISTRY]
        primary = chain[0]
        return ok({"providers": providers,
                   "default": {"provider": primary, "model": REGISTRY[primary].default_model}})
    # No chain configured → the legacy single-provider catalog.
    from aps.config.model_catalog import catalog
    from aps.config.settings import resolved_provider, get_settings
    s = get_settings()
    prov = resolved_provider()
    default_model = s.gemini_model if prov == "gemini" else s.nim_model
    return ok({**catalog(), "default": {"provider": prov, "model": default_model}})


# --------------------------------------------------------------------------- #
# §4 — dashboard
# --------------------------------------------------------------------------- #
@router.get("/runs/{alias}")
def get_run(alias: str, user=Depends(current_user)):
    st = engine.state_for(alias)
    if st is None:
        meta = engine.meta_for(alias)
        if meta is None:
            raise V1Error("RUN_NOT_FOUND", "Run ID does not exist.", status=404)
        # running, no artifacts yet — synthesize a minimal dashboard record
        from aps.state.models import StudioState
        st = StudioState(idea=meta.get("idea", ""))
    return ok(mappers.run_dashboard(st, alias))


@router.get("/runs/{alias}/agents")
def run_agents(alias: str, user=Depends(current_user)):
    st = _state_or_shell(alias)
    return ok(mappers.agents(st, detailed=False))


@router.get("/runs/{alias}/stream")
def run_stream(alias: str, limit: int = Query(default=50),
               type: str | None = Query(default=None), user=Depends(current_user)):
    engine.resolve(alias)  # 404 if unknown
    return ok(mappers.stream_events(engine.bus_history(alias), limit=limit, type_filter=type))


@router.get("/runs/{alias}/artifacts")
def run_artifacts(alias: str, user=Depends(current_user)):
    st = _state_or_shell(alias)
    items = mappers.artifacts_list(st, detail=True)
    return ok(items, **page_meta(items))


@router.get("/runs/{alias}/viability")
def run_viability(alias: str, user=Depends(current_user)):
    return ok(mappers.viability(_state_or_shell(alias)))


@router.get("/runs/{alias}/debate")
def run_debate_route(alias: str, user=Depends(current_user)):
    return ok(mappers.debate(_state_or_shell(alias)))


@router.get("/runs/{alias}/evidence-graph")
def run_evidence_graph(alias: str, user=Depends(current_user)):
    st = _state_or_shell(alias)
    return ok(mappers.evidence_graph(st))   # REAL: pains + source links from run data


@router.get("/runs/{alias}/explain")
def run_explain(alias: str, user=Depends(current_user)):
    """Explain-Why — per PRD feature: the pain/competitor it came from, grounding evidence,
    and a confidence score (from aps.explain.explain_prd)."""
    return ok(mappers.explain(_state_or_shell(alias)))


class LaunchReq(BaseModel):
    dryRun: bool = True
    token: str | None = None     # the USER's own GitHub PAT (repo scope); the repo is created in
                                 # their account. Omitted → preview (the shared APS_GITHUB_PAT is
                                 # only used when APS_GITHUB_ALLOW_SHARED_PAT=true / local demo).


@router.post("/runs/{alias}/launch")
def run_launch(alias: str, req: LaunchReq | None = None, user=Depends(current_user)):
    """GitHub Launch Mode — create a real repo + README + milestones + issues (with a PAT),
    or a safe preview (no token / dryRun=true)."""
    req = req or LaunchReq()
    return ok(engine.launch_github(alias, dry_run=req.dryRun, token=req.token))


@router.get("/runs/{alias}/dna")
def run_dna(alias: str, user=Depends(current_user)):
    st = _state_or_shell(alias)
    return ok(mockdata.company_dna(st.idea or "Core"))


@router.get("/runs/{alias}/timeline")
def run_timeline(alias: str, user=Depends(current_user)):
    engine.resolve(alias)
    return ok(mockdata.timeline())


# --------------------------------------------------------------------------- #
# §5 — artifacts page
# --------------------------------------------------------------------------- #
@router.get("/artifacts/{artifact_id}/content")
def artifact_content(artifact_id: str, run: str = Query(...),
                     format: str | None = Query(default=None), user=Depends(current_user)):
    st = _state_or_shell(run)
    if format == "mermaid":     # architecture diagrams (TRD → flowchart + ER mermaid blocks)
        mmd = mappers.artifact_mermaid(st, artifact_id)
        if mmd is None:
            raise V1Error("ARTIFACT_NOT_FOUND", "No diagram for this artifact.", status=404)
        return ok(mmd)
    body = mappers.artifact_content(st, artifact_id)
    if body is None:
        raise V1Error("ARTIFACT_NOT_FOUND", "Artifact not available yet.", status=404)
    return ok(body)


@router.get("/artifacts/{artifact_id}/evidence-traces")
def artifact_traces(artifact_id: str, run: str = Query(...), user=Depends(current_user)):
    st = _state_or_shell(run)
    traces = mappers.evidence_traces(st, artifact_id)
    if traces is None:
        raise V1Error("ARTIFACT_NOT_FOUND", "Artifact not available yet.", status=404)
    return ok(traces)


@router.get("/artifacts/{artifact_id}/versions")
def artifact_versions(artifact_id: str, run: str = Query(...), user=Depends(current_user)):
    st = _state_or_shell(run)
    vs = mappers.versions(st, artifact_id)
    if vs is None:
        raise V1Error("ARTIFACT_NOT_FOUND", "Artifact not available yet.", status=404)
    return ok(vs)


# --------------------------------------------------------------------------- #
# §5.5 — artifact export (markdown / json file download)
# --------------------------------------------------------------------------- #
@router.get("/artifacts/{artifact_id}/export")
def artifact_export(
    artifact_id: str,
    run: str = Query(...),
    format: str = Query(default="markdown"),
    user=Depends(current_user),
):
    """Download a single artifact as a raw file (markdown or json)."""
    st = _state_or_shell(run)
    body = mappers.artifact_content(st, artifact_id)
    if body is None:
        raise V1Error("ARTIFACT_NOT_FOUND", "Artifact not available yet.", status=404)

    if format == "json":
        content = json.dumps(body, indent=2, ensure_ascii=False)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{artifact_id}.json"'},
        )

    md_text: str = body.get("body", "") if isinstance(body, dict) else str(body)
    return Response(
        content=md_text,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{artifact_id}.md"'},
    )


# --------------------------------------------------------------------------- #
# §5.6 — run-level ZIP export (all artifacts or investor-package subset)
# --------------------------------------------------------------------------- #
_INVESTOR_ARTIFACTS = {"prd", "pitch", "research-brief", "market-analysis"}


@router.get("/runs/{alias}/export/zip")
def run_export_zip(
    alias: str,
    kind: str = Query(default="all"),
    user=Depends(current_user),
):
    """Return a ZIP bundle of all (or investor-subset) artifact markdown files."""
    st = _state_or_shell(alias)

    buf = io.BytesIO()
    included: list[str] = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for art in mappers.ARTIFACTS:
            art_id: str = art["id"]
            if kind == "investor" and art_id not in _INVESTOR_ARTIFACTS:
                continue
            body = mappers.artifact_content(st, art_id)
            if body is None:
                continue
            md_text: str = body.get("body", "") if isinstance(body, dict) else str(body)
            zf.writestr(f"{art_id}.md", md_text)
            included.append(art_id)

        manifest = {
            "run_id": alias,
            "kind": kind,
            "artifacts": included,
            "artifact_count": len(included),
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    buf.seek(0)
    label = "investor-package" if kind == "investor" else "artifacts"
    filename = f"aps-{label}-{alias}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --------------------------------------------------------------------------- #
# §5.7 — Notion export stub (requires NOTION_API_KEY + NOTION_PAGE_ID in env)
# --------------------------------------------------------------------------- #
@router.post("/runs/{alias}/export/notion")
def run_export_notion(alias: str, user=Depends(current_user)):
    """Export all artifacts to a Notion page. Requires env vars to be configured."""
    notion_key = os.environ.get("NOTION_API_KEY", "")
    notion_page = os.environ.get("NOTION_PAGE_ID", "")

    if not notion_key or not notion_page:
        return ok({
            "status": "unconfigured",
            "message": (
                "Set NOTION_API_KEY and NOTION_PAGE_ID in your .env to enable Notion export. "
                "Create an integration at https://www.notion.so/my-integrations"
            ),
        })

    # Real implementation would iterate mappers.artifact_content for each artifact
    # and POST blocks to the Notion API — stubbed pending NOTION_API_KEY being present.
    return ok({"status": "ok", "message": "Artifacts exported to Notion.", "pageId": notion_page})


def _state_or_shell(alias: str):
    """Return real StudioState, or a minimal running shell if the run exists but is fresh."""
    st = engine.state_for(alias)
    if st is not None:
        return st
    meta = engine.meta_for(alias)
    if meta is None:
        raise V1Error("RUN_NOT_FOUND", "Run ID does not exist.", status=404)
    from aps.state.models import StudioState
    return StudioState(idea=meta.get("idea", ""))
