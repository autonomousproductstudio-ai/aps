"""pricing_page_extract — fetch a pricing page and pull out price points / tiers.

Use to capture a competitor's actual pricing for the competitor matrix. Fetches the
page (no key) then regex-extracts currency amounts and nearby tier labels.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from aps.tools.base import BaseTool, fixture_or_error, USER_AGENT, DEFAULT_TIMEOUT
from aps.state.models import ToolResult, Evidence
from aps.tools.retrieval.fetch_page import html_to_text

_PRICE = re.compile(r"(?:[$€£])\s?\d[\d,]*(?:\.\d{1,2})?(?:\s?/\s?(?:mo|month|yr|year|user|seat))?",
                    re.IGNORECASE)
_TIER = re.compile(r"\b(free|starter|basic|pro|plus|team|business|enterprise|premium)\b",
                   re.IGNORECASE)


class Args(BaseModel):
    url: str = Field(..., description="URL of a pricing page")


class PricingPageExtract(BaseTool):
    name = "pricing_page_extract"
    namespace = "retrieval"
    description = (
        "Fetch a competitor's pricing page and extract concrete price points and tier "
        "names (no key). Use to fill the pricing column of a competitor matrix with real "
        "numbers rather than guesses. You must supply the pricing-page URL."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        if not args.url.startswith(("http://", "https://")):
            return ToolResult(ok=False, error="url must start with http:// or https://")
        try:
            from aps.infra import http
            r = http.get(args.url, headers={"User-Agent": USER_AGENT},
                             timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            text = html_to_text(r.text)
            prices = list(dict.fromkeys(_PRICE.findall(text)))[:20]
            tiers = list(dict.fromkeys(t.lower() for t in _TIER.findall(text)))[:10]
            snippet = f"prices: {', '.join(prices) or 'none found'} | tiers: {', '.join(tiers) or 'n/a'}"
            ev = [Evidence(source="web", url=args.url, title="pricing", snippet=snippet[:280])]
            return ToolResult(ok=True, payload={"prices": prices, "tiers": tiers}, evidence=ev)
        except Exception as e:
            return fixture_or_error(str(e), payload={"prices": ["$0", "$12/mo", "$29/mo"],
                                                     "tiers": ["free", "pro", "team"]},
                                    evidence=[
                Evidence(source="web", url=args.url, title="[fixture] pricing",
                         snippet="prices: $0, $12/mo, $29/mo | tiers: free, pro, team")
            ])


TOOL = PricingPageExtract()

if __name__ == "__main__":
    import sys
    import json
    out = TOOL.run(url=sys.argv[1] if len(sys.argv) > 1 else "https://example.com/pricing")
    print(json.dumps(out.model_dump(), indent=2, default=str))
