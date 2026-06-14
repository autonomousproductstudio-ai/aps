"""Availability tool namespace (Launch Studio Phase 4: Trademark / Domain).

The first tools that do LIVE retrieval: domain availability via RDAP (real, keyless) and an
indicative trademark check with official-registry links. Both carry a long cache TTL (6h) so
repeat runs are near-free, go through `aps.infra.http` (rate-limited + circuit-broken), and
fall back to labelled fixtures offline.
"""
