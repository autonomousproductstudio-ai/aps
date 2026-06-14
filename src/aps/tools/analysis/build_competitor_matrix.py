"""build_competitor_matrix — assemble a competitor comparison from evidence.

Groups evidence by the product/company behind it (registrable domain), pulls feature
claims and any pricing hint per competitor, and returns one Competitor row each — i.e.
the rows of a competitor × feature matrix. Research-source domains (github, reddit, hn,
wikipedia, arxiv, package registries) are skipped: they're where we *found* signal, not
competitors. Deterministic, no LLM, no network.
"""
from __future__ import annotations

import html
import re

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Evidence, Competitor
from aps.tools.analysis._text import as_evidence_list, evidence_text, clean_label
from aps.tools.analysis._sources import extractable

# domains that are research sources, never "competitors"
_RESEARCH_HOSTS = (
    "github.com", "reddit.com", "news.ycombinator.com", "ycombinator.com",
    "wikipedia.org", "arxiv.org", "pypi.org", "npmjs.com", "stackexchange.com",
    "stackoverflow.com", "google.com", "example.com", "producthunt.com",
)

# Registrable names that are integrations / dev-or-source platforms / generic category or
# page words — never a competitor (this is what let Github, Zapier, Productivity slip in).
_DENY_NAMES = {
    # integrations / dev / source platforms
    "zapier", "ifttt", "make", "github", "gitlab", "bitbucket", "sourceforge",
    "npmjs", "pypi", "readthedocs", "gist",
    # generic category / page / chrome words
    "productivity", "tools", "tool", "apps", "app", "software", "platform", "platforms",
    "solutions", "solution", "blog", "docs", "doc", "help", "support", "about", "home",
    "index", "pricing", "features", "download", "downloads", "wiki",
    # social / community / content platforms — discussion ABOUT products, not products
    "linkedin", "twitter", "facebook", "instagram", "youtube", "tiktok", "medium",
    "dev", "hashnode", "substack", "quora", "discord", "slack", "telegram",
    "indiehackers", "hackernoon", "vimeo", "slideshare", "wordpress", "blogspot", "tumblr",
    # review / listing / directory / aggregator sites — they RANK products, aren't one
    "g2", "capterra", "getapp", "trustpilot", "trustradius", "crozdesk", "saashub",
    "alternativeto", "slant", "softwareadvice", "financesonline", "goodfirms", "clutch",
    "betalist", "appsumo", "stackshare", "crunchbase", "owler", "similarweb", "builtwith",
    "automateed", "toolify", "futurepedia", "futuretools", "theresanaiforthat", "aitools",
    # news / generic category-page words
    "techcrunch", "forbes", "wired", "venturebeat", "review", "reviews", "compare",
    "comparison", "best", "top", "alternatives", "list", "category", "directory",
    "marketplace", "news", "yahoo", "bloomberg", "reuters", "cnbc", "businessinsider",
    "washingtonpost", "nytimes", "theguardian", "globenewswire", "prnewswire", "businesswire",
    # job boards — postings are not products (source="jobs" is filtered too, but the job's
    # own URL can be any host, so deny the boards by name as a second guard)
    "remotive", "weworkremotely", "indeed", "glassdoor", "ziprecruiter", "lever",
    "greenhouse", "wellfound", "angellist", "monster", "dice", "linkedinjobs", "jobs",
    # market-research / SEO-report publishers — they SELL reports about the market
    "wiseguyreports", "dataintelo", "marketsandmarkets", "grandviewresearch",
    "mordorintelligence", "statista", "alliedmarketresearch", "fortunebusinessinsights",
    "researchandmarkets", "marketresearch", "knack", "verifiedmarketresearch",
    "futuremarketinsights", "polarismarketresearch", "precedenceresearch",
    "marketresearchfuture", "privacyguides", "nih", "ncbi", "pubmed", "researchgate",
}
# Substrings that mark a registrable name as a research/report publisher or reference site —
# catches the long tail (marketresearchfuture, xyz-market-research) without enumerating each.
_DENY_SUBSTR = ("marketresearch", "marketreport", "marketsand", "researchreport",
                "intelligence", "marketinsights")
_FEATURE_CUES = ("support", "integrat", "offer", "feature", "allow", "enable",
                 "provide", "export", "import", "sync", "automat", "dashboard",
                 "api", "real-time", "collaborat", "template", "analytics", "search")
# Table / nav chrome separators — a "feature" carrying these is a pricing-table or menu fragment
# ("Pricing | Hirevue Candidates: …"), not a real capability claim. Reject outright.
_CHROME_MARK = re.compile(r"\s\|\s|»|→|::|·")
# Trailing function words that leave a feature dangling mid-thought ("… screens for", "… and").
_FEAT_TRAIL = {"and", "or", "but", "the", "a", "an", "to", "of", "for", "with", "is", "are",
               "you", "we", "in", "on", "at", "that", "this", "your", "their", "from", "by"}


def _clean_feature(s: str) -> str | None:
    """A competitor feature claim cleaned for promotion into the PRD: no table/nav chrome, no
    dangling truncation, at least two real words. Returns None if it's not a usable claim."""
    if _CHROME_MARK.search(s):
        return None
    lab = clean_label(s, max_words=8, max_chars=80)
    toks = lab.split()
    while toks and toks[-1].lower().strip(",.;:!?") in _FEAT_TRAIL:
        toks.pop()
    lab = " ".join(toks).strip(" -–—:.,")
    if len(toks) < 2 or len(re.sub(r"[^A-Za-z]", "", lab)) < 4:
        return None
    return lab
