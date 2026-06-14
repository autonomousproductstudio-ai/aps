"""Deterministic mock generators for contract fields the backend has no real source for.

Everything here is a pure function of its inputs (or a fixed catalog) — NO random/clock — so
the System page renders rich, plausible data and unit tests can assert exact values. Where a
real count is available (evidence, runs), the caller passes it in and we weave it through.

Formatting helpers enforce the contract's §0.9 number precision and §11 string rules
("42 KB", "3m 12s", em-dash "—").
"""
from __future__ import annotations

import hashlib

DASH = "—"  # em-dash, the contract's "absent string" sentinel (§11.8)

# Material Symbol + fixed identity per agent (§1.1 / §10 fixed ids).
AGENTS = [
    {"id": "research", "name": "Research Agent", "icon": "travel_explore",
     "tools": ["web_search", "github_api", "reddit_api", "hn_scraper", "paper_fetch"]},
    {"id": "product", "name": "Product Agent", "icon": "architecture",
     "tools": ["prd_writer", "user_story_gen", "persona_builder"]},
    {"id": "arch", "name": "Architecture Agent", "icon": "hub",
     "tools": ["diagram_gen", "openapi_spec", "c4_model"]},
    {"id": "execution", "name": "Execution Agent", "icon": "data_object",
     "tools": ["code_gen", "test_runner", "ci_builder"]},
    {"id": "present", "name": "Presentation Agent", "icon": "smart_display",
     "tools": ["deck_builder", "memo_writer", "pitch_scorer"]},
]


# --------------------------------------------------------------------------- #
# Deterministic "jitter": a stable pseudo-value from a string seed, no randomness.
# --------------------------------------------------------------------------- #
def _h(seed: str) -> int:
    return int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16)


def jitter(seed: str, lo: int, hi: int) -> int:
    span = max(1, hi - lo + 1)
    return lo + (_h(seed) % span)


# --------------------------------------------------------------------------- #
# Formatting (contract §11)
# --------------------------------------------------------------------------- #
def fmt_size(num_bytes: int) -> str:
    if num_bytes <= 0:
        return DASH
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024 or unit == "GB":
            n = num_bytes if unit == "B" else round(num_bytes, 1)
            return f"{int(n) if unit == 'B' else n} {unit}"
        num_bytes /= 1024
    return DASH


def fmt_duration(total_sec: int) -> str:
    if total_sec <= 0:
        return DASH
    return f"{total_sec // 60}m {total_sec % 60}s"


def fmt_tokens_k(raw_tokens: int) -> str:
    return DASH if raw_tokens <= 0 else f"{round(raw_tokens / 1000)}K"


# --------------------------------------------------------------------------- #
# System page panels (§6) — fixed catalogs + derived counts
# --------------------------------------------------------------------------- #
def system_models() -> list[dict]:
    """§6.3 — 4 model cards with live-looking but deterministic metrics."""
    base = [
        ("claude", "Claude Sonnet 4.6", "Anthropic", "psychology", True, "#a5e7ff"),
        ("gpt4o", "GPT-4o", "OpenAI", "smart_toy", False, "#79ff5b"),
        ("gemini", "Gemini 1.5 Pro", "Google", "auto_awesome", False, "#bbc9cf"),
        ("local", "Mistral 7B", "Local", "memory", False, "#f59e0b"),
    ]
    out = []
    for mid, name, prov, icon, primary, color in base:
        out.append({
            "id": mid, "name": name, "provider": prov, "icon": icon, "available": True,
            "latencyMs": jitter(f"lat:{mid}", 380, 2200),
            "tokensM": round(jitter(f"tok:{mid}", 80, 870) / 1000, 3),
            "costUSD": 0.0 if mid == "local" else round(jitter(f"cost:{mid}", 130, 1240) / 100, 2),
            "successRate": round(94 + jitter(f"succ:{mid}", 0, 52) / 10, 1),
            "primary": primary, "color": color,
        })
    return out


def system_tools(tool_names_by_ns: dict[str, list[str]]) -> list[dict]:
    """§6.4 — grouped tool ecosystem. Namespaces/tools are REAL (from the registry); the
    invocation/latency/health metrics are deterministic mock."""
    ns_color = {"Research": "#a5e7ff", "Product": "#79ff5b",
                "Architecture": "#bbc9cf", "Execution": "#f59e0b"}
    groups = []
    for ns, names in tool_names_by_ns.items():
        tools = []
        for nm in names:
            inv = jitter(f"inv:{nm}", 1, 850)
            tools.append({
                "name": nm, "inv": inv,
                "succ": round(96 + jitter(f"ts:{nm}", 0, 40) / 10, 1),
                "avgMs": jitter(f"ms:{nm}", 600, 3200),
                "last": "—" if inv < 5 else f"14:0{jitter(f'h:{nm}', 0, 5)}:{jitter(f's:{nm}', 10, 59)}",
                "health": "healthy" if inv >= 5 else "standby",
            })
        groups.append({"ns": ns, "color": ns_color.get(ns, "#a5e7ff"), "tools": tools})
    return groups


