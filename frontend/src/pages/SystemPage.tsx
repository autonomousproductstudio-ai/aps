import { useState, useEffect, useRef } from 'react';
import { NotificationBell } from '../components/NotificationBell';
import { Link } from 'react-router-dom';
import { SettingsMenu } from '../components/SettingsMenu';
import { BillingCard } from '../components/BillingCard';
import { api } from '../lib/api';
import { usePolled } from '../lib/useBackend';

// ─── Data ─────────────────────────────────────────────────────────────────────
// The consts below are the page's original hardcoded mock; each panel polls its live /v1
// counterpart via usePolled and falls back to these when the backend is unreachable — so the
// design + animations always render.

const SYS_AGENTS = [
  { id:'research',  name:'Research Agent',     icon:'travel_explore', status:'running',  memPct:72, tasksCompleted:47, currentJob:'Evidence synthesis — cluster #3', latencyMs:230,  successRate:97.4, confidence:94, lastExec:'14:03:12', tokensUsed:128400 },
  { id:'product',   name:'Product Agent',       icon:'architecture',   status:'queued',   memPct:18, tasksCompleted:12, currentJob:'Awaiting Research output',         latencyMs:0,    successRate:98.1, confidence:0,  lastExec:'13:58:44', tokensUsed:42100 },
  { id:'arch',      name:'Architecture Agent',  icon:'hub',            status:'queued',   memPct:9,  tasksCompleted:8,  currentJob:'Standby',                          latencyMs:0,    successRate:96.8, confidence:0,  lastExec:'13:52:10', tokensUsed:31200 },
  { id:'execution', name:'Execution Agent',     icon:'data_object',    status:'queued',   memPct:5,  tasksCompleted:31, currentJob:'Standby',                          latencyMs:0,    successRate:99.2, confidence:0,  lastExec:'13:47:55', tokensUsed:18900 },
  { id:'present',   name:'Presentation Agent',  icon:'smart_display',  status:'idle',     memPct:3,  tasksCompleted:6,  currentJob:'Idle',                             latencyMs:0,    successRate:94.7, confidence:0,  lastExec:'13:41:22', tokensUsed:9800  },
];

const MODELS = [
  { id:'claude',   name:'Claude Sonnet 4.6', provider:'Anthropic', icon:'psychology',    available:true,  latencyMs:1240, tokensM:0.847, costUSD:12.40, successRate:99.2, primary:true,  color:'rgb(var(--c-primary))' },
  { id:'gpt4o',    name:'GPT-4o',            provider:'OpenAI',    icon:'smart_toy',     available:true,  latencyMs:1820, tokensM:0.243, costUSD:4.86,  successRate:98.7, primary:false, color:'#79ff5b' },
  { id:'gemini',   name:'Gemini 1.5 Pro',    provider:'Google',    icon:'auto_awesome',  available:true,  latencyMs:2140, tokensM:0.091, costUSD:1.37,  successRate:97.3, primary:false, color:'#bbc9cf' },
  { id:'local',    name:'Mistral 7B',        provider:'Local',     icon:'memory',        available:true,  latencyMs:380,  tokensM:0.412, costUSD:0,     successRate:94.1, primary:false, color:'#f59e0b' },
];

const TOOL_GROUPS = [
  { ns:'Research',     color:'rgb(var(--c-primary))', tools:[
    { name:'web_search',    inv:847, succ:98.4, avgMs:1200, last:'14:03:09', health:'healthy' },
    { name:'github_api',    inv:412, succ:99.1, avgMs:840,  last:'14:02:58', health:'healthy' },
    { name:'reddit_api',    inv:231, succ:97.8, avgMs:620,  last:'14:02:45', health:'healthy' },
    { name:'hn_scraper',    inv:89,  succ:96.2, avgMs:980,  last:'14:02:31', health:'healthy' },
    { name:'paper_fetch',   inv:34,  succ:100,  avgMs:1840, last:'14:02:18', health:'healthy' },
  ]},
  { ns:'Product',      color:'#79ff5b', tools:[
    { name:'prd_writer',    inv:12,  succ:100,  avgMs:8400, last:'14:09:32', health:'healthy' },
    { name:'user_story_gen',inv:47,  succ:98.9, avgMs:2100, last:'14:09:18', health:'healthy' },
    { name:'feature_rank',  inv:8,   succ:100,  avgMs:1200, last:'14:09:05', health:'healthy' },
  ]},
  { ns:'Architecture', color:'#bbc9cf', tools:[
    { name:'diagram_gen',   inv:3,   succ:100,  avgMs:3200, last:'—',        health:'standby' },
    { name:'openapi_spec',  inv:2,   succ:100,  avgMs:5100, last:'—',        health:'standby' },
    { name:'c4_model',      inv:1,   succ:100,  avgMs:2800, last:'—',        health:'standby' },
  ]},
  { ns:'Execution',    color:'#f59e0b', tools:[
    { name:'code_gen',      inv:0,   succ:0,    avgMs:0,    last:'—',        health:'standby' },
    { name:'test_runner',   inv:0,   succ:0,    avgMs:0,    last:'—',        health:'standby' },
  ]},
];

const MEMORY_TYPES = [
  { id:'working',   name:'Working Memory',   icon:'memory_alt',    size:'2.4 MB',  nodes:127, speed:12,  pct:72, color:'rgb(var(--c-primary))', note:'Current run context' },
  { id:'run',       name:'Run Memory',        icon:'history',       size:'14.2 MB', nodes:847, speed:28,  pct:45, color:'rgb(var(--c-primary))', note:'Session history' },
  { id:'artifact',  name:'Artifact Memory',   icon:'inventory_2',   size:'8.1 MB',  nodes:312, speed:18,  pct:31, color:'#79ff5b', note:'Generated documents' },
  { id:'evidence',  name:'Evidence Memory',   icon:'device_hub',    size:'31.7 MB', nodes:2841,speed:45,  pct:88, color:'#f59e0b', note:'Source intelligence' },
  { id:'kg',        name:'Knowledge Graph',   icon:'scatter_plot',  size:'5.6 MB',  nodes:493, speed:22,  pct:62, color:'rgb(var(--c-primary))', note:'Concept relationships' },
  { id:'longterm',  name:'Long-Term Memory',  icon:'cloud_sync',    size:'127 MB',  nodes:18400,speed:180, pct:15, color:'#bbc9cf', note:'Cross-run learnings' },
];

const KG_NODES = [
  { id:'idea',    label:'Idea',         y:48,  side:[] as {label:string;dx:number}[] },
  { id:'evidence',label:'Evidence',     y:128, side:[{label:'GitHub ×34',dx:120},{label:'Reddit ×24',dx:-120}] },
  { id:'insights',label:'Insights',     y:208, side:[{label:'TAM $8.4B',dx:120},{label:'Pain ×3',dx:-110}] },
  { id:'req',     label:'Requirements', y:288, side:[{label:'14 Stories',dx:115},{label:'7 Features',dx:-115}] },
  { id:'arch',    label:'Architecture', y:368, side:[{label:'API Design',dx:110},{label:'DB Schema',dx:-110}] },
  { id:'roadmap', label:'Roadmap',      y:448, side:[{label:'Sprint 1',dx:105},{label:'Sprint 2',dx:-100}] },
  { id:'pitch',   label:'Pitch',        y:528, side:[{label:'Deck',dx:80},{label:'Memo',dx:-80}] },
];

const EVENT_SEED = [
  { t:'14:02:01', type:'agent',    icon:'travel_explore', msg:'Research Agent activated — workspace initialized',              color:'cyan'  },
  { t:'14:02:04', type:'tool',     icon:'search',         msg:'Tool: web_search · "resume screening AI" · 847ms',             color:'cyan'  },
  { t:'14:02:09', type:'evidence', icon:'hub',            msg:'Evidence cluster formed · 34 GitHub repositories ingested',    color:'green' },
  { t:'14:02:15', type:'tool',     icon:'forum',          msg:'Tool: reddit_api · r/recruiting · 231 posts scraped',          color:'cyan'  },
  { t:'14:02:23', type:'insight',  icon:'lightbulb',      msg:'Insight: ATS false-negative rate confirmed at 75%',            color:'amber' },
  { t:'14:02:31', type:'tool',     icon:'newspaper',      msg:'Tool: hn_scraper · 89 threads indexed · 980ms',               color:'cyan'  },
  { t:'14:02:44', type:'model',    icon:'psychology',     msg:'Model: Claude Sonnet 4.6 · 47,200 tokens · $0.71',           color:'cyan'  },
  { t:'14:02:58', type:'evidence', icon:'verified',       msg:'Pain cluster #2 committed · evidence score: 91%',             color:'green' },
  { t:'14:03:10', type:'insight',  icon:'trending_up',    msg:'Insight: TAM validated $8.4B across 4 independent sources',   color:'amber' },
  { t:'14:03:22', type:'artifact', icon:'inventory_2',    msg:'Artifact: Research Brief v1 materialized · 42 KB',            color:'green' },
  { t:'14:03:38', type:'tool',     icon:'stars',          msg:'Tool: paper_fetch · 3 papers · NLP hiring bias corpus',       color:'cyan'  },
  { t:'14:03:51', type:'agent',    icon:'architecture',   msg:'Product Agent queued · dependency: Research Brief',            color:'cyan'  },
];

