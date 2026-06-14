"""_text — shared, dependency-free text helpers for the analysis tools.

Leading underscore → the registry skips this module (it isn't a tool). Everything
here is deterministic: analysis tools are mechanical operations over retrieved data,
not LLM calls (the model-driven judgment lives at the agent layer).
"""
from __future__ import annotations

import re

_WORD = re.compile(r"[a-z][a-z0-9+\-]{2,}")

STOPWORDS = set("""
the a an and or but if then this that these those for to of in on at by with from as is
are was were be been being it its do does did have has had not no you your i we they he she
will would can could should about into over under more most some any all out up down can't
just like get got use using used able new one two via per etc com www https http
""".split())


def tokenize(text: str) -> list[str]:
    return [w for w in _WORD.findall((text or "").lower()) if w not in STOPWORDS]


def evidence_text(e) -> str:
    """Combined searchable text for one Evidence (works for objects or dicts)."""
    if isinstance(e, dict):
        return f"{e.get('title') or ''} {e.get('snippet') or ''}"
    return f"{getattr(e, 'title', '') or ''} {getattr(e, 'snippet', '') or ''}"


def as_evidence_list(items):
    """Coerce a list of dicts/Evidence into Evidence objects."""
    from aps.state.models import Evidence
    out = []
    for it in items or []:
        if isinstance(it, Evidence):
            out.append(it)
        elif isinstance(it, dict):
            try:
                out.append(Evidence(**it))
            except Exception:
                pass
    return out


def pluralize(word: str) -> str:
    """English pluralization good enough for REST collection names — never a bare double-s.

    'Resume'->'Resumes', 'Category'->'Categories', 'Class'->'Classes', 'Box'->'Boxes'.
    """
    w = (word or "").strip()
    if not w:
        return "items"
    low = w.lower()
    if low.endswith(("s", "x", "z", "ch", "sh")):
        return w + "es"
    if low.endswith("y") and len(w) > 1 and low[-2] not in "aeiou":
        return w[:-1] + "ies"
    return w + "s"


# --------------------------------------------------------------------------- #
# clean_label — normalize raw issue/snippet text into a short, clean human label
# --------------------------------------------------------------------------- #
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")          # [text](url) -> text
_TAG = re.compile(r"<[^>]+>")                          # html tags
_MD = re.compile(r"[`*_>#~]+")                         # md emphasis/headers/quotes/code
_WS2 = re.compile(r"\s+")
_BOILERPLATE = re.compile(
    r"\b(solve|feature request|bug report|enhancement|checklist|prerequisites"
    r"|is your feature request related to a problem"
    r"|please\s+descr\w*|describe the (solution|alternatives?|bug|feature)"
    r"|additional context|steps to reproduce|to reproduce"
    r"|expected behaviou?r|actual behaviou?r|current behaviou?r"
    r"|hey\s+hn|show\s+hn|ask\s+hn|hi\s+(all|everyone|there|folks)|hello"
    r"|i\s+(built|made|created|wrote)|we\s+(built|made|created))\b[:.,\s\-]*",
    re.I,
)
_CLAUSE = re.compile(r"(?<=[.!?])\s|[\n;…—–]| - ")  # sentence / newline / ellipsis / dash
# A clause that LEADS with a subordinating/continuation conjunction lost its subject to the
# clause split ("When following a Google…", "However the export…") — it's a fragment, not a
# self-contained statement. clean_label skips such clauses in favour of the next content clause.
_CLAUSE_SKIP_LEAD = re.compile(
    r"^(and|but|so|or|yet|also|plus|however|therefore|meanwhile|furthermore|moreover"
    r"|nevertheless|thus|hence|otherwise|besides|although|though|while|whereas|when|where"
    r"|if|because|since|after|before|unless|as)\b", re.I)


# --------------------------------------------------------------------------- #
# pain_to_feature_title — transform a complaint sentence into a feature noun phrase
# --------------------------------------------------------------------------- #
_ARTICLE_LEAD = re.compile(r"^(the\s+|a\s+(?=[a-zA-Z]{2,})|an\s+)", re.I)
# Leading conjunction/subordinator on a sentence that lost its prior context ("And the
# postmortem was …", "However about a week …", "When following a Google …").
_CONJ_LEAD = re.compile(
    r"^(and|but|so|or|yet|also|plus|however|therefore|meanwhile|furthermore|moreover"
    r"|nevertheless|thus|hence|otherwise|besides|although|though|while|whereas|when|where"
    r"|if|because|since)\s+", re.I)
