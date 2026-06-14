"""aps.scoring — derived 0–10 startup scoring over a run's research/PRD (remaining.md T1.4).

A DERIVED artifact, like the renderer: pure, deterministic, computed on demand. It is NOT a
registry tool (the 52-tool count stays honest) and NOT part of the frozen `StudioState`.
"""
from aps.scoring.startup_score import StartupScore, Dimension, score_startup

__all__ = ["StartupScore", "Dimension", "score_startup"]
