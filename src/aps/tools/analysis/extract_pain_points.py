"""extract_pain_points — mine user complaints/frustrations from evidence.

Finds the actual *complaint sentence* in each evidence item (a sentence carrying a pain cue
AND not dominated by page-chrome), emits typed PainPoint objects with severity + source.
A deterministic noise filter rejects nav/CTA chrome ("Log in · Get Started · Book a Demo"),
forum greetings ("Hi …"), and issue-template scaffolding ("Documentation Request", "Steps to
reproduce") so they can't become the PRD's headline feature. No LLM, no network.
"""
from __future__ import annotations

import html
import re

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Evidence, PainPoint, Severity
from aps.tools.analysis._text import as_evidence_list, evidence_text, clean_label
from aps.tools.analysis._sources import extractable

_HIGH = ("unusable", "broken", "crash", "terrible", "awful", "hate", "waste",
         "blocker", "useless", "nightmare", "infuriating")
_MED = ("annoying", "slow", "confusing", "missing", "lacks", "lack of", "wish",
        "frustrat", "difficult", "painful", "pain point", "cumbersome", "tedious",
        "can't", "cannot", "doesn't work", "no way to", "hard to")
# Unmet-need / demand signals. For a research→PRD product, "I couldn't find an app that does
# X" is a pain just as much as "X is broken" — it's a gap in the market. Treated as MED.
# Without this tier, demand-driven ideas (e.g. a habit tracker) returned ZERO pains because
# the evidence is requests/wishes, not complaint verbs.
_DEMAND = ("looking for", "couldn't find", "can't find", "cant find", "no good",
           "is there a", "is there an", "are there any", "wish there was", "would love",
           "need a ", "need an ", "anyone know", "any recommendation", "recommend a",
           "alternative to", "searching for", "would be great if", "none of", "no app",
           "doesn't exist", "does not exist", "hard to find")
_CUES = _HIGH + _MED + _DEMAND

# Split on sentence punctuation FOLLOWED BY whitespace (or newlines) — not on every dot, so
# "resume.txt", "v2.0", and "U.S." stay intact instead of fragmenting into junk pain candidates.
_SENT = re.compile(r"(?<=[.!?])\s+|\n+")
# unambiguous marketing CTAs (rarely part of a genuine complaint sentence)
_CTA = ("book a demo", "get a demo", "request a demo", "schedule a demo", "watch demo",
        "get started", "start free", "start for free", "start your free", "free trial",
        "try for free", "contact sales", "view pricing", "see pricing", "add to cart",
        "sign up free", "learn more", "request access", "join the waitlist")
# forum / conversational openers and issue-template scaffolding that pollute the pain text.
# These are SPECIFIC multi-word phrases (safe to substring-match near the start) — generic
# single words like "description" are intentionally NOT here (they appear in real complaints).
_GREETING = {"hi", "hey", "hello", "dear", "greetings", "hiya", "yo"}
# Issue-template scaffolding / pure chrome only. NOTE: conversational openers like
# "i was looking" / "i'm trying" are deliberately NOT here — they precede the actual unmet-need
# ("I was looking for X but couldn't find one"), so vetoing them dropped the real pain signal.
_NOISE_PREFIX = (
    "documentation request", "feature request", "bug report", "describe the bug",
    "steps to reproduce", "expected behavior", "actual behavior", "is your feature request",
    "describe the solution", "describe alternatives", "additional context",
    "acceptance criteria", "read more",
)
# A URL or bare domain/path — these carry cue words ("…/broken-links") but are never a complaint.
_URL = re.compile(r"https?://\S+|www\.\S+|\b[\w-]+\.(?:com|io|org|net|co|ai|app|dev|gg|xyz)\b\S*", re.I)
# Site-navigation labels. Several of these in a row (no sentence connectives) = a nav bar,
# not a sentence — even when one of them happens to be a pain cue ("… Login broken").
_NAVWORD = {"home", "products", "product", "pricing", "about", "login", "signin", "contact",
            "blog", "features", "docs", "support", "careers", "menu", "dashboard", "account",
            "settings", "help", "faq", "resources", "company", "solutions", "overview"}
