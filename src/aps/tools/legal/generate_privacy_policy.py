"""generate_privacy_policy — a Privacy Policy grounded in the product's data model.

Deterministic: data categories are inferred from the TRD data model (so the policy reflects
what the product actually stores), and the cited privacy regime adapts to the jurisdiction
(DPDP / GDPR / CCPA). Returns a LegalDocument-shaped dict. Template, not legal advice.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult
from aps.tools.legal import _legal


class Args(BaseModel):
    company_name: str = ""
    jurisdiction: str = "India"
    data_model: dict[str, Any] = Field(default_factory=dict)


class GeneratePrivacyPolicy(BaseTool):
    name = "generate_privacy_policy"
    namespace = "legal"
    description = (
        "Generate a Privacy Policy grounded in the product's data model (the categories of "
        "personal data actually collected) and the applicable privacy regime for the "
        "jurisdiction (DPDP / GDPR / CCPA). Deterministic template; not legal advice."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        j = _legal.resolve_jurisdiction(args.jurisdiction)
        company = args.company_name or "[COMPANY NAME]"
        cats = _legal.data_categories(args.data_model)
        principal = j["data_principal"]
        cats_md = "\n".join(f"- {c}" for c in cats)

        body = f"""{_legal.disclaimer_banner()}
# Privacy Policy — {company}

**Effective date:** [EFFECTIVE DATE]

{company} ("we", "us") operates the {company} service. This policy explains what personal
data we process and your rights, consistent with {j['privacy_law']}.

## 1. Data we collect
We collect and process the following categories of personal data:
{cats_md}

## 2. How we use your data
We use this data to provide and secure the service, to communicate with you, to comply with
legal obligations, and to improve the service. We process it on the lawful bases permitted by
{j['privacy_law']} (including your consent and the performance of our contract with you).

## 3. Sharing
We do not sell your personal data. We share it only with processors/sub-processors acting on
our instructions, and where required by law. Sub-processors: [LIST SUB-PROCESSORS].

## 4. Retention
We retain personal data only as long as necessary for the purposes above or as required by
law, after which it is deleted or anonymised.

## 5. Your rights
As a {principal}, you may request access, correction, erasure, and portability of your data,
and may withdraw consent. To exercise these rights, contact us at [CONTACT EMAIL]. You may
also lodge a complaint with {j['privacy_authority']}.

## 6. Security
We apply reasonable technical and organisational measures to protect your data. No method of
transmission or storage is completely secure.

## 7. Contact
Data controller: {company}, [REGISTERED ADDRESS]. Contact: [CONTACT EMAIL].

_Governed by {j['governing_law']}._
"""
        placeholders = ["[EFFECTIVE DATE]", "[CONTACT EMAIL]", "[REGISTERED ADDRESS]",
                        "[LIST SUB-PROCESSORS]"]
        if company == "[COMPANY NAME]":
            placeholders.insert(0, "[COMPANY NAME]")
        return ToolResult(ok=True, payload={
            "title": f"Privacy Policy — {company}",
            "kind": "privacy_policy",
            "body": body,
            "placeholders": placeholders,
        })


TOOL = GeneratePrivacyPolicy()

if __name__ == "__main__":
    out = TOOL.run(company_name="Habitly", jurisdiction="India",
                   data_model={"entities": {"User": {"fields": {"email": "string",
                                                                  "created_at": "datetime"}}}})
    print(out.payload["body"][:600])
