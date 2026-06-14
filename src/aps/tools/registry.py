"""aps.tools.registry — auto-discovers tools so adding one never edits a shared list.

Scans every tools/<namespace>/ package for objects that satisfy the Tool protocol,
indexed by namespace. Agents request tools by namespace (ADR-0005: per-agent scoping,
<=20 visible). The six namespaces total 52 model-callable tools (retrieval 20, analysis
10, product 6, architecture 6, execution 6, presentation 4); infra is NOT a namespace.
"""
from __future__ import annotations
import importlib
import pkgutil
from aps.tools.base import ToolImpl

# Every tool namespace the registry scans. Adding a tool = a new file in one of these
# packages; adding a namespace = one entry here. No shared list of individual tools.
TOOL_PACKAGES = (
    "aps.tools.retrieval",
    "aps.tools.analysis",
    "aps.tools.product",
    "aps.tools.architecture",
    "aps.tools.execution",
    "aps.tools.presentation",
    "aps.tools.brand",
    "aps.tools.legal",
    "aps.tools.funding",
    "aps.tools.availability",
    "aps.tools.compliance",
)


def _discover(package_name: str) -> list[ToolImpl]:
    found: list[ToolImpl] = []
    pkg = importlib.import_module(package_name)
    for mod in pkgutil.iter_modules(pkg.__path__):
        if mod.name.startswith("_"):
            continue
        m = importlib.import_module(f"{package_name}.{mod.name}")
        tool = getattr(m, "TOOL", None)          # each module exposes TOOL = MyTool()
        if isinstance(tool, ToolImpl):
            found.append(tool)
    return found


def load_registry() -> dict[str, list[ToolImpl]]:
    """Return {namespace: [tools]}. Called once at startup."""
    registry: dict[str, list[ToolImpl]] = {}
    for pkg in TOOL_PACKAGES:
        for tool in _discover(pkg):
            registry.setdefault(tool.namespace, []).append(tool)
    return registry


def all_tools() -> list[ToolImpl]:
    """Flat list of every registered tool across all namespaces."""
    return [t for tools in load_registry().values() for t in tools]


def tools_for(namespace: str) -> list[ToolImpl]:
    return load_registry().get(namespace, [])
