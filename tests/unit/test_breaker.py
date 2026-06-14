"""Unit tests for the per-host circuit breaker (plan 2.5)."""
from __future__ import annotations

import time

from aps.infra.breaker import CircuitBreaker


def test_opens_after_threshold_consecutive_failures():
    b = CircuitBreaker(threshold=3, cooldown=60)
    assert b.allow("host") is True and b.state("host") == "closed"
    b.record_failure("host")
    b.record_failure("host")
    assert b.allow("host") is True            # still under threshold
    b.record_failure("host")                  # third → trips
    assert b.allow("host") is False and b.state("host") == "open"


def test_success_resets_failure_count():
    b = CircuitBreaker(threshold=2, cooldown=60)
    b.record_failure("h")
    b.record_success("h")                     # clears the streak
    b.record_failure("h")
    assert b.allow("h") is True               # only one failure since reset → still closed


def test_cooldown_allows_a_half_open_trial():
    b = CircuitBreaker(threshold=1, cooldown=0.05)
    b.record_failure("h")
    assert b.allow("h") is False              # open
    time.sleep(0.06)
    assert b.allow("h") is True               # cooldown elapsed → half-open trial permitted
    b.record_success("h")                     # trial succeeds → fully closed
    assert b.state("h") == "closed"


def test_keys_are_isolated_per_host():
    b = CircuitBreaker(threshold=1, cooldown=60)
    b.record_failure("a")
    assert b.allow("a") is False
    assert b.allow("b") is True               # unrelated host unaffected
