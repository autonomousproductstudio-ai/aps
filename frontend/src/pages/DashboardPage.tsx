import { useState, useEffect, useRef } from 'react';
import { NotificationBell } from '../components/NotificationBell';
import { Link } from 'react-router-dom';
import { SettingsMenu } from '../components/SettingsMenu';
import { api } from '../lib/api';
import { useRunResource, getActiveRun, useRunSocket } from '../lib/useBackend';
import { exportArtifactPDF } from '../lib/pdfExport';

// ─── Data ─────────────────────────────────────────────────────────────────────
// The *_SEED constants are the page's original hardcoded mock. Each animated zone shadows
// them at runtime with live /v1 data via useRunResource, falling back to the seed when the
// backend is unreachable — so the design + animations always render.

const AGENTS_SEED = [
  { id:'research',  name:'Research Agent',     icon:'travel_explore', status:'running',  confidence:94,
    tools:['web_search','github_api','reddit_api'],
    toolLog:['GitHub · 34 repos analyzed','Reddit · 847 posts scraped','Evidence cluster #3 forming…'],
    output:'Synthesizing evidence clusters' },
  { id:'product',   name:'Product Agent',       icon:'architecture',   status:'queued',   confidence:0,
    tools:['prd_writer','user_story_gen'], toolLog:[], output:'Awaiting Research output' },
  { id:'arch',      name:'Architecture Agent',  icon:'hub',            status:'queued',   confidence:0,
    tools:['diagram_gen','openapi_spec','c4_model'], toolLog:[], output:'Standby' },
  { id:'execution', name:'Execution Agent',     icon:'data_object',    status:'queued',   confidence:0,
    tools:['code_gen','test_runner','ci_builder'], toolLog:[], output:'Standby' },
  { id:'present',   name:'Presentation Agent',  icon:'smart_display',  status:'idle',     confidence:0,
    tools:['deck_builder','memo_writer','pitch_scorer'], toolLog:[], output:'Idle' },
];

const STREAM_SEED = [
  { t:'14:02:01', agent:'Research', icon:'travel_explore', type:'start',    msg:'Agent spawned — initializing evidence workspace',           color:'cyan'  },
  { t:'14:02:04', agent:'Research', icon:'search',         type:'tool',     msg:'GitHub Search · "resume screening AI" · 34 repos found',    color:'cyan'  },
  { t:'14:02:09', agent:'Research', icon:'hub',            type:'evidence', msg:'34 repositories analyzed · 8 high-signal sources',          color:'green' },
  { t:'14:02:15', agent:'Research', icon:'forum',          type:'tool',     msg:'Reddit scrape · r/recruiting + r/MachineLearning active',   color:'cyan'  },
  { t:'14:02:23', agent:'Research', icon:'star',           type:'evidence', msg:'Pain Point Cluster #1 · "ATS false-negative bias" formed',   color:'green' },
  { t:'14:02:31', agent:'Research', icon:'newspaper',      type:'tool',     msg:'Hacker News · "Ask HN: why is recruiting broken?"',         color:'cyan'  },
  { t:'14:02:44', agent:'Research', icon:'lightbulb',      type:'insight',  msg:'Market gap confirmed: no AI-native ATS for SMBs',            color:'amber' },
  { t:'14:02:58', agent:'Research', icon:'library_books',  type:'tool',     msg:'3 research papers · NLP hiring bias + CV parsing',          color:'cyan'  },
  { t:'14:03:10', agent:'Research', icon:'verified',       type:'evidence', msg:'Pain Point Cluster #2 · "bias in keyword filtering"',        color:'green' },
  { t:'14:03:22', agent:'Research', icon:'trending_up',    type:'insight',  msg:'TAM: $8.4B · SAM: $1.2B · SOM: $120M — validated',         color:'amber' },
];

const MORE_STREAM = [
  { t:'14:03:38', agent:'Research', icon:'psychology',   type:'insight',  msg:'Hypothesis validated: SMB ATS market underserved by AI',         color:'amber' },
  { t:'14:03:51', agent:'Research', icon:'search',       type:'tool',     msg:'Product Hunt · "AI hiring" · 12 competing products catalogued',  color:'cyan'  },
  { t:'14:04:05', agent:'Research', icon:'stars',        type:'evidence', msg:'Pain Point Cluster #3 · "manual screening >5h/week"',             color:'green' },
  { t:'14:04:18', agent:'Research', icon:'analytics',    type:'insight',  msg:'Gap confirmed: no product scores CVs against JD semantics',       color:'amber' },
  { t:'14:04:35', agent:'Research', icon:'check_circle', type:'evidence', msg:'Research Brief finalized · 47 evidence nodes · 94% confidence',   color:'green' },
];

const ARTIFACTS_SEED = [
  { name:'Research Brief',   icon:'travel_explore', status:'complete', size:'42 KB',  time:'3m 12s', confidence:94, evidence:47, color:'green' },
  { name:'Market Analysis',  icon:'bar_chart',      status:'complete', size:'18 KB',  time:'1m 40s', confidence:91, evidence:23, color:'green' },
  { name:'PRD v1.0',         icon:'description',    status:'building', size:'—',      time:'—',      confidence:0,  evidence:0,  color:'cyan'  },
  { name:'Technical Design', icon:'hub',            status:'queued',   size:'—',      time:'—',      confidence:0,  evidence:0,  color:'muted' },
  { name:'OpenAPI Spec',     icon:'code',           status:'queued',   size:'—',      time:'—',      confidence:0,  evidence:0,  color:'muted' },
  { name:'Roadmap Q1',       icon:'route',          status:'queued',   size:'—',      time:'—',      confidence:0,  evidence:0,  color:'muted' },
  { name:'Investor Memo',    icon:'attach_money',   status:'queued',   size:'—',      time:'—',      confidence:0,  evidence:0,  color:'muted' },
  { name:'Pitch Deck',       icon:'smart_display',  status:'queued',   size:'—',      time:'—',      confidence:0,  evidence:0,  color:'muted' },
];

const RADAR_AXES_SEED = [
  { label:'Market Opp.',   value:88, angle:270 },
  { label:'Competition',   value:62, angle:342 },
  { label:'Monetisation',  value:75, angle:54  },
  { label:'Defensibility', value:71, angle:126 },
  { label:'Exec. Speed',   value:82, angle:198 },
];

const SCENARIOS_SEED = [
  { label:'Best Case',  values:[95,75,85,82,90], color:'#79ff5b', opacity:0.14 },
  { label:'Expected',   values:[88,62,75,71,82], color:'rgb(var(--c-primary))', opacity:0.22 },
  { label:'Worst Case', values:[60,40,50,45,55], color:'#f59e0b', opacity:0.11 },
];

const DEBATE_SEED = [
  { side:'Build',       agent:'Research Agent', point:'$8.4B TAM with proven pain — ATS false-negatives cost $50K/hire'  },
  { side:'Build',       agent:'Product Agent',  point:'No AI-native SMB solution; incumbents bloated & expensive'         },
  { side:"Don't Build", agent:'Risk Agent',     point:'Workday & Greenhouse ship AI features Q3 — 6-month window only'    },
  { side:"Don't Build", agent:'Risk Agent',     point:'Cold-start: need labelled CV corpus before training begins'         },
  { side:'Build',       agent:'Research Agent', point:'OSS models (Mistral) eliminate the training-data moat entirely'     },
];

const TIMELINE_PHASES = [
  { label:'Research',     icon:'travel_explore', start:0,  end:30  },
  { label:'Product',      icon:'architecture',   start:30, end:50  },
  { label:'Architecture', icon:'hub',            start:50, end:70  },
  { label:'Execution',    icon:'data_object',    start:70, end:90  },
  { label:'Presentation', icon:'smart_display',  start:90, end:100 },
];

// Evidence hub graph
const EV_NODES_SEED = [
  { id:'github',   label:'GitHub',          x:200, y:55,  type:'source', count:34 },
  { id:'reddit',   label:'Reddit',          x:75,  y:130, type:'source', count:12 },
  { id:'hn',       label:'HN',             x:325, y:130, type:'source', count:8  },
  { id:'ph',       label:'Prod Hunt',      x:75,  y:240, type:'source', count:12 },
  { id:'papers',   label:'Papers',         x:325, y:240, type:'source', count:3  },
  { id:'pain1',    label:'ATS False Neg.', x:200, y:148, type:'pain',   count:0  },
  { id:'pain2',    label:'Keyword Bias',   x:130, y:210, type:'pain',   count:0  },
  { id:'pain3',    label:'5h+ Manual',     x:270, y:210, type:'pain',   count:0  },
  { id:'req1',     label:'Semantic Score', x:200, y:275, type:'req',    count:0  },
  { id:'arch1',    label:'LLM Scoring',   x:145, y:330, type:'arch',   count:0  },
  { id:'road1',    label:'MVP Sprint 1',  x:255, y:330, type:'roadmap',count:0  },
];

const EV_EDGES_SEED = [
  ['github','pain1'],['reddit','pain2'],['hn','pain1'],['ph','pain3'],['papers','pain1'],
  ['pain1','req1'],['pain2','req1'],['pain3','req1'],
  ['req1','arch1'],['req1','road1'],
];

