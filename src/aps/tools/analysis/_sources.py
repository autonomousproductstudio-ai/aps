"""Evidence source-type tagging + the extraction gate.

Some evidence is real and useful for market sizing / demand signal but must NEVER seed a
competitor row or a product feature: job postings (a Remotive listing is not a product),
SEO / market-research reports and press releases (they describe the market, they aren't in
it), and news articles. Left ungated, a job posting's text gets mined as a competitor's
"capability" and promoted into the PRD — flowing on into requirements, the pitch, and the
execution backlog.

So we TAG each Evidence by kind and GATE the competitor / feature / pain extractors on it —
the same structural drop the ``[fixture]`` label already gets (see ``agent._compress``), but
applied by source TYPE rather than per-tool string heuristics. Market sizing still sees the
report evidence; only the product/feature/pain extractors are barred from the junk kinds.

Deterministic, no LLM, no network.
"""
from __future__ import annotations

import re

from aps.state.models import Evidence
from aps.tools.analysis._text import evidence_text

# ── Evidence.source labels (set by the retrieval tools) ───────────────────────
_JOB_SOURCES = {"jobs", "job"}
_REFERENCE_SOURCES = {"arxiv", "wikipedia", "stackexchange", "stackoverflow"}
_DISCUSSION_SOURCES = {"reddit", "hackernews", "github", "producthunt"}

# ── host families (matched as substrings of the registrable host) ─────────────
_JOB_HOSTS = ("remotive", "weworkremotely", "indeed", "glassdoor", "ziprecruiter",
              "lever.co", "greenhouse", "wellfound", "angellist", "monster", "dice")
_REPORT_HOSTS = ("wiseguyreports", "dataintelo", "marketsandmarkets", "grandviewresearch",
                 "mordorintelligence", "statista", "alliedmarketresearch",
                 "fortunebusinessinsights", "researchandmarkets", "marketresearchfuture",
                 "verifiedmarketresearch", "futuremarketinsights", "polarismarketresearch",
                 "precedenceresearch", "globenewswire", "prnewswire", "businesswire")
_REPORT_SUBSTR = ("marketresearch", "marketreport", "marketsand", "researchreport",
                  "intelligence", "marketinsights")
_NEWS_HOSTS = ("yahoo", "bloomberg", "reuters", "cnbc", "businessinsider", "washingtonpost",
               "nytimes", "theguardian", "techcrunch", "forbes", "wired", "venturebeat")

# Page text that reveals a market-research report / press release even on an unknown host.
_MARKET_REPORT_TEXT = re.compile(
    r"market size|market share|\bcagr\b|forecast (?:to|period|20)|market research report|"
    r"market is (?:expected|projected|anticipated)|billion by 20|million by 20|"
    r"during the forecast period|market report|industry report|press release",
    re.I,
)
_HOST = re.compile(r"^https?://(?:www\.)?([^/]+)", re.I)

# Kinds the competitor / feature / pain extractors must never consume.
_BARRED_FROM_EXTRACTION = {"job", "market_report", "news", "fixture"}


def _host(url: str) -> str:
    m = _HOST.match(url or "")
    return m.group(1).lower() if m else ""


def evidence_kind(e: Evidence) -> str:
    """Classify one Evidence into a source kind:
    ``fixture`` | ``job`` | ``market_report`` | ``news`` | ``reference`` | ``discussion`` |
    ``product``. Order matters — the barred kinds are detected first so they can't be
    mislabeled as a product/discussion by a generic ``source="web"``.
    """
    title = (getattr(e, "title", "") or "")
    if title.startswith("[fixture]"):
        return "fixture"
    src = (getattr(e, "source", "") or "").lower()
    host = _host(getattr(e, "url", "") or "")
    if src in _JOB_SOURCES or any(h in host for h in _JOB_HOSTS):
        return "job"
    if (any(h in host for h in _REPORT_HOSTS)
            or any(s in host for s in _REPORT_SUBSTR)
            or _MARKET_REPORT_TEXT.search(evidence_text(e) or "")):
        return "market_report"
    if any(h in host for h in _NEWS_HOSTS):
        return "news"
    if src in _REFERENCE_SOURCES:
        return "reference"
    if src in _DISCUSSION_SOURCES:
        return "discussion"
    return "product"


def is_extractable(e: Evidence) -> bool:
    """True if this evidence may seed competitors / features / pains. False for job postings,
    market-research/SEO reports, news, and fixtures — they are structurally barred (analogous
    to the ``[fixture]`` drop) so their text can never contaminate the PRD/pitch/execution."""
    return evidence_kind(e) not in _BARRED_FROM_EXTRACTION


def extractable(evidence: list[Evidence]) -> list[Evidence]:
    """Filter a list to the extraction-eligible evidence."""
    return [e for e in evidence if is_extractable(e)]