def system_memory(evidence_count: int) -> list[dict]:
    """§6.5 — six memory layers. evidence layer node count is real; the rest are fixed."""
    return [
        {"id": "working", "name": "Working Memory", "icon": "memory_alt", "size": "2.4 MB",
         "nodes": 127, "speed": 12, "pct": 72, "color": "#a5e7ff", "note": "Current run context"},
        {"id": "run", "name": "Run Memory", "icon": "history", "size": "14.2 MB",
         "nodes": 847, "speed": 28, "pct": 45, "color": "#a5e7ff", "note": "Session history"},
        {"id": "artifact", "name": "Artifact Memory", "icon": "inventory_2", "size": "8.1 MB",
         "nodes": 312, "speed": 18, "pct": 31, "color": "#79ff5b", "note": "Generated documents"},
        {"id": "evidence", "name": "Evidence Memory", "icon": "device_hub", "size": "31.7 MB",
         "nodes": max(evidence_count, 0), "speed": 45, "pct": 88, "color": "#f59e0b",
         "note": "Source intelligence"},
        {"id": "kg", "name": "Knowledge Graph", "icon": "scatter_plot", "size": "5.6 MB",
         "nodes": 493, "speed": 22, "pct": 62, "color": "#a5e7ff", "note": "Concept relationships"},
        {"id": "longterm", "name": "Long-Term Memory", "icon": "cloud_sync", "size": "127 MB",
         "nodes": 18400, "speed": 180, "pct": 15, "color": "#bbc9cf", "note": "Cross-run learnings"},
    ]


def system_knowledge_graph() -> list[dict]:
    """§6.6 — fixed vertical chain layout."""
    return [
        {"id": "idea", "label": "Idea", "y": 48, "side": []},
        {"id": "evidence", "label": "Evidence", "y": 128,
         "side": [{"label": "GitHub ×34", "dx": 120}, {"label": "Reddit ×24", "dx": -120}]},
        {"id": "insights", "label": "Insights", "y": 208,
         "side": [{"label": "TAM $8.4B", "dx": 120}, {"label": "Pain ×3", "dx": -110}]},
        {"id": "req", "label": "Requirements", "y": 288,
         "side": [{"label": "14 Stories", "dx": 115}, {"label": "7 Features", "dx": -115}]},
        {"id": "arch", "label": "Architecture", "y": 368,
         "side": [{"label": "API Design", "dx": 110}, {"label": "DB Schema", "dx": -110}]},
        {"id": "roadmap", "label": "Roadmap", "y": 448,
         "side": [{"label": "Sprint 1", "dx": 105}, {"label": "Sprint 2", "dx": -100}]},
        {"id": "pitch", "label": "Pitch", "y": 528,
         "side": [{"label": "Deck", "dx": 80}, {"label": "Memo", "dx": -80}]},
    ]


def system_quality() -> list[dict]:
    """§6.7 — per-artifact quality rows."""
    rows = [("Research Brief", 9.3, 94, 2, 9.1), ("Market Analysis", 8.8, 91, 3, 8.7),
            ("PRD v1.0", 8.4, 87, 5, 8.2), ("Roadmap Q1–Q3", 8.6, 88, 4, 8.5)]
    return [{"name": n, "score": s, "coverage": c, "hRisk": h, "depth": d}
            for n, s, c, h, d in rows]


def system_cost() -> list[dict]:
    """§6.8 — cost center, descending by value."""
    return [
        {"label": "Claude Sonnet 4.6", "value": 12.40, "tokens": "847K", "category": "Model"},
        {"label": "GPT-4o (fallback)", "value": 4.86, "tokens": "243K", "category": "Model"},
        {"label": "Gemini 1.5 Pro", "value": 1.37, "tokens": "91K", "category": "Model"},
        {"label": "API calls · tools", "value": 0.84, "tokens": DASH, "category": "Tool"},
        {"label": "Storage · memory", "value": 0.12, "tokens": DASH, "category": "Infra"},
    ]


