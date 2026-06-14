"""aps.explain — make the studio's reasoning visible (remaining.md T2.5).

For each PRD feature/requirement, surface *why it exists*: the user pain or competitor it
came from, the evidence that grounds it, and a confidence score. Derived, deterministic,
on-demand — NOT a registry tool, NOT in the frozen `StudioState` (decision.md D25).
"""
from aps.explain.explain import (
    FeatureExplanation, Explanation, explain_prd,
)

__all__ = ["FeatureExplanation", "Explanation", "explain_prd"]
