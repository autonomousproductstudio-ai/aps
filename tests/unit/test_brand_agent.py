"""Brand agent pipeline: populated BrandPackage with and without a PRD."""
from __future__ import annotations

from aps.agents.brand.agent import run_brand
from aps.state.models import StudioState, PRD, Persona, Feature, BrandPackage
from aps.render import render_artifact


def test_run_brand_idea_only():
    state = StudioState(idea="a privacy-first habit tracker")
    brand = run_brand(state)
    assert isinstance(brand, BrandPackage)
    assert brand.name
    assert brand.logo_svg.startswith("<svg") and brand.logo_mark_svg.startswith("<svg")
    assert brand.brand_sheet_svg.startswith("<svg")
    assert len(brand.palette) == 3
    assert brand.taglines and brand.positioning
    assert len(brand.channels) == 4 and len(brand.launch_sequence) == 6


def test_run_brand_uses_prd_cues():
    prd = PRD(
        idea="a privacy-first habit tracker",
        personas=[Persona(name="Sam", role="busy professional")],
        features=[Feature(title="Streak Tracking", description="..."),
                  Feature(title="Private Sync", description="...")],
    )
    state = StudioState(idea="a privacy-first habit tracker", prd=prd)
    brand = run_brand(state)
    # value props lead with the PRD feature titles
    assert brand.value_props[0].startswith("Streak Tracking")


def test_run_brand_is_deterministic():
    state = StudioState(idea="AI-powered accounting for SMEs")
    assert run_brand(state).model_dump() == run_brand(state).model_dump()


def test_brand_renders_to_markdown_with_svg_block():
    brand = run_brand(StudioState(idea="a privacy-first habit tracker"))
    md = render_artifact("brand", brand)
    assert "# Brand & Launch" in md and "```svg" in md
    # also works from a plain dict (artifact-store read-through path)
    md2 = render_artifact("brand", brand.model_dump())
    assert md2 == md
