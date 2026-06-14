"""Competitor matrix: directories / social / review-aggregators are NOT competitors.

Closes the contributor's finding — real tools (Zeropath, Greptile, Latio) surface as
competitors, while discussion/listing sites (Dev, LinkedIn, Crozdesk, Automateed, G2) don't.
"""
from __future__ import annotations

import pytest

from aps.state.models import Evidence
from aps.tools.analysis.build_competitor_matrix import TOOL, _competitor_name


@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/posts/someone_pr-review",
    "https://dev.to/foo/best-code-review-tools",
    "https://crozdesk.com/software/code-review",
    "https://automateed.com/ai-code-review",
    "https://www.g2.com/categories/code-review",
    "https://www.capterra.com/code-review-software/",
    "https://medium.com/@author/top-10-tools",
    "https://www.youtube.com/watch?v=abc",
    "https://news.ycombinator.com/item?id=1",   # research source (pre-existing)
    # adversarial: an IP address / localhost / numeric label is never a product
    "https://192.168.1.1/app",
    "http://10.0.0.5:8080/x",
    "https://localhost:3000/dashboard",
])
def test_noise_domains_are_not_competitors(url):
    assert _competitor_name(url) is None


def test_ip_host_is_not_mined_into_a_numeric_competitor():
    ev = [Evidence(source="web", url="https://192.168.1.1/x", title="t",
                   snippet="supports export and offers a dashboard")]
    rows = TOOL.run(evidence=[e.model_dump() for e in ev]).payload
    assert rows == [] or all(not c.name.strip().isdigit() for c in rows)


def test_competitor_features_reject_table_chrome_and_trim_truncation():
    # real live failure: a pricing-table fragment was promoted to a PRD differentiator feature
    ev = [Evidence(source="web", url="https://hirevue.com/pricing", title="Hirevue",
                   snippet="Pricing | Hirevue Candidates: Are you interviewing and exporting reports."),
          Evidence(source="web", url="https://acme.io/features", title="Acme",
                   snippet="Acme offers automated phone screens for")]
    rows = TOOL.run(evidence=[e.model_dump() for e in ev]).payload
    feats = [f for c in rows for f in c.features]
    assert not any("|" in f for f in feats)                      # no table/nav chrome
    assert not any(f.rstrip().endswith((" and", " for", " the")) for f in feats)  # no dangling truncation


@pytest.mark.parametrize("url,expected", [
    ("https://zeropath.com/pricing", "Zeropath"),
    ("https://www.greptile.com", "Greptile"),
    ("https://latio.tech/features", "Latio"),
    ("https://acme.io/pricing", "Acme"),
])
def test_real_product_domains_are_competitors(url, expected):
    assert _competitor_name(url) == expected


def test_matrix_keeps_real_drops_noise():
    ev = [
        Evidence(source="web", url="https://linkedin.com/posts/x", title="LinkedIn post",
                 snippet="Great thread, supports many integrations"),
        Evidence(source="web", url="https://crozdesk.com/x", title="directory",
                 snippet="offers a dashboard and analytics"),
        Evidence(source="web", url="https://zeropath.com/pricing", title="Zeropath",
                 snippet="Zeropath offers SAST scanning and integrates with GitHub. Pricing $40/mo."),
    ]
    rows = TOOL.run(evidence=[e.model_dump() for e in ev]).payload
    names = {c.name for c in rows}
    assert "Zeropath" in names
    assert not any(n.lower() in {"linkedin", "crozdesk"} for n in names)
