"""generate_brand_campaign — positioning, value props, channels, 14-day launch, posts.

Deterministic go-to-market plan derived from the idea + name (+ optional audience and
value-prop cues from the PRD). Returns a dict matching the campaign portion of BrandPackage.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult
from aps.tools.brand import _svg


class Args(BaseModel):
    idea: str
    name: str = ""
    audience: str = "early-stage founders"
    feature_cues: list[str] = Field(default_factory=list)  # PRD feature titles for value props


class GenerateBrandCampaign(BaseTool):
    name = "generate_brand_campaign"
    namespace = "brand"
    description = (
        "Generate a launch campaign for a product: positioning, value propositions, brand "
        "voice, channels, a 14-day launch sequence, and sample posts. Deterministic; uses "
        "PRD feature cues for value props when provided."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        name = args.name.strip() or _svg.derive_name(args.idea)
        core = _svg.clean_core(args.idea)
        low = core[0].lower() + core[1:] if core else core

        # Identity (taglines + positioning) reused so campaign + sheet stay consistent.
        ident_low = low
        taglines = [
            f"{name} — {core}, done for you.",
            f"Ship faster with {name}.",
            f"The smart way to {ident_low}.",
            f"{name}: less busywork, more building.",
            f"Your {ident_low}, on autopilot.",
        ]
        positioning = (
            f"For teams who need {low} without the overhead, {name} is the tool that "
            f"automates the busywork end to end — so you focus on the work that actually "
            f"moves the needle."
        )

        # Value props: lead with PRD feature cues when available, else demand-grounded defaults.
        value_props = [f"{c}." for c in args.feature_cues[:2] if c]
        value_props += [
            f"Cuts the time to {low} from days to minutes.",
            "Evidence-grounded — every output is traceable, not guessed.",
            "Runs on free tiers; reproducible by anyone.",
        ]
        value_props = value_props[:4]

        return ToolResult(ok=True, payload={
            "name": name,
            "positioning": positioning,
            "taglines": taglines,
            "value_props": value_props,
            "brand_voice": ("Confident, plain-spoken, builder-to-builder. No jargon, no "
                            "hype, show the work."),
            "channels": [
                {"channel": "Product Hunt", "goal": "launch-day reach", "asset": "60s demo + 5 GIFs"},
                {"channel": "X / LinkedIn", "goal": "founder audience", "asset": "build-in-public thread"},
                {"channel": "Hacker News (Show HN)", "goal": "technical credibility", "asset": "write-up + live link"},
                {"channel": "Founder communities", "goal": "design partners", "asset": "direct outreach"},
            ],
            "launch_sequence": [
                {"day": 1, "action": f"Teaser: '{taglines[1]}' + waitlist link"},
                {"day": 3, "action": "Build-in-public thread: the architecture, 1 screenshot"},
                {"day": 5, "action": "Demo video (the live run) released to waitlist"},
                {"day": 8, "action": "Show HN post + answer every comment for 6h"},
                {"day": 10, "action": "Product Hunt launch; rally waitlist for first-hour votes"},
                {"day": 14, "action": "Recap + first design-partner case study"},
            ],
            "sample_posts": [
                {"channel": "X", "text": f"We built {name}: {low} in under a minute, fully "
                                         f"cited. Watch it run 👇 (link)"},
                {"channel": "Show HN", "text": f"Show HN: {name} – {core} with traceable "
                                               f"evidence. Free-tier, reproducible. Feedback welcome."},
                {"channel": "LinkedIn", "text": f"Founders waste weeks on cold-start work. "
                                                f"{name} does it in minutes — {taglines[3]}"},
            ],
            "audience": args.audience,
        })


TOOL = GenerateBrandCampaign()

if __name__ == "__main__":
    import json
    print(json.dumps(TOOL.run(idea="AI-powered accounting for SMEs").payload, indent=2))
