// React hooks that hydrate the animated pages with live /v1 data WITHOUT changing their look.
//
// The pattern: `useLive(fetcher, fallback)` returns `fallback` (the page's existing hardcoded
// mock) immediately, then swaps in real backend data once it arrives. If the backend is down
// or the shape is empty, the page keeps its mock — so design + animations always render. This
// lets each page be wired with a one-line change at its seed point.

import { useEffect, useRef, useState } from 'react';
import { openRunSocket } from './api';

const RUN_KEY = 'aps_active_run';

export function getActiveRun(): string | null {
  try { return localStorage.getItem(RUN_KEY); } catch { return null; }
}
export function setActiveRun(id: string): void {
  try { localStorage.setItem(RUN_KEY, id); } catch { /* ignore */ }
}

/** Returns [data, isLive]. Starts at `fallback`; replaces with the fetch result on success. */
export function useLive<T>(fetcher: () => Promise<T>, fallback: T, deps: any[] = []): [T, boolean] {
  const [data, setData] = useState<T>(fallback);
  const [live, setLive] = useState(false);
  useEffect(() => {
    let alive = true;
    fetcher()
      .then((res) => {
        if (!alive || res == null) return;
        if (Array.isArray(res) && res.length === 0) return; // keep richer mock over empty live
        setData(res);
        setLive(true);
      })
      .catch(() => { /* keep fallback */ });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return [data, live];
}

/** Hydrate a run-scoped resource from the active run, keeping `fallback` until live data lands.
 *  One-liner for the animated zones: `const [AGENTS] = useRunResource(api.runAgents, AGENTS_SEED)`. */
export function useRunResource<T>(fetcher: (runId: string) => Promise<T>, fallback: T): [T, boolean] {
  const runId = getActiveRun();
  return useLive<T>(
    () => (runId ? fetcher(runId) : Promise.reject(new Error('no active run'))),
    fallback,
    [runId],
  );
}

/** Poll a fetcher on an interval (for the System page's "live" panels). Mock until first ok. */
export function usePolled<T>(fetcher: () => Promise<T>, fallback: T, ms = 5000): [T, boolean] {
  const [data, setData] = useState<T>(fallback);
  const [live, setLive] = useState(false);
  useEffect(() => {
    let alive = true;
    const tick = () => fetcher().then((res) => {
      if (!alive || res == null) return;
      if (Array.isArray(res) && res.length === 0) return;
      setData(res); setLive(true);
    }).catch(() => { /* keep fallback */ });
    tick();
    const id = setInterval(tick, ms);
    return () => { alive = false; clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return [data, live];
}

/** Subscribe to a run's WebSocket; invokes handlers for event/metric_tick frames. */
export function useRunSocket(
  runId: string | null,
  handlers: { onEvent?: (e: any) => void; onMetric?: (m: any) => void; onAgent?: (a: any) => void },
): void {
  const ref = useRef<WebSocket | null>(null);
  useEffect(() => {
    if (!runId) return;
    let closed = false;
    openRunSocket(runId, (type, payload) => {
      if (closed) return;
      if (type === 'event') handlers.onEvent?.(payload);
      else if (type === 'metric_tick') handlers.onMetric?.(payload);
      else if (type === 'agent_update') handlers.onAgent?.(payload);
    }).then((ws) => { if (ws) ref.current = ws; });
    return () => { closed = true; ref.current?.close(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);
}
