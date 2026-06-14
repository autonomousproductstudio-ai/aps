"""Analysis tools: deterministic behavior on crafted evidence (the 4 finished stubs +)."""
from __future__ import annotations

from aps.state.models import Evidence, ToolResult
from aps.tools.analysis import (
    extract_pain_points, dedupe_and_rank_evidence, build_competitor_matrix,
    estimate_market_size, rank_opportunities, detect_trend_signal,
    cluster_themes, sentiment_breakdown, extract_competitor_features,
    validate_with_sources,
)


def _ev():
    return [
        Evidence(source="reddit", url="https://reddit.com/r/x/1", title="rant",
                 snippet="The parser is broken and slow, I hate it."),
        Evidence(source="web", url="https://acme.io/pricing", title="Acme",
                 snippet="Acme supports PDF export and integrates with Slack. Pricing $29/mo."),
        Evidence(source="web", url="https://acme.io/features", title="Acme f",
                 snippet="Offers real-time analytics and a dashboard."),
        Evidence(source="web", url="https://report.example.com", title="market",
                 snippet="The market is worth $3 billion and growing."),
    ]


def _dump(ev):
    return [e.model_dump() for e in ev]


def test_extract_pain_points_finds_high_severity():
    out = extract_pain_points.TOOL.run(evidence=_dump(_ev()))
    assert out.ok and out.payload
    assert any(p.severity.value == "high" for p in out.payload)


def test_dedupe_collapses_duplicate_urls():
    e = _ev()
    dupe = Evidence(source="reddit", url="https://reddit.com/r/x/1?utm=1",
                    title="rant", snippet="dup")
    out = dedupe_and_rank_evidence.TOOL.run(evidence=_dump(e + [dupe]))
    urls = [x.url for x in out.payload]
    assert len(urls) == len(set(_norm(u) for u in urls))


def _norm(u):
    return u.split("?")[0]


def test_build_competitor_matrix_skips_research_sources():
    out = build_competitor_matrix.TOOL.run(evidence=_dump(_ev()))
    assert out.ok
    names = [c.name for c in out.payload]
    # acme.io is a competitor; reddit/report are not rivals
    assert any("Acme" in n for n in names)
    assert not any(n.lower().startswith("reddit") for n in names)


def test_estimate_market_size_extracts_figure():
    out = estimate_market_size.TOOL.run(evidence=_dump(_ev()), topic="resumes")
    assert out.ok and isinstance(out.payload, str)
    assert "$3.0B" in out.payload or "$3B" in out.payload


def test_estimate_market_size_no_figure_is_graceful():
    e = [Evidence(source="web", url="https://x.com/a", title="t",
                  snippet="lots of hiring demand and growing adoption")]
    out = estimate_market_size.TOOL.run(evidence=_dump(e))
    assert out.ok and "No explicit market figure" in out.payload


def test_estimate_market_size_floors_implausible_figures():
    # a sub-$1M "$" mention (a price/salary, not a market) must NOT be reported as a TAM
    e = [Evidence(source="web", url="https://x.com/s", title="pay",
                  snippet="median pay is $340 thousand for this role")]
    out = estimate_market_size.TOOL.run(evidence=_dump(e))
    assert "No explicit market figure" in out.payload          # not asserted as a TAM
    assert "credible-TAM floor" in out.payload                 # flagged with provenance


def test_rank_opportunities_orders_by_score():
    out = rank_opportunities.TOOL.run(evidence=_dump(_ev()))
    assert out.ok and out.payload
    scores = [o["score"] for o in out.payload]
    assert scores == sorted(scores, reverse=True)


def test_detect_trend_signal_directions():
    assert detect_trend_signal.TOOL.run(series=[10, 14, 18, 25, 31, 40]).payload["direction"] == "rising"
    assert detect_trend_signal.TOOL.run(series=[40, 31, 25, 18, 10]).payload["direction"] == "declining"
    assert detect_trend_signal.TOOL.run(series=[20, 20, 20, 20]).payload["direction"] == "flat"
    assert detect_trend_signal.TOOL.run(series=[5]).payload["direction"] == "unknown"


def test_cluster_themes_and_sentiment_and_features_run():
    ev = _dump(_ev())
    assert cluster_themes.TOOL.run(evidence=ev).ok
    sb = sentiment_breakdown.TOOL.run(evidence=ev)
    assert sb.ok and sb.payload["total"] == len(ev)
    feats = extract_competitor_features.TOOL.run(evidence=ev)
    assert feats.ok and any("support" in f.lower() or "offer" in f.lower() for f in feats.payload)


def test_validate_with_sources_drops_bad_urls():
    e = [Evidence(source="web", url="https://x.com/a", title="A", snippet="real content here"),
         Evidence(source="web", url="not-a-url", title="B", snippet="x")]
    out = validate_with_sources.TOOL.run(evidence=_dump(e))
    assert out.ok and len(out.payload) == 1


def test_all_analysis_return_toolresult():
    for mod in (extract_pain_points, dedupe_and_rank_evidence, build_competitor_matrix,
                estimate_market_size, rank_opportunities, detect_trend_signal):
        assert isinstance(mod.TOOL.run(evidence=_dump(_ev())), ToolResult)
