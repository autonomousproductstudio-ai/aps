"""npm_package_info — fetch an npm package's metadata + recent downloads (no key).

Use to size/validate a JS/TS tool space: incumbent libraries, description, popularity.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error, USER_AGENT, DEFAULT_TIMEOUT
from aps.state.models import ToolResult, Evidence


class Args(BaseModel):
    package: str = Field(..., description="exact npm package name, e.g. 'react'")


class NpmPackageInfo(BaseTool):
    name = "npm_package_info"
    namespace = "retrieval"
    description = (
        "Look up a JavaScript/TypeScript package on the npm registry (no key): "
        "description, latest version, and last-month download count as a popularity "
        "signal. Use to gauge incumbents in a JS tooling space. JS counterpart of "
        "pypi_package_info."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        try:
            from aps.infra import http
            meta = http.get(
                f"https://registry.npmjs.org/{args.package}",
                headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT,
            )
            meta.raise_for_status()
            m = meta.json()
            latest = (m.get("dist-tags", {}) or {}).get("latest", "?")
            downloads = None
            try:
                d = http.get(
                    f"https://api.npmjs.org/downloads/point/last-month/{args.package}",
                    headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT,
                )
                if d.ok:
                    downloads = d.json().get("downloads")
            except Exception:
                pass
            snippet = (m.get("description") or "")[:200]
            snippet += f" | v{latest}"
            if downloads is not None:
                snippet += f" | {downloads:,} downloads/mo"
            ev = [Evidence(
                source="npm",
                url=f"https://www.npmjs.com/package/{args.package}",
                title=f"{args.package} (npm)",
                snippet=snippet[:280],
            )]
            return ToolResult(ok=True, payload={"meta": m.get("description"),
                                                "latest": latest, "downloads": downloads},
                              evidence=ev)
        except Exception as e:
            return fixture_or_error(str(e), evidence=[
                Evidence(source="npm", url="https://www.npmjs.com/package/example",
                         title="[fixture] example (npm)",
                         snippet="Does the thing | v2.0.0 | 1,000,000 downloads/mo")
            ])


TOOL = NpmPackageInfo()

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(package=sys.argv[1] if len(sys.argv) > 1 else "react")
    print(json.dumps(out.model_dump(), indent=2, default=str))
