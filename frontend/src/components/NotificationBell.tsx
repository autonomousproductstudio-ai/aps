// Notification bell — tells the user when their run has finished (research + all artifacts), from
// any page. Polls the active run's status; on completion it raises a notification once per run and
// shows a badge on the bell. Notifications + "already-notified" runs persist in localStorage, so
// the badge survives navigation and reloads and never double-fires for the same run.
import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { getActiveRun } from '../lib/useBackend';

interface Notif { id: string; runId: string; title: string; body: string; ts: number; seen: boolean; ok: boolean; }

const NKEY = 'aps_notifications';
const DONEKEY = 'aps_notified_runs';

function load(): Notif[] { try { return JSON.parse(localStorage.getItem(NKEY) || '[]'); } catch { return []; } }
function save(n: Notif[]) { try { localStorage.setItem(NKEY, JSON.stringify(n.slice(0, 20))); } catch { /* */ } }
function notifiedRuns(): Set<string> { try { return new Set(JSON.parse(localStorage.getItem(DONEKEY) || '[]')); } catch { return new Set(); } }
function markNotified(runId: string) { const s = notifiedRuns(); s.add(runId); try { localStorage.setItem(DONEKEY, JSON.stringify([...s].slice(-50))); } catch { /* */ } }

function isDone(r: any): { done: boolean; failed: boolean } {
  const status = String(r?.status ?? '').toLowerCase();
  const phase = String(r?.phase ?? '').toLowerCase();
  const failed = status.includes('fail') || status.includes('cancel');
  const done = failed || status.includes('complete') || status.includes('degrade')
    || phase === 'complete' || (typeof r?.progressPct === 'number' && r.progressPct >= 100);
  return { done, failed };
}

function ago(ts: number): string {
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [notifs, setNotifs] = useState<Notif[]>(load);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const unseen = notifs.filter((n) => !n.seen).length;

  // Poll the active run; raise a notification the first time it reaches a terminal state.
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      const runId = getActiveRun();
      if (!runId || notifiedRuns().has(runId)) return;
      try {
        const r: any = await api.run(runId);
        const { done, failed } = isDone(r);
        if (done && alive) {
          markNotified(runId);
          const label = (r?.label || r?.idea || runId) as string;
          const n: Notif = {
            id: `${runId}-${Date.now()}`, runId, ok: !failed,
            title: failed ? 'Run did not complete' : 'Startup ready 🎉',
            body: failed ? `“${label}” stopped before finishing.` : `“${label}” — research and all artifacts are complete.`,
            ts: Date.now(), seen: false,
          };
          setNotifs((prev) => { const next = [n, ...prev].slice(0, 20); save(next); return next; });
        }
      } catch { /* backend down / not ready — try again next tick */ }
    };
    tick();
    const iv = setInterval(tick, 5000);
    return () => { alive = false; clearInterval(iv); };
  }, []);

  // close on outside click / Escape
  useEffect(() => {
    const onDoc = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const onEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onEsc);
    return () => { document.removeEventListener('mousedown', onDoc); document.removeEventListener('keydown', onEsc); };
  }, []);

  function openNotif(n: Notif) {
    setNotifs((prev) => { const next = prev.map((x) => (x.id === n.id ? { ...x, seen: true } : x)); save(next); return next; });
    setOpen(false);
    navigate('/artifacts');
  }
  function markAll() { setNotifs((prev) => { const next = prev.map((x) => ({ ...x, seen: true })); save(next); return next; }); }
  function clearAll() { setNotifs([]); save([]); }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => { setOpen((o) => !o); }}
        aria-label="Notifications"
        className="relative w-8 h-8 flex items-center justify-center rounded-lg text-on-surface-variant hover:text-primary hover:bg-white/[0.06] border border-transparent hover:border-white/[0.08] transition-all duration-200">
        <span className="material-symbols-outlined text-[18px]">notifications</span>
        {unseen > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[15px] h-[15px] px-1 flex items-center justify-center rounded-full bg-[#79ff5b] text-[#04210a] font-mono-label text-[9px] font-bold shadow-[0_0_8px_rgba(121,255,91,0.8)] animate-pulse">
            {unseen}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-[calc(100%+10px)] w-[320px] z-[1000] rounded-2xl overflow-hidden backdrop-blur-2xl"
          style={{ background: 'rgb(var(--c-deep) / 0.97)', border: '1px solid rgb(var(--c-primary) / 0.12)', boxShadow: '0 16px 48px rgb(var(--c-deepest) / 0.6)' }}>
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
            <span className="font-mono-label text-[11px] tracking-[0.14em] uppercase text-on-surface">Notifications</span>
            {notifs.length > 0 && (
              <div className="flex items-center gap-2">
                {unseen > 0 && <button onClick={markAll} className="font-mono-label text-[9px] uppercase tracking-[0.1em] text-primary/70 hover:text-primary">Mark read</button>}
                <button onClick={clearAll} className="font-mono-label text-[9px] uppercase tracking-[0.1em] text-on-surface-variant/45 hover:text-on-surface-variant">Clear</button>
              </div>
            )}
          </div>
          <div className="max-h-[340px] overflow-y-auto">
            {notifs.length === 0 ? (
              <div className="px-4 py-8 text-center">
                <span className="material-symbols-outlined text-on-surface-variant/25 text-[28px]">notifications_off</span>
                <p className="mt-2 text-[12px] text-on-surface-variant/45">No notifications yet.</p>
                <p className="text-[10px] text-on-surface-variant/30 mt-0.5">You'll be alerted when a run finishes.</p>
              </div>
            ) : notifs.map((n) => (
              <button key={n.id} onClick={() => openNotif(n)}
                className={`w-full text-left px-4 py-3 flex gap-3 border-b border-white/[0.04] transition-colors hover:bg-white/[0.04] ${n.seen ? 'opacity-60' : ''}`}>
                <span className="material-symbols-outlined text-[18px] mt-0.5 flex-shrink-0"
                  style={{ color: n.ok ? '#79ff5b' : '#EF4444' }}>{n.ok ? 'task_alt' : 'error'}</span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="text-[12.5px] font-semibold text-on-surface truncate">{n.title}</span>
                    {!n.seen && <span className="w-1.5 h-1.5 rounded-full bg-primary flex-shrink-0" />}
                  </span>
                  <span className="block text-[11px] text-on-surface-variant/60 leading-snug mt-0.5">{n.body}</span>
                  <span className="block font-mono-label text-[9px] text-on-surface-variant/35 mt-1">{n.runId} · {ago(n.ts)}</span>
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
