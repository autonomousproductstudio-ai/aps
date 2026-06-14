"""generate_founders_agreement — a Founders' Agreement template.

Deterministic: standard 4-year vesting / 1-year cliff defaults, IP assignment, roles, and
equity-split placeholders for the stated number of founders. Governing law adapts to the
jurisdiction. Not legal advice.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult
from aps.tools.legal import _legal


class Args(BaseModel):
    company_name: str = ""
    jurisdiction: str = "India"
    num_founders: int = Field(2, ge=1, le=6)


class GenerateFoundersAgreement(BaseTool):
    name = "generate_founders_agreement"
    namespace = "legal"
    description = (
        "Generate a Founders' Agreement: equity split, 4-year vesting with a 1-year cliff, IP "
        "assignment, roles and responsibilities, decision-making, and departure terms. "
        "Deterministic template; not legal advice."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        j = _legal.resolve_jurisdiction(args.jurisdiction)
        company = args.company_name or "[COMPANY NAME]"
        n = args.num_founders

        founders_rows = "\n".join(
            f"| [FOUNDER {i} NAME] | [ROLE] | [EQUITY %] |" for i in range(1, n + 1)
        )

        body = f"""{_legal.disclaimer_banner()}
# Founders' Agreement — {company}

**Date:** [EFFECTIVE DATE]

This Founders' Agreement is made between the founders of **{company}** ("Company"):

| Founder | Role | Equity |
| --- | --- | --- |
{founders_rows}

(Total equity must sum to 100%.)

## 1. Equity and vesting
Each founder's equity vests over **four (4) years** with a **one (1) year cliff**: 25% vests
after the first year, then monthly over the remaining three years. Unvested equity is subject
to repurchase at nominal value if a founder departs.

## 2. Roles and commitment
Each founder will devote [FULL-TIME / time commitment] to the Company and perform the duties
of their role above. Material outside activities require written consent of the other founders.

## 3. Intellectual property
Each founder hereby assigns to the Company all intellectual property created in connection with
the business, and waives moral rights to the extent permitted by law.

## 4. Decision-making
Ordinary decisions are made by majority of founders; the following reserved matters require
unanimous consent: fundraising, issuing equity, selling the Company, incurring debt over
[THRESHOLD], and changing this Agreement.

## 5. Departure
A founder who resigns or is removed keeps only vested equity (subject to clause 1). The
remaining founders may reallocate forfeited equity.

## 6. Confidentiality and non-compete
Each founder agrees to keep Company information confidential and not to compete during their
involvement and for [NON-COMPETE PERIOD] afterward, to the extent enforceable.

## 7. Dispute resolution and governing law
This Agreement is governed by {j['governing_law']}. Disputes will first be resolved by good-
faith discussion, then [ARBITRATION / mediation venue].

Signatures:
{chr(10).join(f"- [FOUNDER {i} NAME]: ______________  Date: ______" for i in range(1, n + 1))}
"""
        placeholders = ["[EFFECTIVE DATE]", "[ROLE]", "[EQUITY %]",
                        "[FULL-TIME / time commitment]", "[THRESHOLD]",
                        "[NON-COMPETE PERIOD]", "[ARBITRATION / mediation venue]"]
        placeholders += [f"[FOUNDER {i} NAME]" for i in range(1, n + 1)]
        if company == "[COMPANY NAME]":
            placeholders.insert(0, "[COMPANY NAME]")
        return ToolResult(ok=True, payload={
            "title": f"Founders' Agreement — {company}",
            "kind": "founders_agreement",
            "body": body,
            "placeholders": placeholders,
        })


TOOL = GenerateFoundersAgreement()

if __name__ == "__main__":
    print(TOOL.run(company_name="Habitly", num_founders=2).payload["body"][:600])