# A relative clause ("API that gives me…", "Export which fails…") — the feature is the head
# noun phrase before the marker, not the whole clause. Cut here once a head word survives.
_RELCLAUSE_CUT = re.compile(r"\s+(that|which|who|whom|whose|where|when)\s+\w", re.I)
# Leading pronoun / expletive subjects that a complaint-cut can leave behind ("It is broken"
# → "It"). These are never a feature name, so strip them before taking the noun phrase.
_PRONOUN_LEAD = re.compile(r"^(it|i|we|they|you|he|she|this|that|there|its|my|our|their)\s+", re.I)
# Degenerate single-token "titles" — a bare pronoun/stopword is not a feature.
_STOPWORD_TITLES = {"it", "i", "we", "they", "you", "he", "she", "this", "that", "there",
                    "the", "a", "an", "is", "are", "my", "our", "its", "their", "of", "to"}
# A title that LEADS with one of these is a complaint fragment, not a capability noun phrase
# ("Is unusable", "Fails to export") → re-map to a theme instead of shipping the fragment.
_VERB_LEAD = {"is", "are", "was", "were", "be", "been", "cant", "cannot", "couldnt",
              "doesnt", "dont", "wont", "fails", "fail", "failed", "keeps", "keep", "not"}
# Trailing function words that read as a dangling fragment at the end of a title.
_TRAIL_STOP = {"to", "with", "for", "of", "a", "an", "the", "and", "my", "your", "our",
               "in", "on", "at", "is", "are", "that", "this"}
# Demand pains name the WANTED thing, not a broken one: the feature is what follows the lead.
_DEMAND_LEAD = re.compile(
    r"\b(?:no way to|can'?t find|can'?t|cannot|could ?n'?t find|couldnt find|looking for|"
    r"searching for|wish there was|would love|need an? |needs an? |is there an? |"
    r"are there any|alternative to)\s+(.+)", re.I)
# Last resort for a subject-less complaint: name the capability by the complaint category.
_THEME = (
    (("unusable", "broken", "crash", "useless", "unreliable", "buggy", "fails",
      "doesn't work", "dont work", "does not work", "won't work"), "Reliability & stability"),
    (("slow", "lag", "latency", "sluggish"), "Performance & speed"),
    (("confusing", "hard to", "difficult", "complicated", "cumbersome", "tedious", "clunky"),
     "Usability & onboarding"),
    (("expensive", "pricey", "costly", "overpriced"), "Pricing & value"),
    (("missing", "lacks", "lack of", "no app", "doesnt exist", "does not exist"),
     "Feature coverage"),
)


def _theme_for(text: str) -> str | None:
    low = (text or "").lower()
    for cues, label in _THEME:
        if any(c in low for c in cues):
            return label
    return None

# Where a pain sentence stops describing the domain and starts voicing the complaint.
# Everything from this match onward is dropped; what remains is the subject noun phrase.
_COMPLAINT_CUT = re.compile(
    r"\b("
    r"is\s+(broken|slow|missing|confusing|painful|hard|difficult|terrible|awful"
    r"|unusable|useless|frustrating|annoying|unreliable|buggy|limited"
    r"|slower|harder|worse|weaker|costlier|messier|clunkier|buggier|trickier|riskier|fiercer)"
    r"|are\s+(broken|slow|missing|confusing|painful|terrible|unusable|useless|frustrating"
    r"|slower|harder|worse|weaker|fewer|costlier)"
    r"|doesn'?t\s+work|don'?t\s+work|won'?t\s+\w+"
    r"|can'?t\s+\w+|cannot\s+\w+"
    r"|(fails?|failing|failed)(\s+to)?"
    r"|keeps?\s+(dropping|crashing|failing|losing|breaking)"
    r"|(drops?|crashes?|breaks?)\s"
    r"|and\s+(we|i|you)\s+(waste|can'?t|lose|spend)"
    r")\b",
    re.I,
)


