"""generate_terms_of_service — a Terms of Service grounded in the product idea + jurisdiction.

Deterministic template; governing law adapts to the jurisdiction. Not legal advice.
"""
from __future__ import annotations

from pydantic import BaseModel

from aps.tools.base import BaseTool
from aps.state.models import ToolResult
from aps.tools.legal import _legal
from aps.tools.analysis._text import clean_label


class Args(BaseModel):
    company_name: str = ""
    jurisdiction: str = "India"
    idea: str = ""


class GenerateTermsOfService(BaseTool):
    name = "generate_terms_of_service"
    namespace = "legal"
    description = (
        "Generate a Terms of Service for the product: service description, acceptable use, "
        "intellectual property, disclaimers, liability cap, termination, and governing law "
        "for the jurisdiction. Deterministic template; not legal advice."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        j = _legal.resolve_jurisdiction(args.jurisdiction)
        company = args.company_name or "[COMPANY NAME]"
        desc = clean_label(args.idea, max_words=14, max_chars=120) if args.idea else "[SERVICE DESCRIPTION]"

        body = f"""{_legal.disclaimer_banner()}
# Terms of Service — {company}

**Effective date:** [EFFECTIVE DATE]

These Terms govern your use of the {company} service ("Service"): {desc}.

## 1. Acceptance
By accessing or using the Service you agree to these Terms. If you do not agree, do not use
the Service.

## 2. The Service
{company} provides {desc}. We may modify or discontinue features at any time.

## 3. Accounts
You are responsible for your account credentials and all activity under your account. You must
provide accurate information and be legally able to enter this agreement.

## 4. Acceptable use
You agree not to misuse the Service, including by attempting unauthorised access, reverse
engineering, infringing others' rights, or using it for unlawful purposes.

## 5. Intellectual property
The Service and its content (excluding your content) are owned by {company}. You retain rights
to content you submit and grant {company} a licence to operate the Service.

## 6. Fees
[PRICING TERMS]. Fees are non-refundable except as required by law.

## 7. Disclaimers
The Service is provided "as is" without warranties of any kind to the extent permitted by law.

## 8. Limitation of liability
To the maximum extent permitted by law, {company}'s aggregate liability is limited to the
amounts you paid in the [12] months preceding the claim.

## 9. Termination
We may suspend or terminate access for breach of these Terms. You may stop using the Service
at any time.

## 10. Governing law
These Terms are governed by {j['governing_law']}, and disputes are subject to the courts of
[VENUE].

## 11. Contact
{company}, [REGISTERED ADDRESS] — [CONTACT EMAIL].
"""
        placeholders = ["[EFFECTIVE DATE]", "[PRICING TERMS]", "[VENUE]",
                        "[REGISTERED ADDRESS]", "[CONTACT EMAIL]"]
        if company == "[COMPANY NAME]":
            placeholders.insert(0, "[COMPANY NAME]")
        if desc == "[SERVICE DESCRIPTION]":
            placeholders.append("[SERVICE DESCRIPTION]")
        return ToolResult(ok=True, payload={
            "title": f"Terms of Service — {company}",
            "kind": "tos",
            "body": body,
            "placeholders": placeholders,
        })


TOOL = GenerateTermsOfService()

if __name__ == "__main__":
    print(TOOL.run(company_name="Habitly", idea="a privacy-first habit tracker").payload["body"][:500])
