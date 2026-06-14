# APS — Latency & Reliability Execution Plan

**Goal:** make a full Idea→Pitch run feel faster and more reliable than the deep-research
products (which take 5–30 min), without over-engineering for the demo. Target a **~25–35 s
cold run** and **~5–10 s warm (cached) run**, with predictable multi-user behavior.

This plan is grounded in the actual stack: FastAPI + background threads, LangGraph
orchestrator, `requests`-based tools, per-provider LLM token bucket, per-host HTTP token
bucket, ThreadPoolExecutor research fan-out, SSE/WS poll-based event delivery.

---

## 0. The latency budget (where the time actually goes)

| Stage | Today (serial) | After fixes | Warm (cached) |
|---|---|---|---|
| `plan_subtopics` (1 LLM call) | ~2–4 s | ~2–4 s | ~2–4 s |
| Research fan-out (3 units ∥) | ~25–45 s | ~15–20 s | ~3–6 s |
| └ tool calls **within** a unit | serial: 12×~2 s = ~24 s | parallel: ~6 s | cache hits: <1 s |
| Compression (1 LLM call) | ~2–4 s | ~2–4 s | ~2–4 s |
| Downstream (Product→Arch→Exec→Pres) | serial ~4–5 s | Arch∥Exec ~3 s | ~3 s |
| **Total** | **~60–120 s** | **~25–35 s** | **~5–10 s** |

The single dominant cost is **serial tool calls inside each research unit**. Fix that first;
everything else is incremental.

---

## 1. Latency fixes — ranked by ROI

### 1.1 Parallelize the tool-call loop (highest ROI, ~10 lines)
**Where:** `agents/research/agent.py::gather_evidence`, the `for call in calls:` loop.
**Problem:** when the model requests 4 tools in one round, they run back-to-back (~8 s).
**Fix:** wrap the loop in a `ThreadPoolExecutor(max_workers=min(len(calls), 4))` and `map`
the executions. Your infra is already thread-safe (rate limiter, `with_retry`, `infra/http`),
so this is contained with no architectural change. ~3–4× cut per unit.
**Industry name:** I/O fan-out / scatter-gather. This is the same pattern your supervisor
already uses one level up — you're just applying it one level down.

### 1.2 Add a tool-result cache (biggest *multi-run* and *warm-start* win)
**Where:** new `infra/cache.py`, wrapped around `BaseTool.run()`.
**Why it matters:** repeated/overlapping queries (same idea re-run in a demo, or two users
researching similar spaces) re-hit GitHub/HN/web for identical results. Cache keyed on
`(tool_name, normalized_args)` turns a 90 s cold run into ~5–10 s on re-run, and lets
concurrent runs share evidence instead of competing for the same rate-limited sources.
**Stack — right-sized:**
- **Demo:** in-process `cachetools.TTLCache` (LRU + TTL, e.g. 15 min). Zero infra.
- **Scale:** Redis with TTL per source (GitHub 10 min, arXiv 24 h, Wikipedia 24 h). Shared
  across worker processes and runs.
**Industry name:** read-through cache / memoization. This is the highest-leverage "hack"
not yet in your system and it directly neutralizes the rate-limit contention from the
A-then-B scenario.

### 1.3 Push-based event delivery (perceived latency)
**Where:** `api/main.py` SSE endpoint (`stream()`, `main.py:239`) + `v1/ws.py`, both poll
`bus_history()` on a 1 s / 0.2 s tick.
**Fix:** replace the poll with a push. The producer is a worker thread; the consumers are
async handlers — so the bridge is a `threading.Condition` on the bus, awaited from the loop:
1. `EventBus.publish()` appends to history (as today) **then** `notify_all()` on a per-run
   `threading.Condition`.
2. The SSE/WS generator, instead of `await asyncio.sleep(0.2)`, blocks on
   `await loop.run_in_executor(None, cond.wait, timeout)` — wakes the instant an event lands,
   with the timeout as a liveness floor (still honor the ~2 min cap and the
   `run_complete`/`run_failed` terminal check that already exist).
3. Keep the `sent` cursor + history replay so a late subscriber still gets the backlog — only
   the *wait* changes from poll to push (this also closes the `ws.py:76` double-`bus_history`
   race, since the seed + subscribe happen under the same lock).

**Why:** the run isn't faster, but progress appears the instant it happens — this is what
makes it *feel* faster than a deep-research spinner that shows nothing until done.
**Industry name:** publish/subscribe, event push vs poll. At scale, back this with Redis
pub/sub so multiple API workers see the same bus.

