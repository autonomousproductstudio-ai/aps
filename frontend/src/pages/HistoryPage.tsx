// History — the signed-in user's personal startup archive. Hydrates from the per-user /v1/history
// API (scoped to the Firebase/Gmail identity on the backend). Matches the APS design language
// exactly: same nav chrome, glass panels, token-driven colors (so it flips with the theme),
// glow accents and Framer-Motion choreography used across the app. No other code is touched.
import { useEffect, useMemo, useRef, useState } from 'react';
import { NotificationBell } from '../components/NotificationBell';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { SettingsMenu } from '../components/SettingsMenu';
import { useAuth } from '../lib/AuthContext';
import { api, downloadRunZip } from '../lib/api';

// ─── Types ──────────────────────────────────────────────────────────────────
interface HistoryRun {
  runId: string; backendId?: string; name: string; idea: string; status: string;
  score: number | null; provider?: string; model?: string; artifacts: string[];
  artifactCount: number; toolCalls: number; evidenceCount: number; agentCount: number;
  durationSec: number | null; createdAt: string; completedAt: string | null;
  timeline?: TimelineEvent[];
}
interface TimelineEvent { ts?: string; type?: string; label?: string; message?: string; }
interface HistoryStats {
  totalStartups: number; successful: number; avgScore: number;
  totalSources: number; totalArtifacts: number; totalToolCalls: number;
}

// ─── Status palette (accent literals — pop identically on both themes) ────────
const STATUS: Record<string, { label: string; dot: string; cls: string }> = {
  complete:  { label: 'COMPLETE',  dot: '#79FF5B', cls: 'text-[#79FF5B] bg-[#79FF5B]/10 border-[#79FF5B]/25' },
  degraded:  { label: 'DEGRADED',  dot: '#F59E0B', cls: 'text-[#F59E0B] bg-[#F59E0B]/10 border-[#F59E0B]/25' },
  running:   { label: 'RUNNING',   dot: '#47d6ff', cls: 'text-primary bg-primary/10 border-primary/25' },
  queued:    { label: 'QUEUED',    dot: '#8B92A5', cls: 'text-on-surface-variant bg-white/[0.05] border-white/[0.08]' },
  failed:    { label: 'FAILED',    dot: '#EF4444', cls: 'text-[#EF4444] bg-[#EF4444]/10 border-[#EF4444]/25' },
  cancelled: { label: 'CANCELLED', dot: '#8B92A5', cls: 'text-on-surface-variant bg-white/[0.05] border-white/[0.08]' },
};
const statusOf = (s: string) => STATUS[s] ?? STATUS.queued;

