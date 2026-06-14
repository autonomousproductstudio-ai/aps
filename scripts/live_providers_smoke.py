"""Live multi-provider smoke — verify tool-calling on each provider you have a key for.

    APS_PROVIDER_CHAIN=groq,gemini,nim GROQ_API_KEY=... GEMINI_API_KEY=... \
        python scripts/live_providers_smoke.py "a privacy-first habit tracker"

For every available provider it runs ONE real research turn (in isolation, that provider
only) and reports whether the model selected tools and gathered evidence — a provider ×
tool-calling support matrix. Makes live network calls; NOT run in CI.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main() -> int:
    idea = sys.argv[1] if len(sys.argv) > 1 else "a privacy-first habit tracker for couples"

    from aps.config.providers import REGISTRY, provider_available
    from aps.agents.research.agent import gather_evidence

    available = [n for n in REGISTRY if provider_available(n)]
    if not available:
        print("No provider keys found. Set e.g. GROQ_API_KEY / GEMINI_API_KEY / NVIDIA_API_KEY "
              "(see .env.example) and re-run.")
        return 1

    print(f">>> idea: {idea!r}")
    print(f">>> testing {len(available)} provider(s): {', '.join(available)}\n")
    print(f"{'provider':<14}{'tools':<8}{'evidence':<10}{'calls':<7}note")
    print("-" * 60)

    results = {}
    for name in available:
        # isolate this provider: a single-provider chain so the loop talks ONLY to it
        os.environ["APS_PROVIDER_CHAIN"] = name
        try:
            ev, n = gather_evidence(idea)
            ok = n > 0 and len(ev) > 0
            results[name] = ok
            print(f"{name:<14}{('YES' if n > 0 else 'no'):<8}{len(ev):<10}{n:<7}"
                  f"{'' if ok else 'no tool-calls/evidence — verify model supports tools'}")
        except Exception as e:  # noqa: BLE001
            results[name] = False
            print(f"{name:<14}{'ERR':<8}{'-':<10}{'-':<7}{type(e).__name__}: {str(e)[:60]}")

    passed = sum(1 for v in results.values() if v)
    print(f"\n{passed}/{len(available)} provider(s) selected tools and gathered evidence.")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
