"""generate_employment_contract — an Employment Agreement template.

Deterministic: offer terms, IP assignment, confidentiality, and employment framing that adapts
to the jurisdiction (notice-period for India/EU/UK; at-will for US). Not legal advice.
"""
from __future__ import annotations

from pydantic import BaseModel

from aps.tools.base import BaseTool
from aps.state.models import ToolResult
from aps.tools.legal import _legal


class Args(BaseModel):
    company_name: str = ""
    jurisdiction: str = "India"


class GenerateEmploymentContract(BaseTool):
    name = "generate_employment_contract"
    namespace = "legal"
    description = (
        "Generate an Employment Agreement: role and compensation, IP assignment, "
        "confidentiality, and termination framing appropriate to the jurisdiction (notice "
        "period or at-will). Deterministic template; not legal advice."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        j = _legal.resolve_jurisdiction(args.jurisdiction)
        company = args.company_name or "[COMPANY NAME]"

        if j["at_will"]:
            termination = (
                "Employment is **at-will**: either party may terminate at any time, with or "
                "without cause or notice, subject to applicable law."
            )
        else:
            np = j.get("notice_period") or "30 days"
            termination = (
                f"Either party may terminate this employment by giving **{np}** written notice "
                f"(or payment in lieu), subject to applicable law and the Company's policies."
            )

        body = f"""{_legal.disclaimer_banner()}
# Employment Agreement — {company}

**Date:** [EFFECTIVE DATE]

This Employment Agreement is between **{company}** ("Company") and **[EMPLOYEE NAME]**
("Employee").

## 1. Position
The Employee is engaged as **[TITLE]**, reporting to [MANAGER], starting on [START DATE].

## 2. Compensation
The Employee will be paid **[SALARY]** per [year/month], plus benefits per Company policy, and
may be granted **[EQUITY / OPTIONS]** subject to the Company's equity plan and vesting.

## 3. Duties
The Employee will perform the duties of their role diligently and devote their working time to
the Company, complying with Company policies.

## 4. Intellectual property
The Employee assigns to the Company all intellectual property created in the course of
employment and agrees to assist in perfecting the Company's rights.

## 5. Confidentiality
The Employee will keep Company and third-party confidential information secret during and after
employment, and return all Company property on termination.

## 6. Restrictive covenants
During employment and for [NON-SOLICIT PERIOD] afterward, the Employee will not solicit Company
employees or customers, to the extent enforceable under {j['governing_law']}.

## 7. Termination
{termination}

## 8. Governing law
This Agreement is governed by {j['governing_law']}.

Signatures:
- {company} (authorised signatory): ______________  Date: ______
- [EMPLOYEE NAME]: ______________  Date: ______
"""
        placeholders = ["[EFFECTIVE DATE]", "[EMPLOYEE NAME]", "[TITLE]", "[MANAGER]",
                        "[START DATE]", "[SALARY]", "[EQUITY / OPTIONS]", "[NON-SOLICIT PERIOD]"]
        if company == "[COMPANY NAME]":
            placeholders.insert(0, "[COMPANY NAME]")
        return ToolResult(ok=True, payload={
            "title": f"Employment Agreement — {company}",
            "kind": "employment",
            "body": body,
            "placeholders": placeholders,
        })


TOOL = GenerateEmploymentContract()

if __name__ == "__main__":
    print(TOOL.run(company_name="Habitly", jurisdiction="India").payload["body"][:600])