// A tiny demo seed so the page is never blank when the backend is unreachable (dev / offline
// preview). The moment the real API answers — even with an empty list — this is replaced.
const DEMO_SEED: HistoryRun[] = [
  { runId: 'RUN_0042', name: 'AI Resume Screening Platform', idea: 'An AI SaaS that screens resumes for SMB recruiters', status: 'complete', score: 9.1, provider: 'openai', model: 'gpt-4o-mini', artifacts: ['research', 'prd', 'trd', 'execution', 'pitch'], artifactCount: 5, toolCalls: 38, evidenceCount: 47, agentCount: 6, durationSec: 1080, createdAt: '2026-06-08T14:02:00Z', completedAt: '2026-06-08T14:20:00Z' },
  { runId: 'RUN_0039', name: 'Carbon Ledger for Logistics', idea: 'Carbon accounting for mid-market freight operators', status: 'complete', score: 8.4, provider: 'nim', model: 'llama-3.3-70b', artifacts: ['research', 'prd', 'trd', 'execution'], artifactCount: 4, toolCalls: 29, evidenceCount: 33, agentCount: 5, durationSec: 845, createdAt: '2026-06-07T09:12:00Z', completedAt: '2026-06-07T09:26:00Z' },
  { runId: 'RUN_0036', name: 'Synaptic Notes', idea: 'A spatial knowledge tool for researchers', status: 'degraded', score: 7.2, provider: 'gemini', model: 'gemini-2.5-flash', artifacts: ['research', 'prd'], artifactCount: 2, toolCalls: 18, evidenceCount: 21, agentCount: 4, durationSec: 612, createdAt: '2026-06-05T17:40:00Z', completedAt: '2026-06-05T17:50:00Z' },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────
function useCountUp(target: number, duration = 1100, decimals = 0): string {
  const [val, setVal] = useState(0);
  useEffect(() => {
    let raf = 0, start = 0;
    const tick = (t: number) => {
      if (!start) start = t;
      const p = Math.min(1, (t - start) / duration);
      setVal(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick); else setVal(target);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return decimals ? val.toFixed(decimals) : Math.round(val).toLocaleString();
}

function fmtDate(iso?: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
      + ' · ' + new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  } catch { return '—'; }
}
function fmtDuration(sec?: number | null): string {
  if (!sec && sec !== 0) return '—';
  const s = Math.round(sec as number);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}

// ─── Nav (History active) ─────────────────────────────────────────────────────
function Nav() {
  const link = 'px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200';
  return (
    <nav className="fixed top-0 w-full z-[60] h-16 px-container-margin flex justify-between items-center">
      <div className="absolute inset-0 bg-gradient-to-r from-[#06080D]/95 via-[#0A0C14]/90 to-[#06080D]/95 backdrop-blur-2xl border-b border-white/[0.05]" />
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent" />
      <div className="relative flex items-center gap-6">
        <Link to="/" className="flex items-center gap-3 group select-none">
          <div className="relative">
            <div className="absolute inset-0 bg-primary/25 rounded-lg blur-[10px] group-hover:blur-[14px] transition-all duration-300" />
            <div className="relative w-9 h-9 bg-gradient-to-br from-primary/20 to-primary/5 border border-primary/40 rounded-lg flex items-center justify-center group-hover:border-primary/70 transition-colors duration-300">
              <span className="material-symbols-outlined text-primary text-[19px]">hub</span>
            </div>
          </div>
          <div className="flex flex-col leading-none">
            <span className="font-display-lg text-[14px] tracking-[0.25em] text-on-surface font-bold uppercase">APS</span>
            <span className="text-[8px] font-mono-label text-primary/50 tracking-[0.18em] uppercase mt-0.5">Autonomous</span>
          </div>
        </Link>
        <div className="w-px h-5 bg-white/[0.08]" />
        <div className="hidden md:flex items-center gap-1">
          <Link to="/" className={link}>Pipeline</Link>
          <Link to="/dashboard" className={link}>Dashboard</Link>
          <Link to="/artifacts" className={link}>Artifacts</Link>
          <Link to="/system" className={link}>System</Link>
          <Link to="/pricing" className={link}>Pricing</Link>
          <Link to="/history" className="relative flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-primary bg-primary/10 border border-primary/25 shadow-[0_0_14px_rgba(71,214,255,0.12)]">
            <span className="w-1.5 h-1.5 rounded-full bg-primary shadow-[0_0_5px_rgba(71,214,255,0.9)] animate-pulse" />
            History
          </Link>
        </div>
      </div>
      <div className="relative flex items-center gap-1.5">
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-secondary-fixed/[0.08] border border-secondary-fixed/20 mr-2">
          <span className="flex h-1.5 w-1.5 rounded-full bg-secondary-fixed shadow-[0_0_6px_rgba(121,255,91,0.9)] animate-pulse" />
          <span className="text-[10px] font-mono-label text-secondary-fixed/80 uppercase tracking-[0.15em]">Optimal</span>
        </div>
        <NotificationBell />
        <SettingsMenu />
      </div>
    </nav>
  );
}

// ─── Animated stat tile ───────────────────────────────────────────────────────
function StatTile({ icon, label, value, decimals = 0, delay = 0 }:
  { icon: string; label: string; value: number; decimals?: number; delay?: number }) {
  const shown = useCountUp(value, 1100, decimals);
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: [0.16, 1, 0.3, 1] }}
      className="glass-panel rounded-2xl border-primary/15 p-lg relative overflow-hidden group">
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 0%, rgb(var(--c-primary) / 0.06) 0%, transparent 65%)' }} />
      <div className="flex items-center gap-2 mb-3">
        <span className="material-symbols-outlined text-primary/70 text-[16px]">{icon}</span>
        <span className="font-mono-label text-[9px] tracking-[0.18em] uppercase text-on-surface-variant/60">{label}</span>
      </div>
      <div className="font-display text-[30px] leading-none text-on-surface font-bold tabular-nums">{shown}</div>
    </motion.div>
  );
}

