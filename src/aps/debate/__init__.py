"""aps.debate — the studio argues with itself (remaining.md T2.3).

A skeptic "Risk agent" (`run_risk`) builds the case AGAINST a venture from the same
evidence; `run_debate` weighs that against the build case (research positives + the
Startup Score) and returns a Build / Pivot / Don't verdict. Derived, deterministic,
on-demand — NOT a registry tool, NOT in the frozen `StudioState` (decision.md D23).
"""
from aps.debate.debate import (
    RiskFlag, RiskAssessment, Debate, run_risk, run_debate,
)

__all__ = ["RiskFlag", "RiskAssessment", "Debate", "run_risk", "run_debate"]