// DNA graph
const DNA_NODES_SEED = [
  { id:'core',     label:'AI SaaS',      x:200, y:170, r:28, core:true  },
  { id:'market',   label:'Market',       x:200, y:60,  r:19, core:false },
  { id:'users',    label:'Users',        x:315, y:115, r:17, core:false },
  { id:'compete',  label:'Competitors', x:315, y:225, r:17, core:false },
  { id:'mono',     label:'Revenue',     x:200, y:282, r:17, core:false },
  { id:'arch',     label:'Architecture',x:85,  y:225, r:17, core:false },
  { id:'features', label:'Features',    x:85,  y:115, r:17, core:false },
];

const DNA_EDGES_SEED = [
  { a:'core', b:'market'   },
  { a:'core', b:'users'    },
  { a:'core', b:'compete'  },
  { a:'core', b:'mono'     },
  { a:'core', b:'arch'     },
  { a:'core', b:'features' },
  { a:'market', b:'users'  },
  { a:'users',  b:'features'},
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function radarPts(axes:{label:string;value:number;angle:number}[], values:number[]|null, cx:number, cy:number, r:number) {
  return axes.map((a, i) => {
    const v   = values ? values[i] : a.value;
    const rad = (a.angle - 90) * Math.PI / 180;
    return { x: cx + (v/100)*r * Math.cos(rad), y: cy + (v/100)*r * Math.sin(rad) };
  });
}
function polyStr(pts:{x:number;y:number}[]) { return pts.map(p=>`${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' '); }

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
          <Link to="/dashboard" className="relative flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-primary bg-primary/10 border border-primary/25 shadow-[0_0_14px_rgba(71,214,255,0.12)]">
            <span className="w-1.5 h-1.5 rounded-full bg-primary shadow-[0_0_5px_rgba(71,214,255,0.9)] animate-pulse" />
            Dashboard
          </Link>
          <Link to="/artifacts" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">Artifacts</Link>
          <Link to="/system" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">System</Link>
          <Link to="/pricing" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">Pricing</Link>
          <Link to="/history" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">History</Link>
        </div>
      </div>

      <div className="relative flex items-center gap-1.5">
        <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.07] text-on-surface-variant text-[11px] font-mono-label mr-2 cursor-pointer hover:border-primary/30 transition-colors">
          <span className="material-symbols-outlined text-[15px]">search</span>
          <span className="opacity-50">Search runs, artifacts…</span>
          <span className="ml-4 text-[10px] opacity-30 border border-white/10 rounded px-1">⌘K</span>
        </div>
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

// ─── Zone 1: Command Center Header ────────────────────────────────────────────

function CommandHeader({ elapsed }: { elapsed: number }) {
  const [run] = useRunResource(api.run, {
    id: 'RUN_0042', label: 'AI SaaS Resume Screening', phase: 'Research Phase',
    progressPct: 63, viabilityScore: 8.7,
  } as any);
  const mm = String(Math.floor(elapsed / 60)).padStart(2,'0');
  const ss = String(elapsed % 60).padStart(2,'0');
  const PCT = Math.round((run as any).progressPct ?? 63);
  const R = 26, SZ = 60, circ = 2 * Math.PI * R;
  const dash = circ * (1 - PCT / 100);

  return (
    <div className="relative border-b border-white/[0.06] overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-[#0A0C12] to-[#0D1016]" />
      {/* Ambient radial */}
      <div className="absolute inset-0 pointer-events-none"
        style={{ background:'radial-gradient(ellipse at 20% 50%, rgb(var(--c-primary) / 0.04) 0%, transparent 55%)' }} />
      {/* Scan line */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent pointer-events-none"
        style={{ animation:'headerScan 6s ease-in-out infinite' }} />

      <div className="relative max-w-[1600px] mx-auto px-container-margin py-5 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-x-6 gap-y-4 items-center">

        {/* Run identity */}
        <div className="col-span-2 lg:col-span-2 flex flex-col">
          <div className="flex items-center gap-2 mb-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-secondary-fixed opacity-50" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-secondary-fixed shadow-[0_0_8px_rgba(121,255,91,0.9)]" />
            </span>
            <span className="font-mono-label text-[10px] text-secondary-fixed tracking-[0.22em] uppercase">Live Autonomous Run</span>
          </div>
          <div className="font-mono-label text-[21px] text-on-surface font-bold tracking-tight leading-tight">{(run as any).label}</div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2">
            <span className="font-mono-label text-[11px] text-primary/70">{(run as any).id}</span>
            <span className="text-white/10">·</span>
            <span className="font-mono-label text-[11px] text-on-surface-variant/50">{mm}:{ss} elapsed</span>
            <span className="text-white/10">·</span>
            <span className="font-mono-label text-[10px] text-on-surface-variant/30 uppercase tracking-wide">{(run as any).phase}</span>
          </div>
        </div>

        {/* Completion ring */}
        <div className="flex items-center gap-3">
          <div className="relative flex-shrink-0">
            <svg width={SZ} height={SZ} viewBox={`0 0 ${SZ} ${SZ}`}>
              <circle cx={SZ/2} cy={SZ/2} r={R} fill="none" stroke="rgb(var(--c-overlay) / 0.05)" strokeWidth="3" />
              <circle cx={SZ/2} cy={SZ/2} r={R} fill="none" stroke="#a5e7ff" strokeWidth="3"
                strokeDasharray={`${circ}`} strokeDashoffset={`${dash}`} strokeLinecap="round"
                transform={`rotate(-90 ${SZ/2} ${SZ/2})`}
                style={{ filter:'drop-shadow(0 0 6px rgb(var(--c-primary) / 0.55))', transition:'stroke-dashoffset 1.2s ease' }} />
              <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle"
                fill="#a5e7ff" fontSize="12" fontWeight="700" fontFamily="JetBrains Mono, monospace">{PCT}%</text>
            </svg>
          </div>
          <div>
            <div className="font-mono-label text-[10px] text-on-surface-variant/40 uppercase tracking-[0.15em] mb-1">Progress</div>
            <div className="text-[13px] font-semibold text-on-surface leading-snug">Research<br/>Complete</div>
          </div>
        </div>

        {/* Active agent */}
        <div className="flex flex-col">
          <span className="font-mono-label text-[10px] text-on-surface-variant/40 uppercase tracking-[0.15em] mb-2">Active Agent</span>
          <div className="flex items-center gap-2.5">
            <div className="relative flex-shrink-0">
              <div className="absolute inset-0 rounded-xl bg-primary/20 blur-md" style={{ animation:'agentPulse 2.5s ease-in-out infinite' }} />
              <div className="relative w-9 h-9 rounded-xl bg-primary/10 border border-primary/30 flex items-center justify-center shadow-[0_0_14px_rgb(var(--c-primary) / 0.15)]">
                <span className="material-symbols-outlined text-primary text-[17px]">travel_explore</span>
              </div>
            </div>
            <div>
              <div className="text-[13px] text-on-surface font-semibold leading-tight">Research Agent</div>
              <div className="flex items-center gap-1 mt-1">
                {[0,1,2].map(i=>(
                  <div key={i} className="w-1 h-1 rounded-full bg-primary/70"
                    style={{ animation:`thinkDot 1.4s ease-in-out ${i*0.2}s infinite` }} />
                ))}
                <span className="font-mono-label text-[9px] text-primary/40 ml-1">Reasoning</span>
              </div>
            </div>
          </div>
        </div>

        {/* System health */}
        <div className="flex flex-col">
          <span className="font-mono-label text-[10px] text-on-surface-variant/40 uppercase tracking-[0.15em] mb-2.5">System Health</span>
          <div className="space-y-2">
            {([['CPU','24%',24],['MEM','61%',61],['API','99.9%',99]] as [string,string,number][]).map(([k,v,pct])=>(
              <div key={k} className="flex items-center gap-2">
                <span className="font-mono-label text-[9px] text-on-surface-variant/40 w-7">{k}</span>
                <div className="flex-1 h-px bg-white/[0.05] rounded-full overflow-hidden">
                  <div className="h-full rounded-full" style={{
                    width:`${pct}%`,
                    background: pct > 80 ? '#79ff5b' : 'rgb(var(--c-primary))',
                    boxShadow: pct > 80 ? '0 0 4px rgba(121,255,91,0.5)' : '0 0 4px rgb(var(--c-primary) / 0.4)',
                    transition:'width 1s ease'
                  }} />
                </div>
                <span className="font-mono-label text-[9px] text-secondary-fixed w-10 text-right">{v}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Viability score */}
        <div className="flex flex-col">
          <span className="font-mono-label text-[10px] text-on-surface-variant/40 uppercase tracking-[0.15em] mb-1.5">Startup Viability</span>
          <div className="flex items-end gap-1 mb-2" style={{ lineHeight:1 }}>
            <span className="text-[44px] font-bold text-primary"
              style={{ textShadow:'0 0 40px rgb(var(--c-primary) / 0.55)', lineHeight:1 }}>{(run as any).viabilityScore}</span>
            <span className="text-[14px] text-on-surface-variant mb-0.5">/10</span>
          </div>
          <div className="flex gap-0.5 mb-1">
            {Array.from({length:10}).map((_,i)=>(
              <div key={i} className="flex-1 h-1 rounded-sm"
                style={i<9 ? { background:'rgb(var(--c-primary))', opacity:0.55, boxShadow:'0 0 3px rgb(var(--c-primary) / 0.4)' } : { background:'rgb(var(--c-overlay) / 0.05)' }} />
            ))}
          </div>
          <span className="font-mono-label text-[9px] text-primary/50 uppercase tracking-[0.12em]">High Viability</span>
        </div>

      </div>
    </div>
  );
}

// ─── Zone 2: Agent Fleet ───────────────────────────────────────────────────────

function AgentFleet() {
  const [AGENTS] = useRunResource(api.runAgents, AGENTS_SEED);
  const [toolIdx, setToolIdx] = useState(0);
  useEffect(()=>{
    const iv = setInterval(()=>setToolIdx(i=>i+1), 2600);
    return ()=>clearInterval(iv);
  },[]);

  return (
    <div className="border-b border-white/[0.04]">
      <div className="max-w-[1600px] mx-auto px-container-margin py-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="font-mono-label text-[11px] text-on-surface-variant/40 uppercase tracking-[0.2em]">Autonomous Agent Fleet</span>
            <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-secondary-fixed/[0.07] border border-secondary-fixed/20">
              <span className="flex h-1.5 w-1.5 rounded-full bg-secondary-fixed shadow-[0_0_5px_rgba(121,255,91,0.8)] animate-pulse" />
              <span className="font-mono-label text-[9px] text-secondary-fixed uppercase tracking-[0.12em]">1 Active · 3 Queued · 1 Idle</span>
            </div>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {AGENTS.map((agent, i)=>(
            <AgentCard key={agent.id} agent={agent} toolIdx={toolIdx} delay={i*0.07} />
          ))}
        </div>
      </div>
    </div>
  );
}

function AgentCard({ agent, toolIdx, delay }: { agent:typeof AGENTS_SEED[0]; toolIdx:number; delay:number }) {
  const isRunning = agent.status === 'running';
  const isQueued  = agent.status === 'queued';
  const currentTool = agent.toolLog.length ? agent.toolLog[toolIdx % agent.toolLog.length] : '';

  return (
    <div className={`relative rounded-xl border overflow-hidden group cursor-pointer transition-all duration-500
      ${isRunning  ? 'bg-primary/[0.035] border-primary/20 shadow-[0_0_28px_rgb(var(--c-primary) / 0.06)]'
      : isQueued   ? 'bg-white/[0.015] border-white/[0.06] hover:border-primary/10 hover:bg-white/[0.025]'
      :              'bg-white/[0.01] border-white/[0.035]'}`}
      style={{ animationDelay:`${delay}s` }}>

      {isRunning && (
        <>
          {/* Pulse overlay */}
          <div className="absolute inset-0 pointer-events-none"
            style={{ animation:'agentPulse 3s ease-in-out infinite', background:'radial-gradient(ellipse at 50% 0%, rgb(var(--c-primary) / 0.08) 0%, transparent 60%)' }} />
          {/* Animated top border sweep */}
          <div className="absolute top-0 left-0 right-0 h-px pointer-events-none"
            style={{ background:'linear-gradient(90deg,transparent,#a5e7ff,transparent)', backgroundSize:'200% 100%', animation:'borderSweep 2.4s linear infinite' }} />
        </>
      )}

      <div className="relative p-4">
        <div className="flex items-start justify-between mb-3">
          <div className={`relative w-10 h-10 rounded-xl flex items-center justify-center border flex-shrink-0
            ${isRunning ? 'bg-primary/10 border-primary/30' : isQueued ? 'bg-white/[0.03] border-white/[0.07]' : 'bg-white/[0.015] border-white/[0.04]'}`}>
            {isRunning && <div className="absolute inset-0 rounded-xl bg-primary/15 blur-sm" style={{ animation:'agentPulse 2.5s ease-in-out infinite' }} />}
            <span className={`material-symbols-outlined text-[20px] relative ${isRunning ? 'text-primary' : isQueued ? 'text-on-surface-variant/30' : 'text-on-surface-variant/15'}`}>
              {agent.icon}
            </span>
          </div>
          <StatusBadge status={agent.status} />
        </div>

        <div className={`text-[13px] font-semibold leading-tight mb-1.5
          ${isRunning ? 'text-on-surface' : isQueued ? 'text-on-surface/55' : 'text-on-surface/25'}`}>
          {agent.name}
        </div>

        {isRunning && currentTool ? (
          <div className="mb-2 h-4 overflow-hidden">
            <div className="font-mono-label text-[10px] text-primary/55 truncate leading-tight"
              style={{ animation:'fadeInUp 0.35s ease-out' }} key={toolIdx}>
              ↳ {currentTool}
            </div>
          </div>
        ) : (
          <div className={`font-mono-label text-[11px] leading-snug mb-2
            ${isQueued ? 'text-on-surface-variant/28' : 'text-on-surface-variant/18'}`}>
            {agent.output}
          </div>
        )}

        {isRunning && (
          <>
            <div className="mt-2 mb-3">
              <div className="flex justify-between mb-1.5">
                <span className="font-mono-label text-[9px] text-on-surface-variant/35 uppercase tracking-[0.12em]">Confidence</span>
                <span className="font-mono-label text-[9px] text-primary font-bold">{agent.confidence}%</span>
              </div>
              <div className="h-px bg-white/[0.05] rounded-full overflow-hidden">
                <div className="h-full rounded-full" style={{
                  width:`${agent.confidence}%`,
                  background:'linear-gradient(90deg, rgb(var(--c-primary) / 0.45), #a5e7ff)',
                  boxShadow:'0 0 8px rgb(var(--c-primary) / 0.5)',
                  transition:'width 1s ease'
                }} />
              </div>
            </div>
            <div className="flex flex-wrap gap-1 mb-3">
              {agent.tools.map(t=>(
                <span key={t} className="px-1.5 py-0.5 rounded bg-primary/[0.07] border border-primary/10 font-mono-label text-[8px] text-primary/50">{t}</span>
              ))}
            </div>
            <div className="flex items-center gap-1.5">
              {[0,1,2].map(i=>(
                <div key={i} className="w-1 h-1 rounded-full bg-primary/60"
                  style={{ animation:`thinkDot 1.4s ease-in-out ${i*0.2}s infinite` }} />
              ))}
              <span className="font-mono-label text-[9px] text-primary/38">Reasoning…</span>
            </div>
          </>
        )}

        {isQueued && (
          <div className="mt-2 h-px bg-white/[0.04] rounded-full overflow-hidden">
            <div className="h-full w-1/4 rounded-full bg-white/[0.08]"
              style={{ animation:'queueSlide 2.2s ease-in-out infinite' }} />
          </div>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status:string }) {
  const cfg: Record<string,{label:string;cls:string}> = {
    running:   { label:'Running',  cls:'bg-secondary-fixed text-[#001a00] shadow-[0_0_8px_rgba(121,255,91,0.6)]' },
    queued:    { label:'Queued',   cls:'bg-white/[0.06] text-on-surface-variant/40' },
    idle:      { label:'Idle',     cls:'bg-white/[0.03] text-on-surface-variant/22' },
    completed: { label:'Done',     cls:'bg-primary/15 text-primary' },
    failed:    { label:'Failed',   cls:'bg-red-500/15 text-red-400' },
  };
  const s = cfg[status] ?? cfg.idle;
  return (
    <span className={`px-2 py-0.5 rounded-full font-mono-label text-[8px] font-bold uppercase tracking-[0.1em] flex-shrink-0 ${s.cls}`}>{s.label}</span>
  );
}

// ─── Zone 3: Live Execution Stream ────────────────────────────────────────────

function ExecutionStream() {
  const runId = getActiveRun();
  const [logs, setLogs] = useState<any[]>(STREAM_SEED);
  const [live, setLive] = useState(false);
  const [filter, setFilter] = useState('all');
  const scrollRef = useRef<HTMLDivElement>(null);

  // Seed from the run's event history, then append live events over the websocket.
  useEffect(()=>{
    if (!runId) return;
    let alive = true;
    api.runStream(runId).then(seed=>{
      if (alive && seed && seed.length) { setLogs(seed); setLive(true); }
    }).catch(()=>{});
    return ()=>{ alive = false; };
  },[runId]);
  useRunSocket(runId, { onEvent:(e)=> { setLive(true); setLogs(prev=>[...prev, e]); } });

  useEffect(()=>{
    if (live) return;                 // demo animation runs only until real events arrive
    let i = 0;
    const iv = setInterval(()=>{
      if (i < MORE_STREAM.length) setLogs(prev=>[...prev, MORE_STREAM[i++]]);
    }, 3400);
    return ()=>clearInterval(iv);
  },[live]);

  useEffect(()=>{
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  },[logs]);

  function typeStyle(c:string) {
    if (c==='green') return { dot:'bg-secondary-fixed', glow:'rgba(121,255,91,0.8)', line:'text-secondary-fixed', border:'border-secondary-fixed/15', bg:'bg-secondary-fixed/[0.03]' };
    if (c==='amber') return { dot:'bg-[#f59e0b]',       glow:'rgba(245,158,11,0.7)', line:'text-[#f59e0b]',       border:'border-[#f59e0b]/15',         bg:'bg-[#f59e0b]/[0.03]' };
    return { dot:'bg-primary', glow:'rgb(var(--c-primary) / 0.7)', line:'text-primary', border:'border-primary/12', bg:'bg-primary/[0.02]' };
  }

  const displayed = filter==='all' ? logs : logs.filter(l=>l.type===filter);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.05] flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary text-[15px]">terminal</span>
          <span className="font-mono-label text-[11px] text-on-surface uppercase tracking-[0.15em]">Execution Stream</span>
          <span className="flex h-1.5 w-1.5 rounded-full bg-secondary-fixed shadow-[0_0_6px_rgba(121,255,91,0.9)] animate-pulse ml-0.5" />
          <span className="font-mono-label text-[9px] text-secondary-fixed/60 ml-0.5">{logs.length} events</span>
        </div>
        <div className="flex items-center gap-0.5">
          {(['all','tool','evidence','insight'] as const).map(f=>(
            <button key={f} onClick={()=>setFilter(f)}
              className={`px-2 py-0.5 rounded font-mono-label text-[9px] uppercase tracking-[0.08em] transition-all
                ${filter===f ? 'bg-primary/12 text-primary border border-primary/22' : 'text-on-surface-variant/35 hover:text-on-surface-variant/60'}`}>
              {f}
            </button>
          ))}
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-1 scrollbar-thin"
        style={{ maskImage:'linear-gradient(to bottom, transparent, black 5%, black 93%, transparent)' }}>
        {displayed.map((log, i)=>{
          const s = typeStyle(log.color);
          return (
            <div key={i}
              className={`flex items-start gap-2.5 px-2.5 py-2 rounded-lg border ${s.border} ${s.bg} hover:bg-white/[0.02] transition-colors group`}
              style={i>=STREAM_SEED.length ? { animation:'streamIn 0.4s cubic-bezier(0.16,1,0.3,1) forwards' } : {}}>
              <span className="font-mono-label text-[10px] text-on-surface-variant/28 mt-0.5 w-14 flex-shrink-0 tabular-nums">{log.t}</span>
              <span className="flex h-1.5 w-1.5 rounded-full mt-1.5 flex-shrink-0"
                style={{ background: s.dot==='bg-primary' ? 'rgb(var(--c-primary))' : s.dot==='bg-secondary-fixed' ? '#79ff5b' : '#f59e0b', boxShadow:`0 0 6px ${s.glow}` }} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className={`material-symbols-outlined text-[12px] ${s.line}`}>{log.icon}</span>
                  <span className={`font-mono-label text-[9px] uppercase tracking-[0.08em] ${s.line} opacity-65`}>{log.agent} · {log.type}</span>
                </div>
                <div className="font-mono-log text-[12px] text-on-surface/75 leading-snug">{log.msg}</div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="px-4 py-2 border-t border-white/[0.04] flex items-center justify-between flex-shrink-0">
        <span className="font-mono-label text-[10px] text-on-surface-variant/25">Auto-scroll · Live</span>
        <button className="font-mono-label text-[10px] text-on-surface-variant/35 hover:text-primary transition-colors flex items-center gap-1">
          <span className="material-symbols-outlined text-[12px]">replay</span> Replay
        </button>
      </div>
    </div>
  );
}

// ─── Zone 4: Evidence Intelligence Hub ───────────────────────────────────────

function EvidenceHub() {
  const [evg] = useRunResource(api.evidenceGraph, { nodes: EV_NODES_SEED, edges: EV_EDGES_SEED });
  const EV_NODES = (evg as any).nodes as typeof EV_NODES_SEED;
  const EV_EDGES = (evg as any).edges as typeof EV_EDGES_SEED;
  const [hovered, setHovered] = useState<string|null>(null);

  function nodeStyle(type:string) {
    switch(type) {
      case 'source':  return { fill:'rgb(var(--c-primary) / 0.08)', stroke:'rgb(var(--c-primary) / 0.35)', color:'rgb(var(--c-primary))', r:20 };
      case 'pain':    return { fill:'rgba(245,158,11,0.08)',   stroke:'rgba(245,158,11,0.35)',   color:'#f59e0b', r:18 };
      case 'req':     return { fill:'rgba(121,255,91,0.08)',   stroke:'rgba(121,255,91,0.35)',   color:'#79ff5b', r:17 };
      case 'arch':    return { fill:'rgb(var(--c-primary) / 0.05)', stroke:'rgb(var(--c-primary) / 0.2)',  color:'rgb(var(--c-primary))', r:15 };
      case 'roadmap': return { fill:'rgb(var(--c-primary) / 0.04)', stroke:'rgb(var(--c-primary) / 0.15)', color:'#bbc9cf', r:15 };
      default:        return { fill:'rgb(var(--c-overlay) / 0.05)', stroke:'rgb(var(--c-overlay) / 0.15)', color:'#bbc9cf', r:16 };
    }
  }

  const hotEdges = new Set<string>();
  if (hovered) {
    EV_EDGES.forEach(([a,b])=>{ if(a===hovered||b===hovered) hotEdges.add(`${a}-${b}`); });
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.05] flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-[#f59e0b] text-[15px]">device_hub</span>
          <span className="font-mono-label text-[11px] text-on-surface uppercase tracking-[0.15em]">Evidence Intelligence</span>
        </div>
        <div className="flex items-center gap-3">
          {([['source','rgb(var(--c-primary))'],['pain','#f59e0b'],['req','#79ff5b']] as [string,string][]).map(([t,c])=>(
            <div key={t} className="flex items-center gap-1">
              <div className="w-1.5 h-1.5 rounded-full" style={{ background:c }} />
              <span className="font-mono-label text-[9px] text-on-surface-variant/35 uppercase">{t}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="flex-1 relative overflow-hidden">
        <svg viewBox="0 0 400 380" className="w-full h-full" preserveAspectRatio="xMidYMid meet">
          <defs>
            <radialGradient id="evHubGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#a5e7ff" stopOpacity="0.05"/>
              <stop offset="100%" stopColor="#a5e7ff" stopOpacity="0"/>
            </radialGradient>
            {EV_EDGES.map(([a,b])=>{
              const na = EV_NODES.find(n=>n.id===a)!;
              const nb = EV_NODES.find(n=>n.id===b)!;
              return (
                <path key={`path-${a}-${b}`} id={`evpath-${a}-${b}`}
                  d={`M${na.x},${na.y} L${nb.x},${nb.y}`} fill="none" />
              );
            })}
          </defs>
          <rect width="400" height="380" fill="url(#evHubGlow)" />

          {/* Edges */}
          {EV_EDGES.map(([a,b])=>{
            const na = EV_NODES.find(n=>n.id===a)!;
            const nb = EV_NODES.find(n=>n.id===b)!;
            const key = `${a}-${b}`;
            const hot = hotEdges.has(key);
            const len = Math.hypot(nb.x-na.x, nb.y-na.y);
            return (
              <g key={key}>
                <line x1={na.x} y1={na.y} x2={nb.x} y2={nb.y}
                  stroke={hot ? 'rgb(var(--c-primary))' : '#3c494e'}
                  strokeWidth={hot ? 1.2 : 0.7}
                  strokeDasharray={hot ? 'none' : '3 4'}
                  opacity={hot ? 0.75 : 0.4}
                  style={{ transition:'all 0.25s' }} />
                {/* Traveling dot along each active edge */}
                <circle r="2.5" fill="#a5e7ff" opacity={hot ? 0.9 : 0.25}
                  style={{ filter:'drop-shadow(0 0 4px rgb(var(--c-primary) / 0.8))' }}>
                  <animateMotion dur={`${1.5 + (len/120)}s`} repeatCount="indefinite" path={`M${na.x},${na.y} L${nb.x},${nb.y}`} />
                </circle>
              </g>
            );
          })}

          {/* Nodes */}
          {EV_NODES.map(n=>{
            const s = nodeStyle(n.type);
            const isHov = hovered===n.id;
            const scale = isHov ? 1.25 : 1;
            return (
              <g key={n.id} transform={`translate(${n.x},${n.y})`}
                onMouseEnter={()=>setHovered(n.id)} onMouseLeave={()=>setHovered(null)}
                style={{ cursor:'pointer', transition:'all 0.2s' }}>
                {isHov && (
                  <circle r={s.r*2.2} fill={s.color} opacity="0.06"
                    style={{ animation:'nodePing 1.2s ease-out infinite' }} />
                )}
                <circle r={s.r * scale} fill={s.fill} stroke={s.stroke} strokeWidth={isHov ? 1.5 : 1}
                  style={{ transition:'all 0.2s', filter: isHov ? `drop-shadow(0 0 10px ${s.color}55)` : 'none' }} />
                <circle r={3.5} fill={s.color} opacity={isHov ? 1 : 0.65}
                  style={{ filter:`drop-shadow(0 0 ${isHov?'6':'3'}px ${s.color})`, transition:'all 0.2s' }} />
                <text y={s.r*scale + 12} textAnchor="middle" fontSize="8" fill={s.color} opacity="0.55"
                  style={{ fontFamily:'JetBrains Mono, monospace', letterSpacing:'0.02em', transition:'all 0.2s' }}>
                  {n.label}
                </text>
                {n.count > 0 && (
                  <text y={s.r*scale + 21} textAnchor="middle" fontSize="7" fill={s.color} opacity="0.35"
                    style={{ fontFamily:'JetBrains Mono, monospace' }}>{n.count} sources</text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

// ─── Zone 5: Artifact Factory ─────────────────────────────────────────────────

function ArtifactFactory() {
  const [ARTIFACTS] = useRunResource(api.runArtifacts, ARTIFACTS_SEED);
  const [buildPct, setBuildPct] = useState(42);
  useEffect(()=>{
    const iv = setInterval(()=>setBuildPct(p=>p>=96 ? 42 : p + 1), 280);
    return ()=>clearInterval(iv);
  },[]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.05] flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary text-[15px]">inventory_2</span>
          <span className="font-mono-label text-[11px] text-on-surface uppercase tracking-[0.15em]">Artifact Factory</span>
        </div>
        <span className="font-mono-label text-[10px] text-secondary-fixed">2 / 8 materialized</span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-1.5 scrollbar-thin">
        {ARTIFACTS.map((a, i)=>{
          const isComplete = a.status==='complete';
          const isBuilding = a.status==='building';
          return (
            <div key={i} className={`group flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-all duration-300 cursor-default
              ${isComplete ? 'border-secondary-fixed/12 bg-secondary-fixed/[0.025] hover:bg-secondary-fixed/[0.04]'
              : isBuilding  ? 'border-primary/18 bg-primary/[0.025]'
              :               'border-white/[0.04] hover:border-white/[0.07]'}`}
              style={isComplete ? { animation:`materialIn 0.5s ${i*0.06}s cubic-bezier(0.16,1,0.3,1) both` } : {}}>

              <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 border transition-colors
                ${isComplete ? 'bg-secondary-fixed/10 border-secondary-fixed/20'
                : isBuilding  ? 'bg-primary/10 border-primary/20'
                :               'bg-white/[0.02] border-white/[0.05]'}`}>
                <span className={`material-symbols-outlined text-[14px]
                  ${isComplete ? 'text-secondary-fixed' : isBuilding ? 'text-primary' : 'text-on-surface-variant/22'}`}>
                  {a.icon}
                </span>
              </div>

              <div className="flex-1 min-w-0">
                <div className={`text-[12px] font-semibold leading-tight
                  ${isComplete ? 'text-on-surface' : isBuilding ? 'text-on-surface/80' : 'text-on-surface-variant/35'}`}>
                  {a.name}
                </div>
                {isComplete && (
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="font-mono-label text-[9px] text-on-surface-variant/35">{a.size}</span>
                    <span className="text-white/10">·</span>
                    <span className="font-mono-label text-[9px] text-secondary-fixed/55">{a.evidence} sources</span>
                    <span className="text-white/10">·</span>
                    <span className="font-mono-label text-[9px] text-on-surface-variant/25">{a.time}</span>
                  </div>
                )}
                {isBuilding && (
                  <>
                    <div className="flex items-center gap-1 mt-1">
                      {[0,1,2].map(j=>(
                        <div key={j} className="w-0.5 h-0.5 rounded-full bg-primary/55"
                          style={{ animation:`thinkDot 1.4s ${j*0.2}s ease-in-out infinite` }} />
                      ))}
                      <span className="font-mono-label text-[9px] text-primary/45 ml-0.5">Generating… {buildPct}%</span>
                    </div>
                    <div className="mt-1.5 h-0.5 bg-white/[0.04] rounded-full overflow-hidden">
                      <div className="h-full rounded-full bg-gradient-to-r from-primary/40 to-primary transition-all duration-300"
                        style={{ width:`${buildPct}%`, boxShadow:'0 0 6px rgb(var(--c-primary) / 0.4)' }} />
                    </div>
                  </>
                )}
                {a.status==='queued' && (
                  <span className="font-mono-label text-[9px] text-on-surface-variant/22">Awaiting predecessor</span>
                )}
              </div>

              {isComplete && (
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className="font-mono-label text-[11px] font-bold text-secondary-fixed">{a.confidence}%</span>
                  <button
                    title={(a as any).id ? 'Download styled PDF' : 'Start a run to download'}
                    onClick={() => {
                      const rid = getActiveRun();
                      const id = (a as any).id;
                      if (rid && id) exportArtifactPDF({ artifactId: id, artifactName: a.name, runId: rid }).catch(() => {});
                    }}
                    className="w-6 h-6 rounded-md bg-white/[0.03] border border-white/[0.06] flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:border-primary/25">
                    <span className="material-symbols-outlined text-[11px] text-on-surface-variant">download</span>
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Zone 6: Startup Intelligence ─────────────────────────────────────────────

function StartupIntelligence() {
  const [via] = useRunResource(api.viability,
    { score: 8.7, radarAxes: RADAR_AXES_SEED, scenarios: SCENARIOS_SEED });
  const RADAR_AXES = (via as any).radarAxes as typeof RADAR_AXES_SEED;
  const SCENARIOS = (via as any).scenarios as typeof SCENARIOS_SEED;
  const [scenario, setScenario] = useState(1); // 0=best,1=expected,2=worst
  const cx=130, cy=130, r=90;
  const gridLevels=[0.25,0.5,0.75,1.0];

  const mainPts = radarPts(RADAR_AXES, SCENARIOS[scenario].values, cx, cy, r);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.05] flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-[#f59e0b] text-[15px]">radar</span>
          <span className="font-mono-label text-[11px] text-on-surface uppercase tracking-[0.15em]">Startup Intelligence</span>
        </div>
        <div className="flex items-center gap-1">
          {SCENARIOS.map((s,i)=>(
            <button key={s.label} onClick={()=>setScenario(i)}
              className={`px-2 py-0.5 rounded font-mono-label text-[9px] uppercase tracking-[0.08em] transition-all
                ${scenario===i ? 'text-on-surface border border-white/10 bg-white/[0.05]' : 'text-on-surface-variant/35 hover:text-on-surface-variant/60'}`}>
              {s.label.split(' ')[0]}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 flex flex-col md:flex-row items-center gap-4 p-4 overflow-hidden">
        <div className="flex-shrink-0">
          <svg viewBox="0 0 260 260" width="240" height="240">
            {/* Grid polygons */}
            {gridLevels.map((lvl,li)=>{
              const gp = radarPts(RADAR_AXES, RADAR_AXES.map(()=>100*lvl), cx, cy, r);
              return <polygon key={li} points={polyStr(gp)} fill="none" stroke="#3c494e" strokeWidth="0.6" opacity="0.4" />;
            })}
            {/* Axes */}
            {RADAR_AXES.map((a,i)=>{
              const rad=(a.angle-90)*Math.PI/180;
              return <line key={i} x1={cx} y1={cy} x2={cx+r*Math.cos(rad)} y2={cy+r*Math.sin(rad)} stroke="#3c494e" strokeWidth="0.6" opacity="0.35" />;
            })}
            {/* All scenario polygons (dim) */}
            {SCENARIOS.map((s,si)=>{
              if (si===scenario) return null;
              const pts = radarPts(RADAR_AXES, s.values, cx, cy, r);
              return <polygon key={si} points={polyStr(pts)} fill={s.color} fillOpacity={s.opacity*0.5} stroke={s.color} strokeWidth="0.7" strokeOpacity="0.3" />;
            })}
            {/* Active scenario polygon */}
            <polygon points={polyStr(mainPts)}
              fill={SCENARIOS[scenario].color} fillOpacity={SCENARIOS[scenario].opacity}
              stroke={SCENARIOS[scenario].color} strokeWidth="1.5" strokeOpacity="0.65"
              style={{ filter:`drop-shadow(0 0 8px ${SCENARIOS[scenario].color}44)`, transition:'all 0.6s ease' }} />
            {/* Data dots */}
            {mainPts.map((p,i)=>(
              <circle key={i} cx={p.x} cy={p.y} r="3.5" fill={SCENARIOS[scenario].color} opacity="0.9"
                style={{ filter:`drop-shadow(0 0 5px ${SCENARIOS[scenario].color})`, transition:'all 0.6s ease' }} />
            ))}
            {/* Axis labels */}
            {RADAR_AXES.map((a,i)=>{
              const rad=(a.angle-90)*Math.PI/180;
              return (
                <text key={i} x={cx+(r+20)*Math.cos(rad)} y={cy+(r+20)*Math.sin(rad)}
                  textAnchor="middle" dominantBaseline="middle"
                  fontSize="8" fill="#bbc9cf" opacity="0.5"
                  style={{ fontFamily:'JetBrains Mono,monospace', letterSpacing:'0.02em' }}>
                  {a.label}
                </text>
              );
            })}
          </svg>
        </div>

        <div className="flex-1 w-full space-y-2">
          {RADAR_AXES.map((a,i)=>{
            const val = SCENARIOS[scenario].values[i];
            const col = SCENARIOS[scenario].color;
            return (
              <div key={i} className="flex items-center gap-3">
                <span className="font-mono-label text-[10px] text-on-surface-variant/45 w-24 flex-shrink-0">{a.label}</span>
                <div className="flex-1 h-px bg-white/[0.04] rounded-full overflow-hidden">
                  <div className="h-full rounded-full" style={{ width:`${val}%`, background:col, boxShadow:`0 0 4px ${col}55`, transition:'width 0.7s ease, background 0.5s ease' }} />
                </div>
                <span className="font-mono-label text-[11px] w-6 text-right font-bold" style={{ color:col, transition:'color 0.5s' }}>{val}</span>
              </div>
            );
          })}
          <div className="mt-4 pt-3 border-t border-white/[0.05]">
            <div className="flex items-center gap-4 mb-2">
              {SCENARIOS.map((s,i)=>(
                <button key={s.label} onClick={()=>setScenario(i)} className="flex items-center gap-1.5 group">
                  <div className="w-2 h-2 rounded-sm transition-all" style={{ background:s.color, opacity: scenario===i ? 0.8 : 0.35 }} />
                  <span className="font-mono-label text-[9px] text-on-surface-variant/40 group-hover:text-on-surface-variant/60 transition-colors">{s.label}</span>
                </button>
              ))}
            </div>
            <div className="font-mono-label text-[10px] text-on-surface-variant/35 leading-relaxed">
              {scenario===0 && <span>Best case scores <span className="text-secondary-fixed">9.4/10</span> viability. Assumes early-mover advantage holds.</span>}
              {scenario===1 && <span>Expected scenario scores <span className="text-primary">8.7/10</span> viability. Strong market offset by competitive pressure.</span>}
              {scenario===2 && <span>Worst case scores <span className="text-[#f59e0b]">5.8/10</span> viability. Large incumbents ship competing features.</span>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Agent Debate Chamber ─────────────────────────────────────────────────────

function DebateChamber() {
  const [DEBATE] = useRunResource(api.debate, DEBATE_SEED);
  const [revealed, setRevealed] = useState(3);

  useEffect(()=>{
    const iv = setInterval(()=>setRevealed(r=>r<DEBATE.length?r+1:r), 3800);
    return ()=>clearInterval(iv);
  },[]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.05] flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-[#f59e0b] text-[15px]">balance</span>
          <span className="font-mono-label text-[11px] text-on-surface uppercase tracking-[0.15em]">Agent Debate</span>
        </div>
        <span className="px-2 py-0.5 rounded-full bg-secondary-fixed/10 border border-secondary-fixed/20 font-mono-label text-[9px] text-secondary-fixed uppercase">Verdict: Build</span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2 scrollbar-thin">
        {DEBATE.slice(0, revealed).map((d,i)=>{
          const isBuild = d.side==='Build';
          return (
            <div key={i} className={`flex gap-2.5 items-start p-2.5 rounded-lg border
              ${isBuild ? 'border-secondary-fixed/12 bg-secondary-fixed/[0.025]' : 'border-[#f59e0b]/12 bg-[#f59e0b]/[0.025]'}`}
              style={{ animation:'streamIn 0.45s cubic-bezier(0.16,1,0.3,1) both' }}>
              <div className={`w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 border
                ${isBuild ? 'bg-secondary-fixed/10 border-secondary-fixed/22' : 'bg-[#f59e0b]/10 border-[#f59e0b]/22'}`}>
                <span className={`material-symbols-outlined text-[13px] ${isBuild ? 'text-secondary-fixed' : 'text-[#f59e0b]'}`}>
                  {isBuild ? 'check' : 'close'}
                </span>
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className={`font-mono-label text-[9px] font-bold uppercase tracking-[0.08em] ${isBuild ? 'text-secondary-fixed' : 'text-[#f59e0b]'}`}>{d.side}</span>
                  <span className="text-white/10">·</span>
                  <span className="font-mono-label text-[9px] text-on-surface-variant/35">{d.agent}</span>
                </div>
                <p className="text-[11px] text-on-surface/65 leading-snug">{d.point}</p>
              </div>
            </div>
          );
        })}
        {revealed < DEBATE.length && (
          <div className="flex items-center gap-2 py-2 px-3">
            {[0,1,2].map(i=>(
              <div key={i} className="w-1 h-1 rounded-full bg-on-surface-variant/30"
                style={{ animation:`thinkDot 1.4s ease-in-out ${i*0.2}s infinite` }} />
            ))}
            <span className="font-mono-label text-[10px] text-on-surface-variant/30">Agent deliberating…</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Replay Timeline ──────────────────────────────────────────────────────────

function ReplayTimeline() {
  const [playing, setPlaying] = useState(false);
  const [pos, setPos]         = useState(32);

  useEffect(()=>{
    if (!playing) return;
    const iv = setInterval(()=>setPos(p=>{
      if (p>=100) { setPlaying(false); return 0; }
      return p + 0.5;
    }), 100);
    return ()=>clearInterval(iv);
  },[playing]);

  const active = TIMELINE_PHASES.find(p=>pos>=p.start && pos<p.end);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.05] flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary text-[15px]">movie</span>
          <span className="font-mono-label text-[11px] text-on-surface uppercase tracking-[0.15em]">Company Replay</span>
        </div>
        <span className="font-mono-label text-[10px] text-on-surface-variant/35">{Math.round(pos)}% of run</span>
      </div>
      <div className="flex-1 p-4 flex flex-col justify-between">
        {/* Phase indicators */}
        <div className="flex items-start gap-1.5 mb-5">
          {TIMELINE_PHASES.map((p,i)=>{
            const active   = pos>=p.start && pos<p.end;
            const done     = pos>=p.end;
            const pctLocal = active ? Math.round((pos-p.start)/(p.end-p.start)*100) : done ? 100 : 0;
            return (
              <div key={i} className="flex-1 flex flex-col items-center gap-1.5">
                <div className={`relative w-9 h-9 rounded-xl border flex items-center justify-center transition-all duration-400
                  ${done   ? 'bg-secondary-fixed/10 border-secondary-fixed/25'
                  : active ? 'bg-primary/10 border-primary/30 shadow-[0_0_12px_rgb(var(--c-primary) / 0.18)]'
                  :          'bg-white/[0.02] border-white/[0.05]'}`}>
                  {active && <div className="absolute inset-0 rounded-xl bg-primary/10 blur-sm animate-pulse" />}
                  <span className={`material-symbols-outlined text-[15px] relative
                    ${done ? 'text-secondary-fixed' : active ? 'text-primary' : 'text-on-surface-variant/20'}`}>{p.icon}</span>
                </div>
                <span className={`font-mono-label text-[7.5px] uppercase text-center leading-tight
                  ${done ? 'text-secondary-fixed/55' : active ? 'text-primary/65' : 'text-on-surface-variant/22'}`}>
                  {p.label}
                </span>
                {active && (
                  <span className="font-mono-label text-[7px] text-primary/40">{pctLocal}%</span>
                )}
              </div>
            );
          })}
        </div>

        {/* Scrubber */}
        <div className="space-y-3">
          <div className="relative h-2 bg-white/[0.04] rounded-full overflow-hidden cursor-pointer"
            onClick={e=>{
              const r=e.currentTarget.getBoundingClientRect();
              setPos(Math.round(((e.clientX-r.left)/r.width)*100));
            }}>
            <div className="h-full rounded-full transition-all duration-300"
              style={{ width:`${pos}%`, background:'linear-gradient(90deg,rgb(var(--c-primary) / 0.35),#a5e7ff)', boxShadow:'0 0 8px rgb(var(--c-primary) / 0.45)' }} />
            {TIMELINE_PHASES.slice(1).map((p,i)=>(
              <div key={i} className="absolute top-0 bottom-0 w-px bg-white/[0.08]" style={{ left:`${p.start}%` }} />
            ))}
            {/* Playhead */}
            <div className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-primary border-2 border-[#111417] shadow-[0_0_8px_rgb(var(--c-primary) / 0.6)] transition-all duration-300"
              style={{ left:`calc(${pos}% - 6px)` }} />
          </div>

          <div className="flex items-center justify-center gap-3">
            {[
              { icon:'fast_rewind',  action:()=>setPos(p=>Math.max(0,p-10)) },
              { icon:playing?'pause':'play_arrow', action:()=>setPlaying(p=>!p), primary:true },
              { icon:'fast_forward', action:()=>setPos(p=>Math.min(100,p+10)) },
            ].map((btn,i)=>(
              <button key={i} onClick={btn.action}
                className={`flex items-center justify-center rounded-xl border transition-all
                  ${btn.primary
                    ? 'w-10 h-10 bg-primary/10 border-primary/28 text-primary hover:bg-primary/18 shadow-[0_0_14px_rgb(var(--c-primary) / 0.12)]'
                    : 'w-8 h-8 bg-white/[0.03] border-white/[0.07] text-on-surface-variant hover:text-on-surface hover:border-white/10'}`}>
                <span className="material-symbols-outlined text-[17px]">{btn.icon}</span>
              </button>
            ))}
          </div>
        </div>

        {active && (
          <div className="mt-3 px-3 py-2 rounded-lg bg-primary/[0.035] border border-primary/12">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-primary text-[14px]">{active.icon}</span>
              <span className="font-mono-label text-[11px] text-primary">{active.label} phase in progress</span>
              <span className="ml-auto font-mono-label text-[10px] text-on-surface-variant/30">{Math.round(pos)}%</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Startup DNA Graph (NEW) ──────────────────────────────────────────────────

function StartupDNAGraph() {
  const [dna] = useRunResource(api.dna, { nodes: DNA_NODES_SEED, edges: DNA_EDGES_SEED });
  const DNA_NODES = (dna as any).nodes as typeof DNA_NODES_SEED;
  const DNA_EDGES = (dna as any).edges as typeof DNA_EDGES_SEED;
  const [hovered, setHovered] = useState<string|null>(null);

  const pathD = (a:{x:number;y:number}, b:{x:number;y:number}) => `M${a.x},${a.y} L${b.x},${b.y}`;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.05] flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-secondary-fixed text-[15px]">scatter_plot</span>
          <span className="font-mono-label text-[11px] text-on-surface uppercase tracking-[0.15em]">Startup DNA</span>
        </div>
        <span className="font-mono-label text-[9px] text-on-surface-variant/30 uppercase tracking-wider">Living Network</span>
      </div>
      <div className="flex-1 relative overflow-hidden">
        <svg viewBox="0 0 400 340" className="w-full h-full" preserveAspectRatio="xMidYMid meet">
          <defs>
            <radialGradient id="dnaGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#a5e7ff" stopOpacity="0.07" />
              <stop offset="100%" stopColor="#a5e7ff" stopOpacity="0" />
            </radialGradient>
            {DNA_EDGES.map(e=>{
              const na = DNA_NODES.find(n=>n.id===e.a)!;
              const nb = DNA_NODES.find(n=>n.id===e.b)!;
              return <path key={`dnapath-${e.a}-${e.b}`} id={`dnapath-${e.a}-${e.b}`} d={pathD(na,nb)} />;
            })}
          </defs>
          <rect width="400" height="340" fill="url(#dnaGlow)" />

          {/* Edges */}
          {DNA_EDGES.map(e=>{
            const na = DNA_NODES.find(n=>n.id===e.a)!;
            const nb = DNA_NODES.find(n=>n.id===e.b)!;
            const hot = hovered===e.a || hovered===e.b;
            const dur = 1.8 + (Math.hypot(nb.x-na.x,nb.y-na.y)/120);
            return (
              <g key={`${e.a}-${e.b}`}>
                <line x1={na.x} y1={na.y} x2={nb.x} y2={nb.y}
                  stroke={hot ? 'rgb(var(--c-primary))' : '#3c494e'}
                  strokeWidth={hot ? 1.2 : 0.7}
                  opacity={hot ? 0.6 : 0.35}
                  style={{ transition:'all 0.25s' }} />
                {/* Traveling pulse */}
                <circle r="2.5" fill={hot?'rgb(var(--c-primary))':'rgb(var(--c-primary))'} opacity={hot?0.9:0.35}
                  style={{ filter:'drop-shadow(0 0 4px rgb(var(--c-primary) / 0.75))' }}>
                  <animateMotion dur={`${dur}s`} repeatCount="indefinite" path={pathD(na,nb)} />
                </circle>
                {/* Reverse pulse (offset) */}
                <circle r="1.8" fill="#79ff5b" opacity={hot?0.7:0.18}
                  style={{ filter:'drop-shadow(0 0 3px rgba(121,255,91,0.6))' }}>
                  <animateMotion dur={`${dur*1.3}s`} begin={`${-dur*0.5}s`} repeatCount="indefinite" path={pathD(nb,na)} />
                </circle>
              </g>
            );
          })}

          {/* Nodes */}
          {DNA_NODES.map(n=>{
            const isHov  = hovered===n.id;
            const isCore = n.core;
            const glow   = isCore ? 'rgb(var(--c-primary))' : '#79ff5b';
            const scale  = isHov ? 1.2 : 1;
            return (
              <g key={n.id} transform={`translate(${n.x},${n.y})`}
                onMouseEnter={()=>setHovered(n.id)} onMouseLeave={()=>setHovered(null)}
                style={{ cursor:'pointer' }}>
                {/* Ping ring */}
                {(isCore || isHov) && (
                  <circle r={n.r * scale * 1.8} fill="none" stroke={glow} strokeWidth="0.8"
                    opacity="0.2" style={{ animation:'nodePing 2s ease-out infinite' }} />
                )}
                {/* Node fill */}
                <circle r={n.r * scale} fill={isCore ? 'rgb(var(--c-primary) / 0.08)' : 'rgba(121,255,91,0.06)'}
                  stroke={isCore ? 'rgb(var(--c-primary) / 0.4)' : 'rgba(121,255,91,0.3)'}
                  strokeWidth={isHov ? 1.5 : 1}
                  style={{ transition:'all 0.25s', filter: isHov ? `drop-shadow(0 0 10px ${glow}55)` : isCore ? `drop-shadow(0 0 8px rgb(var(--c-primary) / 0.3))` : 'none' }} />
                {/* Center dot */}
                <circle r={isCore ? 5 : 3.5} fill={glow} opacity={isHov?1:0.75}
                  style={{ filter:`drop-shadow(0 0 ${isHov?'8':'4'}px ${glow})`, transition:'all 0.2s' }} />
                {/* Label */}
                <text y={n.r * scale + 13} textAnchor="middle"
                  fontSize={isCore ? 9 : 8} fontWeight={isCore ? '700' : '500'}
                  fill={isCore ? 'rgb(var(--c-primary))' : '#79ff5b'}
                  opacity={isHov ? 0.9 : isCore ? 0.7 : 0.5}
                  style={{ fontFamily:'JetBrains Mono,monospace', letterSpacing:'0.04em', transition:'all 0.2s' }}>
                  {n.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

// ─── Explain-Why (per-feature provenance + confidence) ────────────────────────

const EXPLAIN_SEED = {
  overallConfidence: 86,
  features: [
    { title:'AI resume parsing', priority:'Must', why:'Core retrieval capability inspired by Greenhouse', inspiredBy:'Greenhouse', confidence:91,
      evidence:[{ source:'github', title:'resume-screening/issues#12: "good candidates rejected"' }] },
    { title:'Bias-free ranking', priority:'Must', why:'Addresses the highest-severity pain in research', inspiredBy:null, confidence:84,
      evidence:[{ source:'reddit', title:'r/recruiting: "ATS keyword bias drops strong devs"' }] },
    { title:'Candidate match score', priority:'Should', why:'Differentiator vs. competitor gap analysis', inspiredBy:'Lever', confidence:77,
      evidence:[{ source:'hn', title:'HN: "every ATS is a keyword grep, none rank on signal"' }] },
  ],
};

function ExplainWhy() {
  const [data] = useRunResource(api.explain, EXPLAIN_SEED);
  const feats = data.features ?? [];
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.05] flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary text-[15px]">psychology</span>
          <span className="font-mono-label text-[11px] text-on-surface uppercase tracking-[0.15em]">Explain Why</span>
        </div>
        <span className="px-2 py-0.5 rounded-full bg-primary/10 border border-primary/20 font-mono-label text-[9px] text-primary uppercase">
          {data.overallConfidence}% grounded
        </span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2 scrollbar-thin">
        {feats.map((f:any,i:number)=>(
          <div key={i} className="p-2.5 rounded-lg border border-white/[0.06] bg-white/[0.015]"
            style={{ animation:'fadeInUp 0.4s ease both', animationDelay:`${i*0.08}s` }}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[12px] text-on-surface/85 font-medium">{f.title}</span>
              <span className="font-mono-label text-[9px] text-on-surface-variant/40 uppercase">{f.priority}</span>
            </div>
            <p className="text-[11px] text-on-surface/55 leading-snug mb-1.5">{f.why}</p>
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1 rounded-full bg-white/[0.06] overflow-hidden">
                <div className="h-full rounded-full bg-gradient-to-r from-primary/60 to-secondary-fixed/60"
                  style={{ width:`${f.confidence}%` }} />
              </div>
              <span className="font-mono-label text-[9px] text-primary/70">{f.confidence}%</span>
              {f.inspiredBy && (
                <span className="px-1.5 py-0.5 rounded bg-secondary-fixed/8 border border-secondary-fixed/15 font-mono-label text-[8px] text-secondary-fixed/70">
                  ↪ {f.inspiredBy}
                </span>
              )}
            </div>
            {f.evidence?.[0] && (
              <div className="mt-1 flex items-center gap-1 text-on-surface-variant/35">
                <span className="material-symbols-outlined text-[11px]">link</span>
                <span className="font-mono-label text-[9px] truncate">{f.evidence[0].title || f.evidence[0].source}</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── GitHub Launch Mode (ships a real repo + milestones + issues) ──────────────

function LaunchMode() {
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState<null | 'preview' | 'create'>(null);
  const [err, setErr] = useState<string|null>(null);
  const [token, setToken] = useState('');

  // dryRun=true → safe preview (no token). dryRun=false → create a REAL repo in the user's own
  // GitHub account using the PAT they paste here (never stored; sent once with this request).
  async function launch(dryRun: boolean) {
    const runId = getActiveRun();
    if (!runId) { setErr('No active run — start a pipeline first.'); return; }
    if (!dryRun && !token.trim()) { setErr('Paste a GitHub PAT (repo scope) to create a real repo.'); return; }
    setBusy(dryRun ? 'preview' : 'create'); setErr(null);
    try {
      const res = await api.launch(runId, { dryRun, ...(token.trim() ? { token: token.trim() } : {}) });
      setResult(res);
      if (!dryRun && res?.created) setToken('');   // drop the secret from memory once used
      if (!dryRun && !res?.created && res?.message) setErr(res.message);
    } catch { setErr('Run not ready (needs a completed PRD).'); }
    finally { setBusy(null); }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.05] flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-on-surface text-[15px]">rocket_launch</span>
          <span className="font-mono-label text-[11px] text-on-surface uppercase tracking-[0.15em]">Launch Mode</span>
        </div>
        <span className="px-2 py-0.5 rounded-full bg-[#f59e0b]/10 border border-[#f59e0b]/20 font-mono-label text-[9px] text-[#f59e0b] uppercase">GitHub</span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 scrollbar-thin">
        <p className="text-[11px] text-on-surface/55 leading-snug mb-3">
          Turn the execution package into a <span className="text-on-surface/80">real GitHub repository</span> — README,
          milestones from the roadmap, and an issue per backlog item. Preview is safe; creating one ships it to
          <span className="text-on-surface/80"> your own GitHub account</span>.
        </p>

        {/* User's own PAT — the repo is created in THEIR account. Never stored; sent once. */}
        <label className="block font-mono-label text-[9px] text-on-surface-variant/55 uppercase tracking-[0.12em] mb-1">Your GitHub PAT · repo scope</label>
        <div className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-white/[0.03] border border-white/[0.07] focus-within:border-primary/30 transition-colors mb-1.5">
          <span className="material-symbols-outlined text-on-surface-variant/40 text-[15px]">key</span>
          <input value={token} onChange={e => setToken(e.target.value)} type="password" autoComplete="off"
            placeholder="ghp_…  (creates the repo in your account)"
            className="bg-transparent border-none outline-none flex-1 text-[11px] text-on-surface placeholder:text-on-surface-variant/30 font-mono-label" />
        </div>
        <a href="https://github.com/settings/tokens/new?scopes=repo&description=APS%20Launch" target="_blank" rel="noreferrer"
          className="inline-flex items-center gap-1 mb-3 font-mono-label text-[9px] text-primary/60 hover:text-primary transition-colors">
          <span className="material-symbols-outlined text-[12px]">open_in_new</span> create a token (repo scope)
        </a>

        <div className="flex items-center gap-2">
          <button onClick={() => launch(true)} disabled={busy !== null}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-white/[0.08] bg-white/[0.03] hover:bg-white/[0.06] transition-colors disabled:opacity-50">
            <span className="material-symbols-outlined text-on-surface-variant/70 text-[15px]">{busy==='preview'?'progress_activity':'preview'}</span>
            <span className="font-mono-label text-[11px] text-on-surface-variant/80 uppercase tracking-[0.1em]">{busy==='preview'?'…':'Preview'}</span>
          </button>
          <button onClick={() => launch(false)} disabled={busy !== null || !token.trim()}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-primary/25 bg-primary/[0.08] hover:bg-primary/[0.14] transition-colors disabled:opacity-40">
            <span className="material-symbols-outlined text-primary text-[15px]">{busy==='create'?'progress_activity':'rocket_launch'}</span>
            <span className="font-mono-label text-[11px] text-primary uppercase tracking-[0.1em]">{busy==='create'?'Creating…':'Create repo'}</span>
          </button>
        </div>
        {err && <p className="mt-2 text-[10px] text-[#f59e0b]/80 font-mono-label leading-snug">{err}</p>}
        {result && (
          <div className="mt-3 space-y-2" style={{ animation:'fadeInUp 0.4s ease both' }}>
            <div className="flex items-center gap-2 p-2 rounded-lg border border-secondary-fixed/15 bg-secondary-fixed/[0.03]">
              <span className="material-symbols-outlined text-secondary-fixed text-[14px]">folder</span>
              <span className="font-mono-label text-[11px] text-on-surface/80">{result.fullName ?? result.repoName}</span>
              <span className={`ml-auto px-1.5 py-0.5 rounded font-mono-label text-[8px] uppercase ${result.created ? 'bg-secondary-fixed/15 text-secondary-fixed' : 'bg-white/[0.05] text-on-surface-variant/50'}`}>
                {result.created ? 'Live' : 'Preview'}
              </span>
            </div>
            {result.created && result.repoUrl && (
              <a href={result.repoUrl} target="_blank" rel="noreferrer"
                className="flex items-center gap-2 p-2 rounded-lg border border-primary/25 bg-primary/[0.06] hover:bg-primary/[0.12] transition-colors">
                <span className="material-symbols-outlined text-primary text-[14px]">open_in_new</span>
                <span className="font-mono-label text-[10px] text-primary truncate">{result.repoUrl}</span>
              </a>
            )}
            <div className="grid grid-cols-3 gap-2">
              <div className="p-2 rounded-lg border border-white/[0.06] text-center">
                <div className="font-mono-num text-[18px] text-on-surface">{result.filesCreated || result.fileCount || 0}</div>
                <div className="font-mono-label text-[8px] text-on-surface-variant/45 uppercase">Files</div>
              </div>
              <div className="p-2 rounded-lg border border-white/[0.06] text-center">
                <div className="font-mono-num text-[18px] text-primary">{result.milestoneCount}</div>
                <div className="font-mono-label text-[8px] text-on-surface-variant/45 uppercase">Milestones</div>
              </div>
              <div className="p-2 rounded-lg border border-white/[0.06] text-center">
                <div className="font-mono-num text-[18px] text-secondary-fixed">{result.issueCount}</div>
                <div className="font-mono-label text-[8px] text-on-surface-variant/45 uppercase">Issues</div>
              </div>
            </div>
            <p className="text-[10px] text-on-surface/50 leading-snug">{result.message}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [elapsed, setElapsed] = useState(863);
  useEffect(()=>{
    const iv = setInterval(()=>setElapsed(e=>e+1), 1000);
    return ()=>clearInterval(iv);
  },[]);

  return (
    <div className="bg-background text-on-surface min-h-screen overflow-x-hidden select-none"
      style={{ fontFamily:'Inter,system-ui,sans-serif' }}>
      <style>{`
        @keyframes headerScan {
          0%,100% { opacity:0.2; transform:translateX(-100%); }
          50%      { opacity:1;   transform:translateX(100%); }
        }
        @keyframes agentPulse {
          0%,100% { opacity:1; }
          50%     { opacity:0.65; }
        }
        @keyframes thinkDot {
          0%,80%,100% { transform:scale(1);   opacity:0.35; }
          40%          { transform:scale(1.7); opacity:1; }
        }
        @keyframes fadeInUp {
          from { opacity:0; transform:translateY(6px); }
          to   { opacity:1; transform:translateY(0); }
        }
        @keyframes streamIn {
          from { opacity:0; transform:translateX(-6px); }
          to   { opacity:1; transform:translateX(0); }
        }
        @keyframes materialIn {
          from { opacity:0; clip-path:inset(0 100% 0 0 round 8px); }
          to   { opacity:1; clip-path:inset(0 0%   0 0 round 8px); }
        }
        @keyframes borderSweep {
          0%   { background-position: -200% 0; }
          100% { background-position:  200% 0; }
        }
        @keyframes queueSlide {
          0%   { transform:translateX(-150%); }
          100% { transform:translateX(500%);  }
        }
        @keyframes nodePing {
          0%   { transform:scale(1);   opacity:0.5; }
          100% { transform:scale(1.8); opacity:0;   }
        }
        .scrollbar-thin::-webkit-scrollbar       { width:3px; }
        .scrollbar-thin::-webkit-scrollbar-track  { background:transparent; }
        .scrollbar-thin::-webkit-scrollbar-thumb  { background:rgb(var(--c-primary) / 0.08); border-radius:2px; }
      `}</style>

      <Nav />

      <main className="pt-16">
        {/* Zone 1 — Command Header */}
        <CommandHeader elapsed={elapsed} />

        {/* Zone 2 — Agent Fleet */}
        <AgentFleet />

        {/* Main grid */}
        <div className="max-w-[1600px] mx-auto px-container-margin py-4 space-y-4">

          {/* Row 1: Execution Stream + Evidence Hub */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4" style={{ height:440 }}>
            <div className="lg:col-span-3 rounded-xl border border-white/[0.055] bg-[#0A0C11]/85 overflow-hidden flex flex-col">
              <ExecutionStream />
            </div>
            <div className="lg:col-span-2 rounded-xl border border-white/[0.055] bg-[#0A0C11]/85 overflow-hidden flex flex-col">
              <EvidenceHub />
            </div>
          </div>

          {/* Row 2: Artifact Factory + Startup Intelligence */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4" style={{ height:390 }}>
            <div className="lg:col-span-2 rounded-xl border border-white/[0.055] bg-[#0A0C11]/85 overflow-hidden flex flex-col">
              <ArtifactFactory />
            </div>
            <div className="lg:col-span-3 rounded-xl border border-white/[0.055] bg-[#0A0C11]/85 overflow-hidden flex flex-col">
              <StartupIntelligence />
            </div>
          </div>

          {/* Row 3: Debate + Replay + DNA */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 pb-10" style={{ minHeight:340 }}>
            <div className="rounded-xl border border-white/[0.055] bg-[#0A0C11]/85 overflow-hidden flex flex-col">
              <DebateChamber />
            </div>
            <div className="rounded-xl border border-white/[0.055] bg-[#0A0C11]/85 overflow-hidden flex flex-col">
              <ReplayTimeline />
            </div>
            <div className="rounded-xl border border-white/[0.055] bg-[#0A0C11]/85 overflow-hidden flex flex-col">
              <StartupDNAGraph />
            </div>
          </div>

          {/* Row 4: Explain-Why + GitHub Launch Mode */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 pb-10" style={{ minHeight:320 }}>
            <div className="lg:col-span-3 rounded-xl border border-white/[0.055] bg-[#0A0C11]/85 overflow-hidden flex flex-col">
              <ExplainWhy />
            </div>
            <div className="lg:col-span-2 rounded-xl border border-white/[0.055] bg-[#0A0C11]/85 overflow-hidden flex flex-col">
              <LaunchMode />
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}
