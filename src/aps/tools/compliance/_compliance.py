"""Shared deterministic compliance logic (Launch Studio Phase 5).

Leading underscore ⇒ the registry skips it. Maps the product's country + data model to the
regulatory regimes that apply and a concrete checklist. Reuses the legal-side jurisdiction map
and data-category inference so the two agents stay consistent. No LLM, no network.
"""
from __future__ import annotations

from typing import Any

from aps.tools.legal._legal import resolve_jurisdiction, data_categories

DISCLAIMER = (
    "Compliance scaffolding only — not legal or compliance advice. Confirm scope and "
    "obligations with a qualified professional before relying on it."
)

# Field-name hints that signal a special-category data regime beyond baseline privacy.
_HEALTH = ("health", "medical", "vitals", "diagnos", "patient", "bloodpressure", "heartrate",
           "bmi", "symptom", "prescription")
_PAYMENT = ("card", "payment", "cardnumber", "cvv", "billing", "iban", "upi", "bank_account",
            "paymentmethod")
_CREDS = ("password", "secret", "token", "ssn", "aadhaar", "passport", "biometric")


def _field_names(data_model: dict[str, Any] | None) -> list[str]:
    out: list[str] = []
    entities = (data_model or {}).get("entities", {}) if isinstance(data_model, dict) else {}
    for spec in entities.values():
        fields = (spec or {}).get("fields", {}) if isinstance(spec, dict) else {}
        out.extend(str(f).lower().replace("_", "") for f in fields)
    return out


def _privacy_regime(country: str) -> dict[str, str]:
    j = resolve_jurisdiction(country)
    # name the headline privacy law for the regime
    law = j["privacy_law"]
    if "DPDP" in law:
        name = "DPDP Act (India)"
    elif "GDPR" in law and "UK" in law:
        name = "UK GDPR"
    elif "GDPR" in law:
        name = "GDPR (EU)"
    elif "CCPA" in law:
        name = "CCPA/CPRA (US)"
    else:
        name = law
    return {"name": name, "law": law, "authority": j["privacy_authority"]}


def assess(country: str, data_model: dict[str, Any] | None,
           idea: str = "") -> dict[str, Any]:
    """Return {country, regimes, checklist} from the country + data model (+ idea text).

    Health/payment regimes are detected from the data-model field names AND from the idea
    text — the auto-generated data model often uses generic field names (id/status/…), so an
    idea like 'a health tracker that stores vitals' would otherwise miss the health regime.
    Deterministic.
    """
    fields = _field_names(data_model)
    blob = (idea or "").lower().replace("_", "")
    cats = data_categories(data_model)  # always non-empty → the privacy regime always applies
    has_health = (any(any(h in f for h in _HEALTH) for f in fields)
                  or any(h in blob for h in _HEALTH))
    has_payment = (any(any(p in f for p in _PAYMENT) for f in fields)
                   or any(p in blob for p in _PAYMENT))
    has_creds = any(any(c in f for c in _CREDS) for f in fields)

    regimes: list[dict[str, Any]] = []
    checklist: list[dict[str, Any]] = []

    # 1) Privacy regime (always applies — any service handling personal data)
    pr = _privacy_regime(country)
    regimes.append({
        "name": pr["name"], "applicable": True,
        "why": f"The service processes personal data ({', '.join(cats[:4])}).",
        "obligations": [
            "Publish a privacy notice and obtain a lawful basis / consent",
            "Honour data-subject rights (access, correction, erasure, portability)",
            f"Be ready to respond to {pr['authority']}",
            "Maintain a record of processing and a breach-notification process",
        ],
    })
    for ob in ("Publish a compliant privacy notice", "Implement consent capture + withdrawal",
               "Build data-subject-request handling (access/erasure)",
               "Document a 72h breach-notification runbook"):
        checklist.append({"item": ob, "regime": pr["name"], "status": "todo"})

    # 2) Security baseline (SOC 2 / ISO 27001) — always recommended for a SaaS
    regimes.append({
        "name": "SOC 2 / ISO 27001 (security baseline)", "applicable": True,
        "why": "Operating a multi-tenant SaaS that stores customer data.",
        "obligations": ["Access control + audit logging", "Encryption in transit and at rest",
                        "Vendor/sub-processor risk review", "Incident response plan"],
    })
    for ob in ("Enforce least-privilege access + audit logs", "Encrypt data in transit and at rest",
               "Maintain a sub-processor register"):
        checklist.append({"item": ob, "regime": "SOC 2 / ISO 27001", "status": "todo"})

    # 3) Conditional regimes from the data model
    if has_health:
        regimes.append({
            "name": "Health-data rules (e.g. HIPAA / special-category data)", "applicable": True,
            "why": "The data model stores health/medical fields (special-category data).",
            "obligations": ["Extra consent + purpose limitation for health data",
                            "Stronger access controls and audit", "Data-processing agreements with any processors"],
        })
        checklist.append({"item": "Apply special-category safeguards to health data",
                          "regime": "Health-data rules", "status": "todo"})
    if has_payment:
        regimes.append({
            "name": "PCI-DSS", "applicable": True,
            "why": "The data model stores payment/card fields.",
            "obligations": ["Never store raw card data — tokenise via a PCI-compliant processor",
                            "Scope reduction (SAQ-A where possible)"],
        })
        checklist.append({"item": "Use a PCI-compliant processor; do not store raw card data",
                          "regime": "PCI-DSS", "status": "todo"})
    if has_creds:
        checklist.append({"item": "Hash/secret-manage credentials & sensitive identifiers",
                          "regime": "SOC 2 / ISO 27001", "status": "todo"})

    return {"country": resolve_jurisdiction(country)["name"], "regimes": regimes,
            "checklist": checklist}
