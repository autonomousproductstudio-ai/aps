"""_inflect — singular/plural for entity names.

Uses the `inflect` package when importable (a real inflector — handles irregulars and edge
cases), else a dependency-free hand-rolled fallback so the suite/CI never depends on it.
Leading underscore → the registry skips this module.
"""
from __future__ import annotations

from aps.tools.analysis._text import pluralize as _fallback_plural

try:  # optional dependency
    import inflect as _inflect_mod
    _ENGINE = _inflect_mod.engine()
except Exception:
    _ENGINE = None


def pluralize(word: str) -> str:
    w = (word or "").strip()
    if not w:
        return "items"
    if _ENGINE is not None:
        try:
            out = _ENGINE.plural_noun(w)
            if out:
                return out
        except Exception:
            pass
    return _fallback_plural(w)


def singularize(word: str) -> str:
    w = (word or "").strip()
    if not w:
        return w
    if _ENGINE is not None:
        try:
            out = _ENGINE.singular_noun(w)   # inflect returns False if already singular
            return out or w
        except Exception:
            pass
    low = w.lower()                          # hand-rolled fallback
    if low.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if low.endswith(("ses", "xes", "zes", "ches", "shes")) and len(w) > 4:
        return w[:-2]
    if low.endswith("s") and not low.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w