_CONNECTIVE = re.compile(r"\b(?:the|and|is|are|to|a|of|for|with|that|but|my|it|i|this|was|"
                         r"when|because|so|they|you|we|on|in|no|not)\b")


# Leading rating / score prefixes a formatter prepends to GitHub/HN snippets ("4★", "★★",
# "120 points") — never part of the complaint.
_RATING_LEAD = re.compile(r"^\s*(?:[★⭐✪☆»>•]+|\d+\s*(?:★|⭐|pts?|points?|upvotes?|stars?))[\s,:|.–-]*", re.I)
# Self-promotion / product-DESCRIPTION markers — a pitch or a repo blurb, not a user complaint.
_PITCH = ("we built", "i built", "we made", "i made", "we created", "i created", "built this",
          "we're building", "we are building", "i'm building", "im building", "introducing ",
          "check out", "show hn", "is an open", "is a community", "designed to", "our app",
          "our tool", "our platform", "just launched", "we launched", "launching ",
          "was born out", "born out of", "came out of", "we work hard", "work hard to")
# Opinion-SOLICITATION: a forum post asking the reader for input, not stating a pain itself
# ("What are your thoughts or pain points on…"). Distinct from a rhetorical complaint question
# ("Why do companies make it so hard…"), which we keep.
_SOLICIT = ("what are your", "what are you", "what do you think", "what do you all",
            "anyone else", "am i the only", "your thoughts", "any thoughts", "thoughts?",
            "curious what", "what would you", "would love your", "let me know what")
# Marketing / listicle / article-title leads — a headline, not a user complaint
# ("Why You Need a Subscription Tracker App", "The 12 Best AI Recruiting Tools").
_TITLE_LEAD = ("why you need", "how to ", "the best ", "ultimate guide", "complete guide",
               "a guide to", "your guide to", "everything you need", "top 10", "top 5",
               "the 1", "the 2", "best ways", "reasons to")
# Positive idioms that contain a complaint cue but express PRAISE/surprise, not a pain
# ("honestly can't believe this worked", "works great").
_POSITIVE = ("can't believe", "cant believe", "works great", "so good", "highly recommend",
             "game changer", "game-changer", "love how", "love that", "best thing")
# Product/repo DESCRIPTION masquerading as a pain ("ZeroTrace is a powerful ethical hacking tool
# for anonymization", "Foo is an open-source CLI"). A definition of a product, not a user
# complaint. Only barred when NO complaint actually follows the description (see _looks_like_noise),
# so "ActivityWatch is a free time tracker but idle detection fails" still yields the pain.
_PRODUCT_DESC = re.compile(
    r"\b[\w][\w.\-]* is an?\s+(?:[\w\-]+\s+){0,3}"
    r"(?:tool|app|application|platform|library|framework|service|cli|extension|sdk|api|plugin"
    r"|wrapper|client|server|dashboard|suite|bot|engine|package|module|program|software|website"
    r"|site|product|solution|system|utility|daemon|gem|crate|project|repo|repository)\b", re.I)
_PRODUCT_DESC_COMPLAINT = re.compile(
    r"\b(but|however|yet|though|unfortunately|sadly|except|annoying|broken|crash\w*|fail\w*|slow"
    r"|buggy|unreliable|can'?t|cannot|doesn'?t|won'?t|lacks?|missing|no way)\b", re.I)