const MORE_EVENTS = [
  { t:'14:04:05', type:'evidence', icon:'check_circle', msg:'Evidence coverage complete · 47 nodes · confidence 94%',       color:'green' },
  { t:'14:04:18', type:'model',    icon:'psychology',   msg:'Model: Claude Sonnet 4.6 · reasoning chain 14 steps',         color:'cyan'  },
  { t:'14:04:35', type:'artifact', icon:'bar_chart',    msg:'Artifact: Market Analysis v1 · competitor matrix complete',   color:'green' },
];

const QUALITY_SCORES = [
  { name:'Research Brief',   score:9.3, coverage:94, hRisk:2,  depth:9.1 },
  { name:'Market Analysis',  score:8.8, coverage:91, hRisk:3,  depth:8.7 },
  { name:'PRD v1.0',         score:8.4, coverage:87, hRisk:5,  depth:8.2 },
  { name:'Roadmap Q1–Q3',   score:8.6, coverage:88, hRisk:4,  depth:8.5 },
];

const COST_ITEMS = [
  { label:'Claude Sonnet 4.6', value:12.40, tokens:'847K', category:'Model' },
  { label:'GPT-4o (fallback)',  value:4.86,  tokens:'243K', category:'Model' },
  { label:'Gemini 1.5 Pro',    value:1.37,  tokens:'91K',  category:'Model' },
  { label:'API calls · tools', value:0.84,  tokens:'—',    category:'Tool' },
  { label:'Storage · memory',  value:0.12,  tokens:'—',    category:'Infra' },
];

// Sparkline data (hardcoded realistic values)
const SPARK = {
  latency: [1240,1180,1320,1240,1390,1180,1260,1340,1200,1280,1420,1180,1250,1340,1200,1380,1240,1300,1180,1260],
  tokens:  [12,18,14,22,17,28,21,35,26,42,31,48,37,54,42,61,47,70,53,80],
  errors:  [0,0,1,0,0,0,1,0,0,0,0,1,0,0,0,0,0,1,0,0],
  runs:    [1,2,1,3,2,4,3,5,4,6,5,7,6,8,7,9,8,10,9,12],
};

// Activity heatmap (seeded fake data 7×24)
const HEATMAP = Array.from({length:7*24},(_,i)=>{
  const h=i%24, row=Math.floor(i/24);
  const base = (h>8&&h<18) ? 0.5 : 0.1;
  const boost= row===0&&h>9&&h<15 ? 0.5 : 0;
  return Math.min(1, base + boost + (Math.sin(i*0.7)*0.2 + 0.15));
});

// ─── Helpers ──────────────────────────────────────────────────────────────────

function Sparkline({ data, color='rgb(var(--c-primary))', h=32 }: { data:number[]; color?:string; h?:number }) {
  const max=Math.max(...data,1), w=100;
  const pts=data.map((v,i)=>`${(i/(data.length-1))*w},${h-(v/max)*(h-2)+1}`).join(' ');
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" preserveAspectRatio="none" style={{ height:h }}>
      <defs>
        <linearGradient id={`sg-${color.slice(1)}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.15" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`0,${h} ${pts} ${w},${h}`} fill={`url(#sg-${color.slice(1)})`} />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5"
        style={{ filter:`drop-shadow(0 0 4px ${color}88)` }} />
    </svg>
  );
}

function MiniBar({ pct, color='rgb(var(--c-primary))' }: { pct:number; color?:string }) {
  return (
    <div className="h-px bg-white/[0.04] rounded-full overflow-hidden">
      <div className="h-full rounded-full" style={{ width:`${pct}%`, background:color, boxShadow:`0 0 4px ${color}55`, transition:'width 1s ease' }} />
    </div>
  );
}

function PanelHeader({ icon, label, iconColor='text-primary', badge }: { icon:string; label:string; iconColor?:string; badge?:React.ReactNode }) {
  return (
    <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.05] flex-shrink-0">
      <div className="flex items-center gap-2">
        <span className={`material-symbols-outlined text-[15px] ${iconColor}`}>{icon}</span>
        <span className="font-mono-label text-[11px] text-on-surface uppercase tracking-[0.15em]">{label}</span>
      </div>
      {badge}
    </div>
  );
}

function StatusDot({ status }: { status:string }) {
  const col = status==='running'||status==='healthy'||status==='optimal'
    ? { bg:'bg-secondary-fixed', glow:'rgba(121,255,91,0.9)', animate:true }
    : status==='queued'||status==='standby'
    ? { bg:'bg-primary/40', glow:'rgb(var(--c-primary) / 0.4)', animate:false }
    : { bg:'bg-on-surface-variant/20', glow:'', animate:false };
  return (
    <span className={`flex h-1.5 w-1.5 rounded-full ${col.bg} flex-shrink-0 ${col.animate?'animate-pulse':''}`}
      style={col.glow ? { boxShadow:`0 0 6px ${col.glow}` } : {}} />
  );
}

// ─── Nav ──────────────────────────────────────────────────────────────────────

