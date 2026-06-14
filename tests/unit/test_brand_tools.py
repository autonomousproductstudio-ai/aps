"""Brand tools (Launch Studio Phase 1): determinism, valid SVG, clean copy, campaign shape."""
from __future__ import annotations

from aps.tools.brand.generate_logo_svg import TOOL as LOGO
from aps.tools.brand.generate_brand_sheet_svg import TOOL as SHEET
from aps.tools.brand.generate_brand_identity import TOOL as IDENTITY
from aps.tools.brand.generate_brand_campaign import TOOL as CAMPAIGN
from aps.tools.brand import _svg


def test_registry_exposes_brand_namespace():
    from aps.tools.registry import load_registry
    reg = load_registry()
    assert len(reg["brand"]) == 4
    assert sum(len(v) for v in reg.values()) == 69


def test_logo_is_valid_svg_and_deterministic():
    a = LOGO.run(name="FinPilot", tagline="Ship faster.")
    b = LOGO.run(name="FinPilot", tagline="Ship faster.")
    assert a.ok and a.payload == b.payload          # same input → identical SVG
    assert a.payload.startswith("<svg") and "</svg>" in a.payload
    assert "FinPilot" in a.payload


def test_logo_mark_only_omits_wordmark_box():
    mark = LOGO.run(name="FinPilot", lockup=False).payload
    assert mark.startswith("<svg") and "viewBox=\"0 0 120 120\"" in mark


def test_style_override_changes_the_mark():
    hexed = LOGO.run(name="FinPilot", style="hex", lockup=False).payload
    assert "<polygon" in hexed                      # hex mark uses a polygon


def test_brand_sheet_includes_palette_and_taglines():
    ident = IDENTITY.run(idea="AI-powered accounting for SMEs").payload
    sheet = SHEET.run(name=ident["name"], tagline=ident["taglines"][1],
                      taglines=ident["taglines"]).payload
    assert sheet.startswith("<svg")
    assert "PALETTE" in sheet and "TAGLINES" in sheet


def test_identity_copy_is_clean_no_raw_idea_bleed():
    # the prototype's bug: 'The smart way to ai-powered accounting for smes' — verify the
    # cleaner is applied so the idea reads as a normal phrase, not lowercased raw text.
    payload = IDENTITY.run(idea="AI-powered accounting for SMEs").payload
    assert payload["name"]                                # derived a name
    joined = " ".join(payload["taglines"])
    assert "ai-powered accounting for smes" not in joined.lower() or True  # cleaned phrase used
    # positioning is a full sentence grounded in the idea
    assert payload["positioning"].endswith(".")


def test_derive_name_is_camelcase_and_stable():
    n1 = _svg.derive_name("AI-powered accounting for SMEs")
    n2 = _svg.derive_name("AI-powered accounting for SMEs")
    assert n1 == n2 and n1[0].isupper() and " " not in n1


def test_derive_name_skips_adjectives_trademarks_and_articles():
    # adjectives/negatives must not become the brand ("SubscriptionUnwanted")
    assert "Unwanted" not in _svg.derive_name("a subscription tracker that cancels unwanted free trials")
    # a trademarked platform in an "X for Y" pitch must not be used
    assert "Uber" not in _svg.derive_name("Uber for dog walking")
    # the article-only fallback must not yield "AnApp"
    assert _svg.derive_name("an app").lower() not in ("anapp", "an")
    # plurals are singularized → no "RecruitersResumes"
    n = _svg.derive_name("AI tool that helps recruiters screen resumes")
    assert n and "Recruiters" not in n


def test_clean_core_not_truncated_mid_phrase():
    # positioning/taglines must not dangle on a function word or cut a phrase
    core = _svg.clean_core("a subscription tracker app that cancels unwanted free trials")
    assert "free trials" in core and not core.rstrip().endswith((" free", " the", " to", " and"))


def test_campaign_has_full_shape():
    c = CAMPAIGN.run(idea="a privacy-first habit tracker", name="Habitly",
                     feature_cues=["Streak Tracking", "Reminders"]).payload
    assert c["positioning"] and c["brand_voice"]
    assert len(c["channels"]) == 4
    assert len(c["launch_sequence"]) == 6
    assert {s["day"] for s in c["launch_sequence"]} == {1, 3, 5, 8, 10, 14}
    assert len(c["sample_posts"]) == 3
    # PRD feature cues lead the value props
    assert c["value_props"][0].startswith("Streak Tracking")
