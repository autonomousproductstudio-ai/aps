"""Feature-title quality: pain phrasing → noun phrase; labels are properly cased."""
from __future__ import annotations

from aps.tools.analysis._text import pain_to_feature_title
from aps.state.models import PainPoint, Competitor, Severity
from aps.tools.product.prioritize_features import TOOL as prioritize


def test_complaint_framing_stripped():
    cases = [
        ("The resume parser is broken and keeps dropping valid PDFs", "resume parser"),
        ("Candidate ranking is slow and confusing", "candidate ranking"),
        ("Integration with ATS platforms doesn't work", "integration with ats"),
        ("parser drops PDFs", "parser"),
    ]
    for raw, expected_substr in cases:
        out = pain_to_feature_title(raw).lower()
        assert expected_substr in out, f"{raw!r} → {out!r}"


def test_no_complaint_words_in_title():
    complaint_words = {"broken", "slow", "confusing", "painful", "doesn't", "can't",
                       "drops", "crashes", "fails", "frustrating", "annoying"}
    for raw in [
        "The parser is broken",
        "Auth is slow and painful",
        "Export fails to handle large files",
        "The dashboard crashes on load",
    ]:
        title = pain_to_feature_title(raw).lower()
        assert not any(b in title for b in complaint_words), (
            f"complaint word in {title!r} (from {raw!r})"
        )


def test_leading_article_stripped():
    assert not pain_to_feature_title("The resume parser is broken").lower().startswith("the ")
    assert not pain_to_feature_title("A candidate ranking is slow").lower().startswith("a ")
    assert not pain_to_feature_title("An integration with ATS doesn't work").lower().startswith("an ")


def test_fallback_when_only_complaint():
    # pure complaint with no subject noun → should still return a non-empty string
    result = pain_to_feature_title("Is broken")
    assert isinstance(result, str) and len(result) > 0


# ── adversarial hardening: pronoun-subject complaints must NOT become a feature titled "It"/"I",
#    demand pains name the WANTED capability, and shouts/fragments get a clean theme. ──────────
def test_pronoun_subject_never_becomes_the_title():
    for raw in ["It is unusable", "I can't find a good app", "it is unusable and i hate it",
                "Is broken", "this is slow"]:
        title = pain_to_feature_title(raw)
        toks = title.lower().split()
        # never a bare pronoun / stopword, and never starts with a complaint/aux verb
        assert title.lower() not in {"it", "i", "this", "that", "is", "are"}
        assert toks and toks[0] not in {"it", "i", "is", "are", "cant", "cannot", "doesnt"}
        assert len(title) >= 3


def test_demand_pain_extracts_the_wanted_capability():
    assert "bulk delete" in pain_to_feature_title("no way to bulk delete").lower()
    assert "habit tracker" in pain_to_feature_title("looking for a privacy-first habit tracker").lower()


def test_subjectless_complaint_maps_to_a_theme():
    assert pain_to_feature_title("It is unusable") == "Reliability & stability"
    assert pain_to_feature_title("THIS APP IS USELESS") == "Reliability & stability"


def test_no_dangling_trailing_preposition():
    title = pain_to_feature_title("can't export my data to csv")
    assert not title.lower().rstrip().endswith((" to", " with", " for", " of", " and", " my"))


def test_clean_noun_phrases_are_preserved():
    # the good path must be untouched by the new guards
    assert pain_to_feature_title("The resume parser is broken").lower() == "resume parser"
    assert pain_to_feature_title("Candidate ranking is slow").lower() == "candidate ranking"
    assert "integration with ats" in pain_to_feature_title("Integration with ATS doesn't work").lower()


# ── fragment hardening: orphaned conjunctions, subordinate-clause leads, relative clauses,
#    and stray brackets must not survive into a feature title (the "However about a week",
#    "When following a Google", "API that gives me", "Maintainer]" class of garbage). ─────────
def test_orphaned_leading_conjunction_is_dropped():
    for raw in ["However about a week the sync kept failing",
                "Therefore the dashboard never loaded",
                "Moreover the export was incomplete"]:
        title = pain_to_feature_title(raw).lower()
        assert not title.startswith(("however", "therefore", "moreover", "and ", "but ")), title


def test_subordinate_clause_lead_skipped_for_real_subject():
    # the clause split orphaned "When following a Google…"; the real content follows the ellipsis
    title = pain_to_feature_title("When following a Google… Ads setup is terrible and slow").lower()
    assert not title.startswith(("when ", "where ", "while ", "if ")), title
    assert "ads" in title or "setup" in title, title


def test_relative_clause_reduced_to_head_noun():
    # "API that gives me the wrong totals" → the feature is the head noun phrase, not the clause
    title = pain_to_feature_title("API that gives me the wrong totals").lower()
    assert "that" not in title.split() and "which" not in title.split(), title
    assert "api" in title, title


def test_stray_bracket_is_stripped():
    assert pain_to_feature_title("Maintainer]") == "Maintainer"
    assert "]" not in pain_to_feature_title("Export]") and "[" not in pain_to_feature_title("[Export")


def test_table_stakes_are_title_cased():
    pains = [PainPoint(text="slow export", severity=Severity.HIGH)]
    comps = [
        Competitor(name="A", features=["pdf export support", "slack sync"]),
        Competitor(name="B", features=["pdf export support", "analytics dashboard"]),
    ]
    feats = prioritize.run(pain_points=pains, competitors=comps).payload
    ts = [f for f in feats if f.title.startswith("Table stakes:")]
    assert ts, "expected at least one table-stakes feature"
    label = ts[0].title.split(":", 1)[1].strip()
    assert label[0].isupper(), f"table-stakes label should be title-cased, got: {label!r}"
    assert label != label.lower(), f"label should not be all-lowercase: {label!r}"


def test_differentiator_are_title_cased():
    # one pain, one competitor with one feature → promotes as Differentiator
    pains = [PainPoint(text="slow export", severity=Severity.HIGH)]
    comps = [Competitor(name="A", features=["analytics dashboard"])]
    feats = prioritize.run(pain_points=pains, competitors=comps, min_features=2).payload
    diff = [f for f in feats if f.title.startswith("Differentiator:")]
    if diff:
        label = diff[0].title.split(":", 1)[1].strip()
        assert label[0].isupper(), f"differentiator label should be title-cased, got: {label!r}"