# Pure listing metadata ("1 points, 0 comments") — no content to mine.
_META = re.compile(r"^\s*\d+\s*(?:points?|pts?|comments?|upvotes?|votes?)\b", re.I)
# VCS-internal terms: a "missing/doesn't exist" gripe about these is a dev meta-issue, not a pain.
_VCS = re.compile(r"\b(?:repo|repository|readme|changelog|commit|branch|pull request|\.txt|\.md)\b", re.I)
# People/role nouns: "looking for employers/candidates" is seeking PEOPLE, not a product gap.
_SEEK_ROLES = {"employer", "employers", "candidate", "candidates", "people", "someone", "anyone",
               "developer", "developers", "engineer", "engineers", "freelancer", "freelancers",
               "client", "clients", "recruiter", "recruiters", "applicant", "applicants",
               "talent", "staff", "employee", "employees", "cofounder", "cofounders"}
_SEEK = re.compile(r"\b(?:looking for|looking to hire|seeking|hiring|in search of)\s+(?:an?\s+|the\s+|some\s+)?(\w+)", re.I)
# Trailing function words that leave a dangling, truncated-looking pain ("… and", "… the").
_TRAIL_FN = {"and", "or", "but", "the", "a", "an", "to", "of", "for", "with", "is", "are",
             "in", "on", "at", "that", "this", "we", "i", "it", "so", "because", "cause", "my"}


def _strip_lead(text: str) -> str:
    return re.sub(r"^[^\w]+", "", text or "").strip()


def _is_title_heading(s: str) -> bool:
    """A Title-Case headline ('The 7 Best Subscription Apps', 'When Websites Make It Hard') is a
    marketing/article title, not a user complaint — real forum/issue prose is lowercase. True when
    most words are Capitalized. (Proper-noun-naming complaints stay well under the ratio because
    their verbs/articles are lowercase.)"""
    alpha = [w for w in s.split() if any(c.isalpha() for c in w)]
    if len(alpha) < 4:
        return False
    caps = sum(1 for w in alpha if w[0].isupper())
    return caps / len(alpha) >= 0.6


def _looks_like_noise(sentence: str) -> bool:
    """True if a candidate sentence is page-chrome / a URL / greeting / issue-template
    scaffolding rather than a genuine complaint — even if it carries a pain cue."""
    s = _strip_lead(sentence)
    low = s.lower()
    if len(low) < 8:
        return True
    # URL-dominated: drop URLs/domains; if little real prose remains, it's just a link.
    if len(re.sub(r"[^a-z ]", "", _URL.sub(" ", low)).replace(" ", "")) < 8:
        return True
    words = low.split()
    # A complaint is prose: it needs ≥2 plain word tokens. A lone path fragment like
    # "com/broken-links-guide" (a URL split on its dot) has none and must be rejected.
    if sum(1 for w in words if re.match(r"^[a-z][a-z'-]*$", w) and len(w) >= 2) < 2:
        return True
    if words and words[0].strip(",.!:;") in _GREETING:
        return True
    if any(p in low[:60] for p in _NOISE_PREFIX):    # template/opener near the start (after a title)
        return True
    if sum(1 for c in _CTA if c in low) >= 2:                 # jammed nav CTAs
        return True
    if sum(1 for w in words if w.strip(",.!:;|·-") in _NAVWORD) >= 3:   # nav-bar labels in a row
        return True
    if len(re.findall(r"[A-Z][a-z]+", s)) >= 4 and not _CONNECTIVE.search(low):  # chrome, no prose
        return True
    if _is_title_heading(s):                        # Title-Case article/listicle headline
        return True
    if _META.match(s):                              # "1 points, 0 comments" — listing metadata
        return True
    if any(p in low for p in _PITCH):               # a product pitch / repo description, not a pain
        return True
    pd = _PRODUCT_DESC.search(s)                     # "X is a powerful Y tool" definition…
    if pd and not _PRODUCT_DESC_COMPLAINT.search(low[pd.end():]):  # …with no complaint after it
        return True
    if any(p in low for p in _POSITIVE):            # praise/surprise idiom, not a complaint
        return True
    if any(p in low for p in _SOLICIT):             # forum question soliciting input, not a pain
        return True
    if any(low.startswith(t) for t in _TITLE_LEAD):  # marketing / listicle headline
        return True
    if _VCS.search(low) and any(d in low for d in ("does not exist", "doesn't exist",
                                                   "not found", "missing", "no way")):
        return True                                  # a VCS/file gripe, not a user pain
    m = _SEEK.match(s)                               # "looking for employers" → seeking people
    if m and m.group(1).lower() in _SEEK_ROLES:
        return True
    return False


