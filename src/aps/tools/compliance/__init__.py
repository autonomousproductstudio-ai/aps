"""Compliance tool namespace (Launch Studio Phase 5, gated hard).

Two tools: `assess_compliance` (deterministic regime applicability + checklist from the data
model + country) and `search_compliance_guidance` (best-effort live regulator citations, cached
24h, fixture fallback). Only invoked when APS_ENABLE_COMPLIANCE is set (default off).
"""
