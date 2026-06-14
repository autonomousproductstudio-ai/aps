"""generate_nda — a mutual Non-Disclosure Agreement template.

Deterministic; governing law adapts to the jurisdiction. Not legal advice.
"""
from __future__ import annotations

from pydantic import BaseModel

from aps.tools.base import BaseTool
from aps.state.models import ToolResult
from aps.tools.legal import _legal


class Args(BaseModel):
    company_name: str = ""
    jurisdiction: str = "India"


class GenerateNDA(BaseTool):
    name = "generate_nda"
    namespace = "legal"
    description = (
        "Generate a mutual Non-Disclosure Agreement (NDA) for sharing confidential information "
        "with partners, candidates, or investors: definition, obligations, exclusions, term, "
        "and governing law. Deterministic template; not legal advice."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        j = _legal.resolve_jurisdiction(args.jurisdiction)
        company = args.company_name or "[COMPANY NAME]"

        body = f"""{_legal.disclaimer_banner()}
# Mutual Non-Disclosure Agreement

**Date:** [EFFECTIVE DATE]

This Mutual Non-Disclosure Agreement ("Agreement") is entered into between **{company}**
("Party A") and **[COUNTERPARTY NAME]** ("Party B"), each a "Party".

## 1. Purpose
The Parties wish to explore [PURPOSE OF DISCLOSURE] and may disclose confidential information
to each other for that purpose.

## 2. Confidential Information
"Confidential Information" means non-public information disclosed by one Party (the "Disclosing
Party") to the other (the "Receiving Party"), whether oral, written, or electronic, that is
marked or would reasonably be understood to be confidential.

## 3. Obligations
The Receiving Party shall (a) use Confidential Information solely for the Purpose, (b) protect
it with at least reasonable care, and (c) not disclose it to third parties except to employees
or advisers with a need to know who are bound by similar obligations.

## 4. Exclusions
Confidential Information does not include information that is or becomes public through no
fault of the Receiving Party, was lawfully known before disclosure, is independently
developed, or is rightfully received from a third party.

## 5. Compelled disclosure
The Receiving Party may disclose Confidential Information if required by law, provided it gives
prompt notice where permitted.

## 6. Term
This Agreement remains in effect for [TERM, e.g. 2 years] from the Date, and confidentiality
obligations survive for [SURVIVAL PERIOD, e.g. 3 years] after disclosure.

## 7. No licence
No licence or ownership is granted by disclosure. All Confidential Information remains the
property of the Disclosing Party.

## 8. Governing law
This Agreement is governed by {j['governing_law']}.

**{company}** — Signature: ______________  Name: [SIGNATORY NAME]  Date: ______
**[COUNTERPARTY NAME]** — Signature: ______________  Name: [SIGNATORY NAME]  Date: ______
"""
        placeholders = ["[EFFECTIVE DATE]", "[COUNTERPARTY NAME]", "[PURPOSE OF DISCLOSURE]",
                        "[TERM, e.g. 2 years]", "[SURVIVAL PERIOD, e.g. 3 years]",
                        "[SIGNATORY NAME]"]
        if company == "[COMPANY NAME]":
            placeholders.insert(0, "[COMPANY NAME]")
        return ToolResult(ok=True, payload={
            "title": "Mutual Non-Disclosure Agreement",
            "kind": "nda",
            "body": body,
            "placeholders": placeholders,
        })


TOOL = GenerateNDA()

if __name__ == "__main__":
    print(TOOL.run(company_name="Habitly").payload["body"][:500])