def pain_to_feature_title(text: str, max_words: int = 4) -> str:
    """Turn a pain-point sentence into a short product-feature noun phrase (no LLM).

    'The resume parser is broken and keeps dropping' → 'Resume Parser'
    'Integration with ATS platforms doesn't work'   → 'Integration with ATS'
    'Candidate ranking is slow and confusing'        → 'Candidate Ranking'
    """
    if text and text.isupper() and len(text) > 6:  # an all-caps shout → name the theme, not "APP"
        shout = _theme_for(text)
        if shout:
            return shout
    cleaned = clean_label(text)                    # strip boilerplate/markdown first
    # 1) demand pains ("no way to bulk delete", "looking for an offline tracker") → the feature
    #    is the WANTED capability that follows the lead, not the complaint.
    dm = _DEMAND_LEAD.search(cleaned)
    if dm:
        s = dm.group(1)
    else:
        s = cleaned
        m = _COMPLAINT_CUT.search(s)
        if m:
            s = s[: m.start()].strip(" -–—:.,")    # drop from complaint signal onward
    s = _CONJ_LEAD.sub("", s).strip()              # drop a leading "And/However/When" continuation
    s = _PRONOUN_LEAD.sub("", _ARTICLE_LEAD.sub("", s).strip()).strip()  # drop leading the/a/pronoun
    s = _ARTICLE_LEAD.sub("", s).strip()           # (a demand object may have its own article)
    rc = _RELCLAUSE_CUT.search(s)                  # "API that gives me" → head noun phrase "API"
    if rc and len(re.sub(r"[^A-Za-z]", "", s[: rc.start()])) >= 3:
        s = s[: rc.start()].strip(" -–—:.,")
    words = s.split()[:max_words]
    while words and words[-1].lower().strip(",.") in _TRAIL_STOP:   # no dangling "… to"/"… my"
        words.pop()
    result = " ".join(words).strip(" -–—:.,[](){}")
    first = result.split()[0].lower().strip("',.") if result else ""

    # Degenerate / complaint-fragment guard: a bare pronoun, a <3-letter scrap, or a verb-led
    # fragment ("Is unusable") is not a capability. Map to a theme; never emit "It"/"I"/junk.
    if (not result or result.lower() in _STOPWORD_TITLES
            or len(re.sub(r"[^A-Za-z]", "", result)) < 3 or first in _VERB_LEAD):
        theme = _theme_for(text)
        if theme:
            return theme
        fb = _PRONOUN_LEAD.sub("", clean_label(text, max_words=max_words + 2)).strip(" -–—:.,")
        result = fb or result
        if not result or result.lower() in _STOPWORD_TITLES:
            return "Core capability"                # honest generic; never a pronoun
    if result.isupper() and len(result) > 3:        # normalize ALL-CAPS shout → Title Case
        result = result.title()
    return result[0].upper() + result[1:]


def clean_label(text: str, max_words: int = 8, max_chars: int = 64) -> str:
    """Turn raw issue/snippet text into a short, clean label.

    Strips markdown/HTML and issue-template boilerplate ('Solve:', '## Feature Request:',
    'Please describe…'), takes the first clause, and truncates at a WORD boundary (never
    mid-word, so 'Please descr' can't become a 'Descr' entity). Deterministic; falls back to
    a trimmed snippet if nothing meaningful survives.
    """
    raw = text or ""
    s = _LINK.sub(r"\1", raw)
    s = _TAG.sub(" ", s)
    s = _MD.sub(" ", s)
    s = _BOILERPLATE.sub(" ", s)
    s = re.sub(r"^\s*\[[^\]]*\]\s*", " ", s)         # drop a leading "[label]" prefix whole
    s = _WS2.sub(" ", s).strip(" -–—:•|.[](){}\t")
    parts = [p.strip() for p in _CLAUSE.split(s) if any(c.isalpha() for c in p)]
    # Prefer the first SELF-CONTAINED clause: skip leading fragments ("When following a Google")
    # that the clause split orphaned, but fall back to the first clause if every clause is one.
    s = next((p for p in parts if not _CLAUSE_SKIP_LEAD.match(p)), (parts[0] if parts else "")).strip()
    if not s:
        s = _WS2.sub(" ", raw).strip()
    words = s.split()
    if len(words) > max_words:
        s = " ".join(words[:max_words])
    if len(s) > max_chars:
        s = (s[:max_chars].rsplit(" ", 1)[0] or s[:max_chars])
    s = s.strip(" -–—:•|.,[](){}").strip()
    if not s:
        return _WS2.sub(" ", raw).strip()[:max_chars]
    return s[0].upper() + s[1:]
