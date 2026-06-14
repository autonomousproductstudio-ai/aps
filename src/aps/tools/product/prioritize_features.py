"""prioritize_features — synthesize features from pains and rank them (severity → MoSCoW).

Deterministic. Instead of pasting one feature per raw pain, it SYNTHESIZES: pains are clustered
by their clean feature-title theme (`pain_to_feature_title`), near-duplicate and subset variants
are merged ("Export" absorbs "Export quickly"), and each theme becomes ONE feature whose priority
is the MAX severity across the cluster and whose description aggregates the grounding pains. Then
table-stakes features (shared across competitors) are added. A **feature floor** (W3) guards the
thin-PRD problem: when too few themes result but real competitive signal exists, it promotes
single-competitor capabilities as candidate differentiators — never fabricating, so a genuinely
sparse space still yields an honestly short PRD. No LLM, no network.
"""
from __future__ import annotations

import re
from collections import Counter

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, PainPoint, Competitor, Feature, Severity
from aps.tools.analysis._text import clean_label, pain_to_feature_title
from aps.tools.analysis._inflect import singularize

_PRI = {Severity.HIGH: "Must", Severity.MED: "Should", Severity.LOW: "Could"}
_SEV_RANK = {Severity.HIGH: 3, Severity.MED: 2, Severity.LOW: 1}


def _title_tokens(title: str) -> frozenset[str]:
    """Singularized token set of a feature title — the unit pains are clustered/merged on."""
    return frozenset(singularize(w) for w in re.findall(r"[a-z0-9]+", title.lower()))


def _max_sev(a: Severity, b: Severity) -> Severity:
    return a if _SEV_RANK.get(a, 0) >= _SEV_RANK.get(b, 0) else b


def synthesize_pain_features(pains: list[PainPoint]) -> list[Feature]:
    """Cluster pains into themed features instead of one-feature-per-pain.

    1) name each pain's theme via `pain_to_feature_title` (clean noun phrase, never a fragment);
    2) group pains whose titles share the same token set (merges exact + plural/inflection dups,
       e.g. "Export"/"Exports"), keeping the shortest title and the MAX severity;
    3) subset-merge a specific theme into a more general one ("Export quickly" → "Export");
    4) emit one Feature per surviving theme, grounded in all its pains.

    Distinct themes stay distinct (so "pain 0/1/2" remain three features — the floor is honoured);
    only genuinely overlapping pains collapse.
    """
    # (2) group by exact title token-set, preserving first-seen order
    groups: dict[frozenset[str], dict] = {}
    order: list[frozenset[str]] = []
    for p in pains:
        title = pain_to_feature_title(p.text)
        toks = _title_tokens(title)
        g = groups.get(toks)
        if g is None:
            g = {"title": title, "toks": toks, "pains": [], "sev": p.severity}
            groups[toks] = g
            order.append(toks)
        g["pains"].append(p)
        g["sev"] = _max_sev(g["sev"], p.severity)
        if len(title) < len(g["title"]):          # keep the cleanest/shortest label
            g["title"] = title
    clusters = [groups[k] for k in order]

    # (3) subset-merge: fold a specific theme into the more general one it extends
    merged: list[dict] = []
    for c in clusters:
        host = next((m for m in merged if c["toks"] < m["toks"] or m["toks"] < c["toks"]), None)
        if host is None:
            merged.append(c)
            continue
        if c["toks"] < host["toks"]:               # c is more general → it sets the label
            host["title"], host["toks"] = c["title"], c["toks"]
        host["pains"].extend(c["pains"])
        host["sev"] = _max_sev(host["sev"], c["sev"])

    # (4) one feature per theme, grounded in its pains
    feats: list[Feature] = []
    for c in merged:
        pts = c["pains"]
        if len(pts) == 1:
            desc = f"Addresses the user pain: '{pts[0].text}'."
        else:
            extra = f" and '{pts[1].text}'" if len(pts) > 1 else ""
            desc = f"Synthesized from {len(pts)} related user pains: '{pts[0].text}'{extra}."
        feats.append(Feature(title=c["title"], description=desc,
                             priority=_PRI.get(c["sev"], "Should")))
    return feats


class Args(BaseModel):
    pain_points: list[PainPoint] = Field(default_factory=list)
    competitors: list[Competitor] = Field(default_factory=list)
    max_features: int = Field(12, ge=1, le=30)
    min_features: int = Field(3, ge=1, le=30,
                              description="floor: promote real competitor signal up to this many")


class PrioritizeFeatures(BaseTool):
    name = "prioritize_features"
    namespace = "product"
    description = (
        "Derive candidate features from pain points and prioritize them with a MoSCoW "
        "label inferred from pain severity (high→Must, med→Should, low→Could). Adds "
        "table-stakes features common across competitors, and—when few features result "
        "but real competitive signal exists—promotes single-competitor capabilities so "
        "the PRD isn't a one-feature doc. Never fabricates features."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        feats: list[Feature] = []
        seen: set[str] = set()

        def add(feature: Feature) -> None:
            key = feature.title.lower()
            if key not in seen and len(feats) < args.max_features:
                seen.add(key)
                feats.append(feature)

        # 1) SYNTHESIZE features from pains: cluster by clean-title theme + subset-merge, one
        #    feature per theme (priority = max severity, description aggregates the pains). Distinct
        #    themes stay distinct so the floor still holds; only overlapping pains collapse.
        for f in synthesize_pain_features(args.pain_points):
            add(f)

        # 2) table-stakes: capabilities offered by 2+ competitors.
        #    Keep a display label (clean, title-cased) separate from the dedup key (lowercase).
        common: Counter = Counter()
        _display: dict[str, str] = {}          # dedup_key → display label
        for c in args.competitors:
            for f in c.features:
                key = f.strip().lower()[:50]
                if key:
                    common[key] += 1
                    if key not in _display:
                        _display[key] = clean_label(f.strip(), max_words=5) or f.strip()[:50]

        for key, n in common.most_common():
            if n >= 2:
                display = _display.get(key, key).strip()
                add(Feature(title=f"Table stakes: {display}",
                            description=f"Offered by {n} competitors; expected baseline.",
                            priority="Should"))

        # 3) feature floor (W3): if still thin, promote single-competitor capabilities as
        #    candidate differentiators — real signal, never invented. If none exist, the PRD
        #    stays honestly short (the eval records the thinness rather than masking it).
        if len(feats) < args.min_features:
            for key, n in common.most_common():
                if len(feats) >= args.min_features:
                    break
                display = _display.get(key, key).strip()
                add(Feature(title=f"Differentiator: {display}",
                            description=f"Capability seen in the competitive set ({n}×); "
                                        f"candidate parity/differentiator feature.",
                            priority="Could"))

        order = {"Must": 0, "Should": 1, "Could": 2, "Won't": 3}
        feats.sort(key=lambda f: order.get(f.priority, 1))
        return ToolResult(ok=True, payload=feats)


TOOL = PrioritizeFeatures()

if __name__ == "__main__":
    import json
    out = TOOL.run(pain_points=[PainPoint(text="parser drops PDFs", severity="high").model_dump()],
                   competitors=[Competitor(name="A", features=["export", "sync"]).model_dump(),
                                Competitor(name="B", features=["analytics"]).model_dump()])
    print(json.dumps(out.model_dump(), indent=2, default=str))
