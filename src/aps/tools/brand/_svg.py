"""Shared, deterministic brand primitives (Launch Studio Phase 1).

Leading underscore ⇒ the registry never mistakes this for a TOOL module. Pure stdlib,
no network, no image model: a name seeds a palette + mark style, and the mark builders
emit inline SVG. Same input → same output (decision D2), so an LLM can later replace the
templating without changing the typed I/O.

Ported from the `aps_brand.py` prototype; kept verbatim in spirit so the visual output the
user already approved is reproduced byte-for-byte.
"""
from __future__ import annotations

import hashlib
from typing import Optional

# Curated, tasteful palettes: (primary, accent, ink)
PALETTES = [
    ("#4F46E5", "#06B6D4", "#0F172A"),  # indigo / cyan
    ("#059669", "#34D399", "#064E3B"),  # emerald
    ("#EA580C", "#F59E0B", "#7C2D12"),  # sunset
    ("#E11D48", "#FB7185", "#4C0519"),  # rose
    ("#2563EB", "#38BDF8", "#0C1B33"),  # blue
    ("#0D9488", "#2DD4BF", "#042F2E"),  # teal
    ("#7C3AED", "#A78BFA", "#2E1065"),  # violet
]
STYLES = ["stack", "orbit", "hex"]

_FONT = "system-ui,Segoe UI,Helvetica,Arial,sans-serif"


def seed(name: str) -> int:
    return int(hashlib.sha256(name.encode("utf-8")).hexdigest(), 16)


