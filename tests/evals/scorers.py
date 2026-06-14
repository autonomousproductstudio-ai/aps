"""E1..E10 scorers (EVALUATION.md §2) — deterministic functions over a run's outputs.

These are pure scorers: given a tool-call trace and the produced PRD, return a number/
bool. They have NO dependency on the orchestrator, so they are unit-testable on their
own (see tests/unit/test_scorers.py). `run_eval.py` wires these to live runs (P1).

A `trace` here is a list of tool-call records: dicts like
    {"tool": "github_list_issues", "namespace": "retrieval", "evidence": [Evidence|dict]}
A `prd` is a PRD model (or an equivalent dict).
"""
from __future__ import annotations

import re


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{4,}", (text or "").lower())}


def _evidence_iter(trace):
    for call in trace or []:
        for ev in (call.get("evidence") if isinstance(call, dict) else []) or []:
            yield ev


def _ev_field(ev, name: str):
    return ev.get(name) if isinstance(ev, dict) else getattr(ev, name, None)


def _prd_field(prd, name: str):
    if isinstance(prd, dict):
        return prd.get(name)
    return getattr(prd, name, None)


def selection_validity(trace) -> float:  # E1
    """Fraction of tool calls that selected a real, known tool name."""
    from aps.tools.registry import all_tools
    known = {t.name for t in all_tools()}
    calls = [c.get("tool") for c in (trace or []) if isinstance(c, dict)]
    if not calls:
        return 0.0
    return round(sum(1 for name in calls if name in known) / len(calls), 3)


def source_diversity(trace) -> int:  # E3
    """Number of distinct evidence sources gathered across the run."""
    return len({_ev_field(ev, "source") for ev in _evidence_iter(trace)
                if _ev_field(ev, "source")})


def evidence_coverage(prd) -> float:  # E4
    """Fraction of PRD features whose wording overlaps some cited source snippet."""
    features = _prd_field(prd, "features") or []
    sources = _prd_field(prd, "sources") or []
    if not features:
        return 0.0
    source_toks = set()
    for s in sources:
        source_toks |= _tokens((_ev_field(s, "title") or "") + " " + (_ev_field(s, "snippet") or ""))
    if not source_toks:
        return 0.0
    covered = 0
    for f in features:
        title = f.get("title") if isinstance(f, dict) else getattr(f, "title", "")
        desc = f.get("description") if isinstance(f, dict) else getattr(f, "description", "")
        if _tokens(f"{title} {desc}") & source_toks:
            covered += 1
    return round(covered / len(features), 3)


def prd_schema_valid(prd) -> bool:  # E6
    """True iff the PRD validates against the contract and carries real content."""
    from aps.state.models import PRD
    try:
        obj = prd if isinstance(prd, PRD) else PRD.model_validate(prd)
    except Exception:
        return False
    return bool(obj.idea) and bool(obj.features) and bool(obj.requirements)


def prd_feature_count(prd) -> int:  # E11 (W3/W5 regression guard)
    """Number of features in the PRD. The eval guards `>= 3` on rich-signal ideas so the
    thin-PRD problem (a one-feature doc) can't regress unnoticed."""
    features = _prd_field(prd, "features") or []
    return len(features)


def meets_feature_floor(prd, floor: int = 3) -> bool:
    """Whether the PRD clears the feature floor (W3). Reported per gold idea by run_eval."""
    return prd_feature_count(prd) >= floor


# --------------------------------------------------------------------------- #
# Relevance metrics (E12–E14) — lock the research-quality work so it can't regress.
# --------------------------------------------------------------------------- #
def evidence_relevance_rate(idea: str, evidence, threshold: float = 0.15) -> float:  # E12
    """Fraction of evidence that scores at/above the relevance threshold for the idea.

    The headline guard: on-topic research should keep almost only on-topic evidence (target
    >= 0.8). A drop means the gate/query-planning regressed and junk is flowing back in."""
    from aps.tools.analysis.score_evidence_relevance import idea_profile, relevance_score
    items = list(evidence or [])
    if not items:
        return 0.0
    prof = idea_profile(idea)
    on = sum(1 for e in items if relevance_score(prof, e) >= threshold)
    return round(on / len(items), 3)


def off_topic_rejection_rate(idea: str, junk_evidence, threshold: float = 0.15) -> float:  # E13
    """Fraction of KNOWN-JUNK items the gate would reject (score < threshold). Target 1.0 —
    seed this with the off-topic fixtures (sales jobs, "Stake bonus", sun-position API)."""
    from aps.tools.analysis.score_evidence_relevance import idea_profile, relevance_score
    items = list(junk_evidence or [])
    if not items:
        return 1.0
    prof = idea_profile(idea)
    rejected = sum(1 for e in items if relevance_score(prof, e) < threshold)
    return round(rejected / len(items), 3)


# A feature title that LEADS with a conjunction/subordinator is an orphaned sentence fragment.
_FRAGMENT_TITLE = re.compile(
    r"^(however|therefore|moreover|furthermore|meanwhile|nevertheless|thus|hence|otherwise"
    r"|besides|although|though|whereas|while|when|where|because|since|unless|and|but|so|or|yet"
    r"|implement|solve|fix|todo)\b[\s:.\-]", re.I)
# Template/scaffolding or truncation markers that should never appear in a clean feature title.
_BAD_TITLE_MARKERS = ("]", "[", "feature request", "steps to reproduce", "describe the",
                      "documentation request", "...")


def feature_titles_clean(prd) -> bool:  # E14
    """True iff no PRD feature title is a raw fragment — never leads with a conjunction
    ("However…/When…/Implement:"), never carries a stray bracket or template/truncation marker."""
    features = _prd_field(prd, "features") or []
    for f in features:
        title = (f.get("title") if isinstance(f, dict) else getattr(f, "title", "")) or ""
        t = title.strip()
        low = t.lower()
        if _FRAGMENT_TITLE.match(t):
            return False
        if any(m in low for m in _BAD_TITLE_MARKERS):
            return False
    return True