_PRICE = re.compile(r"(\$\s?\d[\d,]*(?:\.\d+)?\s?(?:/\s?(?:mo|month|yr|year|user|seat))?|free tier|freemium|free plan)", re.I)
_SPLIT = re.compile(r"[.!?\n;]")
_HOST = re.compile(r"^https?://(?:www\.)?([^/]+)", re.I)


def _competitor_name(url: str) -> str | None:
    m = _HOST.match(url or "")
    if not m:
        return None
    host = m.group(1).lower().split(":")[0]
    if any(host == h or host.endswith("." + h) for h in _RESEARCH_HOSTS):
        return None
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host) or host in ("localhost",):
        return None                                    # an IP/localhost is not a product
    label = host.split(".")
    # registrable label: second-to-last segment for normal domains
    name = label[-2] if len(label) >= 2 else label[0]
    low = name.lower()
    if not name or len(name) < 2 or name.isdigit() or low in _DENY_NAMES \
            or any(sub in low for sub in _DENY_SUBSTR):
        return None
    return name.replace("-", " ").title()


_SHOW_HN = re.compile(r"^\s*show\s+hn:\s*(.+)$", re.I)
_NAME_SEP = re.compile(r"\s*[–—\-:|(]\s*")  # split a product name from its tagline


def _structured_name(e: Evidence) -> str | None:
    """A clean product name from a STRUCTURED source where the title IS the product:
    ProductHunt posts (title == product name) and 'Show HN: <name>' HN posts. Returns None
    for everything else — this is title-only, deliberately NOT free-text extraction, so it
    surfaces real competitors (ProductHunt/Show-HN products) without false positives."""
    title = html.unescape(getattr(e, "title", "") or "").strip()
    src = (getattr(e, "source", "") or "").lower()
    if not title or title.lower().startswith("[fixture]"):
        return None
    if src == "producthunt":
        raw = title
    else:
        m = _SHOW_HN.match(title)
        if not m:
            return None
        raw = m.group(1)
    name = _NAME_SEP.split(raw, 1)[0].strip()        # drop the tagline after a dash/colon
    name = re.sub(r"[*_`#\"']", "", name).strip()    # strip stray markdown/quotes
    words = name.split()
    if not (1 <= len(words) <= 4):                   # a product name is short; longer = a sentence
        return None
    if len(name) < 2 or name.lower() in _DENY_NAMES:
        return None
    return name


class Args(BaseModel):
    evidence: list[Evidence] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list,
                                   description="optional explicit competitor names to seed rows")
    max_competitors: int = Field(8, ge=1, le=25)
    max_features_each: int = Field(6, ge=1, le=20)


class BuildCompetitorMatrix(BaseTool):
    name = "build_competitor_matrix"
    namespace = "analysis"
    description = (
        "Build a competitor comparison matrix from gathered evidence: one row per "
        "product (grouped by its domain) with its extracted feature claims and any "
        "pricing hint. Run after retrieval to see who the competitors are and how they "
        "stack up. Returns Competitor rows; research sources are not treated as rivals."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        # STRUCTURAL GATE: bar job postings, market-research/SEO reports, news and fixtures
        # before any extraction (same idea as the [fixture] drop). This is the root-cause fix
        # for Remotive job listings being mined into "capabilities" → PRD features → pitch →
        # backlog. Only product/discussion/reference evidence reaches the matrix.
        ev = extractable(as_evidence_list(args.evidence))
        groups: dict[str, list[Evidence]] = {}
        for e in ev:
            # High-precision: a ProductHunt / Show-HN title IS a real product name — surface it
            # even though its host is a research source (which the domain rule would skip).
            name = _structured_name(e) or _competitor_name(e.url)
            if name:
                groups.setdefault(name, []).append(e)
        for seed in args.competitors:
            groups.setdefault(seed.strip().title(), [])

        rows: list[Competitor] = []
        for name, items in groups.items():
            feats: list[str] = []
            seen: set[str] = set()
            pricing: str | None = None
            url = items[0].url if items else None
            for e in items:
                text = html.unescape(evidence_text(e))   # decode &#x27;/&amp; before mining claims
                if pricing is None:
                    pm = _PRICE.search(text)
                    if pm:
                        pricing = pm.group(0).strip()
                for sent in _SPLIT.split(text):
                    s = sent.strip()
                    low = s.lower()
                    if 8 <= len(s) <= 140 and any(c in low for c in _FEATURE_CUES):
                        key = low[:50]
                        if key not in seen:
                            seen.add(key)
                            # clean to a short readable phrase — these can be promoted into the
                            # PRD as differentiator features, so they must not be raw chrome.
                            cleaned = _clean_feature(s)
                            if cleaned:
                                feats.append(cleaned)
                    if len(feats) >= args.max_features_each:
                        break
            rows.append(Competitor(name=name, url=url, features=feats, pricing=pricing,
                                   notes=f"{len(items)} evidence item(s)"))

        # most-evidenced competitors first, capped
        rows.sort(key=lambda c: len(c.features), reverse=True)
        rows = rows[: args.max_competitors]
        return ToolResult(ok=True, payload=rows, evidence=ev)


TOOL = BuildCompetitorMatrix()

if __name__ == "__main__":
    import json
    e = [Evidence(source="web", url="https://acme.io/pricing", title="Acme",
                  snippet="Acme supports PDF export and integrates with Slack. Pricing $29/mo."),
         Evidence(source="web", url="https://acme.io/features", title="Acme features",
                  snippet="Offers real-time analytics and a dashboard."),
         Evidence(source="github", url="https://github.com/x/y", title="ignored",
                  snippet="supports webhooks")]
    out = TOOL.run(evidence=[x.model_dump() for x in e])
    print(json.dumps(out.model_dump(), indent=2, default=str))