def initials(name: str) -> str:
    parts = [p for p in name.replace("-", " ").split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name.strip()[:2].upper() if name.strip() else "?"


def choose(name: str, palette: Optional[tuple] = None, style: str = "auto"):
    """Deterministically pick a (palette, style) for a name."""
    s = seed(name)
    pal = palette or PALETTES[s % len(PALETTES)]
    sty = style if style in STYLES else STYLES[(s // 7) % len(STYLES)]
    return pal, sty


# ------------------------------------------------------------------- marks ---
def _mark_stack(gid, primary, accent, mono):
    return f"""
  <defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{primary}"/><stop offset="1" stop-color="{accent}"/>
  </linearGradient></defs>
  <rect x="14" y="14" width="92" height="92" rx="24" fill="url(#{gid})"/>
  <text x="60" y="60" font-family="{_FONT}"
        font-size="46" font-weight="800" fill="#ffffff"
        text-anchor="middle" dominant-baseline="central">{mono}</text>
  <circle cx="96" cy="24" r="7" fill="#ffffff" opacity="0.9"/>"""


def _mark_orbit(gid, primary, accent, mono):
    return f"""
  <defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{primary}"/><stop offset="1" stop-color="{accent}"/>
  </linearGradient></defs>
  <circle cx="60" cy="60" r="46" fill="url(#{gid})"/>
  <circle cx="60" cy="60" r="46" fill="none" stroke="#ffffff" stroke-opacity="0.35" stroke-width="4"/>
  <circle cx="104" cy="48" r="8" fill="{accent}" stroke="#ffffff" stroke-width="3"/>
  <text x="60" y="60" font-family="{_FONT}"
        font-size="44" font-weight="800" fill="#ffffff"
        text-anchor="middle" dominant-baseline="central">{mono}</text>"""


def _mark_hex(gid, primary, accent, mono):
    pts = "60,12 104,36 104,84 60,108 16,84 16,36"
    return f"""
  <defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{primary}"/><stop offset="1" stop-color="{accent}"/>
  </linearGradient></defs>
  <polygon points="{pts}" fill="url(#{gid})"/>
  <text x="60" y="61" font-family="{_FONT}"
        font-size="44" font-weight="800" fill="#ffffff"
        text-anchor="middle" dominant-baseline="central">{mono}</text>"""


MARKS = {"stack": _mark_stack, "orbit": _mark_orbit, "hex": _mark_hex}


def logo_svg(name: str, tagline: str = "", palette: Optional[tuple] = None,
             style: str = "auto", lockup: bool = True) -> str:
    """SVG string. lockup=True → mark + wordmark; False → mark only."""
    (primary, accent, ink), sty = choose(name, palette, style)
    mono = initials(name)
    gid = f"g{seed(name) % 100000}"
    mark = MARKS[sty](gid, primary, accent, mono)

    if not lockup:
        return (f'<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" '
                f'role="img" aria-label="{name} logo mark">{mark}</svg>')

    fs = 46 if len(name) <= 9 else (40 if len(name) <= 13 else 32)
    tag = (f'<text x="150" y="92" font-family="{_FONT}"'
           f' font-size="15" fill="#64748B" letter-spacing="0.5">{tagline}</text>') if tagline else ""
    return f'''<svg viewBox="0 0 460 120" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{name} logo">
  <g>{mark}</g>
  <text x="148" y="62" font-family="{_FONT}"
        font-size="{fs}" font-weight="800" fill="{ink}"
        dominant-baseline="middle" letter-spacing="-0.5">{name}</text>
  {tag}
</svg>'''


def brand_sheet_svg(name: str, tagline: str, taglines: list,
                    palette: Optional[tuple] = None, style: str = "auto") -> str:
    """A single shareable brand card: lockup + palette swatches + alt taglines."""
    (primary, accent, ink), sty = choose(name, palette, style)
    mono = initials(name)
    gid = f"s{seed(name) % 100000}"
    mark = MARKS[sty](gid, primary, accent, mono)
    swatches = ""
    for i, c in enumerate([primary, accent, ink, "#E2E8F0"]):
        x = 40 + i * 70
        swatches += (f'<rect x="{x}" y="250" width="56" height="56" rx="12" fill="{c}"/>'
                     f'<text x="{x+28}" y="324" font-family="{_FONT}" font-size="11" '
                     f'fill="#475569" text-anchor="middle">{c}</text>')
    alts = ""
    for i, t in enumerate(taglines[:3]):
        alts += (f'<text x="330" y="{210 + i*26}" font-family="{_FONT}" '
                 f'font-size="14" fill="#475569">• {t}</text>')
    return f'''<svg viewBox="0 0 600 360" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="0" width="600" height="360" rx="20" fill="#ffffff" stroke="#E2E8F0" stroke-width="2"/>
  <g transform="translate(28,28)">{mark}</g>
  <text x="170" y="70" font-family="{_FONT}" font-size="40"
        font-weight="800" fill="{ink}" dominant-baseline="middle" letter-spacing="-0.5">{name}</text>
  <text x="172" y="104" font-family="{_FONT}" font-size="15"
        fill="#64748B">{tagline}</text>
  <line x1="40" y1="150" x2="560" y2="150" stroke="#E2E8F0" stroke-width="1.5"/>
  <text x="40" y="178" font-family="{_FONT}" font-size="12"
        font-weight="700" fill="#94A3B8" letter-spacing="1">PALETTE</text>
  {swatches}
  <text x="330" y="178" font-family="{_FONT}" font-size="12"
        font-weight="700" fill="#94A3B8" letter-spacing="1">TAGLINES</text>
  {alts}
</svg>'''


# --------------------------------------------------------- identity helpers ---
def clean_core(idea: str) -> str:
    """A clean, human-readable phrase for the idea, reused across taglines/positioning.

    Reuses the analysis-side `clean_label` normalizer so brand copy never bleeds raw
    snippet/markdown text (the same root cause as the PRD feature-title fixes). Falls back
    to a trimmed idea if the normalizer yields nothing.
    """
    from aps.tools.analysis._text import clean_label
    # 12 words (not 8) so a normal idea isn't cut mid-phrase ("cancels unwanted free" — losing
    # "trials"); then trim trailing function words so it never dangles on a preposition/conjunction.
    core = clean_label(idea, max_words=12, max_chars=90).rstrip(".")
    _TRAIL = {"and", "or", "but", "the", "a", "an", "to", "of", "for", "with",
              "is", "are", "in", "on", "at", "that", "your", "my"}
    toks = core.split()
    while len(toks) > 3 and toks[-1].lower().strip(",.") in _TRAIL:
        toks.pop()
    core = " ".join(toks)
    return core or (idea or "").strip().rstrip(".")


def derive_name(idea: str) -> str:
    """Deterministically derive a one/two-word brand name from the idea.

    Picks the most distinctive content words (longest, skipping stopwords/filler) and
    concatenates them CamelCase — e.g. 'AI-powered accounting for SMEs' → 'AccountingSme'.
    Stable for a given idea; an LLM can later replace this without changing the I/O.
    """
    import re
    core = clean_core(idea)
    # Articles / filler / generic product words / common adjectives + verbs — none of these is a
    # distinctive brand noun, so a name built from them ("SubscriptionUnwanted", "AnApp") reads wrong.
    _STOP = {
        "the", "a", "an", "for", "to", "of", "and", "or", "with", "in", "on", "at", "your", "their",
        "my", "our", "that", "this", "it", "we", "i", "you", "when", "where", "what", "why", "how",
        "which", "more", "than", "without", "ever",
        "app", "tool", "tools", "platform", "software", "solution", "solutions", "service", "system",
        "ai", "powered", "based", "smart", "simple", "easy", "best", "new", "first", "better",
        "powerful", "automated", "personal", "realtime", "multiplayer", "social", "decentralized",
        "distributed", "modern", "premium", "basic", "advanced", "secure", "private", "public",
        "online", "offline", "local", "cloud", "mobile", "native", "custom", "flexible", "scalable",
        "reliable", "robust", "seamless", "intuitive", "free", "unwanted", "great", "awesome", "fast",
        "slow", "weird", "damn", "fair", "fairly",
        "cancels", "cancel", "track", "tracks", "manage", "manages", "build", "builds", "create",
        "creates", "helps", "help", "screen", "screens", "generate", "generates", "find", "finds",
        "automate", "automates", "handle", "handles",
    }
    # Trademarked platform names that appear in "X for Y" pitches — never use them as the brand.
    _DENY = {"uber", "airbnb", "netflix", "spotify", "slack", "notion", "figma", "zoom", "stripe",
             "shopify", "amazon", "google", "apple", "microsoft", "facebook", "instagram", "twitter",
             "tiktok", "youtube", "linkedin", "github", "salesforce", "tinder", "doordash",
             "instacart", "robinhood", "venmo", "paypal", "dropbox", "canva", "reddit", "discord"}
    # Tokenize on any non-alphanumeric (so 'privacy-first' → 'privacy','first') for clean,
    # hyphen-free CamelCase names.
    words = [w for w in re.split(r"[^A-Za-z0-9]+", core) if w and any(c.isalpha() for c in w)]
    cand = [w for w in words if w.lower() not in _STOP and w.lower() not in _DENY]
    if not cand:   # fallback: drop only trademarks + articles/generic-product words, keep any noun
        _SOFT = {"the", "a", "an", "of", "to", "and", "or", "for", "with", "app", "tool",
                 "platform", "software"}
        cand = [w for w in words if w.lower() not in _DENY and w.lower() not in _SOFT]
    cand = cand or ["Studio"]
    # most distinctive = longest two, preserving order of appearance
    top = sorted(cand, key=len, reverse=True)[:2]
    picked = [w for w in cand if w in top][:2] or cand[:2]
    try:    # singularize so a name reads as a brand, not a plural ("RecruitersResumes")
        from aps.tools.analysis._inflect import singularize
        picked = [singularize(p) for p in picked]
    except Exception:
        pass
    name = "".join(p[:1].upper() + p[1:].lower() for p in picked)
    return name or "Studio"
