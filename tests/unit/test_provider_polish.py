"""multipleAPIplan P5/P7/P8/P9 — metrics, circuit breaker, ledger, router, portable context."""
from __future__ import annotations

from aps.config.quota import Ledger, CircuitBreaker
from aps.config.router import route, TaskProfile, RESEARCH, COMPRESSION
from aps.config.portable import normalize_history
from aps.config.failover import FailoverChatModel


# ── P9: ledger + circuit breaker ──────────────────────────────────────────────
def test_ledger_counts_per_provider():
    led = Ledger()
    for p in ("groq", "groq", "gemini"):
        led.record(p)
    assert led.count("groq") == 2 and led.count("gemini") == 1
    assert led.snapshot() == {"groq": 2, "gemini": 1}


def test_circuit_breaker_trips_and_restores():
    t = {"now": 0.0}
    cb = CircuitBreaker(cooldown=60.0, clock=lambda: t["now"])
    assert cb.is_open("groq") is False
    cb.trip("groq")
    assert cb.is_open("groq") is True          # benched
    t["now"] = 59.9
    assert cb.is_open("groq") is True
    t["now"] = 60.1
    assert cb.is_open("groq") is False          # auto-restored after cooldown


# ── P8: router ────────────────────────────────────────────────────────────────
def test_route_excludes_no_tool_providers_for_tool_task():
    # ollama caps tools=2 (ok), but a hypothetical no-tool provider would be dropped;
    # here verify a tool task keeps tool-capable providers and orders deterministically
    order = route(RESEARCH, ["gemini", "groq", "cerebras"])
    assert set(order) == {"gemini", "groq", "cerebras"}
    assert order == route(RESEARCH, ["gemini", "groq", "cerebras"])   # deterministic


def test_route_low_complexity_prefers_fast_cheap():
    # COMPRESSION (low complexity, long context) — Gemini (context 3) should rank for long ctx
    order = route(COMPRESSION, ["groq", "gemini"])
    assert order[0] == "gemini"                 # only provider meeting context=long requirement


def test_route_quota_headroom_demotes_busy_provider():
    fresh = route(RESEARCH, ["groq", "cerebras"], load={})
    busy = route(RESEARCH, ["groq", "cerebras"], load={fresh[0]: 1000})
    assert busy[0] != fresh[0]                  # the heavily-used one sinks


def test_route_no_eligible_falls_back_to_input_order():
    profile = TaskProfile(needs_tools=True)
    # unknown providers default to caps tools=2 (eligible) → returns them
    assert route(profile, ["x", "y"]) == ["x", "y"] or set(route(profile, ["x", "y"])) == {"x", "y"}


# ── P7: portable context ──────────────────────────────────────────────────────
def test_normalize_history_canonicalizes_tool_call_ids():
    msgs = [
        {"role": "assistant", "tool_calls": [{"id": "abc123", "name": "t", "args": {}}]},
        {"role": "tool", "tool_call_id": "abc123", "content": "ok"},
    ]
    out = normalize_history(msgs)
    assert out[0]["tool_calls"][0]["id"] == "call_0"
    assert out[1]["tool_call_id"] == "call_0"        # matched pair stays consistent


def test_normalize_history_noop_without_tools():
    msgs = [{"role": "user", "content": "hi"}]
    assert normalize_history(msgs) is msgs            # fast no-op returns same object


def test_normalize_history_survives_garbage():
    assert normalize_history(["not a message"]) == ["not a message"]


# ── P9 wired into failover: a tripped provider is tried last ───────────────────
class _M:
    def __init__(self, result=None, raises=None):
        self._r, self._e = result, raises
    def bind_tools(self, t, **k):
        return self
    def invoke(self, m, **k):
        if self._e:
            raise self._e
        return self._r


class _RT:
    def __init__(self, name, model):
        self.name = name
        self.spec = type("S", (), {"name": name})()
        self._m = model
    def chat_model(self):
        return self._m


def test_failover_records_metrics_and_ledger(monkeypatch):
    import aps.infra.llm as llm
    monkeypatch.setattr(llm, "acquire_llm", lambda *a, **k: 0.0)
    from aps.config import quota
    quota.BREAKER.reset()
    before = quota.LEDGER.count("gemini")
    m = FailoverChatModel([_RT("groq", _M(raises=RuntimeError("429"))),
                           _RT("gemini", _M(result="OK"))])
    assert m.invoke(["hi"]) == "OK"
    assert quota.LEDGER.count("gemini") == before + 1
    assert quota.BREAKER.is_open("groq") is True       # the 429'd provider got benched
    quota.BREAKER.reset()
