"""Shared Markdown helpers for the renderers (plan.md W1).

Everything here is a pure function: no I/O, no network, no LLM, deterministic for a given
input. `evidence_link`/`citation_refs` are the credibility primitives — every citation in
every rendered doc flows through them, with graceful fallback when url/title are absent.
"""
from __future__ import annotations

from aps.state.models import Evidence

PLACEHOLDER = "_— none identified —_"


def h1(text: str) -> str:
    return f"# {text}\n"


def h2(text: str) -> str:
    return f"\n## {text}\n"


def h3(text: str) -> str:
    return f"\n### {text}\n"


def _cell(value) -> str:
    """One table cell: stringify, collapse newlines, escape pipes."""
    s = "" if value is None else str(value)
    return s.replace("\n", " ").replace("|", "\\|").strip() or "—"


def table(headers: list[str], rows: list[list]) -> str:
    """A GitHub-flavored Markdown table. Empty rows → graceful placeholder."""
    if not rows:
        return PLACEHOLDER + "\n"
    head = "| " + " | ".join(_cell(h) for h in headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(_cell(c) for c in row) + " |" for row in rows)
    return f"{head}\n{sep}\n{body}\n"


def bullet_list(items: list) -> str:
    items = [str(i).strip() for i in (items or []) if str(i).strip()]
    if not items:
        return PLACEHOLDER + "\n"
    return "\n".join(f"- {i}" for i in items) + "\n"


def numbered_list(items: list) -> str:
    items = [str(i).strip() for i in (items or []) if str(i).strip()]
    if not items:
        return PLACEHOLDER + "\n"
    return "\n".join(f"{n}. {i}" for n, i in enumerate(items, 1)) + "\n"


def fenced(text: str, lang: str = "") -> str:
    return f"```{lang}\n{text}\n```\n"


def evidence_link(ev: Evidence) -> str:
    """`[source · title](url)`, degrading gracefully when title/url are missing."""
    source = (ev.source or "source").strip()
    title = (ev.title or "").strip()
    label = f"{source} · {title}" if title else source
    url = (ev.url or "").strip()
    return f"[{label}]({url})" if url.startswith("http") else label


def citation_refs(evidence: list[Evidence], limit: int = 6) -> str:
    """Compact inline citations: `[github · …](u) · [hn · …](u)`; `+N more` past the cap."""
    evs = list(evidence or [])
    if not evs:
        return PLACEHOLDER
    shown = " · ".join(evidence_link(e) for e in evs[:limit])
    extra = len(evs) - limit
    return shown + (f" · +{extra} more" if extra > 0 else "")


def front_matter(title: str, idea: str | None = None, generated_at: str | None = None) -> str:
    """Self-describing header for a downloaded doc. `generated_at` is opt-in so renders stay
    byte-deterministic by default (the caller may pass a fixed timestamp)."""
    lines = [h1(title)]
    if idea:
        lines.append(f"**Idea:** {idea}\n")
    if generated_at:
        lines.append(f"*Generated: {generated_at}*\n")
    return "".join(lines)


def severity_badge(sev) -> str:
    val = getattr(sev, "value", sev)
    return {"high": "**HIGH**", "med": "MED", "low": "low"}.get(str(val), str(val))