// ─── Score ring ───────────────────────────────────────────────────────────────
function ScoreRing({ score, size = 46 }: { score: number | null; size?: number }) {
  if (score == null) return (
    <div className="rounded-full flex items-center justify-center bg-white/[0.04] border border-white/[0.07]"
      style={{ width: size, height: size }}>
      <span className="font-mono-label text-[9px] text-on-surface-variant/40">—</span>
    </div>
  );
  const pct = Math.max(0, Math.min(1, score / 10));
  return (
    <div className="rounded-full flex items-center justify-center flex-shrink-0"
      style={{ width: size, height: size, background: `conic-gradient(#47d6ff ${pct * 360}deg, rgb(var(--c-overlay) / 0.06) 0deg)` }}>
      <div className="rounded-full bg-app-bg flex flex-col items-center justify-center" style={{ width: size - 8, height: size - 8 }}>
        <span className="font-display text-[13px] text-primary font-bold leading-none">{score.toFixed(1)}</span>
        <span className="font-mono-label text-[6px] text-on-surface-variant/40 tracking-[0.1em] mt-0.5">/10</span>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const s = statusOf(status);
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border font-mono-label text-[9px] font-bold uppercase tracking-[0.12em] ${s.cls}`}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: s.dot, boxShadow: `0 0 5px ${s.dot}` }} />
      {s.label}
    </span>
  );
}

function Metric({ icon, value, title }: { icon: string; value: React.ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-1.5" title={title}>
      <span className="material-symbols-outlined text-on-surface-variant/40 text-[14px]">{icon}</span>
      <span className="font-mono-label text-[11px] text-on-surface-variant/70 tabular-nums">{value}</span>
    </div>
  );
}

// ─── Run card ─────────────────────────────────────────────────────────────────
function RunCard({ run, index, onOpen, onReplay, onDuplicate, onExport }:
  { run: HistoryRun; index: number; onOpen: () => void; onReplay: () => void; onDuplicate: () => void; onExport: () => void; }) {
  const [hover, setHover] = useState(false);
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 22 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.45, delay: Math.min(index * 0.05, 0.4), ease: [0.16, 1, 0.3, 1] }}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      onClick={onOpen}
      className="relative rounded-2xl border overflow-hidden cursor-pointer transition-all duration-300 group"
      style={{
        background: 'rgb(var(--c-surface) / 0.55)',
        borderColor: hover ? 'rgb(var(--c-primary) / 0.30)' : 'rgb(var(--c-overlay) / 0.07)',
        boxShadow: hover ? '0 12px 40px rgb(var(--c-deepest) / 0.45), 0 0 0 1px rgb(var(--c-primary) / 0.10)' : 'none',
      }}>
      {/* animated border trace on hover */}
      {hover && (
        <div className="absolute top-0 left-0 right-0 h-px pointer-events-none"
          style={{ background: 'linear-gradient(90deg,transparent,#47d6ff,transparent)', backgroundSize: '200% 100%', animation: 'borderSweep 2.4s linear infinite' }} />
      )}
      <div className="p-lg">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1.5"><StatusBadge status={run.status} /></div>
            <h3 className="font-display text-[16px] text-on-surface font-semibold leading-tight truncate">{run.name}</h3>
            <p className="font-mono-label text-[10px] text-on-surface-variant/45 mt-1 tracking-[0.05em]">{fmtDate(run.createdAt)}</p>
          </div>
          <ScoreRing score={run.score} />
        </div>

        <p className="text-[12px] text-on-surface-variant/60 leading-relaxed line-clamp-2 mb-4 min-h-[2.4em]">{run.idea}</p>

        <div className="flex items-center flex-wrap gap-x-4 gap-y-2 pb-4 border-b border-white/[0.05]">
          <Metric icon="travel_explore" value={run.evidenceCount} title="Research sources" />
          <Metric icon="deployed_code" value={run.artifactCount} title="Artifacts" />
          <Metric icon="build" value={run.toolCalls} title="Tool calls" />
          <Metric icon="schedule" value={fmtDuration(run.durationSec)} title="Execution time" />
          <Metric icon="groups" value={run.agentCount} title="Agents" />
        </div>

        <div className="flex items-center gap-1.5 mt-3" onClick={(e) => e.stopPropagation()}>
          <button onClick={onOpen}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-primary/10 border border-primary/25 text-primary font-mono-label text-[10px] uppercase tracking-[0.12em] hover:bg-primary/15 transition-all duration-200">
            <span className="material-symbols-outlined text-[15px]">open_in_full</span> Open
          </button>
          <CardIcon icon="replay" title="Replay generation" onClick={onReplay} />
          <CardIcon icon="content_copy" title="Duplicate idea" onClick={onDuplicate} />
          <CardIcon icon="download" title="Export bundle" onClick={onExport} />
        </div>
      </div>
    </motion.div>
  );
}
function CardIcon({ icon, title, onClick }: { icon: string; title: string; onClick: () => void }) {
  return (
    <button title={title} onClick={onClick}
      className="w-9 h-9 flex items-center justify-center rounded-lg bg-white/[0.03] border border-white/[0.07] text-on-surface-variant/60 hover:text-primary hover:border-primary/25 hover:bg-primary/[0.06] transition-all duration-200">
      <span className="material-symbols-outlined text-[16px]">{icon}</span>
    </button>
  );
}

// ─── Detail panel (slide-in) ──────────────────────────────────────────────────
function DetailPanel({ run, replay, onClose, onExport, onDuplicate }:
  { run: HistoryRun; replay: boolean; onClose: () => void; onExport: () => void; onDuplicate: () => void; }) {
  const [detail, setDetail] = useState<any>(null);
  const [revealed, setRevealed] = useState<number>(replay ? 0 : 9999);
  const [replaying, setReplaying] = useState(replay);
  const timer = useRef<any>(null);

  useEffect(() => {
    let alive = true;
    api.historyDetail(run.runId).then((d) => { if (alive) setDetail(d); }).catch(() => { /* keep card data */ });
    return () => { alive = false; };
  }, [run.runId]);

  const timeline: TimelineEvent[] = detail?.timeline?.length ? detail.timeline : (run.timeline ?? []);

  const runReplay = () => {
    if (timer.current) clearInterval(timer.current);
    setReplaying(true); setRevealed(0);
    let i = 0;
    timer.current = setInterval(() => {
      i += 1; setRevealed(i);
      if (i >= timeline.length) { clearInterval(timer.current); setReplaying(false); }
    }, 520);
  };
  useEffect(() => { if (replay && timeline.length) runReplay(); /* eslint-disable-next-line */ }, [detail]);
  useEffect(() => () => timer.current && clearInterval(timer.current), []);

  const scores = detail?.scores;
  // viability() returns { score, radarAxes:[{label,value 0..100}], scenarios }. Map each axis to
  // a 0..10 bar so the scorecard mirrors the real per-dimension scoring.
  const breakdown: { label: string; val: number }[] = (scores?.radarAxes ?? [])
    .map((a: any) => ({ label: a.label, val: (Number(a.value) || 0) / 10 }));

  return (
    <motion.div className="fixed inset-0 z-[80] flex justify-end"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
        transition={{ type: 'spring', damping: 30, stiffness: 280 }}
        className="relative w-full max-w-[560px] h-full overflow-y-auto terminal-scroll"
        style={{ background: 'rgb(var(--c-deep))', borderLeft: '1px solid rgb(var(--c-primary) / 0.12)' }}>
        {/* header */}
        <div className="sticky top-0 z-10 px-lg py-4 flex items-start justify-between gap-3 backdrop-blur-2xl border-b border-white/[0.06]"
          style={{ background: 'rgb(var(--c-deep) / 0.85)' }}>
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1.5"><StatusBadge status={run.status} /></div>
            <h2 className="font-display text-[19px] text-on-surface font-bold leading-tight">{run.name}</h2>
            <p className="font-mono-label text-[10px] text-on-surface-variant/45 mt-1">{run.runId} · {fmtDate(run.createdAt)}</p>
          </div>
          <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-lg text-on-surface-variant/60 hover:text-on-surface hover:bg-white/[0.06] transition-all flex-shrink-0">
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        </div>

        <div className="p-lg space-y-6">
          {/* overview metrics */}
          <Section title="Overview" icon="dashboard">
            <div className="grid grid-cols-3 gap-2">
              <OverviewStat label="Score" value={run.score != null ? run.score.toFixed(1) : '—'} accent />
              <OverviewStat label="Sources" value={run.evidenceCount} />
              <OverviewStat label="Artifacts" value={run.artifactCount} />
              <OverviewStat label="Tool Calls" value={run.toolCalls} />
              <OverviewStat label="Agents" value={run.agentCount} />
              <OverviewStat label="Runtime" value={fmtDuration(run.durationSec)} />
            </div>
            <p className="text-[12px] text-on-surface-variant/60 leading-relaxed mt-3">{run.idea}</p>
          </Section>

          {/* scores */}
          {breakdown.length > 0 && (
            <Section title="Viability Scorecard" icon="analytics">
              <div className="space-y-2.5">
                {breakdown.map((b, i) => (
                  <div key={b.label}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono-label text-[10px] text-on-surface-variant/60 uppercase tracking-[0.1em]">{b.label}</span>
                      <span className="font-mono-label text-[11px] text-primary tabular-nums">{Number(b.val).toFixed(1)}</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-white/[0.05] overflow-hidden">
                      <motion.div initial={{ width: 0 }} animate={{ width: `${Math.min(100, (Number(b.val) / 10) * 100)}%` }}
                        transition={{ duration: 0.7, delay: 0.1 + i * 0.08, ease: [0.16, 1, 0.3, 1] }}
                        className="h-full rounded-full" style={{ background: 'linear-gradient(90deg,#47d6ff,#a5e7ff)' }} />
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* artifacts */}
          <Section title="Artifacts" icon="deployed_code" count={(detail?.artifacts?.length) ?? run.artifacts.length}>
            <div className="grid grid-cols-2 gap-2">
              {(detail?.artifacts?.length ? detail.artifacts.map((a: any) => a.name ?? a.title ?? a.id) : run.artifacts).map((name: string, i: number) => (
                <motion.div key={i} initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.04 }}
                  className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-white/[0.025] border border-white/[0.06]">
                  <span className="material-symbols-outlined text-primary/70 text-[15px]">description</span>
                  <span className="text-[12px] text-on-surface-variant/80 capitalize truncate">{String(name)}</span>
                </motion.div>
              ))}
              {run.artifacts.length === 0 && <p className="col-span-2 text-[12px] text-on-surface-variant/40">No artifacts produced.</p>}
            </div>
            <button onClick={onExport}
              className="w-full mt-3 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-primary/10 border border-primary/25 text-primary font-mono-label text-[10px] uppercase tracking-[0.12em] hover:bg-primary/15 transition-all">
              <span className="material-symbols-outlined text-[15px]">download</span> Export bundle (.zip)
            </button>
          </Section>

          {/* execution timeline + replay */}
          <Section title="Execution Timeline" icon="timeline"
            action={timeline.length > 0 && (
              <button onClick={runReplay} disabled={replaying}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-primary/10 border border-primary/25 text-primary font-mono-label text-[9px] uppercase tracking-[0.12em] hover:bg-primary/15 transition-all disabled:opacity-50">
                <span className="material-symbols-outlined text-[13px]">{replaying ? 'sync' : 'play_arrow'}</span>
                {replaying ? 'Replaying' : 'Replay'}
              </button>
            )}>
            {timeline.length === 0 ? (
              <p className="text-[12px] text-on-surface-variant/40">No timeline recorded for this run.</p>
            ) : (
              <div className="relative pl-4">
                <div className="absolute left-[5px] top-1 bottom-1 w-px bg-white/[0.08]" />
                {timeline.map((ev, i) => {
                  const on = i < revealed;
                  return (
                    <motion.div key={i} className="relative pb-3 last:pb-0"
                      animate={{ opacity: on ? 1 : 0.25, x: on ? 0 : -4 }} transition={{ duration: 0.3 }}>
                      <span className="absolute -left-4 top-1 w-2.5 h-2.5 rounded-full border-2 transition-all duration-300"
                        style={{ background: on ? '#47d6ff' : 'transparent', borderColor: on ? '#47d6ff' : 'rgb(var(--c-overlay) / 0.2)', boxShadow: on ? '0 0 8px rgba(71,214,255,0.7)' : 'none' }} />
                      <div className="flex items-baseline gap-2">
                        <span className="font-mono-label text-[9px] text-on-surface-variant/35 tabular-nums flex-shrink-0">
                          {ev.ts ? new Date(ev.ts).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : `#${i + 1}`}
                        </span>
                        <span className="text-[12px] text-on-surface-variant/75">{ev.label ?? ev.message ?? ev.type ?? 'Event'}</span>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            )}
          </Section>

          <div className="flex items-center gap-2 pt-1 pb-6">
            <button onClick={onDuplicate}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-white/[0.03] border border-white/[0.08] text-on-surface-variant/80 font-mono-label text-[10px] uppercase tracking-[0.12em] hover:border-primary/25 hover:text-primary transition-all">
              <span className="material-symbols-outlined text-[15px]">content_copy</span> Duplicate idea
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
function Section({ title, icon, count, action, children }:
  { title: string; icon: string; count?: number; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary/70 text-[16px]">{icon}</span>
          <h4 className="font-mono-label text-[10px] tracking-[0.18em] uppercase text-on-surface-variant/70">{title}</h4>
          {count != null && <span className="font-mono-label text-[9px] text-on-surface-variant/40">· {count}</span>}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}
function OverviewStat({ label, value, accent }: { label: string; value: React.ReactNode; accent?: boolean }) {
  return (
    <div className="rounded-lg bg-white/[0.025] border border-white/[0.06] px-3 py-2.5">
      <div className={`font-display text-[18px] font-bold leading-none tabular-nums ${accent ? 'text-primary' : 'text-on-surface'}`}>{value}</div>
      <div className="font-mono-label text-[8px] tracking-[0.14em] uppercase text-on-surface-variant/45 mt-1.5">{label}</div>
    </div>
  );
}

// ─── Empty state ──────────────────────────────────────────────────────────────
function EmptyState() {
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
      className="flex flex-col items-center justify-center text-center py-24">
      <div className="relative mb-6">
        <div className="absolute inset-0 bg-primary/20 rounded-3xl blur-2xl" />
        <div className="relative w-20 h-20 rounded-3xl bg-gradient-to-br from-primary/15 to-primary/5 border border-primary/30 flex items-center justify-center">
          <span className="material-symbols-outlined text-primary text-[38px]">inventory_2</span>
        </div>
      </div>
      <h2 className="font-display text-[24px] text-on-surface font-bold mb-2">No startup history yet</h2>
      <p className="text-[14px] text-on-surface-variant/60 max-w-md leading-relaxed mb-6">
        Generate your first startup idea and APS will automatically archive every output here —
        research, artifacts, scores and the full execution timeline.
      </p>
      <Link to="/"
        className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary/15 border border-primary/30 text-primary font-mono-label text-[11px] uppercase tracking-[0.15em] hover:bg-primary/20 transition-all">
        <span className="material-symbols-outlined text-[17px]">rocket_launch</span> Create Startup
      </Link>
    </motion.div>
  );
}

