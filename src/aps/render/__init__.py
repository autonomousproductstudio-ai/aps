"""aps.render — on-demand typed-artifact → Markdown rendering (platform infra).

NOT a tool, never in the registry, never counted toward the 52 (plan.md W1 / MEMO). The
pipeline stays JSON-native and JSON-only-persisted; rendering is a pure, request-time
transform over an already-stored typed object. Entry point: `render_artifact(name, obj)`.
"""
from aps.render.registry import render_artifact, RENDERERS

__all__ = ["render_artifact", "RENDERERS"]
