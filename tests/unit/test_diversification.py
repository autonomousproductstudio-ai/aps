"""Parallel diversification (multipleAPIplan P10) — fan-out units spread across providers."""
from __future__ import annotations

import pytest

from aps.agents.research.supervisor import unit_providers
from aps.config.failover import build_failover_model, FailoverChatModel
from aps.config.settings import get_chat_model

_CHAIN_KEYS = ("APS_PROVIDER_CHAIN", "GROQ_API_KEY", "CEREBRAS_API_KEY",
               "GEMINI_API_KEY", "NVIDIA_API_KEY")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for v in _CHAIN_KEYS:
        monkeypatch.delenv(v, raising=False)


# ── unit_providers (the round-robin assignment) ───────────────────────────────
def test_no_diversification_without_chain():
    assert unit_providers(3) == [None, None, None]


def test_no_diversification_with_single_provider(monkeypatch):
    monkeypatch.setenv("APS_PROVIDER_CHAIN", "groq,gemini")
    monkeypatch.setenv("GROQ_API_KEY", "k")          # only groq available → 1-provider pool
    assert unit_providers(3) == [None, None, None]


def test_three_units_get_three_distinct_providers(monkeypatch):
    monkeypatch.setenv("APS_PROVIDER_CHAIN", "groq,cerebras,gemini")
    for k in ("GROQ_API_KEY", "CEREBRAS_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setenv(k, "k")
    assigned = unit_providers(3)
    # router may reorder by fit, but all three are distinct → 3 quotas in parallel
    assert len(set(assigned)) == 3
    assert set(assigned) == {"groq", "cerebras", "gemini"}


def test_diversify_off_makes_all_units_use_chain_head(monkeypatch):
    # APS_RESEARCH_DIVERSIFY=false → every unit uses the default chain head (e.g. paid OpenAI) +
    # failover, instead of spreading across (possibly exhausted) free providers.
    monkeypatch.setenv("APS_PROVIDER_CHAIN", "openai,nim,gemini")
    for k in ("OPENAI_API_KEY", "NVIDIA_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setenv(k, "k")
    monkeypatch.setenv("APS_RESEARCH_DIVERSIFY", "false")
    assert unit_providers(3) == [None, None, None]
    monkeypatch.setenv("APS_RESEARCH_DIVERSIFY", "true")    # default behavior still diversifies
    assert len(set(unit_providers(3))) == 3


def test_more_units_than_providers_round_robin(monkeypatch):
    monkeypatch.setenv("APS_PROVIDER_CHAIN", "groq,gemini")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    assigned = unit_providers(5)
    assert set(assigned) == {"groq", "gemini"}        # round-robin over the routed 2-provider pool
    assert assigned[0] != assigned[1] and assigned[0] == assigned[2] == assigned[4]


# ── prefer (the per-unit head-of-chain) ───────────────────────────────────────
def test_prefer_moves_provider_to_head(monkeypatch):
    monkeypatch.setenv("APS_PROVIDER_CHAIN", "groq,gemini,cerebras")
    for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "CEREBRAS_API_KEY"):
        monkeypatch.setenv(k, "k")
    m = build_failover_model(prefer="gemini")
    assert m.providers == ["gemini", "groq", "cerebras"]   # preferred first, rest as backup


def test_prefer_not_in_chain_is_ignored(monkeypatch):
    monkeypatch.setenv("APS_PROVIDER_CHAIN", "groq,gemini")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    assert build_failover_model(prefer="nim").providers == ["groq", "gemini"]


def test_get_chat_model_prefer_threads_through(monkeypatch):
    monkeypatch.setenv("APS_PROVIDER_CHAIN", "groq,gemini")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    m = get_chat_model(prefer="gemini")
    assert isinstance(m, FailoverChatModel) and m.providers[0] == "gemini"