def _pick_pain(text: str) -> tuple[str, Severity] | None:
    """The first genuine complaint sentence (cue-bearing, not noise) + its severity."""
    for seg in _SENT.split(text or ""):
        s = _RATING_LEAD.sub("", seg.strip()).strip()   # drop a leading "4★" / "120 points"
        if not (8 <= len(s) <= 220):
            continue
        low = s.lower()
        sev = (Severity.HIGH if any(c in low for c in _HIGH)
               else Severity.MED if any(c in low for c in _MED) or any(c in low for c in _DEMAND)
               else None)
        if sev is None or _looks_like_noise(s):
            continue
        # Keep the pain a FULL clause (not an 8-word stub that dangles on "… and"/"… the"):
        # widen the cap, then trim trailing function words so it reads as a complete thought.
        cleaned = clean_label(s, max_words=20, max_chars=160)
        toks = cleaned.split()
        while toks and toks[-1].lower().strip(",.;:!?") in _TRAIL_FN:
            toks.pop()
        cleaned = " ".join(toks).strip(" -–—:.,")
        if cleaned and len(re.sub(r"[^A-Za-z]", "", cleaned)) >= 6:
            return cleaned, sev
    return None


class Args(BaseModel):
    evidence: list[Evidence] = Field(default_factory=list)
    max_points: int = Field(15, ge=1, le=50)


class ExtractPainPoints(BaseTool):
    name = "extract_pain_points"
    namespace = "analysis"
    description = (
        "Extract concrete user pain points from gathered evidence, each tagged with a "
        "severity and linked to its source. Use during compression to turn raw forum/"
        "issue text into the structured pains that drive the PRD."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        # Structural gate (same as the competitor matrix): a job posting or a market-research
        # report is never a user pain — bar those kinds before extraction.
        ev = extractable(as_evidence_list(args.evidence))
        points: list[PainPoint] = []
        seen: set[str] = set()
        for e in ev:
            # html.unescape first: raw snippets carry entities like &#x27; / &amp; that, left
            # encoded, leak into pains/features as junk ("I& x27" once the punctuation is stripped).
            # Try snippet first — avoids title-template contamination ("Feature request: …")
            # blocking the pain cue that lives in the snippet. Falls back to combined
            # title+snippet so Reddit/HN post-titles-as-pain-sentences still work.
            snippet = html.unescape((getattr(e, "snippet", "") or "").strip())
            picked = (_pick_pain(snippet) if snippet else None) or _pick_pain(html.unescape(evidence_text(e)))
            if picked is None:
                continue
            summary, sev = picked
            key = summary.lower()[:60]
            if key in seen:
                continue
            seen.add(key)
            points.append(PainPoint(text=summary, severity=sev, source_evidence=[e]))
            if len(points) >= args.max_points:
                break
        # surface highest severity first
        order = {Severity.HIGH: 0, Severity.MED: 1, Severity.LOW: 2}
        points.sort(key=lambda p: order[p.severity])
        return ToolResult(ok=True, payload=points, evidence=ev)


TOOL = ExtractPainPoints()

if __name__ == "__main__":
    import json
    e = [Evidence(source="reddit", url="https://r/1", title="rant",
                  snippet="The parser is broken and keeps dropping my resume, I hate it."),
         Evidence(source="hackernews", url="https://h/2", title="meh",
                  snippet="It's a bit slow and the export is missing.")]
    out = TOOL.run(evidence=[x.model_dump() for x in e])
    print(json.dumps(out.model_dump(), indent=2, default=str))
