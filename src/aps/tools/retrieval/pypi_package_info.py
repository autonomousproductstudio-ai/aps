"""pypi_package_info — fetch a PyPI package's metadata (no key).

Use to size/validate a Python tool space: is there an incumbent library, how is it
described, what version maturity. Signals existing solutions and competitor SDKs.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error, USER_AGENT, DEFAULT_TIMEOUT
from aps.state.models import ToolResult, Evidence


class Args(BaseModel):
    package: str = Field(..., description="exact PyPI package name, e.g. 'langchain'")


class PypiPackageInfo(BaseTool):
    name = "pypi_package_info"
    namespace = "retrieval"
    description = (
        "Look up a Python package on PyPI (no key): summary, latest version, homepage. "
        "Use to check whether an incumbent library already solves a problem and how "
        "mature it is. Python-ecosystem equivalent of npm_package_info."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        try:
            from aps.infra import http
            r = http.get(
                f"https://pypi.org/pypi/{args.package}/json",
                headers={"User-Agent": USER_AGENT},
                timeout=DEFAULT_TIMEOUT,
            )
            r.raise_for_status()
            info = r.json().get("info", {})
            snippet = (info.get("summary") or "")[:200]
            snippet += f" | v{info.get('version', '?')}"
            ev = [Evidence(
                source="pypi",
                url=info.get("project_url") or f"https://pypi.org/project/{args.package}/",
                title=f"{info.get('name', args.package)} (PyPI)",
                snippet=snippet[:280],
            )]
            return ToolResult(ok=True, payload=info, evidence=ev)
        except Exception as e:
            return fixture_or_error(str(e), evidence=[
                Evidence(source="pypi", url="https://pypi.org/project/example/",
                         title="[fixture] example (PyPI)",
                         snippet="A library that does the thing | v1.2.3")
            ])


TOOL = PypiPackageInfo()

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(package=sys.argv[1] if len(sys.argv) > 1 else "requests")
    print(json.dumps(out.model_dump(), indent=2, default=str))
