"""BrandPackage → Markdown (Launch Studio Phase 1).

Embeds the inline SVGs in fenced ```svg blocks (renderable/copy-pasteable), then the
identity, value props, channels, 14-day launch sequence, and sample posts. Pure and
deterministic, like the other renderers.
"""
from __future__ import annotations

from aps.state.models import BrandPackage
from aps.render import base as b


def render(p: BrandPackage) -> str:
    out = [b.front_matter(f"Brand & Launch — {p.name or 'Untitled'}")]

    if p.positioning:
        out.append(b.h2("Positioning"))
        out.append(p.positioning.strip() + "\n")

    out.append(b.h2("Logo"))
    out.append(b.fenced(p.logo_svg or "", "svg") if p.logo_svg else b.PLACEHOLDER + "\n")
    if p.logo_mark_svg:
        out.append(b.h3("Mark"))
        out.append(b.fenced(p.logo_mark_svg, "svg"))

    if p.brand_sheet_svg:
        out.append(b.h2("Brand Sheet"))
        out.append(b.fenced(p.brand_sheet_svg, "svg"))

    if p.palette:
        out.append(b.h2("Palette"))
        out.append(b.bullet_list(p.palette))

    out.append(b.h2("Taglines"))
    out.append(b.bullet_list(p.taglines))

    out.append(b.h2("Value Propositions"))
    out.append(b.bullet_list(p.value_props))

    if p.brand_voice:
        out.append(b.h2("Brand Voice"))
        out.append(p.brand_voice.strip() + "\n")

    out.append(b.h2("Channels"))
    out.append(b.table(
        ["Channel", "Goal", "Asset"],
        [[c.get("channel"), c.get("goal"), c.get("asset")] for c in p.channels],
    ))

    out.append(b.h2("14-Day Launch Sequence"))
    out.append(b.table(
        ["Day", "Action"],
        [[s.get("day"), s.get("action")] for s in p.launch_sequence],
    ))

    out.append(b.h2("Sample Posts"))
    out.append(b.table(
        ["Channel", "Post"],
        [[s.get("channel"), s.get("text")] for s in p.sample_posts],
    ))

    return "".join(out)