### 1.4 Migrate network I/O from `requests` → `httpx.AsyncClient` (higher ceiling)
**Where:** `infra/http.py` and the retrieval tools.
**Why:** `requests` is blocking, so you pay a thread per concurrent call. Async I/O lets one
event loop hold hundreds of in-flight network calls cheaply — this is what ODR does natively
with `asyncio.gather`, and it's the better long-term fit for an I/O-bound fan-out system.
**Tradeoff:** it's a real refactor (every tool becomes `async def`, the loop and supervisor
follow). **Do NOT do this for the demo** — 1.1's ThreadPoolExecutor gets you 80% of the
benefit for 5% of the effort. Schedule the async migration as the production step that
raises the concurrency ceiling.
**Stack:** `httpx.AsyncClient` with HTTP/2 + connection pooling (keep-alive reuses TCP/TLS
across calls to the same host — a free latency cut on GitHub/HN where you hit one host
repeatedly).

### 1.5 Parallelize the deterministic downstream — ❌ NOT APPLICABLE (verified)
**Where:** `orchestrator/graph.py`.
**Original idea:** run Architecture and Execution concurrently after Product, ~1–2 s.
**Finding (2026-06-11):** they are **not** independent in this codebase. `run_execution(trd,
prd)` consumes `trd.stack`, `trd.api_spec`, and `trd.scale_estimate`
(`agents/execution/agent.py:23-31`), so Execution depends on Architecture's output. The real
downstream shape is a chain — product → architecture → execution → presentation — with no
parallel pair. Implementing the split would feed Execution an empty TRD and corrupt the
artifact. **Skipped deliberately.** (To unlock it later, Execution would have to stop reading
the TRD — a design change, not a scheduling one.)

### 1.6 Stream partial artifacts
**Where:** orchestrator → SSE.
**Fix:** emit each artifact (`research_ready`, `prd_ready`, …) the moment it's produced so
the UI renders the package assembling, instead of waiting for `run_complete`.
**Why:** deep research shows nothing until the end; you show the PRD forming while
Architecture is still running. Pure perceived-speed win, and it's a demo differentiator.

### 1.7 "Deep mode" tunable (answers the breadth critique)
**Where:** `config/settings.py` + `supervisor.py`.
**Fix:** one knob that scales fan-out width (sub-researchers) and per-unit tool budget.
- `fast` (default): 3 units, ~8 tool calls each → ~20 s.
- `deep`: 6 units, ~20 tool calls each → ~60 s but matches deep-research breadth on demand.
**Why:** you're faster by default and can match their depth when asked — so "is it faster
because it's shallower?" stops being a valid criticism.

---

## 2. Concurrency, fairness & reliability (the A-then-B problem)

Today every `POST /runs` spawns `threading.Thread(daemon=True).start()` immediately, with no
queue. Two overlapping runs both start and **fight over the shared per-provider and per-host
rate buckets**, halving each other's throughput. There's no cancel, no deadline, no
admission control. Fixes:

