"""Explanation → Markdown (remaining.md T2.5). Pure, deterministic."""
from __future__ import annotations

from aps.explain.explain import Explanation
from aps.render import base as b


def render(x: Explanation) -> str:
    out = [b.front_matter("Explain-Why", x.idea)]
    out.append(f"\n## Overall confidence: {int(x.overall_confidence * 100)}% "
               f"across {len(x.features)} feature(s)\n")
    if not x.features:
        out.append(b.PLACEHOLDER + "\n")
    for fe in x.features:
        out.append(b.h3(f"{fe.feature_title} `[{fe.priority}]` — {int(fe.confidence * 100)}%"))
        out.append(f"{fe.why}.\n")
        if fe.inspired_by:
            out.append(f"\n*Inspired by competitor:* **{fe.inspired_by}**\n")
        if fe.evidence:
            out.append("\n*Evidence:* " + b.citation_refs(fe.evidence) + "\n")
    return "".join(out)
