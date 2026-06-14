"""Phase-0 smoke test — proves model wiring and config centralization work.

Run from the aps/ directory:
    python scripts/smoke_test.py

Exits 0 on success, 1 on failure. Prints provider + model used.
No agents, no tools — just a round-trip through get_chat_model().
"""
from __future__ import annotations

import sys
import os

# Allow running from aps/ without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from langchain_core.messages import HumanMessage

from aps.config.settings import get_chat_model, get_compression_model, get_settings


def main() -> int:
    s = get_settings()
    print(f"provider : {s.model_provider}")
    print(f"model    : {s.gemini_model if s.model_provider == 'gemini' else s.nim_model}")

    # ── main model round-trip ─────────────────────────────────────────────
    print("\n[1/2] invoking main model …")
    try:
        model = get_chat_model()
        reply = model.invoke([HumanMessage("Reply with exactly one word: ready")])
        text = reply.content if hasattr(reply, "content") else str(reply)
        print(f"      response: {text!r}")
    except Exception as exc:
        print(f"      FAILED: {exc}", file=sys.stderr)
        return 1

    # ── compression model round-trip ─────────────────────────────────────
    print("[2/2] invoking compression model …")
    try:
        comp = get_compression_model()
        reply2 = comp.invoke([HumanMessage("Reply with exactly one word: compressed")])
        text2 = reply2.content if hasattr(reply2, "content") else str(reply2)
        print(f"      response: {text2!r}")
    except Exception as exc:
        print(f"      FAILED: {exc}", file=sys.stderr)
        return 1

    print("\nPhase-0 smoke test PASSED — model factory is wired.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