function Toast({ msg }: { msg: string }) {
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 20 }}
      className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[90] px-4 py-2.5 rounded-xl backdrop-blur-2xl flex items-center gap-2"
      style={{ background: 'rgb(var(--c-deep) / 0.95)', border: '1px solid rgb(var(--c-primary) / 0.25)', boxShadow: '0 10px 40px rgb(var(--c-deepest) / 0.5)' }}>
      <span className="material-symbols-outlined text-primary text-[16px]">check_circle</span>
      <span className="text-[12px] text-on-surface">{msg}</span>
    </motion.div>
  );
}

// ─── Sort dropdown (custom — native <select> popups render with an OS-themed white
//     box that's unreadable in dark mode; this is token-driven so it's crisp in both). ──
type SortKey = 'newest' | 'oldest' | 'score';
const SORT_OPTS: { k: SortKey; label: string }[] = [
  { k: 'newest', label: 'Newest' }, { k: 'oldest', label: 'Oldest' }, { k: 'score', label: 'Highest Score' },
];
function SortDropdown({ value, onChange }: { value: SortKey; onChange: (v: SortKey) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onDoc = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const onEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onEsc);
    return () => { document.removeEventListener('mousedown', onDoc); document.removeEventListener('keydown', onEsc); };
  }, []);
  const current = SORT_OPTS.find(o => o.k === value)?.label ?? 'Newest';
  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:border-primary/25 transition-all duration-200">
        <span className="material-symbols-outlined text-on-surface-variant/40 text-[16px]">sort</span>
        <span className="text-[12px] text-on-surface-variant/80 font-mono-label whitespace-nowrap">{current}</span>
        <span className={`material-symbols-outlined text-on-surface-variant/40 text-[16px] transition-transform duration-200 ${open ? 'rotate-180' : ''}`}>expand_more</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.16 }}
            className="absolute right-0 top-[calc(100%+6px)] min-w-[170px] z-[70] rounded-xl overflow-hidden backdrop-blur-2xl"
            style={{ background: 'rgb(var(--c-deep) / 0.97)', border: '1px solid rgb(var(--c-primary) / 0.14)', boxShadow: '0 14px 44px rgb(var(--c-deepest) / 0.6)' }}>
            {SORT_OPTS.map(o => {
              const active = o.k === value;
              return (
                <button key={o.k} onClick={() => { onChange(o.k); setOpen(false); }}
                  className={`w-full text-left px-3.5 py-2.5 text-[12px] font-mono-label flex items-center gap-2 transition-colors duration-150 ${active ? 'text-primary bg-primary/10' : 'text-on-surface-variant/70 hover:text-on-surface hover:bg-white/[0.05]'}`}>
                  <span className="material-symbols-outlined text-[14px]" style={{ opacity: active ? 1 : 0 }}>check</span>
                  {o.label}
                </button>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
const STATUS_FILTERS = ['All', 'Completed', 'Running', 'Failed'] as const;

export default function HistoryPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [runs, setRuns] = useState<HistoryRun[]>([]);
  const [stats, setStats] = useState<HistoryStats | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [usingDemo, setUsingDemo] = useState(false);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<typeof STATUS_FILTERS[number]>('All');
  const [sort, setSort] = useState<SortKey>('newest');
  const [selected, setSelected] = useState<{ run: HistoryRun; replay: boolean } | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(null), 2400); };

  useEffect(() => {
    let alive = true;
    Promise.all([api.history(), api.historyStats().catch(() => null)])
      .then(([list, st]) => {
        if (!alive) return;
        setLoaded(true);
        if (Array.isArray(list) && list.length > 0) {
          setRuns(list as HistoryRun[]); setUsingDemo(false);
          if (st) setStats(st as HistoryStats);
        } else {
          setRuns([]); setUsingDemo(false);
          setStats(st as HistoryStats ?? { totalStartups: 0, successful: 0, avgScore: 0, totalSources: 0, totalArtifacts: 0, totalToolCalls: 0 });
        }
      })
      .catch(() => {
        if (!alive) return;
        // backend unreachable → show the demo seed so the page still demonstrates the design
        setRuns(DEMO_SEED); setUsingDemo(true); setLoaded(true);
      });
    return () => { alive = false; };
  }, []);

  const computedStats: HistoryStats = useMemo(() => {
    if (stats && !usingDemo) return stats;
    const scored = runs.filter(r => r.score).map(r => r.score as number);
    return {
      totalStartups: runs.length,
      successful: runs.filter(r => r.status === 'complete' || r.status === 'degraded').length,
      avgScore: scored.length ? +(scored.reduce((a, b) => a + b, 0) / scored.length).toFixed(1) : 0,
      totalSources: runs.reduce((a, r) => a + (r.evidenceCount || 0), 0),
      totalArtifacts: runs.reduce((a, r) => a + (r.artifactCount || 0), 0),
      totalToolCalls: runs.reduce((a, r) => a + (r.toolCalls || 0), 0),
    };
  }, [stats, runs, usingDemo]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    let out = runs.filter(r => {
      if (q && !(`${r.name} ${r.idea}`.toLowerCase().includes(q))) return false;
      if (statusFilter === 'Completed') return r.status === 'complete' || r.status === 'degraded';
      if (statusFilter === 'Running') return r.status === 'running' || r.status === 'queued';
      if (statusFilter === 'Failed') return r.status === 'failed' || r.status === 'cancelled';
      return true;
    });
    out = [...out].sort((a, b) => {
      if (sort === 'score') return (b.score ?? -1) - (a.score ?? -1);
      const ta = new Date(a.createdAt).getTime(), tb = new Date(b.createdAt).getTime();
      return sort === 'oldest' ? ta - tb : tb - ta;
    });
    return out;
  }, [runs, query, statusFilter, sort]);

  const duplicate = async (run: HistoryRun) => {
    try { await navigator.clipboard.writeText(run.idea); } catch { /* ignore */ }
    flash('Idea copied — paste it on the Pipeline to generate again');
    setTimeout(() => navigate('/'), 700);
  };
  const exportRun = async (run: HistoryRun) => {
    flash('Preparing export…');
    const ok = await downloadRunZip(run.runId).catch(() => false);
    if (!ok) flash('Nothing to export for this run yet');
  };

  return (
    <div className="min-h-screen" style={{ background: 'rgb(var(--c-bg-deep))' }}>
      <Nav />
      {/* ambient backdrop */}
      <div className="fixed inset-0 pointer-events-none ambient-glow" />

      <main className="relative max-w-[1240px] mx-auto px-container-margin pt-28 pb-20">
        {/* header */}
        <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}>
          <div className="flex items-center gap-2 mb-2">
            <span className="font-mono-label text-[10px] tracking-[0.2em] uppercase text-primary/70">Personal Archive</span>
            {usingDemo && <span className="font-mono-label text-[9px] text-on-surface-variant/40">· preview data (offline)</span>}
          </div>
          <h1 className="font-display text-[44px] leading-[1.05] text-on-surface font-bold tracking-tight">History</h1>
          <p className="text-[15px] text-on-surface-variant/60 mt-2 max-w-2xl">
            Browse, revisit, and manage every startup generated by APS{user?.email ? ` for ${user.email}` : ''}.
          </p>
        </motion.div>

        {/* animated stats */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mt-8">
          <StatTile icon="rocket_launch" label="Startups" value={computedStats.totalStartups} delay={0.04} />
          <StatTile icon="task_alt" label="Successful" value={computedStats.successful} delay={0.08} />
          <StatTile icon="trending_up" label="Avg Score" value={computedStats.avgScore} decimals={1} delay={0.12} />
          <StatTile icon="travel_explore" label="Sources" value={computedStats.totalSources} delay={0.16} />
          <StatTile icon="deployed_code" label="Artifacts" value={computedStats.totalArtifacts} delay={0.20} />
          <StatTile icon="build" label="Tool Calls" value={computedStats.totalToolCalls} delay={0.24} />
        </div>

        {/* filter bar */}
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.18 }}
          className="glass-panel rounded-2xl border-primary/12 p-2 mt-8 flex flex-col md:flex-row md:items-center gap-2">
          <div className="flex items-center gap-2 flex-1 px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.06]">
            <span className="material-symbols-outlined text-on-surface-variant/40 text-[18px]">search</span>
            <input value={query} onChange={(e) => setQuery(e.target.value)}
              placeholder="Search startups, runs, ideas…"
              className="bg-transparent border-none outline-none flex-1 text-[13px] text-on-surface placeholder:text-on-surface-variant/35" />
          </div>
          <div className="flex items-center gap-1 px-1">
            {STATUS_FILTERS.map(f => (
              <button key={f} onClick={() => setStatusFilter(f)}
                className={`px-3 py-1.5 rounded-lg font-mono-label text-[10px] uppercase tracking-[0.1em] transition-all duration-200 border ${statusFilter === f ? 'text-primary bg-primary/10 border-primary/25' : 'text-on-surface-variant/55 border-transparent hover:text-on-surface hover:bg-white/[0.04]'}`}>
                {f}
              </button>
            ))}
          </div>
          <SortDropdown value={sort} onChange={setSort} />
        </motion.div>

        {/* grid / states */}
        <div className="mt-8">
          {!loaded ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[0, 1, 2, 3, 4, 5].map(i => (
                <div key={i} className="rounded-2xl border border-white/[0.06] bg-white/[0.02] h-[230px] animate-pulse" />
              ))}
            </div>
          ) : runs.length === 0 ? (
            <EmptyState />
          ) : filtered.length === 0 ? (
            <div className="text-center py-20 text-on-surface-variant/50 text-[14px]">No runs match your filters.</div>
          ) : (
            <motion.div layout className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <AnimatePresence mode="popLayout">
                {filtered.map((run, i) => (
                  <RunCard key={run.runId} run={run} index={i}
                    onOpen={() => setSelected({ run, replay: false })}
                    onReplay={() => setSelected({ run, replay: true })}
                    onDuplicate={() => duplicate(run)}
                    onExport={() => exportRun(run)} />
                ))}
              </AnimatePresence>
            </motion.div>
          )}
        </div>
      </main>

      <AnimatePresence>
        {selected && (
          <DetailPanel run={selected.run} replay={selected.replay}
            onClose={() => setSelected(null)}
            onExport={() => exportRun(selected.run)}
            onDuplicate={() => duplicate(selected.run)} />
        )}
      </AnimatePresence>
      <AnimatePresence>{toast && <Toast msg={toast} />}</AnimatePresence>
    </div>
  );
}
