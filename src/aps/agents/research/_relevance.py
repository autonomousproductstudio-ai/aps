"""Language-level relevance judge for the research compression gate (Phase 3 — ODR's enforcement).

Deterministic lexical scoring (`tools/analysis/score_evidence_relevance`) is the always-on
backstop. When `APS_ENABLE_RELEVANCE_LLM` is set AND a model key is present AND we are NOT under
pytest, `judge()` runs a SECOND, language-level relevance pass — the point where ODR actually
enforces topicality. It judges the lexically-relevant set (plus borderline items) and returns the
subset the model confirms is on-topic: it can both DISCARD a lexical false-positive (a particle-
physics "tracker" paper for an activity-tracker app) and RESCUE a borderline true-positive.

Hermetic by construction: flag-off / no-key / under-pytest ⇒ returns the deterministic set
unchanged, so the suite stays offline and the prior behavior is preserved. The prompt adapts ODR's
`compress_research_system_prompt` ("keep only information relevant to the topic, discard the rest").
"""
from __future__ import annotations

import re
import sys

_SYS = (
    "You are a research relevance filter for a startup studio, applying the deep-research "
    "compression rule: KEEP only evidence relevant to THIS product idea's market, users, "
    "competitors, or problem space; DISCARD anything off-topic (it merely shares a word) or that "
    "is a product advertisement rather than a real user/market signal. Given the idea and a "
    "numbered list of snippets, reply with ONLY the numbers to KEEP, comma-separated (e.g. "
    "'1, 4'). Reply 'none' if none are relevant. No other text."
)


def _enabled(settings) -> bool:
    if not getattr(settings, "enable_relevance_llm", False):
        return False
    if "pytest" in sys.modules:          # keep the suite hermetic/offline
        return False
    try:
        from aps.infra.llm import has_llm_key
        return has_llm_key()
    except Exception:
        return False


def _parse_idxs(text: str, n: int) -> list[int]:
    if "none" in (text or "").lower():
        return []
    out: list[int] = []
    for tok in re.findall(r"\d+", text or ""):
        i = int(tok) - 1                  # 1-based in the prompt
        if 0 <= i < n and i not in out:
            out.append(i)
    return out


def judge(idea: str, all_evidence: list, det_relevant: list, settings, *, min_score: float) -> list:
    """Second, language-level relevance pass over the lexically-relevant set + borderline items.

    Returns the LLM-confirmed on-topic subset — DISCARDING lexical false-positives and RESCUING
    borderline true-positives. No-op (returns `det_relevant`) unless enabled+keyed+not-pytest, or
    on any failure / empty verdict, so a working run is never broken and the suite stays hermetic.
    """
    if not _enabled(settings):
        return det_relevant
    kept_ids = {id(e) for e in det_relevant}
    band_lo = max(0.0, min_score * 0.4)
    borderline = [e for e in all_evidence
                  if id(e) not in kept_ids and band_lo <= (e.relevance or 0.0) < min_score]
    candidates = (det_relevant + borderline)[:20]      # bound the batch (cost + parse reliability)
    if not candidates:
        return det_relevant
    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        from aps.config.settings import get_chat_model
        from aps.infra.llm import acquire_llm
        lines = [f"{i + 1}. {(e.title or '').strip()} — {(e.snippet or '').strip()[:160]}"
                 for i, e in enumerate(candidates)]
        acquire_llm()
        resp = get_chat_model(temperature=0).invoke(
            [SystemMessage(_SYS), HumanMessage(f"Product idea: {idea}\n\nSnippets:\n" + "\n".join(lines))])
        text = resp.content if hasattr(resp, "content") else str(resp)
        judged = [candidates[i] for i in _parse_idxs(str(text), len(candidates))]
        return judged or det_relevant                  # never let a garbage/empty verdict zero it out
    except Exception:
        return det_relevant
