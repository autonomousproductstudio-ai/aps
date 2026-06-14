"""aps.config.portable — provider-agnostic conversation context (multipleAPIplan P7).

The agent's working state is already a portable `list[BaseMessage]`; the only thing that can
trip a *different* provider when failover happens mid-loop is mismatched `tool_call_id`s.
`normalize_history` rewrites them to a canonical, self-consistent scheme (`call_0`, `call_1`,
…) so a tool exchange one provider started is accepted by the next — the "memory transfer."

Defensive by design: a fast no-op when there are no tool calls, and it returns the original
messages unchanged on any error (it must never break a working loop).
"""
from __future__ import annotations

import copy as _copy


def _get(m, attr):
    return m.get(attr) if isinstance(m, dict) else getattr(m, attr, None)


def _set(m, attr, val):
    if isinstance(m, dict):
        return {**m, attr: val}
    if hasattr(m, "model_copy"):
        try:
            return m.model_copy(update={attr: val})
        except Exception:
            pass
    m2 = _copy.copy(m)
    try:
        setattr(m2, attr, val)
    except Exception:
        return m
    return m2


def normalize_history(messages, target_spec=None):
    """Return `messages` with tool_call ids canonicalized so any provider accepts the history.
    No-op (returns the same list) when there are no tool calls, or on any error."""
    try:
        if not any(_get(m, "tool_calls") for m in messages):
            return messages
        id_map: dict[str, str] = {}
        out = []
        for m in messages:
            tcs = _get(m, "tool_calls")
            if tcs:
                new_tcs = []
                for tc in tcs:
                    old = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                    nid = id_map.setdefault(old, f"call_{len(id_map)}")
                    new_tcs.append({**tc, "id": nid} if isinstance(tc, dict) else tc)
                m = _set(m, "tool_calls", new_tcs)
            tcid = _get(m, "tool_call_id")
            if tcid is not None and tcid in id_map:
                m = _set(m, "tool_call_id", id_map[tcid])
            out.append(m)
        return out
    except Exception:
        return messages