### 2.1 Bounded queue + admission control (core fix)
**Where:** in front of run execution in `api/main.py`.
**Fix:** a bounded `queue.Queue` (or `asyncio.Semaphore`) capping concurrent runs at, say,
2–3. Run 3 waits for a slot. Gives FIFO fairness (A isn't starved by B) and back-pressure
(threads can't grow unbounded under load).
**Industry name:** bulkhead + admission control. At scale this becomes a real task queue —
**arq** (async, Redis, lightweight) or **Celery/RQ** — with a worker pool. For the demo, the
in-process bounded queue is correct; don't pull in Celery yet.

### 2.2 Cooperative cancellation
**Where:** `_RUNS[run_id]["cancel_event"]` + new `POST /runs/{id}/cancel` (or `DELETE`).
**Fix:** store a `threading.Event` per run (set in `start_run`, `main.py:124`, alongside the
bus); the endpoint sets it. Daemon threads can't be killed, so cancellation is *cooperative* —
the run must poll the flag at its own boundaries:
- **Orchestrator** (`graph.py`): check `cancel_event.is_set()` between the 5 named stages →
  raise a `RunCancelled` that `_run_in_background` (`main.py:110`) catches and records as a
  `run_cancelled` status (a 4th honest terminal state next to complete/degraded/failed).
- **Research loop** (`agent.py:90`, the `for call in calls:` loop): check before each tool
  call so a long fan-out unit stops mid-flight; pass the event into `gather_evidence`.
- **SSE/WS** already terminate on the terminal event — emit `run_cancelled` so the stream
  closes cleanly.

A cancelled run stops at the next boundary and frees its 2.1 queue slot.
**Why:** matches the interrupt feature deep research only shipped in Feb 2026, and prevents
a stuck run from holding a slot.

### 2.3 Per-run deadline / timeout budget
**Fix:** a wall-clock cap (e.g. 90 s `fast`, 5 min `deep`) that trips the cancel event, plus
a layered timeout budget: per-tool (15 s, exists) < per-unit < per-run. A hung LLM call that
stalls *before* the HTTP timeout is then bounded by the unit/run deadline.
**Industry name:** deadline propagation / timeout budgeting.

### 2.4 Idempotency guard (dedup double-submits)
**Fix:** accept an `Idempotency-Key` header (or hash of idea+config); if a run with that key
is in-flight, return the existing `run_id` instead of starting a duplicate. Stops accidental
double-clicks and retried POSTs from spawning twin runs.
**Industry name:** idempotency key — standard for any "create" endpoint (Stripe-style).

### 2.5 Circuit breaker on flaky sources
**Where:** `infra/http.py`, per host.
**Fix:** if a source (e.g. Reddit) returns errors N times in a window, open the breaker and
skip it for a cooldown instead of burning retry budget and latency on every call.
**Stack:** `pybreaker`, or a small hand-rolled per-host state machine.
**Industry name:** circuit breaker. Pairs with your existing retry + graceful degradation.

### 2.6 Protect the health/ping lane
**Why it's a real risk here:** the run-start path holds no event-loop time (it just spawns a
thread), so `GET /health` won't actually queue behind a `/runs` *today*. The lane only gets
contended once heavy work moves onto the loop (the async migration, 1.4) **or** any sync route
does blocking work in the handler. So this is a guard against regressions, sized accordingly.
**Fix (demo, ~free):**
- Keep `GET /health` (`main.py:147`) dependency-free — no `_auth`, no `engine.stats()`, no
  store reads. It already is; the rule is "don't let it grow a dependency."
- Move any blocking sync route off the loop with `fastapi.concurrency.run_in_threadpool` (or
  `def` handlers, which FastAPI already threadpools) so one slow handler can't stall liveness.
- Add a cheap `GET /v1/system/ping` that returns `{"ok": true}` with zero engine touch, for
  the frontend's high-frequency poll — separate from the heavier `/v1/system/health`.
**Fix (scale):** a dedicated Uvicorn worker for the health path, or an ASGI middleware
fast-path that short-circuits `/health` before the router. Out of scope for the demo.

---

## 3. Reliability patterns you already have (keep, don't rebuild)

- **Retry with backoff** on transient 429/5xx (`with_retry`) — thread-safe. ✓
- **Per-provider + per-host token buckets** — thread-safe. ✓
- **Graceful degradation** — fan-out → single-unit → keyless real-evidence fallback. ✓
- **Empty-fan-out fallback** — retries single-unit before raising. ✓

What to *add* on top: the **cache (1.2)**, **circuit breaker (2.5)**, **deadline budget
(2.3)**, and **idempotency (2.4)**. Together these are the standard resilience quartet
(retry / cache / breaker / timeout) that production I/O systems run.

---

## 4. Observability (so you can prove the speedup)

- **Per-tool timing** — ✅ **done**: `BaseTool.run()` emits `tool_call` + `tool_result`
  (with elapsed ms, ok, evidence count) through a ContextVar event sink onto the run's bus,
  including from the parallel fan-out workers. Unlocks the frontend live-tool-stream money
  shot and per-tool latency in the trace (`infra/trace.py`, `tools/base.py`).
- **Subsystem stats** — ✅ **done**: `/stats` now reports `queue_depth`, `max_concurrent_runs`,
  `queued`, and `tool_cache` hit-rate/size alongside the existing honest run metrics.
- **Load test** — ✅ **done**: `scripts/loadtest.py` fires N concurrent `POST /runs` and reports
  admission p50/p95, 202-vs-503 spread (back-pressure), and live queue depth — the in-process
  k6/Locust analog, zero extra deps. Run it before claiming multi-user reliability.
- **Prometheus** — already wired (`infra/metrics.py`, `/metrics`); extend with run-latency
  histograms + breaker state when needed.
- **OpenTelemetry traces** — ⏸ **deferred (Phase 4)**: agent/tool spans → a flamegraph. A real
  dependency + instrumentation pass; a demo *asset*, not a demo *requirement*. The
  `infra/trace.py` sink is the seam an OTel exporter would hang off.

---

## 5. Phased execution order (do in this sequence)

### Phase 1 — Demo speed (a few hours, do now)
1. **Parallel tool-call loop** (1.1) — the headline latency cut.
2. **Tool-result cache, in-process TTLCache** (1.2) — warm runs in seconds, kills A/B contention.
3. **Push-based events** (1.3) — instant live UI.
4. **Stream partial artifacts** (1.6) — package assembles on screen.

> After Phase 1: cold run ~25–35 s, warm ~5–10 s, UI feels instant. This is the demo.

### Phase 2 — Predictable multi-user (half a day)
5. **Bounded queue + admission control** (2.1).
6. **Cancellation token + endpoint** (2.2).
7. **Per-run deadline** (2.3).
8. **Idempotency guard** (2.4).

> After Phase 2: "whose request runs?" has a clean answer — A runs, B queues, both stay fast,
> either can be cancelled, nothing hangs.

### Phase 3 — Robustness polish (half a day)
9. **Circuit breaker** (2.5) + **deep-mode knob** (1.7). *(1.5 parallel downstream dropped —
   Execution depends on the TRD; see §1.5.)*
10. **OTel traces + k6 load test** (§4) to prove the numbers.

### Phase 4 — Production ceiling (post-demo, optional)
11. **Async migration** `requests`→`httpx.AsyncClient` + HTTP/2 pooling (1.4).
12. **Redis** for cache + pub/sub events; **arq** task queue replacing the in-process queue.

> Phase 4 raises the concurrency ceiling for real traffic. Explicitly **not** demo work —
> note it in the MEMO as "what more time / scale would add."

---

## 6. What NOT to do for the demo (avoid over-engineering)

- **No Celery/Kafka/microservices.** An in-process bounded queue is correct at demo scale;
  distributed task queues add ops overhead with no demo payoff.
- **No async rewrite yet.** ThreadPoolExecutor (1.1) captures most of the benefit; the async
  migration is a Phase-4 production move, not a demo move.
- **No LLM batching.** Batch endpoints cut cost on large workloads but *add* latency for a
  real-time single run — wrong direction for the demo.
- **No priority queue** unless a real use case needs B to jump ahead of A. FIFO fairness is
  enough; build priority only on demand. *If* the need appears (e.g. a "fast/interactive" run
  should preempt a queued "deep" run), it's a one-line swap on the 2.1 queue —
  `queue.PriorityQueue` keyed on `(priority, submit_seq)`, with `submit_seq` breaking ties so
  equal-priority runs stay FIFO. No new infrastructure; don't build it speculatively.
- **No multi-region / CDN / autoscaling.** Out of scope; the static frontend can sit on a CDN
  trivially later, but it's not a latency lever for the run itself.

---

## 7. One-line summary per technique

| Technique | Industry pattern | Phase | Payoff |
|---|---|---|---|
| Parallel tool calls | scatter-gather I/O fan-out | 1 | 3–4× per unit |
| Tool-result cache | read-through cache / memoization | 1 | warm runs ~5–10 s; kills contention |
| Push events | pub/sub vs poll | 1 | near-zero UI lag |
| Stream artifacts | progressive rendering | 1 | perceived speed |
| Bounded queue | bulkhead + admission control | 2 | fair, bounded multi-user |
| Cancellation token | cooperative cancellation | 2 | interrupt + free slots |
| Deadline budget | timeout propagation | 2 | no hung runs |
| Idempotency key | dedup create | 2 | no twin runs |
| Circuit breaker | breaker (retry/cache/breaker/timeout quartet) | 3 | skip dead sources fast |
| Deep-mode knob | tunable depth | 3 | matches breadth on demand |
| OTel + k6 | tracing + load test | 3 | prove the numbers |
| httpx async + HTTP/2 pool | async I/O + connection reuse | 4 | concurrency ceiling |
| Redis + arq | distributed cache + task queue | 4 | horizontal scale |

**Start with Phase 1, items 1–4.** That's the few hours that turn "as slow as deep research"
into "watch the package build in under a minute," and the cache is what keeps it fast when a
second user shows up.
