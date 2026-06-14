"""Brand Agent (Launch Studio Phase 1, thin/deterministic).

Consumes the StudioState, emits a BrandPackage: a derived name, logo + mark + brand-sheet
SVGs, and a launch campaign. A deterministic pipeline over the scoped `brand` tools
(ADR-0005) — same shape as the Presentation agent — so it adds ~0 wall-clock and runs in a
parallel graph branch without an LLM key.

Works with or without a PRD: audience comes from a persona role when present, value-prop
cues from PRD feature titles; otherwise it derives everything from the idea alone.
"""
from __future__ import annotations

from aps.state.models import StudioState, BrandPackage
from aps.agents._pipeline import scoped, call
from aps.infra.metrics import AGENT_RUNS
from aps.tools.brand import _svg


def run_brand(state: StudioState) -> BrandPackage:
    AGENT_RUNS.labels(agent="brand").inc()
    t = scoped("brand")

    idea = state.idea
    prd = state.prd
    name = _svg.derive_name(idea)

    # PRD-derived cues (when the PRD ran): a target persona for audience, feature titles for
    # value props. Falls back cleanly to idea-only when prd is None.
    audience = "early-stage founders"
    feature_cues: list[str] = []
    if prd is not None:
        if prd.personas:
            audience = prd.personas[0].role or audience
        feature_cues = [f.title for f in prd.features[:2] if f.title]

    ident = call(t, "generate_brand_identity", idea=idea, name=name)
    taglines = ident["taglines"]
    tagline = taglines[1] if len(taglines) > 1 else (taglines[0] if taglines else "")

    logo = call(t, "generate_logo_svg", name=name, tagline=tagline, lockup=True)
    mark = call(t, "generate_logo_svg", name=name, lockup=False)
    sheet = call(t, "generate_brand_sheet_svg", name=name, tagline=tagline, taglines=taglines)
    camp = call(t, "generate_brand_campaign", idea=idea, name=name,
                audience=audience, feature_cues=feature_cues)

    palette, _ = _svg.choose(name)

    return BrandPackage(
        name=name,
        logo_svg=logo,
        logo_mark_svg=mark,
        brand_sheet_svg=sheet,
        palette=list(palette),
        taglines=taglines,
        positioning=ident["positioning"],
        value_props=camp["value_props"],
        brand_voice=camp["brand_voice"],
        channels=camp["channels"],
        launch_sequence=camp["launch_sequence"],
        sample_posts=camp["sample_posts"],
    )
