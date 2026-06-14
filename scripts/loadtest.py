"""Concurrency load test (plan §4) — prove the bounded queue holds under burst.

Fires N concurrent POST /runs at a running API and reports admission latency p50/p95, the
status spread (202 admitted vs 503 back-pressure), and the live queue depth from /stats. This
is the "before claiming multi-user reliability" check the execution plan calls for — the
in-process analog of k6/Locust, with zero extra deps (uses the `requests` already in the env).

Usage (start the API first):
    uvicorn aps.api.main:app
    python scripts/loadtest.py --n 10 --url http://127.0.0.1:8000 --key dev-key

It does NOT wait for runs to finish — it measures the admission path (queue + worker pool),
which is what determines whether a flood stays fair and bounded.
"""
from __future__ import annotations

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import requests


def _one(url: str, key: str, i: int) -> tuple[int, float]:
    t0 = time.perf_counter()
    r = requests.post(f"{url}/runs", headers={"X-APS-Key": key},
                      json={"idea": f"load-test idea #{i}"}, timeout=30)
    return r.status_code, (time.perf_counter() - t0) * 1000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10, help="concurrent POST /runs")
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--key", default="dev-key")
    args = ap.parse_args()

    print(f"firing {args.n} concurrent POST {args.url}/runs ...")
    with ThreadPoolExecutor(max_workers=args.n) as pool:
        results = list(pool.map(lambda i: _one(args.url, args.key, i), range(args.n)))

    codes = [c for c, _ in results]
    lat = sorted(ms for _, ms in results)
    admitted = sum(1 for c in codes if c == 202)
    throttled = sum(1 for c in codes if c == 503)
    p50 = statistics.median(lat)
    p95 = lat[min(len(lat) - 1, int(len(lat) * 0.95))]

    print(f"  admitted (202):     {admitted}")
    print(f"  back-pressure (503): {throttled}")
    print(f"  other codes:        {[c for c in codes if c not in (202, 503)]}")
    print(f"  admission p50/p95:  {p50:.1f} ms / {p95:.1f} ms")

    try:
        s = requests.get(f"{args.url}/stats", headers={"X-APS-Key": args.key}, timeout=10).json()
        print(f"  queue_depth:        {s.get('queue_depth')} "
              f"(cap {s.get('max_concurrent_runs')} concurrent)")
        print(f"  by_status:          {s.get('by_status')}")
        print(f"  tool_cache:         {s.get('tool_cache')}")
    except Exception as e:
        print(f"  (could not read /stats: {e})")


if __name__ == "__main__":
    main()
