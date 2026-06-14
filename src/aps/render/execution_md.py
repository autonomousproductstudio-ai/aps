"""ExecutionPlan → Markdown (plan.md W1)."""
from __future__ import annotations

from aps.state.models import ExecutionPlan
from aps.render import base as b


def _repo_tree(repo_plan: dict) -> str:
    dirs = (repo_plan or {}).get("dirs", [])
    files = (repo_plan or {}).get("key_files", [])
    if not dirs and not files:
        return b.PLACEHOLDER + "\n"
    lines = [f"{d}/" for d in dirs] + list(files)
    return b.fenced("\n".join(sorted(lines)))


def render(e: ExecutionPlan) -> str:
    out = [b.front_matter("Execution Plan")]

    out.append(b.h2("Repository Structure"))
    out.append(_repo_tree(e.repo_plan))

    out.append(b.h2(f"Backlog ({len(e.backlog)})"))
    rows = [[i.get("id", ""), i.get("title", ""), i.get("type", ""),
             i.get("priority", ""), i.get("points", "")] for i in e.backlog]
    out.append(b.table(["ID", "Title", "Type", "Priority", "Points"], rows))

    out.append(b.h2(f"Sprints ({len(e.sprints)})"))
    if e.sprints:
        for s in e.sprints:
            titles = [it.get("title", "") for it in s.get("items", [])]
            out.append(b.h3(f"Sprint {s.get('sprint', '?')} — {s.get('points', 0)} pts"))
            out.append(b.bullet_list(titles))
    else:
        out.append(b.PLACEHOLDER + "\n")

    out.append(b.h2("Roadmap"))
    out.append((e.roadmap or b.PLACEHOLDER) + "\n")

    out.append(b.h2("Infrastructure Cost"))
    out.append((e.infra_cost or b.PLACEHOLDER) + "\n")
    return "".join(out)
