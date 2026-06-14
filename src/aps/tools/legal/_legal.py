"""Shared, deterministic primitives for the legal document tools (Launch Studio Phase 2).

Leading underscore ⇒ the registry never mistakes this for a TOOL module. Pure stdlib, no
network, no LLM. Holds the NOT-LEGAL-ADVICE disclaimer, a small jurisdiction map that adapts
the cited privacy regime + employment framing, and a helper that infers data categories from
the TRD data model so the privacy policy reflects what the product actually stores.
"""
from __future__ import annotations

from typing import Any

# Shown at the top of every document AND on the package — these are templates, not advice.
DISCLAIMER = (
    "**NOT LEGAL ADVICE.** This document is an automatically generated template produced "
    "from your product facts. It is a starting point only and may not reflect the law of your "
    "jurisdiction or your specific circumstances. Have a qualified attorney review and adapt "
    "it before any use. Bracketed [PLACEHOLDERS] must be completed."
)

# Jurisdiction → cited regimes + framing. Keys are matched loosely (substring, case-insensitive)
# so "India", "Delaware, USA", "European Union", "United Kingdom" all resolve. India is the
# default (chosen by the user); the others are supported for the env override.
JURISDICTIONS: dict[str, dict[str, Any]] = {
    "india": {
        "governing_law": "the laws of India",
        "privacy_law": "the Digital Personal Data Protection Act, 2023 (DPDP Act)",
        "privacy_authority": "the Data Protection Board of India",
        "data_principal": "Data Principal",          # DPDP term for the individual
        "at_will": False,                              # India uses notice-period employment
        "notice_period": "30 days",
    },
    "european union": {
        "governing_law": "the laws of the relevant EU member state",
        "privacy_law": "the EU General Data Protection Regulation (GDPR)",
        "privacy_authority": "the competent supervisory authority",
        "data_principal": "Data Subject",
        "at_will": False,
        "notice_period": "one month",
    },
    "united kingdom": {
        "governing_law": "the laws of England and Wales",
        "privacy_law": "the UK GDPR and the Data Protection Act 2018",
        "privacy_authority": "the Information Commissioner's Office (ICO)",
        "data_principal": "Data Subject",
        "at_will": False,
        "notice_period": "one month",
    },
    "delaware": {
        "governing_law": "the laws of the State of Delaware, USA",
        "privacy_law": "the California Consumer Privacy Act (CCPA/CPRA) where applicable",
        "privacy_authority": "the applicable state authority",
        "data_principal": "Consumer",
        "at_will": True,                               # US default
        "notice_period": None,
    },
}
_DEFAULT_KEY = "india"


def resolve_jurisdiction(jurisdiction: str) -> dict[str, Any]:
    """Map a free-text jurisdiction to its regime record (loose substring match; India default)."""
    j = (jurisdiction or "").strip().lower()
    for key, rec in JURISDICTIONS.items():
        if key in j or j in key:
            return {**rec, "name": jurisdiction.strip() or "India"}
    # also catch common aliases
    if any(t in j for t in ("usa", "united states", "u.s", "america")):
        return {**JURISDICTIONS["delaware"], "name": jurisdiction.strip()}
    if any(t in j for t in ("eu", "europe", "gdpr")):
        return {**JURISDICTIONS["european union"], "name": jurisdiction.strip()}
    if any(t in j for t in ("uk", "britain", "england")):
        return {**JURISDICTIONS["united kingdom"], "name": jurisdiction.strip()}
    return {**JURISDICTIONS[_DEFAULT_KEY], "name": jurisdiction.strip() or "India"}


# Field-name → human data-category mapping for the privacy policy. Keeps the policy grounded in
# what the data model actually stores rather than a generic boilerplate list.
_PII_HINTS = {
    "email": "Email address",
    "name": "Name",
    "phone": "Phone number",
    "address": "Postal address",
    "dob": "Date of birth",
    "avatar": "Profile image",
    "photo": "Profile image",
}
_ACCOUNT_HINTS = {"id", "owner_id", "user_id", "role", "status"}
_USAGE_HINTS = {"created_at", "updated_at", "timestamp", "last_seen", "deleted_at"}


def data_categories(data_model: dict[str, Any] | None) -> list[str]:
    """Infer human-readable data categories from the TRD data model entities/fields.

    Returns a de-duplicated, stable-ordered list (e.g. 'Email address', 'Account identifiers',
    'Usage and activity data'). Falls back to a sensible generic set when the model is empty.
    """
    cats: list[str] = []

    def _add(c: str) -> None:
        if c not in cats:
            cats.append(c)

    entities = (data_model or {}).get("entities", {}) if isinstance(data_model, dict) else {}
    for _ent, spec in entities.items():
        fields = (spec or {}).get("fields", {}) if isinstance(spec, dict) else {}
        for field in fields:
            f = str(field).lower()
            matched = False
            for hint, label in _PII_HINTS.items():
                if hint in f:
                    _add(label)
                    matched = True
                    break
            if matched:
                continue
            if f in _ACCOUNT_HINTS or f.endswith("_id"):
                _add("Account identifiers")
            elif f in _USAGE_HINTS or f.endswith("_at"):
                _add("Usage and activity data")
            else:
                _add("Content you create in the service")

    if not cats:
        cats = ["Account identifiers", "Email address", "Usage and activity data",
                "Content you create in the service"]
    return cats


def placeholder(label: str) -> str:
    """Format a party-specific placeholder token consistently: `[LABEL]`."""
    return f"[{label.strip().upper()}]"


def disclaimer_banner() -> str:
    """The disclaimer as a Markdown blockquote, for the top of a rendered document body."""
    return "> " + DISCLAIMER.replace("\n", "\n> ") + "\n"
