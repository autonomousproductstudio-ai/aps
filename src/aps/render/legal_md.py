"""LegalPackage → Markdown (Launch Studio Phase 2).

A disclaimer banner + jurisdiction header, then each generated document (its own body already
carries the per-doc disclaimer) followed by the list of placeholders a lawyer must complete.
Pure and deterministic, like the other renderers.
"""
from __future__ import annotations

from aps.state.models import LegalPackage
from aps.render import base as b


def render(p: LegalPackage) -> str:
    out = [b.front_matter(f"Legal Documents — {p.company_name or 'Untitled'}")]

    if p.disclaimer:
        out.append("> " + p.disclaimer.replace("\n", "\n> ") + "\n")

    out.append(b.h2("Overview"))
    out.append(b.table(
        ["Field", "Value"],
        [["Company", p.company_name or "—"],
         ["Jurisdiction", p.jurisdiction or "—"],
         ["Governing law", p.governing_law or "—"],
         ["Documents", str(len(p.documents))]],
    ))

    for doc in p.documents:
        out.append(b.h2(doc.title or doc.kind or "Document"))
        out.append((doc.body.strip() + "\n") if doc.body and doc.body.strip()
                   else b.PLACEHOLDER + "\n")
        if doc.placeholders:
            out.append(b.h3("Placeholders to complete"))
            out.append(b.bullet_list(doc.placeholders))

    return "".join(out)