function Nav() {
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
          <Link to="/" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">Pipeline</Link>
          <Link to="/dashboard" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">Dashboard</Link>
          <Link to="/artifacts" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">Artifacts</Link>
          <Link to="/system" className="relative flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-primary bg-primary/10 border border-primary/25 shadow-[0_0_14px_rgba(71,214,255,0.12)]">
            <span className="w-1.5 h-1.5 rounded-full bg-primary shadow-[0_0_5px_rgba(71,214,255,0.9)] animate-pulse" />
            System
          </Link>
          <Link to="/pricing" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">Pricing</Link>
          <Link to="/history" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">History</Link>
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

// ─── Section 1: Global System Health ─────────────────────────────────────────

function SystemHealthBar({ elapsed }: { elapsed:number }) {
  const [h] = usePolled<any>(api.systemHealth, null, 5000);
  const mm=String(Math.floor(elapsed/60)).padStart(2,'0');
  const ss=String(elapsed%60).padStart(2,'0');
  const totalTokens = 128400 + 42100 + elapsed * 12;

  const STATS = [
    { label:'Agents Active', value: h?.agentsActive ?? '5/5',   icon:'groups',        color:'#79ff5b' },
    { label:'Tools Online',  value: h?.toolsOnline ?? '84/84',  icon:'construction',  color:'rgb(var(--c-primary))' },
    { label:'Memory Load',   value: h?.memoryLoad ?? '2.4 GB',  icon:'memory_alt',    color:'rgb(var(--c-primary))' },
    { label:'Models Ready',  value: h?.modelsReady ?? '4/4',    icon:'psychology',    color:'#79ff5b' },
    { label:'Evidence Items',value: h?.evidenceItems ?? '2,841',icon:'device_hub',    color:'rgb(var(--c-primary))' },
    { label:'Runs Today',    value: String(h?.runsToday ?? '12'), icon:'play_circle', color:'#f59e0b' },
    { label:'Tokens Used',   value: h ? `${(h.tokensUsed/1000).toFixed(0)}K` : `${(totalTokens/1000).toFixed(0)}K`, icon:'token', color:'rgb(var(--c-primary))' },
    { label:'Runtime',       value:`${mm}:${ss}`, icon:'timer',    color:'#79ff5b' },
  ];

  return (
    <div className="relative border-b border-white/[0.06] overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-[#0A0C12] to-[#0D1018]" />
      <div className="absolute inset-0 pointer-events-none"
        style={{ background:'radial-gradient(ellipse at 50% 100%, rgba(121,255,91,0.04) 0%, transparent 55%)' }} />
      <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-secondary-fixed/25 to-transparent" />

      <div className="relative max-w-[1600px] mx-auto px-container-margin py-6">
        {/* Headline */}
        <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="relative">
                <span className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-secondary-fixed opacity-35" />
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-secondary-fixed shadow-[0_0_12px_rgba(121,255,91,0.9)]" />
                </span>
              </div>
              <span className="font-mono-label text-[18px] md:text-[22px] font-bold text-on-surface tracking-[0.08em]">
                ALL SYSTEMS OPERATIONAL
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
              <span className="font-mono-label text-[11px] text-on-surface-variant/40">APS v4.0.2-STABLE</span>
              <span className="text-white/10">·</span>
              <span className="font-mono-label text-[11px] text-primary/60">RUN_0042 ACTIVE</span>
              <span className="text-white/10">·</span>
              <span className="font-mono-label text-[11px] text-on-surface-variant/40">Autonomous startup creation in progress</span>
            </div>
          </div>
          <div className="flex items-end gap-2">
            <span className="font-mono-label font-bold text-secondary-fixed leading-none"
              style={{ fontSize:'clamp(36px,5vw,52px)', textShadow:'0 0 40px rgba(121,255,91,0.5)' }}>
              99.98
            </span>
            <div className="flex flex-col pb-1.5 gap-0">
              <span className="font-mono-label text-[18px] text-secondary-fixed/60">%</span>
              <span className="font-mono-label text-[9px] text-secondary-fixed/40 uppercase tracking-[0.15em]">uptime</span>
            </div>
          </div>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
          {STATS.map(s=>(
            <div key={s.label} className="p-3 rounded-xl border border-white/[0.05] bg-white/[0.015] group hover:border-white/[0.08] transition-colors">
              <div className="flex items-center gap-1.5 mb-2">
                <span className="material-symbols-outlined text-[13px]" style={{ color:s.color }}>{s.icon}</span>
                <span className="font-mono-label text-[9px] text-on-surface-variant/35 uppercase tracking-[0.12em] truncate">{s.label}</span>
              </div>
              <div className="font-mono-label text-[16px] font-bold text-on-surface" style={{ textShadow:`0 0 10px ${s.color}33` }}>{s.value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Section 2: Agent Fleet ───────────────────────────────────────────────────

function AgentFleet({ onInspect }: { onInspect:(id:string)=>void }) {
  const [AG] = usePolled(api.systemAgents, SYS_AGENTS, 6000);
  return (
    <div className="flex flex-col h-full">
      <PanelHeader icon="groups" label="Agent Fleet"
        badge={<span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-secondary-fixed/[0.08] border border-secondary-fixed/20 font-mono-label text-[9px] text-secondary-fixed">
          <span className="flex h-1.5 w-1.5 rounded-full bg-secondary-fixed animate-pulse" />1 Running · 3 Queued · 1 Idle
        </span>} />
      <div className="flex-1 p-3 space-y-2 overflow-y-auto scrollbar-thin">
        {(AG as typeof SYS_AGENTS).map(agent=>(
          <AgentRow key={agent.id} agent={agent} onInspect={()=>onInspect(agent.id)} />
        ))}
      </div>
    </div>
  );
}

function AgentRow({ agent, onInspect }: { agent:typeof SYS_AGENTS[0]; onInspect:()=>void }) {
  const isRunning = agent.status==='running';
  return (
    <div
      onClick={onInspect}
      className={`relative rounded-xl border overflow-hidden cursor-pointer group transition-all duration-300
        ${isRunning ? 'border-primary/20 bg-primary/[0.03] hover:border-primary/35' : 'border-white/[0.05] bg-white/[0.01] hover:border-white/[0.08]'}`}>
      {isRunning && (
        <div className="absolute inset-0 pointer-events-none"
          style={{ animation:'agentPulse 3s ease-in-out infinite', background:'radial-gradient(ellipse at 0% 50%, rgb(var(--c-primary) / 0.06) 0%, transparent 60%)' }} />
      )}
      {isRunning && (
        <div className="absolute top-0 left-0 right-0 h-px pointer-events-none"
          style={{ background:'linear-gradient(90deg,transparent,#a5e7ff,transparent)', backgroundSize:'200% 100%', animation:'borderSweep 2.4s linear infinite' }} />
      )}
      <div className="relative p-3 flex items-center gap-3">
        {/* Icon */}
        <div className={`relative w-9 h-9 rounded-xl flex items-center justify-center border flex-shrink-0
          ${isRunning ? 'bg-primary/10 border-primary/30' : 'bg-white/[0.02] border-white/[0.07]'}`}>
          {isRunning && <div className="absolute inset-0 rounded-xl bg-primary/10 blur-sm" style={{ animation:'agentPulse 2.5s ease-in-out infinite' }} />}
          <span className={`material-symbols-outlined text-[18px] relative ${isRunning?'text-primary':'text-on-surface-variant/30'}`}>{agent.icon}</span>
        </div>

        {/* Name + job */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className={`text-[13px] font-semibold ${isRunning?'text-on-surface':'text-on-surface/55'}`}>{agent.name}</span>
            <StatusDot status={agent.status} />
          </div>
          <div className={`font-mono-label text-[10px] truncate ${isRunning?'text-primary/55':'text-on-surface-variant/28'}`}>{agent.currentJob}</div>
        </div>

        {/* Metrics */}
        <div className="flex items-center gap-4 flex-shrink-0">
          <div className="hidden md:flex flex-col items-end gap-0.5">
            <span className="font-mono-label text-[9px] text-on-surface-variant/30 uppercase">Mem</span>
            <span className="font-mono-label text-[11px] font-bold text-on-surface/60">{agent.memPct}%</span>
          </div>
          <div className="hidden md:flex flex-col items-end gap-0.5">
            <span className="font-mono-label text-[9px] text-on-surface-variant/30 uppercase">Tasks</span>
            <span className="font-mono-label text-[11px] font-bold text-on-surface/60">{agent.tasksCompleted}</span>
          </div>
          <div className="hidden lg:flex flex-col items-end gap-0.5">
            <span className="font-mono-label text-[9px] text-on-surface-variant/30 uppercase">Success</span>
            <span className={`font-mono-label text-[11px] font-bold ${agent.successRate>97?'text-secondary-fixed':'text-primary'}`}>{agent.successRate}%</span>
          </div>
          {isRunning && (
            <div className="flex gap-0.5">
              {[0,1,2].map(i=>(
                <div key={i} className="w-1 h-1 rounded-full bg-primary/60" style={{ animation:`thinkDot 1.4s ease-in-out ${i*0.2}s infinite` }} />
              ))}
            </div>
          )}
          <span className="material-symbols-outlined text-[14px] text-on-surface-variant/20 group-hover:text-on-surface-variant/50 transition-colors">chevron_right</span>
        </div>
      </div>

      {/* Memory bar */}
      {isRunning && (
        <div className="relative px-3 pb-2">
          <MiniBar pct={agent.memPct} color="#a5e7ff" />
        </div>
      )}
    </div>
  );
}

// ─── Section 3: Model Orchestration ──────────────────────────────────────────

const PROV_SEED = {
  resolved: 'gemini', configured: false,
  chain: [
    { name:'gemini', label:'Gemini', model:'gemini-2.0-flash', available:true,  breakerOpen:false, primary:true },
    { name:'groq',   label:'GROQ',   model:'llama-3.3-70b',    available:false, breakerOpen:false, primary:false },
    { name:'nim',    label:'NIM',    model:'nemotron-nano-9b', available:false, breakerOpen:false, primary:false },
  ],
  registry: [] as any[],
};

const PROV_ICON: Record<string, string> = {
  gemini:'auto_awesome', nim:'memory', groq:'bolt', cerebras:'developer_board',
  sambanova:'dns', mistral:'air', openrouter:'router', openai:'smart_toy',
};

function ModelOrchestration() {
  const [MODELS_LIVE] = usePolled(api.systemModels, MODELS, 6000);
  const [PROV] = usePolled<typeof PROV_SEED>(api.systemProviders, PROV_SEED, 8000);
  const chain = PROV.chain ?? [];
  const primary = chain.find((p:any)=>p.primary) ?? chain[0];
  const fallbacks = chain.filter((p:any)=>p!==primary);
  const [routePos, setRoutePos] = useState(0);
  useEffect(()=>{
    const iv = setInterval(()=>setRoutePos(p=>(p+1)%100),80);
    return ()=>clearInterval(iv);
  },[]);

  return (
    <div className="flex flex-col h-full">
      <PanelHeader icon="psychology" label="Model Orchestration" iconColor="text-primary" />
      <div className="flex-1 flex flex-col p-3 gap-3 overflow-y-auto scrollbar-thin">
        {/* Routing diagram */}
        <div className="rounded-xl border border-white/[0.05] bg-[#080A0F] p-4">
          <div className="font-mono-label text-[9px] text-on-surface-variant/30 uppercase tracking-[0.15em] mb-3">Active Routing — RUN_0042</div>
          <div className="flex flex-col items-center gap-0">
            {/* Agent */}
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary/[0.06] border border-primary/20 w-full max-w-[200px]">
              <span className="material-symbols-outlined text-primary text-[14px]">travel_explore</span>
              <span className="font-mono-label text-[11px] text-primary/80">Research Agent</span>
            </div>
            {/* Arrow with traveling dot */}
            <div className="relative flex flex-col items-center my-0.5" style={{ height:28 }}>
              <div className="w-px h-full bg-primary/20" />
              <div className="absolute w-2 h-2 rounded-full bg-primary shadow-[0_0_8px_rgb(var(--c-primary) / 0.8)]"
                style={{ top:`${routePos > 50 ? 0 : routePos * 2}%`, transition:'top 0.08s linear', filter:'drop-shadow(0 0 6px rgb(var(--c-primary) / 0.9))' }} />
            </div>
            {/* PRIMARY — the resolved provider at the head of the real failover chain */}
            {primary && (
              <div className="relative flex items-center gap-2 px-3 py-2 rounded-lg bg-primary/[0.06] border border-primary/25 w-full max-w-[200px] shadow-[0_0_14px_rgb(var(--c-primary) / 0.07)]">
                <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-primary rounded-l-lg" />
                <span className="material-symbols-outlined text-primary text-[14px]">{PROV_ICON[primary.name] ?? 'psychology'}</span>
                <div className="flex-1 min-w-0">
                  <div className="font-mono-label text-[11px] text-primary/80 font-bold truncate">{primary.model || primary.label}</div>
                  <div className="font-mono-label text-[8px] text-primary/40 uppercase">PRIMARY · {primary.label}</div>
                </div>
                <span className={`flex h-1.5 w-1.5 rounded-full ${primary.available ? 'bg-secondary-fixed shadow-[0_0_5px_rgba(121,255,91,0.8)] animate-pulse' : 'bg-on-surface-variant/30'}`} />
              </div>
            )}
            <div className="w-px h-3 bg-white/[0.06]" />
            <div className="font-mono-label text-[8px] text-on-surface-variant/20 uppercase tracking-wider">
              fallback chain{PROV.configured===false && ' · default'}
            </div>
            <div className="w-px h-2 bg-white/[0.05]" />
            {/* Fallbacks — the rest of the resolved chain, with live availability + breaker state */}
            {fallbacks.map((m:any,i:number)=>(
              <div key={m.name} className="flex flex-col items-center gap-0 w-full max-w-[200px]">
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-white/[0.05] bg-white/[0.01] w-full">
                  <span className="material-symbols-outlined text-on-surface-variant/30 text-[13px]">{PROV_ICON[m.name] ?? 'smart_toy'}</span>
                  <div className="flex-1 min-w-0">
                    <div className="font-mono-label text-[10px] text-on-surface-variant/45 truncate">{m.model || m.label}</div>
                    <div className="font-mono-label text-[8px] text-on-surface-variant/25 uppercase">{m.label}</div>
                  </div>
                  {m.breakerOpen
                    ? <span className="material-symbols-outlined text-[#f59e0b] text-[12px]" title="circuit open">bolt</span>
                    : <span className={`flex h-1.5 w-1.5 rounded-full ${m.available ? 'bg-secondary-fixed/60' : 'bg-on-surface-variant/20'}`} title={m.available?'key set':'no key'} />}
                </div>
                {i < fallbacks.length-1 && <div className="w-px h-1.5 bg-white/[0.04]" />}
              </div>
            ))}
            <div className="w-px h-2 bg-white/[0.04]" />
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-secondary-fixed/[0.06] border border-secondary-fixed/15 w-full max-w-[200px]">
              <span className="material-symbols-outlined text-secondary-fixed text-[14px]">check_circle</span>
              <span className="font-mono-label text-[11px] text-secondary-fixed/70">Success · 99.2% rate</span>
            </div>
          </div>
        </div>

        {/* Model cards */}
        <div className="space-y-2">
          {(MODELS_LIVE as typeof MODELS).map(m=>(
            <div key={m.id} className={`p-3 rounded-xl border transition-colors ${m.primary ? 'border-primary/15 bg-primary/[0.025]' : 'border-white/[0.04] hover:border-white/[0.07]'}`}>
              <div className="flex items-center gap-2 mb-2">
                <span className="material-symbols-outlined text-[14px]" style={{ color:m.color }}>{m.icon}</span>
                <span className="font-mono-label text-[11px] font-semibold text-on-surface/70">{m.name}</span>
                {m.primary && <span className="ml-auto px-1.5 py-0.5 rounded-full bg-primary/10 border border-primary/20 font-mono-label text-[8px] text-primary">PRIMARY</span>}
              </div>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { label:'Latency',     value:`${m.latencyMs}ms` },
                  { label:'Success',     value:`${m.successRate}%` },
                  { label:'Cost',        value:`$${m.costUSD.toFixed(2)}` },
                ].map(s=>(
                  <div key={s.label}>
                    <div className="font-mono-label text-[8px] text-on-surface-variant/30 uppercase">{s.label}</div>
                    <div className="font-mono-label text-[12px] font-bold text-on-surface/60">{s.value}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Section 4: Tool Ecosystem ────────────────────────────────────────────────

function ToolEcosystem() {
  const [activeNs, setActiveNs] = useState('Research');
  const [TG] = usePolled(api.systemTools, TOOL_GROUPS, 8000);
  const TOOL_GROUPS_LIVE = TG as typeof TOOL_GROUPS;
  const group = TOOL_GROUPS_LIVE.find(g=>g.ns===activeNs) ?? TOOL_GROUPS_LIVE[0];

  return (
    <div className="flex flex-col h-full">
      <PanelHeader icon="construction" label="Tool Ecosystem"
        badge={<span className="font-mono-label text-[10px] text-secondary-fixed">84 tools · 98.1% avg success</span>} />
      <div className="flex-shrink-0 flex gap-1 px-3 pt-2">
        {TOOL_GROUPS_LIVE.map(g=>(
          <button key={g.ns} onClick={()=>setActiveNs(g.ns)}
            className={`px-2.5 py-1 rounded-lg font-mono-label text-[9px] uppercase tracking-[0.08em] transition-all border
              ${activeNs===g.ns ? 'bg-white/[0.06] border-white/10 text-on-surface' : 'border-transparent text-on-surface-variant/35 hover:text-on-surface-variant/55'}`}>
            {g.ns}
          </button>
        ))}
      </div>
      <div className="flex-1 flex gap-3 p-3 overflow-hidden">
        {/* Tool list */}
        <div className="flex-1 space-y-1.5 overflow-y-auto scrollbar-thin">
          {group.tools.map(t=>(
            <div key={t.name} className="p-3 rounded-xl border border-white/[0.05] bg-white/[0.01] hover:border-white/[0.08] transition-colors group">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-1.5 h-1.5 rounded-full" style={{ background:group.color, opacity: t.health==='healthy'?0.8:0.3, boxShadow:`0 0 4px ${group.color}66` }} />
                <span className="font-mono-label text-[11px] text-on-surface/65 font-semibold">{t.name}</span>
                <span className={`ml-auto font-mono-label text-[9px] ${t.health==='healthy'?'text-secondary-fixed/60':'text-on-surface-variant/25'}`}>{t.health}</span>
              </div>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { label:'Calls',    value:t.inv||'—' },
                  { label:'Success',  value:t.succ?`${t.succ}%`:'—' },
                  { label:'Avg ms',   value:t.avgMs||'—' },
                  { label:'Last',     value:t.last },
                ].map(m=>(
                  <div key={m.label}>
                    <div className="font-mono-label text-[8px] text-on-surface-variant/25 uppercase">{m.label}</div>
                    <div className="font-mono-label text-[11px] text-on-surface/55">{m.value}</div>
                  </div>
                ))}
              </div>
              {t.succ > 0 && <div className="mt-2"><MiniBar pct={t.succ} color={group.color} /></div>}
            </div>
          ))}
        </div>

        {/* Heatmap */}
        <div className="w-24 flex-shrink-0 flex flex-col">
          <div className="font-mono-label text-[8px] text-on-surface-variant/25 uppercase tracking-[0.1em] mb-2">Activity 24h</div>
          <div className="flex-1 grid gap-px" style={{ gridTemplateColumns:`repeat(6,1fr)`, gridTemplateRows:`repeat(${Math.ceil(HEATMAP.length/6)},1fr)` }}>
            {HEATMAP.slice(0,group.tools.length*6).map((v,i)=>(
              <div key={i} className="rounded-sm" style={{ background:group.color, opacity:v*0.75, minHeight:8 }} />
            ))}
          </div>
          <div className="flex justify-between mt-1">
            <span className="font-mono-label text-[7px] text-on-surface-variant/20">Low</span>
            <span className="font-mono-label text-[7px] text-on-surface-variant/20">High</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Section 5: Memory Engine ─────────────────────────────────────────────────

function MemoryEngine() {
  const [MT] = usePolled(api.systemMemory, MEMORY_TYPES, 8000);
  return (
    <div className="flex flex-col h-full">
      <PanelHeader icon="memory_alt" label="Memory Engine"
        badge={<span className="font-mono-label text-[10px] text-primary/60">183 MB · 22,520 nodes</span>} />
      <div className="flex-1 p-3 space-y-1.5 overflow-y-auto scrollbar-thin">
        {(MT as typeof MEMORY_TYPES).map((m,i)=>(
          <div key={m.id} className="p-3 rounded-xl border border-white/[0.05] bg-white/[0.01] hover:border-white/[0.08] transition-colors group"
            style={{ animation:`fadeInUp 0.4s ${i*0.05}s cubic-bezier(0.16,1,0.3,1) both` }}>
            <div className="flex items-center gap-2 mb-2">
              <div className="w-7 h-7 rounded-lg bg-white/[0.03] border border-white/[0.06] flex items-center justify-center flex-shrink-0">
                <span className="material-symbols-outlined text-[14px]" style={{ color:m.color }}>{m.icon}</span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-mono-label text-[11px] font-semibold text-on-surface/70 leading-tight">{m.name}</div>
                <div className="font-mono-label text-[9px] text-on-surface-variant/28">{m.note}</div>
              </div>
              <div className="text-right flex-shrink-0">
                <div className="font-mono-label text-[11px] font-bold text-on-surface/60">{m.size}</div>
                <div className="font-mono-label text-[8px] text-on-surface-variant/25">{m.nodes.toLocaleString()} nodes</div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <MiniBar pct={m.pct} color={m.color} />
              <span className="font-mono-label text-[9px] text-on-surface-variant/30 flex-shrink-0">{m.speed}ms</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Section 6: Knowledge Graph ───────────────────────────────────────────────

function KnowledgeGraph() {
  const [waveStep, setWaveStep] = useState(0);
  useEffect(()=>{
    const iv = setInterval(()=>setWaveStep(s=>(s+1)%(KG_NODES.length*2)), 600);
    return ()=>clearInterval(iv);
  },[]);

  const CX = 200;

  return (
    <div className="flex flex-col h-full">
      <PanelHeader icon="scatter_plot" label="Knowledge Graph" iconColor="text-secondary-fixed"
        badge={<span className="font-mono-label text-[10px] text-on-surface-variant/35">Live propagation</span>} />
      <div className="flex-1 relative overflow-hidden">
        <svg viewBox="0 0 400 590" className="w-full h-full" preserveAspectRatio="xMidYMid meet">
          <defs>
            <radialGradient id="kgGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#a5e7ff" stopOpacity="0.05" />
              <stop offset="100%" stopColor="#a5e7ff" stopOpacity="0" />
            </radialGradient>
            {KG_NODES.slice(0,-1).map((n,i)=>{
              const next = KG_NODES[i+1];
              return <path key={`kg-path-${i}`} id={`kg-conn-${i}`} d={`M${CX},${n.y} L${CX},${next.y}`} />;
            })}
          </defs>
          <rect width="400" height="590" fill="url(#kgGlow)" />

          {/* Main vertical connectors with traveling dots */}
          {KG_NODES.slice(0,-1).map((n,i)=>{
            const next = KG_NODES[i+1];
            const nodeActive = waveStep === i || waveStep === i+KG_NODES.length;
            return (
              <g key={`conn-${i}`}>
                <line x1={CX} y1={n.y+16} x2={CX} y2={next.y-16}
                  stroke={nodeActive?'rgb(var(--c-primary))':'#3c494e'} strokeWidth={nodeActive?1.2:0.7}
                  opacity={nodeActive?0.7:0.35} style={{ transition:'all 0.4s' }} />
                <circle r="2.5" fill="#a5e7ff" opacity={nodeActive?0.9:0.35}
                  style={{ filter:'drop-shadow(0 0 4px rgb(var(--c-primary) / 0.7))' }}>
                  <animateMotion dur="1.2s" repeatCount="indefinite" path={`M${CX},${n.y+16} L${CX},${next.y-16}`}
                    begin={`${i*0.3}s`} />
                </circle>
              </g>
            );
          })}

          {/* Side connectors */}
          {KG_NODES.map((n,ni)=>
            n.side.map((s,si)=>{
              const sx = CX + s.dx;
              const nodeActive = waveStep===ni || waveStep===ni+KG_NODES.length;
              return (
                <g key={`side-${ni}-${si}`}>
                  <line x1={CX} y1={n.y} x2={sx} y2={n.y}
                    stroke={nodeActive?'rgb(var(--c-primary))':'#3c494e'} strokeWidth="0.7"
                    strokeDasharray="3 4" opacity={nodeActive?0.55:0.25} style={{ transition:'all 0.4s' }} />
                  <circle cx={sx} cy={n.y} r="10"
                    fill={nodeActive?'rgb(var(--c-primary) / 0.08)':'rgb(var(--c-overlay) / 0.02)'}
                    stroke={nodeActive?'rgb(var(--c-primary) / 0.35)':'rgba(60,73,78,0.5)'}
                    strokeWidth="0.8" style={{ transition:'all 0.4s' }} />
                  <circle cx={sx} cy={n.y} r="2.5"
                    fill="#a5e7ff" opacity={nodeActive?0.8:0.25}
                    style={{ filter: nodeActive?'drop-shadow(0 0 4px rgb(var(--c-primary) / 0.7))':'none', transition:'all 0.4s' }} />
                  <text x={sx} y={n.y+20} textAnchor="middle" fontSize="7.5" fill="#bbc9cf" opacity="0.45"
                    style={{ fontFamily:'JetBrains Mono,monospace' }}>{s.label}</text>
                </g>
              );
            })
          )}

          {/* Main nodes */}
          {KG_NODES.map((n,i)=>{
            const nodeActive = waveStep===i || waveStep===i+KG_NODES.length;
            const colors = ['rgb(var(--c-primary))','#f59e0b','#f59e0b','#79ff5b','rgb(var(--c-primary))','#79ff5b','rgb(var(--c-primary))'];
            const col = colors[i];
            return (
              <g key={n.id} transform={`translate(${CX},${n.y})`}>
                {nodeActive && (
                  <circle r="30" fill={col} opacity="0.06"
                    style={{ animation:'nodePing 1.5s ease-out infinite' }} />
                )}
                <circle r="18" fill={nodeActive?`${col}18`:'rgb(var(--c-overlay) / 0.03)'}
                  stroke={nodeActive?col:'#3c494e'} strokeWidth={nodeActive?1.5:0.8}
                  style={{ transition:'all 0.4s', filter:nodeActive?`drop-shadow(0 0 10px ${col}55)`:'none' }} />
                <circle r="5" fill={col} opacity={nodeActive?1:0.4}
                  style={{ filter:nodeActive?`drop-shadow(0 0 8px ${col})`:'none', transition:'all 0.4s' }} />
                <text y="30" textAnchor="middle" fontSize="9" fill={col} opacity={nodeActive?0.9:0.5} fontWeight={nodeActive?'700':'400'}
                  style={{ fontFamily:'JetBrains Mono,monospace', transition:'all 0.4s' }}>{n.label}</text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

// ─── Section 7: Observability ─────────────────────────────────────────────────

function ObservabilityCenter() {
  const [OBS] = usePolled<typeof SPARK>(api.systemObservability, SPARK, 5000);
  const METRICS = [
    { label:'Total Runs',     value:'12',       delta:'+2', spark:OBS.runs,    color:'rgb(var(--c-primary))' },
    { label:'Avg Latency',    value:'1,240ms',  delta:'-8%', spark:OBS.latency, color:'#79ff5b' },
    { label:'Tokens Used',    value:'1.59M',    delta:'+24%', spark:OBS.tokens,  color:'rgb(var(--c-primary))' },
    { label:'Error Rate',     value:'0.31%',    delta:'-0.1', spark:OBS.errors,  color:'#f59e0b' },
  ];

  return (
    <div className="flex flex-col h-full">
      <PanelHeader icon="monitoring" label="Observability Center" iconColor="text-[#f59e0b]"
        badge={<span className="flex items-center gap-1.5"><span className="flex h-1.5 w-1.5 rounded-full bg-secondary-fixed animate-pulse" /><span className="font-mono-label text-[10px] text-secondary-fixed/60">Live</span></span>} />
      <div className="flex-1 p-3 space-y-3 overflow-y-auto scrollbar-thin">
        {/* Metric sparklines */}
        <div className="grid grid-cols-2 gap-2">
          {METRICS.map(m=>(
            <div key={m.label} className="p-3 rounded-xl border border-white/[0.05] bg-white/[0.01]">
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono-label text-[9px] text-on-surface-variant/35 uppercase tracking-[0.1em]">{m.label}</span>
                <span className="font-mono-label text-[9px]" style={{ color: m.delta.startsWith('+')&&m.label!=='Error Rate'?'#79ff5b':m.delta.startsWith('-')&&m.label==='Error Rate'?'#79ff5b':'#f59e0b' }}>{m.delta}</span>
              </div>
              <div className="font-mono-label text-[16px] font-bold text-on-surface/70 mb-2">{m.value}</div>
              <Sparkline data={m.spark} color={m.color} h={28} />
            </div>
          ))}
        </div>

        {/* Activity heatmap */}
        <div className="p-3 rounded-xl border border-white/[0.05] bg-white/[0.01]">
          <div className="flex items-center justify-between mb-2">
            <span className="font-mono-label text-[10px] text-on-surface uppercase tracking-[0.12em]">Tool Activity Heatmap</span>
            <span className="font-mono-label text-[9px] text-on-surface-variant/30">7 tools × 24h</span>
          </div>
          <div className="grid gap-0.5" style={{ gridTemplateColumns:'repeat(24,1fr)' }}>
            {Array.from({length:7}).map((_,row)=>
              Array.from({length:24}).map((_,col)=>{
                const v = HEATMAP[row*24+col];
                return (
                  <div key={`${row}-${col}`} className="aspect-square rounded-sm"
                    style={{ background:'rgb(var(--c-primary))', opacity:v*0.65, minHeight:6 }} />
                );
              })
            )}
          </div>
          <div className="flex justify-between mt-1.5">
            {['00:00','06:00','12:00','18:00','24:00'].map(t=>(
              <span key={t} className="font-mono-label text-[7px] text-on-surface-variant/20">{t}</span>
            ))}
          </div>
        </div>

        {/* Key stats */}
        <div className="grid grid-cols-3 gap-2">
          {[
            { label:'Tool Calls', value:'1,614', icon:'construction' },
            { label:'Evidence',   value:'2,841', icon:'device_hub' },
            { label:'Artifacts',  value:'4/8',   icon:'inventory_2' },
          ].map(s=>(
            <div key={s.label} className="p-3 rounded-xl border border-white/[0.05] bg-white/[0.01] text-center">
              <span className="material-symbols-outlined text-primary text-[18px] block mb-1">{s.icon}</span>
              <div className="font-mono-label text-[16px] font-bold text-on-surface/70">{s.value}</div>
              <div className="font-mono-label text-[8px] text-on-surface-variant/30 uppercase mt-0.5">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Latency distribution bars */}
        <div className="p-3 rounded-xl border border-white/[0.05] bg-white/[0.01]">
          <div className="font-mono-label text-[10px] text-on-surface uppercase tracking-[0.12em] mb-3">Latency Distribution</div>
          <div className="space-y-1.5">
            {[['<500ms','22%',22,'#79ff5b'],['500–1s','31%',31,'rgb(var(--c-primary))'],['1–2s','34%',34,'rgb(var(--c-primary))'],['2–5s','11%',11,'#f59e0b'],['>5s','2%',2,'#ef4444']].map(([b,l,p,c])=>(
              <div key={b as string} className="flex items-center gap-3">
                <span className="font-mono-label text-[9px] text-on-surface-variant/35 w-16 flex-shrink-0">{b}</span>
                <div className="flex-1 h-1.5 bg-white/[0.04] rounded-full overflow-hidden">
                  <div className="h-full rounded-full" style={{ width:`${p}%`, background:c as string, boxShadow:`0 0 4px ${c as string}55` }} />
                </div>
                <span className="font-mono-label text-[9px] text-on-surface-variant/40 w-7 text-right">{l}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Section 8: Event Stream ──────────────────────────────────────────────────

function EventStream() {
  const [events, setEvents] = useState(EVENT_SEED);
  const [paused, setPaused] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(()=>{
    let i=0;
    const iv=setInterval(()=>{
      if (!paused && i<MORE_EVENTS.length) setEvents(prev=>[...prev, MORE_EVENTS[i++]]);
    },4000);
    return ()=>clearInterval(iv);
  },[paused]);

  useEffect(()=>{
    if (!paused && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  },[events,paused]);

  function typeStyle(c:string) {
    if(c==='green') return { dot:'#79ff5b', line:'text-secondary-fixed', border:'border-secondary-fixed/12', bg:'bg-secondary-fixed/[0.025]' };
    if(c==='amber') return { dot:'#f59e0b',  line:'text-[#f59e0b]',       border:'border-[#f59e0b]/12',         bg:'bg-[#f59e0b]/[0.025]' };
    return { dot:'rgb(var(--c-primary))', line:'text-primary', border:'border-primary/10', bg:'bg-primary/[0.015]' };
  }

  return (
    <div className="flex flex-col h-full">
      <PanelHeader icon="stream" label="Event Stream"
        badge={
          <button onClick={()=>setPaused(p=>!p)}
            className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full border font-mono-label text-[9px] uppercase tracking-[0.08em] transition-all
              ${paused ? 'border-[#f59e0b]/25 bg-[#f59e0b]/10 text-[#f59e0b]' : 'border-secondary-fixed/20 bg-secondary-fixed/[0.06] text-secondary-fixed'}`}>
            <span className={`flex h-1.5 w-1.5 rounded-full ${paused?'bg-[#f59e0b]':'bg-secondary-fixed animate-pulse'}`} />
            {paused ? 'Paused' : 'Live'}
          </button>
        } />
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-1 scrollbar-thin"
        onMouseEnter={()=>setPaused(true)} onMouseLeave={()=>setPaused(false)}
        style={{ maskImage:'linear-gradient(to bottom, transparent, black 5%, black 93%, transparent)' }}>
        {events.map((e,i)=>{
          const s=typeStyle(e.color);
          return (
            <div key={i} className={`flex items-start gap-2.5 px-2.5 py-2 rounded-lg border ${s.border} ${s.bg} hover:bg-white/[0.02] transition-colors`}
              style={i>=EVENT_SEED.length?{animation:'streamIn 0.4s cubic-bezier(0.16,1,0.3,1) forwards'}:{}}>
              <span className="font-mono-label text-[10px] text-on-surface-variant/25 mt-0.5 w-14 flex-shrink-0 tabular-nums">{e.t}</span>
              <span className="flex h-1.5 w-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ background:s.dot, boxShadow:`0 0 5px ${s.dot}99` }} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className={`material-symbols-outlined text-[12px] ${s.line}`}>{e.icon}</span>
                  <span className={`font-mono-label text-[9px] uppercase tracking-[0.08em] ${s.line} opacity-60`}>{e.type}</span>
                </div>
                <div className="font-mono-log text-[11px] text-on-surface/70 leading-snug">{e.msg}</div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="px-4 py-2 border-t border-white/[0.04] flex items-center justify-between flex-shrink-0">
        <span className="font-mono-label text-[10px] text-on-surface-variant/25">{events.length} events · Mission Control</span>
        <button className="font-mono-label text-[10px] text-on-surface-variant/35 hover:text-primary transition-colors flex items-center gap-1">
          <span className="material-symbols-outlined text-[12px]">replay</span> Replay
        </button>
      </div>
    </div>
  );
}

// ─── Section 9: Quality & Evaluation ─────────────────────────────────────────

function QualityEvaluation() {
  const [QS] = usePolled(api.systemQuality, QUALITY_SCORES, 8000);
  return (
    <div className="flex flex-col h-full">
      <PanelHeader icon="verified" label="Quality Evaluation" iconColor="text-secondary-fixed"
        badge={<span className="font-mono-label text-[10px] text-secondary-fixed">Avg 8.78 / 10</span>} />
      <div className="flex-1 p-3 space-y-3 overflow-y-auto scrollbar-thin">
        {(QS as typeof QUALITY_SCORES).map((q,i)=>(
          <div key={i} className="p-3.5 rounded-xl border border-white/[0.05] bg-white/[0.01] hover:border-white/[0.08] transition-colors">
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono-label text-[12px] font-semibold text-on-surface/70">{q.name}</span>
              <div className="flex items-end gap-1">
                <span className="font-mono-label text-[22px] font-bold text-primary leading-none"
                  style={{ textShadow:'0 0 15px rgb(var(--c-primary) / 0.4)' }}>{q.score}</span>
                <span className="font-mono-label text-[11px] text-on-surface-variant/40 mb-0.5">/10</span>
              </div>
            </div>
            <div className="space-y-2">
              {[
                { label:'Evidence Coverage', value:q.coverage, color:'rgb(var(--c-primary))' },
                { label:'Research Depth',    value:q.depth*10, color:'#79ff5b' },
                { label:'Hallucination Risk',value:100-q.hRisk*10, color:'#f59e0b', invert:true },
              ].map(m=>(
                <div key={m.label}>
                  <div className="flex justify-between mb-1">
                    <span className="font-mono-label text-[9px] text-on-surface-variant/30 uppercase tracking-[0.1em]">{m.label}</span>
                    <span className="font-mono-label text-[9px] font-bold" style={{ color:m.color }}>
                      {m.invert ? `${q.hRisk}% risk` : `${m.label==='Evidence Coverage'?q.coverage:q.depth}/10`}
                    </span>
                  </div>
                  <MiniBar pct={m.value} color={m.color} />
                </div>
              ))}
            </div>
          </div>
        ))}

        {/* Overall quality summary */}
        <div className="p-3.5 rounded-xl border border-primary/12 bg-primary/[0.025]">
          <div className="font-mono-label text-[10px] text-primary/60 uppercase tracking-[0.15em] mb-3">Overall Assessment</div>
          <div className="space-y-2">
            {[
              { label:'Artifact Quality',          score:9.1, icon:'inventory_2'   },
              { label:'Evidence Coverage',          score:9.3, icon:'device_hub'    },
              { label:'Requirement Completeness',   score:8.7, icon:'description'   },
              { label:'Architecture Confidence',    score:8.2, icon:'hub'           },
            ].map(r=>(
              <div key={r.label} className="flex items-center gap-3">
                <span className="material-symbols-outlined text-primary/40 text-[14px]">{r.icon}</span>
                <span className="flex-1 font-mono-label text-[10px] text-on-surface-variant/50">{r.label}</span>
                <span className="font-mono-label text-[12px] font-bold text-primary">{r.score}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Section 10: Infrastructure Map ──────────────────────────────────────────

function InfrastructureMap() {
  const [pulse, setPulse] = useState(0);
  useEffect(()=>{
    const iv=setInterval(()=>setPulse(p=>(p+1)%6),800);
    return ()=>clearInterval(iv);
  },[]);

  const LAYERS = [
    { label:'User',     nodes:[{id:'user',label:'User',icon:'person'}],            color:'#bbc9cf', x:55 },
    { label:'APS Core', nodes:[{id:'aps',label:'APS',icon:'hub'}],                 color:'rgb(var(--c-primary))', x:145 },
    { label:'Agents',   nodes:SYS_AGENTS.map(a=>({id:a.id,label:a.name.split(' ')[0],icon:a.icon})), color:'rgb(var(--c-primary))', x:255 },
    { label:'Tools',    nodes:[{id:'t1',label:'Search',icon:'search'},{id:'t2',label:'GitHub',icon:'code'},{id:'t3',label:'Reddit',icon:'forum'},{id:'t4',label:'Papers',icon:'library_books'}], color:'#79ff5b', x:355 },
    { label:'Output',   nodes:[{id:'o1',label:'Artifacts',icon:'inventory_2'},{id:'o2',label:'Evidence',icon:'device_hub'}], color:'rgb(var(--c-primary))', x:445 },
  ];

  const H = 280;

  function nodeY(_layerIdx:number, nodeIdx:number, total:number) {
    const spacing = H / (total + 1);
    return spacing * (nodeIdx + 1);
  }

  return (
    <div className="flex flex-col h-full">
      <PanelHeader icon="account_tree" label="Infrastructure Map"
        badge={<span className="font-mono-label text-[10px] text-on-surface-variant/30">Live dependency graph</span>} />
      <div className="flex-1 relative overflow-hidden p-2">
        <svg viewBox="0 0 500 280" className="w-full h-full" preserveAspectRatio="xMidYMid meet">
          <defs>
            <radialGradient id="infraGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#a5e7ff" stopOpacity="0.04"/>
              <stop offset="100%" stopColor="#a5e7ff" stopOpacity="0"/>
            </radialGradient>
          </defs>
          <rect width="500" height="280" fill="url(#infraGlow)" />

          {/* Connections */}
          {LAYERS.slice(0,-1).map((layer,li)=>{
            const nextLayer = LAYERS[li+1];
            return layer.nodes.map((na,ni)=>{
              const y1 = nodeY(li, ni, layer.nodes.length);
              return nextLayer.nodes.map((nb,nj)=>{
                const y2 = nodeY(li+1, nj, nextLayer.nodes.length);
                const edgeActive = pulse===li+ni || pulse===li+nj;
                return (
                  <g key={`${na.id}-${nb.id}`}>
                    <line x1={layer.x+14} y1={y1} x2={nextLayer.x-14} y2={y2}
                      stroke={edgeActive?'rgb(var(--c-primary))':'#3c494e'}
                      strokeWidth={edgeActive?0.9:0.5}
                      opacity={edgeActive?0.6:0.25}
                      style={{ transition:'all 0.4s' }} />
                    {edgeActive && (
                      <circle r="2" fill="#a5e7ff" opacity="0.8"
                        style={{ filter:'drop-shadow(0 0 3px rgb(var(--c-primary) / 0.7))' }}>
                        <animateMotion dur="0.8s" repeatCount="indefinite"
                          path={`M${layer.x+14},${y1} L${nextLayer.x-14},${y2}`} />
                      </circle>
                    )}
                  </g>
                );
              });
            });
          })}

          {/* Nodes */}
          {LAYERS.map((layer,li)=>
            layer.nodes.map((n,ni)=>{
              const y = nodeY(li, ni, layer.nodes.length);
              const nodeActive = (pulse>=li && pulse<=li+1);
              return (
                <g key={n.id} transform={`translate(${layer.x},${y})`}>
                  {nodeActive && <circle r="22" fill={layer.color} opacity="0.06" style={{ animation:'nodePing 1.5s ease-out infinite' }} />}
                  <circle r="14" fill={nodeActive?`rgb(var(--c-primary) / 0.07)`:'rgb(var(--c-overlay) / 0.02)'}
                    stroke={nodeActive?layer.color:'#3c494e'} strokeWidth={nodeActive?1.2:0.7}
                    style={{ transition:'all 0.4s', filter:nodeActive?`drop-shadow(0 0 8px ${layer.color}44)`:'none' }} />
                  <circle r="3.5" fill={layer.color} opacity={nodeActive?0.9:0.3}
                    style={{ filter:nodeActive?`drop-shadow(0 0 5px ${layer.color})`:'none', transition:'all 0.4s' }} />
                  <text y="24" textAnchor="middle" fontSize="7.5" fill="#bbc9cf" opacity={nodeActive?0.65:0.35}
                    style={{ fontFamily:'JetBrains Mono,monospace', transition:'all 0.4s' }}>{n.label}</text>
                </g>
              );
            })
          )}

          {/* Layer labels */}
          {LAYERS.map(l=>(
            <text key={l.label} x={l.x} y="270" textAnchor="middle" fontSize="7" fill="#bbc9cf" opacity="0.25"
              style={{ fontFamily:'JetBrains Mono,monospace' }}>{l.label}</text>
          ))}
        </svg>
      </div>
    </div>
  );
}

// ─── Section 11: Cost Center ──────────────────────────────────────────────────

function CostCenter({ elapsed }: { elapsed:number }) {
  const [CI_LIVE] = usePolled(api.systemCost, COST_ITEMS, 8000);
  const COST = CI_LIVE as typeof COST_ITEMS;
  const base = 19.63;
  const live = (base + elapsed * 0.0042).toFixed(2);
  const total = COST.reduce((s,i)=>s+i.value,0);

  return (
    <div className="flex flex-col h-full">
      <PanelHeader icon="payments" label="Cost & Resource Center"
        badge={<span className="font-mono-label text-[10px] text-[#f59e0b]">$0.0042/s</span>} />
      <div className="flex-1 p-3 space-y-3 overflow-y-auto scrollbar-thin">
        {/* Live counter */}
        <div className="p-4 rounded-xl border border-[#f59e0b]/12 bg-[#f59e0b]/[0.025] text-center">
          <div className="font-mono-label text-[10px] text-[#f59e0b]/50 uppercase tracking-[0.15em] mb-1">Current Run Cost</div>
          <div className="font-mono-label text-[38px] font-bold text-[#f59e0b] leading-none"
            style={{ textShadow:'0 0 20px rgba(245,158,11,0.4)' }}>
            ${live}
          </div>
          <div className="font-mono-label text-[9px] text-[#f59e0b]/35 mt-1 uppercase tracking-wider">Ticking live</div>
        </div>

        {/* Breakdown */}
        <div className="space-y-1.5">
          {COST.map((c,i)=>(
            <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg border border-white/[0.04] bg-white/[0.01]">
              <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${c.category==='Model'?'bg-primary/60':c.category==='Tool'?'bg-secondary-fixed/60':'bg-on-surface-variant/30'}`} />
              <span className="flex-1 font-mono-label text-[11px] text-on-surface-variant/55 truncate">{c.label}</span>
              {c.tokens!=='—' && <span className="font-mono-label text-[9px] text-on-surface-variant/30">{c.tokens}</span>}
              <span className="font-mono-label text-[12px] font-bold text-on-surface/60 flex-shrink-0">${c.value.toFixed(2)}</span>
            </div>
          ))}
        </div>

        {/* Cost distribution bar */}
        <div>
          <div className="font-mono-label text-[9px] text-on-surface-variant/30 uppercase tracking-[0.12em] mb-2">Distribution</div>
          <div className="flex h-2 rounded-full overflow-hidden gap-px">
            {COST.map((c,i)=>(
              <div key={i} className="rounded-sm" style={{
                width:`${(c.value/total*100).toFixed(1)}%`,
                background: c.category==='Model'?'rgb(var(--c-primary))':c.category==='Tool'?'#79ff5b':'#3c494e',
                opacity: 0.6
              }} />
            ))}
          </div>
        </div>

        {/* Efficiency */}
        <div className="p-3 rounded-xl border border-secondary-fixed/10 bg-secondary-fixed/[0.02]">
          <div className="flex items-center justify-between mb-2">
            <span className="font-mono-label text-[10px] text-secondary-fixed/60 uppercase">Efficiency Score</span>
            <span className="font-mono-label text-[18px] font-bold text-secondary-fixed">9.2/10</span>
          </div>
          <MiniBar pct={92} color="#79ff5b" />
          <div className="font-mono-label text-[9px] text-on-surface-variant/25 mt-2">Cost per artifact: ~$4.91 · Well within budget</div>
        </div>
      </div>
    </div>
  );
}

// ─── Section 12: Security & Governance ───────────────────────────────────────

const APIS_SEED = [
  { name:'Anthropic API',  status:'active',  icon:'psychology',   lastUsed:'14:03:44' },
  { name:'OpenAI API',     status:'standby', icon:'smart_toy',    lastUsed:'13:52:11' },
  { name:'Google APIs',    status:'standby', icon:'auto_awesome', lastUsed:'13:41:28' },
  { name:'GitHub API',     status:'active',  icon:'code',         lastUsed:'14:02:58' },
];

function SecurityGovernance() {
  const [PROV] = usePolled<typeof PROV_SEED>(api.systemProviders, PROV_SEED, 8000);
  // Real provider access: each registry provider → active (key set) / open (breaker) / standby.
  const reg = PROV.registry ?? PROV.chain ?? [];
  const APIS = reg.length
    ? reg.slice(0, 6).map((p:any)=>({
        name: `${p.label} API`,
        status: p.breakerOpen ? 'open' : (p.available ? 'active' : 'standby'),
        icon: PROV_ICON[p.name] ?? 'smart_toy',
        lastUsed: p.model || p.name,
      }))
    : APIS_SEED;
  const AUDIT = [
    { t:'14:03:22', event:'Artifact materialization authorized',  level:'info'    },
    { t:'14:02:58', event:'GitHub API rate limit check passed',   level:'info'    },
    { t:'14:02:15', event:'Evidence ingestion policy validated',  level:'info'    },
    { t:'13:58:02', event:'PRD generation permissions granted',   level:'info'    },
    { t:'13:47:19', event:'Run RUN_0042 policy check complete',   level:'success' },
  ];

  return (
    <div className="rounded-xl border border-white/[0.055] bg-[#0A0C11]/85 overflow-hidden">
      <PanelHeader icon="shield" label="Security & Governance" iconColor="text-secondary-fixed"
        badge={<div className="flex items-center gap-2">
          <span className="flex h-1.5 w-1.5 rounded-full bg-secondary-fixed animate-pulse" />
          <span className="font-mono-label text-[10px] text-secondary-fixed/70 uppercase tracking-wider">All checks passed</span>
        </div>} />
      <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* API Keys */}
        <div>
          <div className="font-mono-label text-[9px] text-on-surface-variant/35 uppercase tracking-[0.15em] mb-2">Provider Access</div>
          <div className="space-y-1.5">
            {APIS.map(a=>(
              <div key={a.name} className="flex items-center gap-2.5 p-2.5 rounded-lg border border-white/[0.04] bg-white/[0.01]">
                <span className="material-symbols-outlined text-[14px] text-on-surface-variant/40">{a.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="font-mono-label text-[11px] text-on-surface/60">{a.name}</div>
                  <div className="font-mono-label text-[9px] text-on-surface-variant/25">{a.lastUsed}</div>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={`flex h-1.5 w-1.5 rounded-full ${a.status==='active'?'bg-secondary-fixed shadow-[0_0_5px_rgba(121,255,91,0.8)] animate-pulse':'bg-on-surface-variant/20'}`} />
                  <span className={`font-mono-label text-[9px] ${a.status==='active'?'text-secondary-fixed/70':'text-on-surface-variant/30'}`}>{a.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Compliance */}
        <div>
          <div className="font-mono-label text-[9px] text-on-surface-variant/35 uppercase tracking-[0.15em] mb-2">Compliance</div>
          <div className="space-y-1.5">
            {[
              { label:'Data Privacy Policy',   ok:true  },
              { label:'Rate Limit Compliance', ok:true  },
              { label:'Evidence Attribution',  ok:true  },
              { label:'Model Usage Terms',     ok:true  },
              { label:'Output Filtering',      ok:true  },
            ].map(c=>(
              <div key={c.label} className="flex items-center gap-2 p-2 rounded-lg border border-white/[0.03]">
                <span className={`material-symbols-outlined text-[14px] ${c.ok?'text-secondary-fixed':'text-[#f59e0b]'}`}>{c.ok?'check_circle':'warning'}</span>
                <span className="font-mono-label text-[10px] text-on-surface-variant/50">{c.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Audit Log */}
        <div>
          <div className="font-mono-label text-[9px] text-on-surface-variant/35 uppercase tracking-[0.15em] mb-2">Audit Log</div>
          <div className="space-y-1">
            {AUDIT.map((a,i)=>(
              <div key={i} className="flex gap-2 px-2 py-1.5 rounded-lg border border-white/[0.03] bg-white/[0.01]">
                <span className="font-mono-label text-[9px] text-on-surface-variant/25 flex-shrink-0 tabular-nums">{a.t}</span>
                <span className="font-mono-label text-[9px] text-on-surface-variant/45 leading-tight">{a.event}</span>
                <span className={`ml-auto flex-shrink-0 font-mono-label text-[8px] ${a.level==='success'?'text-secondary-fixed/60':'text-primary/40'}`}>
                  {a.level==='success'?'✓':'i'}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Agent Inspection Drawer ──────────────────────────────────────────────────

function AgentInspectionDrawer({ agentId, onClose }: { agentId:string|null; onClose:()=>void }) {
  const agent = SYS_AGENTS.find(a=>a.id===agentId);
  if (!agentId || !agent) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
      <div className="relative w-full max-w-sm bg-[#0A0C11] border-l border-white/[0.08] overflow-y-auto shadow-2xl"
        onClick={e=>e.stopPropagation()}
        style={{ animation:'slideInRight 0.3s cubic-bezier(0.16,1,0.3,1) forwards' }}>
        {/* Header */}
        <div className="sticky top-0 flex items-center gap-3 px-5 py-4 border-b border-white/[0.06] bg-[#0A0C11]/95 backdrop-blur-md z-10">
          <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/25 flex items-center justify-center flex-shrink-0">
            <span className="material-symbols-outlined text-primary text-[20px]">{agent.icon}</span>
          </div>
          <div className="flex-1">
            <div className="text-[15px] font-bold text-on-surface">{agent.name}</div>
            <div className="flex items-center gap-2 mt-0.5">
              <StatusDot status={agent.status} />
              <span className="font-mono-label text-[10px] text-on-surface-variant/40 capitalize">{agent.status}</span>
            </div>
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-lg bg-white/[0.04] border border-white/[0.07] flex items-center justify-center hover:border-primary/25 transition-colors">
            <span className="material-symbols-outlined text-[16px] text-on-surface-variant">close</span>
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Current job */}
          <div className="p-4 rounded-xl border border-primary/12 bg-primary/[0.025]">
            <div className="font-mono-label text-[9px] text-primary/50 uppercase tracking-[0.15em] mb-1">Current Objective</div>
            <div className="text-[13px] text-on-surface/80">{agent.currentJob}</div>
          </div>

          {/* Metrics grid */}
          <div className="grid grid-cols-2 gap-2">
            {[
              { label:'Memory',       value:`${agent.memPct}%`,        color:'rgb(var(--c-primary))' },
              { label:'Tasks Done',   value:`${agent.tasksCompleted}`,  color:'#79ff5b' },
              { label:'Success Rate', value:`${agent.successRate}%`,    color:'#79ff5b' },
              { label:'Confidence',   value:agent.confidence?`${agent.confidence}%`:'—', color:'rgb(var(--c-primary))' },
              { label:'Latency',      value:agent.latencyMs?`${agent.latencyMs}ms`:'—',  color:'rgb(var(--c-primary))' },
              { label:'Tokens Used',  value:`${(agent.tokensUsed/1000).toFixed(1)}K`,    color:'#f59e0b' },
            ].map(m=>(
              <div key={m.label} className="p-3 rounded-xl border border-white/[0.05] bg-white/[0.01]">
                <div className="font-mono-label text-[8px] text-on-surface-variant/30 uppercase mb-1">{m.label}</div>
                <div className="font-mono-label text-[16px] font-bold" style={{ color:m.color }}>{m.value}</div>
              </div>
            ))}
          </div>

          {/* Memory bar */}
          <div>
            <div className="flex justify-between mb-2">
              <span className="font-mono-label text-[9px] text-on-surface-variant/35 uppercase">Memory Usage</span>
              <span className="font-mono-label text-[9px] text-primary">{agent.memPct}%</span>
            </div>
            <div className="h-2 bg-white/[0.04] rounded-full overflow-hidden">
              <div className="h-full rounded-full bg-gradient-to-r from-primary/50 to-primary" style={{ width:`${agent.memPct}%`, boxShadow:'0 0 8px rgb(var(--c-primary) / 0.4)' }} />
            </div>
          </div>

          {/* Last execution */}
          <div>
            <div className="font-mono-label text-[9px] text-on-surface-variant/30 uppercase tracking-[0.15em] mb-2">Execution Log</div>
            <div className="space-y-1.5">
              {['Task initialized','Context loaded from memory','Tool calls dispatched','Evidence synthesized','Output committed'].slice(0, agent.tasksCompleted>0?5:0).map((step,i)=>(
                <div key={i} className="flex items-center gap-2 p-2 rounded-lg border border-white/[0.03]">
                  <span className="material-symbols-outlined text-secondary-fixed text-[12px]">check_circle</span>
                  <span className="font-mono-label text-[10px] text-on-surface-variant/50">{step}</span>
                </div>
              ))}
              {agent.tasksCompleted===0 && (
                <div className="text-center py-4 font-mono-label text-[11px] text-on-surface-variant/25">No tasks executed yet</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function SystemPage() {
  const [elapsed, setElapsed] = useState(863);
  const [inspecting, setInspecting] = useState<string|null>(null);

  useEffect(()=>{
    const iv=setInterval(()=>setElapsed(e=>e+1),1000);
    return ()=>clearInterval(iv);
  },[]);

  const PANEL = 'rounded-xl border border-white/[0.055] bg-[#0A0C11]/85 overflow-hidden flex flex-col';

  return (
    <div className="bg-background text-on-surface min-h-screen overflow-x-hidden select-none"
      style={{ fontFamily:'Inter,system-ui,sans-serif' }}>
      <style>{`
        @keyframes agentPulse { 0%,100%{opacity:1}50%{opacity:.65} }
        @keyframes borderSweep { 0%{background-position:-200% 0}100%{background-position:200% 0} }
        @keyframes thinkDot { 0%,80%,100%{transform:scale(1);opacity:.35}40%{transform:scale(1.7);opacity:1} }
        @keyframes fadeInUp { from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)} }
        @keyframes streamIn { from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:translateX(0)} }
        @keyframes nodePing { 0%{transform:scale(1);opacity:.5}100%{transform:scale(1.8);opacity:0} }
        @keyframes slideInRight { from{transform:translateX(100%)}to{transform:translateX(0)} }
        .scrollbar-thin::-webkit-scrollbar{width:3px}
        .scrollbar-thin::-webkit-scrollbar-track{background:transparent}
        .scrollbar-thin::-webkit-scrollbar-thumb{background:rgb(var(--c-primary) / 0.07);border-radius:2px}
      `}</style>

      <Nav />

      <main className="pt-16">
        {/* Section 1: Global Health */}
        <SystemHealthBar elapsed={elapsed} />

        <div className="max-w-[1600px] mx-auto px-container-margin py-4 space-y-4 pb-10">

          {/* Billing — additive Dodo Payments subscription card (small, matches APS panels) */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <BillingCard />
          </div>

          {/* Row 1: Agent Fleet + Model Orchestration */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4" style={{ minHeight:480 }}>
            <div className={`lg:col-span-3 ${PANEL}`}><AgentFleet onInspect={setInspecting} /></div>
            <div className={`lg:col-span-2 ${PANEL}`}><ModelOrchestration /></div>
          </div>

          {/* Row 2: Tool Ecosystem + Memory Engine */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4" style={{ minHeight:360 }}>
            <div className={`lg:col-span-3 ${PANEL}`}><ToolEcosystem /></div>
            <div className={`lg:col-span-2 ${PANEL}`}><MemoryEngine /></div>
          </div>

          {/* Row 3: Knowledge Graph + Observability */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4" style={{ minHeight:440 }}>
            <div className={`lg:col-span-2 ${PANEL}`}><KnowledgeGraph /></div>
            <div className={`lg:col-span-3 ${PANEL}`}><ObservabilityCenter /></div>
          </div>

          {/* Row 4: Event Stream + Quality Evaluation */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4" style={{ minHeight:420 }}>
            <div className={`lg:col-span-2 ${PANEL}`}><EventStream /></div>
            <div className={`lg:col-span-3 ${PANEL}`}><QualityEvaluation /></div>
          </div>

          {/* Row 5: Infrastructure Map + Cost Center */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4" style={{ minHeight:340 }}>
            <div className={`lg:col-span-3 ${PANEL}`}><InfrastructureMap /></div>
            <div className={`lg:col-span-2 ${PANEL}`}><CostCenter elapsed={elapsed} /></div>
          </div>

          {/* Row 6: Security & Governance (full width) */}
          <SecurityGovernance />

        </div>
      </main>

      {/* Agent Inspection Drawer */}
      {inspecting && <AgentInspectionDrawer agentId={inspecting} onClose={()=>setInspecting(null)} />}
    </div>
  );
}