def system_observability() -> dict:
    """§6.9 — four 20-point sparkline series (deterministic)."""
    return {
        "latency": [jitter(f"obs-lat:{i}", 1180, 1420) for i in range(20)],
        "tokens": [12 + i * 3 + (i % 3) * 2 for i in range(20)],
        "errors": [1 if i in (2, 6, 11, 17) else 0 for i in range(20)],
        "runs": [1 + (i * 11) // 20 for i in range(20)],
    }


def system_activity_heatmap() -> dict:
    """§6.10 — 7 days × 24 hours = 168 floats 0..1, row-major day*24+hour."""
    vals = []
    for day in range(7):
        for hour in range(24):
            vals.append(round(jitter(f"heat:{day}:{hour}", 1, 95) / 100, 2))
    return {"values": vals}


# --------------------------------------------------------------------------- #
# Run-scoped graph layouts (§4.7 / §4.8 / §4.9) — fixed coordinates + real counts
# --------------------------------------------------------------------------- #
def evidence_graph(source_counts: dict[str, int]) -> dict:
    """§4.7 — source→pain→req network. Node coords are fixed; source `count` is real where known."""
    def c(key: str) -> int:
        return int(source_counts.get(key, 0))
    nodes = [
        {"id": "github", "label": "GitHub", "x": 200, "y": 55, "type": "source", "count": c("github")},
        {"id": "reddit", "label": "Reddit", "x": 75, "y": 130, "type": "source", "count": c("reddit")},
        {"id": "hn", "label": "HN", "x": 325, "y": 130, "type": "source", "count": c("hackernews")},
        {"id": "ph", "label": "Prod Hunt", "x": 75, "y": 240, "type": "source", "count": c("producthunt")},
        {"id": "papers", "label": "Papers", "x": 325, "y": 240, "type": "source", "count": c("arxiv")},
        {"id": "pain1", "label": "Pain #1", "x": 200, "y": 148, "type": "pain", "count": 0},
        {"id": "pain2", "label": "Pain #2", "x": 130, "y": 210, "type": "pain", "count": 0},
        {"id": "pain3", "label": "Pain #3", "x": 270, "y": 210, "type": "pain", "count": 0},
        {"id": "req1", "label": "Requirement", "x": 200, "y": 275, "type": "req", "count": 0},
        {"id": "arch1", "label": "Architecture", "x": 145, "y": 330, "type": "arch", "count": 0},
        {"id": "road1", "label": "Roadmap", "x": 255, "y": 330, "type": "roadmap", "count": 0},
    ]
    edges = [["github", "pain1"], ["reddit", "pain2"], ["hn", "pain1"], ["ph", "pain3"],
             ["papers", "pain1"], ["pain1", "req1"], ["pain2", "req1"], ["pain3", "req1"],
             ["req1", "arch1"], ["req1", "road1"]]
    return {"nodes": nodes, "edges": edges}


def company_dna(core_label: str) -> dict:
    """§4.8 — radial DNA graph; fixed layout, core label from the idea."""
    nodes = [
        {"id": "core", "label": core_label[:14] or "Core", "x": 200, "y": 170, "r": 28, "core": True},
        {"id": "market", "label": "Market", "x": 200, "y": 60, "r": 19, "core": False},
        {"id": "users", "label": "Users", "x": 315, "y": 115, "r": 17, "core": False},
        {"id": "compete", "label": "Competitors", "x": 315, "y": 225, "r": 17, "core": False},
        {"id": "mono", "label": "Revenue", "x": 200, "y": 282, "r": 17, "core": False},
        {"id": "arch", "label": "Architecture", "x": 85, "y": 225, "r": 17, "core": False},
        {"id": "features", "label": "Features", "x": 85, "y": 115, "r": 17, "core": False},
    ]
    edges = [{"a": "core", "b": b} for b in
             ("market", "users", "compete", "mono", "arch", "features")]
    edges += [{"a": "market", "b": "users"}, {"a": "users", "b": "features"}]
    return {"nodes": nodes, "edges": edges}


def timeline() -> list[dict]:
    """§4.9 — fixed 5-phase 0..100 bar (no gaps/overlaps)."""
    return [
        {"label": "Research", "icon": "travel_explore", "start": 0, "end": 30},
        {"label": "Product", "icon": "architecture", "start": 30, "end": 50},
        {"label": "Architecture", "icon": "hub", "start": 50, "end": 70},
        {"label": "Execution", "icon": "data_object", "start": 70, "end": 90},
        {"label": "Presentation", "icon": "smart_display", "start": 90, "end": 100},
    ]
