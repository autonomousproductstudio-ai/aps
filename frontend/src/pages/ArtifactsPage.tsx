import { useState, useEffect, useRef } from 'react';
import { NotificationBell } from '../components/NotificationBell';
import { Link } from 'react-router-dom';
import { SettingsMenu } from '../components/SettingsMenu';
import { api } from '../lib/api';
import { getActiveRun, setActiveRun, useLive } from '../lib/useBackend';
import { exportArtifactPDF } from '../lib/pdfExport';
import { MermaidDiagram, extractMermaidBlocks } from '../components/MermaidDiagram';
import { MarkdownArtifact } from '../components/MarkdownArtifact';

// ─── Types ────────────────────────────────────────────────────────────────────

type ArtifactStatus = 'complete' | 'building' | 'queued';
type RightTab = 'intelligence' | 'evidence' | 'dna';
type CenterTab = 'overview' | 'evidence' | 'versions';

// ─── Evidence Traces ──────────────────────────────────────────────────────────

const TRACES: Record<string, { label: string; sources: { platform: string; icon: string; count: number; examples: string[] }[] }> = {
  'tam': {
    label: '$8.4B total addressable market',
    sources: [
      { platform:'Market Reports', icon:'bar_chart',     count:4,  examples:['Gartner HRTech 2024 Report', 'IDC Recruitment Software Forecast', 'Grand View Research ATS Market', 'Allied Market Research HR Tech'] },
      { platform:'GitHub',         icon:'code',          count:12, examples:['OSS ATS repos: combined star growth +340% YoY', 'hiring-tools: 12k stars', '+10 more'] },
      { platform:'Research Papers',icon:'library_books', count:2,  examples:['LinkedIn Economic Graph Research 2023', 'IEEE HR Automation Study'] },
    ],
  },
  'ats-fnr': {
    label: 'ATS false-negative rates reaching 75% of qualified candidates',
    sources: [
      { platform:'GitHub',        icon:'code',    count:34, examples:['resume-screening/issues#12: "good candidates rejected"', 'awesome-job-boards#47', '+32 more'] },
      { platform:'Reddit',        icon:'forum',   count:18, examples:['r/recruiting: "75% good candidates rejected"', 'r/jobs: "ATS black hole destroyed my career"', 'r/cscareerquestions#847', '+15 more'] },
      { platform:'Hacker News',   icon:'newspaper',count:7, examples:['"Ask HN: ATS is broken for software engineers"', '+6 more'] },
      { platform:'Research',      icon:'library_books',count:3, examples:['Raghavan et al. 2020: Bias in Algorithmic Hiring', 'Harvard Business Review: Hidden Workers', '+1 more'] },
    ],
  },
  'manual-time': {
    label: 'manual screening consuming >5 hours per week per recruiter',
    sources: [
      { platform:'Reddit',       icon:'forum',   count:24, examples:['r/humanresources: "5+ hours weekly on screening"', 'r/recruiting: "drowning in CVs"', '+22 more'] },
      { platform:'Product Hunt', icon:'stars',   count:8,  examples:['Hiring tool reviews citing manual workload', '+7 more'] },
      { platform:'Hacker News',  icon:'newspaper',count:4, examples:['"Ask HN: how long does it take to screen 200 CVs?"', '+3 more'] },
    ],
  },
  'no-smb': {
    label: 'no AI-native ATS solution targeting SMBs exists',
    sources: [
      { platform:'Product Hunt', icon:'stars',   count:12, examples:['"AI hiring" search — 12 products, 0 SMB-native AI', 'Greenhouse reviews: "too expensive"', '+10 more'] },
      { platform:'Reddit',       icon:'forum',   count:9,  examples:['r/smallbusiness: "can\'t afford Greenhouse"', '+8 more'] },
      { platform:'GitHub',       icon:'code',    count:6,  examples:['Open-source ATS repos — limited AI integration', '+5 more'] },
    ],
  },
  'oss-moat': {
    label: 'OSS models eliminate the training-data moat',
    sources: [
      { platform:'GitHub',       icon:'code',    count:22, examples:['mistralai/mistral-7b: 47k stars', 'huggingface/transformers: 120k stars', 'BAAI/bge-large-en: SOTA retrieval', '+19 more'] },
      { platform:'Hacker News',  icon:'newspaper',count:8, examples:['"Mistral matches GPT-3.5 on classification tasks"', '+7 more'] },
      { platform:'Research',     icon:'library_books',count:4, examples:['Jiang et al. 2023: Mistral 7B', '+3 more'] },
    ],
  },
};

// ─── Artifact List ────────────────────────────────────────────────────────────

const ARTIFACTS = [
  { id:'research-brief',  name:'Research Brief',   icon:'travel_explore', category:'Research',      status:'complete' as ArtifactStatus, confidence:94, quality:9.1, size:'42 KB',  genTime:'3m 12s', agents:['Research Agent'],                       evidenceCount:47, sourceCount:8,  versions:2, generatedAt:'14:03:12', summary:'Confirmed $8.4B TAM. 47 evidence nodes. ATS false-negative rate 75%. No AI-native SMB solution.' },
  { id:'market-analysis', name:'Market Analysis',  icon:'bar_chart',      category:'Research',      status:'complete' as ArtifactStatus, confidence:91, quality:8.8, size:'18 KB',  genTime:'1m 40s', agents:['Research Agent'],                       evidenceCount:23, sourceCount:6,  versions:1, generatedAt:'14:04:52', summary:'Competitive landscape mapping 14 ATS players. Critical gap confirmed in AI-native SMB tier.' },
  { id:'prd',             name:'PRD v1.0',         icon:'description',    category:'Product',       status:'complete' as ArtifactStatus, confidence:87, quality:8.4, size:'31 KB',  genTime:'5m 20s', agents:['Research Agent','Product Agent'],        evidenceCount:34, sourceCount:5,  versions:1, generatedAt:'14:09:32', summary:'14 user stories across 3 epics. Feature priority validated against competitor gap analysis.' },
  { id:'trd',             name:'Technical Design', icon:'hub',            category:'Architecture',  status:'complete' as ArtifactStatus, confidence:85, quality:8.7, size:'26 KB',   genTime:'4m 08s', agents:['Architecture Agent'],                   evidenceCount:18, sourceCount:5,  versions:1, generatedAt:'14:14:21', summary:'System architecture, API design, and database schema — rendered as live diagrams.' },
  { id:'openapi',         name:'OpenAPI Spec',     icon:'code',           category:'Architecture',  status:'queued'  as ArtifactStatus, confidence:0,  quality:0,   size:'—',       genTime:'—',      agents:['Architecture Agent'],                   evidenceCount:0,  sourceCount:0,  versions:0, generatedAt:'—',       summary:'Awaiting Technical Design completion.' },
  { id:'roadmap',         name:'Roadmap Q1–Q3',   icon:'route',          category:'Execution',     status:'complete' as ArtifactStatus, confidence:88, quality:8.6, size:'12 KB',  genTime:'2m 05s', agents:['Product Agent','Execution Agent'],       evidenceCount:28, sourceCount:4,  versions:1, generatedAt:'14:11:37', summary:'3-phase execution plan, 9 milestones over 9 months, derived from feature priority matrix.' },
  { id:'investor-memo',   name:'Investor Memo',    icon:'attach_money',   category:'Business',      status:'queued'  as ArtifactStatus, confidence:0,  quality:0,   size:'—',       genTime:'—',      agents:['Research Agent','Presentation Agent'],  evidenceCount:0,  sourceCount:0,  versions:0, generatedAt:'—',       summary:'Awaiting all upstream artifacts.' },
  { id:'pitch-deck',      name:'Pitch Deck',       icon:'smart_display',  category:'Business',      status:'queued'  as ArtifactStatus, confidence:0,  quality:0,   size:'—',       genTime:'—',      agents:['Presentation Agent'],                   evidenceCount:0,  sourceCount:0,  versions:0, generatedAt:'—',       summary:'Awaiting all upstream artifacts.' },
];

const CATEGORIES = ['Research', 'Product', 'Architecture', 'Execution', 'Business',
                    'Brand', 'Legal', 'Funding'];

const AGENT_META: Record<string,{icon:string}> = {
  'Research Agent':     { icon:'travel_explore' },
  'Product Agent':      { icon:'architecture' },
  'Architecture Agent': { icon:'hub' },
  'Execution Agent':    { icon:'data_object' },
  'Presentation Agent': { icon:'smart_display' },
};

const VERSIONS = [
  { label:'v1 — Initial Draft', time:'14:03:12', note:'First pass from raw evidence' },
  { label:'v2 — Refined',       time:'14:06:45', note:'Competitor data cross-validated', current:true },
];

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
          <Link to="/artifacts" className="relative flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-primary bg-primary/10 border border-primary/25 shadow-[0_0_14px_rgba(71,214,255,0.12)]">
            <span className="w-1.5 h-1.5 rounded-full bg-primary shadow-[0_0_5px_rgba(71,214,255,0.9)] animate-pulse" />
            Artifacts
          </Link>
          <Link to="/system" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">System</Link>
          <Link to="/pricing" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">Pricing</Link>
          <Link to="/history" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">History</Link>
        </div>
      </div>
      <div className="relative flex items-center gap-1.5">
        <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.07] text-on-surface-variant text-[11px] font-mono-label mr-2 cursor-pointer hover:border-primary/30 transition-colors">
          <span className="material-symbols-outlined text-[15px]">search</span>
          <span className="opacity-50">Search intelligence…</span>
          <span className="ml-4 text-[10px] opacity-30 border border-white/10 rounded px-1">⌘K</span>
        </div>
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-secondary-fixed/[0.08] border border-secondary-fixed/20 mr-2">
          <span className="flex h-1.5 w-1.5 rounded-full bg-secondary-fixed shadow-[0_0_6px_rgba(121,255,91,0.9)] animate-pulse" />
          <span className="text-[10px] font-mono-label text-secondary-fixed/80 uppercase tracking-[0.15em]">8 Artifacts</span>
        </div>
        <NotificationBell />
          <SettingsMenu />
      </div>
    </nav>
  );
}

// ─── Left Panel: Artifact Navigator ───────────────────────────────────────────

// Run switcher — pick which run's artifacts the vault shows. Replaces the old static RUN_0042
// label with a dropdown over the user's run archive (GET /v1/history, newest first).
function RunSwitcher({ runId, runs, onChange }: {
  runId: string; runs: any[]; onChange:(id:string)=>void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function handler(e: MouseEvent) { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const current = runs.find(r => r.runId === runId);
  const label = current?.name ?? current?.idea ?? 'AI SaaS Resume';
  const statusColor = (s?: string) =>
    s === 'complete' ? 'text-secondary-fixed' : s === 'failed' || s === 'cancelled'
      ? 'text-error' : 'text-primary';

  return (
    <div ref={ref} className="relative px-4 py-2.5 border-b border-white/[0.03] flex-shrink-0">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2 group"
        title="Switch run"
      >
        <span className={`flex h-1.5 w-1.5 rounded-full bg-secondary-fixed shadow-[0_0_5px_rgba(121,255,91,0.8)] ${open ? '' : 'animate-pulse'}`} />
        <span className="font-mono-label text-[10px] text-secondary-fixed/70 uppercase tracking-wider">{runId || 'NO RUN'}</span>
        <span className="ml-auto font-mono-label text-[10px] text-on-surface-variant/30 max-w-[110px] truncate">{label}</span>
        <span className={`material-symbols-outlined text-on-surface-variant/40 text-[14px] transition-transform ${open ? 'rotate-180' : ''}`}>expand_more</span>
      </button>

      {open && (
        <div className="absolute left-2 right-2 top-full mt-1 z-50 max-h-[260px] overflow-y-auto rounded-lg border border-white/[0.08] bg-[#0C0C12] shadow-xl shadow-black/40 scrollbar-thin">
          {runs.length === 0 && (
            <div className="px-3 py-3 font-mono-label text-[10px] text-on-surface-variant/40">
              No other runs yet
            </div>
          )}
          {runs.map(r => (
            <button
              key={r.runId}
              onClick={() => { onChange(r.runId); setOpen(false); }}
              className={`w-full text-left px-3 py-2 border-b border-white/[0.03] last:border-0 hover:bg-white/[0.04] transition-colors flex flex-col gap-0.5 ${r.runId === runId ? 'bg-primary/[0.06]' : ''}`}
            >
              <div className="flex items-center gap-2">
                <span className="font-mono-label text-[10px] text-secondary-fixed/80 uppercase tracking-wider">{r.runId}</span>
                <span className={`font-mono-label text-[9px] uppercase tracking-wider ${statusColor(r.status)}`}>{(r.status ?? '').toString()}</span>
              </div>
              <span className="font-mono-label text-[10px] text-on-surface-variant/45 truncate">{r.name ?? r.idea ?? ''}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ArtifactNavigator({ artifacts, selected, onSelect, query, onQuery, runId, runs, onRunChange }: {
  artifacts: typeof ARTIFACTS; selected: string; onSelect:(id:string)=>void; query:string; onQuery:(q:string)=>void;
  runId: string; runs: any[]; onRunChange:(id:string)=>void;
}) {
  const filtered = artifacts.filter(a =>
    !query || a.name.toLowerCase().includes(query.toLowerCase()) || a.category.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <aside className="w-[260px] flex-shrink-0 border-r border-white/[0.05] flex flex-col bg-[#09090E]">
      {/* Header */}
      <div className="px-4 py-4 border-b border-white/[0.04] flex-shrink-0">
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-primary text-[15px]">inventory_2</span>
          <span className="font-mono-label text-[11px] text-on-surface uppercase tracking-[0.18em]">Intelligence Vault</span>
        </div>
        <div className="relative">
          <span className="material-symbols-outlined text-on-surface-variant/35 text-[14px] absolute left-2.5 top-1/2 -translate-y-1/2">search</span>
          <input
            value={query} onChange={e=>onQuery(e.target.value)}
            placeholder="Filter artifacts…"
            className="w-full bg-white/[0.03] border border-white/[0.07] rounded-lg pl-8 pr-3 py-1.5 font-mono-label text-[11px] text-on-surface placeholder-on-surface-variant/25 focus:outline-none focus:border-primary/30 transition-colors"
          />
        </div>
      </div>

      {/* Run context — switch between this user's runs */}
      <RunSwitcher runId={runId} runs={runs} onChange={onRunChange} />

      {/* Grouped list */}
      <div className="flex-1 overflow-y-auto py-2 scrollbar-thin">
        {CATEGORIES.map(cat => {
          const items = filtered.filter(a=>a.category===cat);
          if (!items.length) return null;
          return (
            <div key={cat} className="mb-1">
              <div className="px-4 py-1.5">
                <span className="font-mono-label text-[9px] text-on-surface-variant/30 uppercase tracking-[0.2em]">{cat}</span>
              </div>
              {items.map(a=>(
                <ArtifactNavItem key={a.id} artifact={a} selected={selected===a.id} onSelect={()=>onSelect(a.id)} />
              ))}
            </div>
          );
        })}
      </div>

      {/* Bottom stats */}
      <div className="px-4 py-3 border-t border-white/[0.04] flex-shrink-0">
        <div className="flex items-center justify-between">
          <span className="font-mono-label text-[9px] text-on-surface-variant/30 uppercase tracking-wider">
            {ARTIFACTS.filter(a=>a.status==='complete').length} complete · {ARTIFACTS.filter(a=>a.status==='building').length} building
          </span>
          <span className="font-mono-label text-[9px] text-primary/50">v2.0</span>
        </div>
      </div>
    </aside>
  );
}

function ArtifactNavItem({ artifact, selected, onSelect }: { artifact: typeof ARTIFACTS[0]; selected:boolean; onSelect:()=>void }) {
  const statusColor = artifact.status==='complete' ? '#79ff5b' : artifact.status==='building' ? 'rgb(var(--c-primary))' : '#3c494e';
  return (
    <button onClick={onSelect}
      className={`w-full text-left px-3 py-2.5 flex items-center gap-2.5 group transition-all duration-150 relative
        ${selected ? 'bg-primary/[0.07] border-l-2 border-primary' : 'border-l-2 border-transparent hover:bg-white/[0.025] hover:border-white/[0.05]'}`}>
      {selected && <div className="absolute inset-0 bg-gradient-to-r from-primary/[0.05] to-transparent pointer-events-none" />}
      <div className={`relative w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 border transition-all
        ${selected ? 'bg-primary/10 border-primary/25' : 'bg-white/[0.03] border-white/[0.06] group-hover:border-white/10'}`}>
        <span className={`material-symbols-outlined text-[14px] ${selected ? 'text-primary' : 'text-on-surface-variant/40 group-hover:text-on-surface-variant/60'}`}>
          {artifact.icon}
        </span>
      </div>
      <div className="flex-1 min-w-0">
        <div className={`text-[12px] font-medium leading-tight truncate ${selected ? 'text-on-surface' : 'text-on-surface/60 group-hover:text-on-surface/80'}`}>
          {artifact.name}
        </div>
        <div className="flex items-center gap-1.5 mt-0.5">
          <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background:statusColor, boxShadow:`0 0 4px ${statusColor}66` }} />
          {artifact.status==='complete' && <span className="font-mono-label text-[9px] text-on-surface-variant/35">{artifact.confidence}% conf</span>}
          {artifact.status==='building' && <span className="font-mono-label text-[9px] text-primary/50">Building…</span>}
          {artifact.status==='queued'   && <span className="font-mono-label text-[9px] text-on-surface-variant/25">Queued</span>}
        </div>
      </div>
      {artifact.status==='complete' && (
        <div className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center"
          style={{ background:`conic-gradient(#a5e7ff ${artifact.confidence*3.6}deg, rgb(var(--c-overlay) / 0.04) 0deg)` }}>
          <div className="w-5 h-5 rounded-full bg-[#09090E] flex items-center justify-center">
            <span className="font-mono-label text-[7px] text-primary font-bold">{artifact.confidence}</span>
          </div>
        </div>
      )}
    </button>
  );
}

// ─── Center Panel: Content Renderers ──────────────────────────────────────────

function Traceable({ traceId, children, onTrace, active }: { traceId:string; children:React.ReactNode; onTrace:(id:string)=>void; active:boolean }) {
  return (
    <span
      onClick={()=>onTrace(traceId)}
      className={`cursor-pointer transition-all duration-200 rounded px-0.5
        ${active
          ? 'text-primary bg-primary/10 border-b border-primary'
          : 'text-primary/80 border-b border-dashed border-primary/35 hover:text-primary hover:border-primary/70 hover:bg-primary/[0.05]'
        }`}>
      {children}
      <span className="material-symbols-outlined text-[10px] ml-0.5 align-middle opacity-60">link</span>
    </span>
  );
}

function ResearchContent({ onTrace, activeTrace }: { onTrace:(id:string)=>void; activeTrace:string|null }) {
  const PAIN_POINTS = [
    { label:'ATS False-Negative Rate', value:75, unit:'% of qualified candidates rejected', conf:94, traceId:'ats-fnr', sources:47 },
    { label:'Manual Screening Time',   value:5,  unit:'+ hours/week per recruiter',          conf:88, traceId:'manual-time', sources:24 },
    { label:'Keyword Bias Incidence',  value:68, unit:'% of rejections bias-attributable',   conf:82, traceId:'ats-fnr', sources:18 },
  ];
  const COMPETITORS = [
    { name:'Greenhouse',  ai:'✗', smb:'✗', semantic:'✗', price:'$$$$',  threat:'Low'    },
    { name:'Workday ATS', ai:'✗', smb:'✗', semantic:'~', price:'$$$$$', threat:'Medium' },
    { name:'Lever',       ai:'✗', smb:'✓', semantic:'✗', price:'$$$',   threat:'Medium' },
    { name:'Rippling HR', ai:'~', smb:'✓', semantic:'✗', price:'$$$',   threat:'High'   },
    { name:'APS (this)',  ai:'✓', smb:'✓', semantic:'✓', price:'$$',    threat:'—'      },
  ];

  return (
    <div className="space-y-8">
      {/* Executive Summary */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <div className="h-px flex-1 bg-white/[0.05]" />
          <span className="font-mono-label text-[10px] text-on-surface-variant/40 uppercase tracking-[0.2em]">Executive Summary</span>
          <div className="h-px flex-1 bg-white/[0.05]" />
        </div>
        <p className="text-[14px] text-on-surface/70 leading-[1.8] font-body-lg">
          APS has identified a{' '}
          <Traceable traceId="tam" onTrace={onTrace} active={activeTrace==='tam'}>
            $8.4B total addressable market
          </Traceable>
          {' '}in the B2B HR Technology sector, specifically within Applicant Tracking Systems (ATS).
          Research across 8 independent data sources yielded 47 unique evidence nodes confirming systemic failure in
          current ATS platforms — particularly their inability to evaluate candidates against job description semantics.
        </p>
        <p className="text-[14px] text-on-surface/70 leading-[1.8] font-body-lg mt-4">
          The most critical finding:{' '}
          <Traceable traceId="ats-fnr" onTrace={onTrace} active={activeTrace==='ats-fnr'}>
            ATS false-negative rates reaching 75% of qualified candidates
          </Traceable>
          {' '}across enterprise deployments. Simultaneously,{' '}
          <Traceable traceId="no-smb" onTrace={onTrace} active={activeTrace==='no-smb'}>
            no AI-native ATS solution targeting SMBs exists
          </Traceable>
          {' '}in the current market, creating a clear and defensible entry point.
        </p>
      </section>

      {/* Market Sizing */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <div className="h-px flex-1 bg-white/[0.05]" />
          <span className="font-mono-label text-[10px] text-on-surface-variant/40 uppercase tracking-[0.2em]">Market Sizing</span>
          <div className="h-px flex-1 bg-white/[0.05]" />
        </div>
        <div className="space-y-3">
          {[
            { label:'TAM — Total Addressable Market', value:'$8.4B',  pct:100, sublabel:'Global ATS + HR automation spend' },
            { label:'SAM — Serviceable Available',    value:'$1.2B',  pct:14,  sublabel:'SMB segment with active hiring' },
            { label:'SOM — Serviceable Obtainable',   value:'$120M',  pct:1.4, sublabel:'AI-native early adopters, Year 1–2' },
          ].map(m=>(
            <div key={m.label} className="flex items-center gap-4 group">
              <div className="w-44 flex-shrink-0">
                <div className="font-mono-label text-[11px] text-on-surface/70">{m.label}</div>
                <div className="font-mono-label text-[9px] text-on-surface-variant/30 mt-0.5">{m.sublabel}</div>
              </div>
              <div className="flex-1 h-2 bg-white/[0.04] rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all duration-1000"
                  style={{ width:`${Math.max(m.pct, 1.5)}%`, background:'linear-gradient(90deg,rgb(var(--c-primary) / 0.4),#a5e7ff)', boxShadow:'0 0 8px rgb(var(--c-primary) / 0.3)' }} />
              </div>
              <span className="font-mono-label text-[14px] font-bold text-primary w-16 text-right">{m.value}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Pain Points */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <div className="h-px flex-1 bg-white/[0.05]" />
          <span className="font-mono-label text-[10px] text-on-surface-variant/40 uppercase tracking-[0.2em]">Validated Pain Points</span>
          <div className="h-px flex-1 bg-white/[0.05]" />
        </div>
        <div className="space-y-3">
          {PAIN_POINTS.map((p,i)=>(
            <div key={i}
              className={`p-4 rounded-xl border transition-all duration-200 cursor-pointer group
                ${activeTrace===p.traceId ? 'border-primary/25 bg-primary/[0.04]' : 'border-white/[0.06] bg-white/[0.015] hover:border-primary/15 hover:bg-primary/[0.02]'}`}
              onClick={()=>onTrace(p.traceId)}>
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="text-[13px] font-semibold text-on-surface">{p.label}</div>
                  <div className="font-mono-label text-[11px] text-on-surface-variant/45 mt-0.5">{p.unit}</div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className="font-mono-label text-[10px] text-on-surface-variant/30">{p.sources} sources</span>
                  <span className="font-mono-label text-[11px] font-bold text-primary">{p.conf}%</span>
                </div>
              </div>
              <div className="h-1.5 bg-white/[0.04] rounded-full overflow-hidden">
                <div className="h-full rounded-full" style={{
                  width:`${p.value}%`,
                  background:`linear-gradient(90deg, rgb(var(--c-primary) / 0.4), #a5e7ff)`,
                  boxShadow:'0 0 8px rgb(var(--c-primary) / 0.35)'
                }} />
              </div>
              <div className="flex items-center justify-between mt-1.5">
                <span className="font-mono-label text-[9px] text-on-surface-variant/25">0%</span>
                <span className="font-mono-label text-[12px] font-bold text-primary">{p.value}{p.unit.startsWith('+') ? '+' : '%'}</span>
                <span className="font-mono-label text-[9px] text-on-surface-variant/25">100%</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Competitor Matrix */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <div className="h-px flex-1 bg-white/[0.05]" />
          <span className="font-mono-label text-[10px] text-on-surface-variant/40 uppercase tracking-[0.2em]">Competitor Matrix</span>
          <div className="h-px flex-1 bg-white/[0.05]" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-white/[0.05]">
                {['Company','AI Native','SMB Focus','Semantic CV','Price','Threat'].map(h=>(
                  <th key={h} className="pb-2 pr-4 font-mono-label text-[10px] text-on-surface-variant/35 uppercase tracking-[0.12em]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {COMPETITORS.map((c,i)=>{
                const isUs = c.name.startsWith('APS');
                return (
                  <tr key={i} className={`border-b transition-colors
                    ${isUs ? 'border-primary/15 bg-primary/[0.03]' : 'border-white/[0.03] hover:bg-white/[0.015]'}`}>
                    <td className={`py-2.5 pr-4 font-mono-label text-[12px] ${isUs ? 'text-primary font-bold' : 'text-on-surface/70'}`}>{c.name}</td>
                    {[c.ai,c.smb,c.semantic].map((v,j)=>(
                      <td key={j} className="py-2.5 pr-4">
                        <span className={`font-mono-label text-[13px] ${v==='✓' ? 'text-secondary-fixed' : v==='~' ? 'text-[#f59e0b]' : 'text-on-surface-variant/25'}`}>{v}</span>
                      </td>
                    ))}
                    <td className="py-2.5 pr-4 font-mono-label text-[11px] text-on-surface-variant/45">{c.price}</td>
                    <td className="py-2.5">
                      <span className={`px-2 py-0.5 rounded-full font-mono-label text-[9px] font-bold
                        ${c.threat==='Low' ? 'bg-secondary-fixed/10 text-secondary-fixed' : c.threat==='High' ? 'bg-[#f59e0b]/10 text-[#f59e0b]' : c.threat==='Medium' ? 'bg-primary/10 text-primary' : 'bg-primary/10 text-primary'}`}>
                        {c.threat}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Key Findings */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <div className="h-px flex-1 bg-white/[0.05]" />
          <span className="font-mono-label text-[10px] text-on-surface-variant/40 uppercase tracking-[0.2em]">Key Intelligence Findings</span>
          <div className="h-px flex-1 bg-white/[0.05]" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { icon:'lightbulb', color:'rgb(var(--c-primary))', title:'Market Gap Confirmed',       body:'No competitor combines AI-native CV scoring with SMB pricing. Defensible 18-month window.' },
            { icon:'trending_up', color:'#79ff5b', title:'Strong Tailwinds',          body:'Remote hiring surge +340% post-2020. SMB hiring budget increasing 28% YoY.' },
            { icon:'warning',   color:'#f59e0b',  title:'Competitive Risk',           body:'Workday and Greenhouse shipping AI features Q3. 6-month head-start window critical.' },
            { icon:'check_circle', color:'#79ff5b', title:'OSS Unlocks the Moat',    body:<><Traceable traceId="oss-moat" onTrace={onTrace} active={activeTrace==='oss-moat'}>OSS models eliminate the training-data moat</Traceable>. Mistral 7B achieves GPT-3.5 parity on classification.</> },
          ].map((f,i)=>(
            <div key={i} className="p-4 rounded-xl border border-white/[0.05] bg-white/[0.015] hover:border-white/[0.08] transition-colors">
              <div className="flex items-center gap-2 mb-2">
                <span className="material-symbols-outlined text-[16px]" style={{ color:f.color }}>{f.icon}</span>
                <span className="font-mono-label text-[11px] font-semibold text-on-surface">{f.title}</span>
              </div>
              <p className="text-[12px] text-on-surface-variant/55 leading-relaxed">{f.body}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function PRDContent({ onTrace }: { onTrace:(id:string)=>void; activeTrace:string|null }) {
  const STORIES = [
    { id:'US-001', epic:'Semantic Scoring', title:'CV Semantic Scoring Engine', priority:'P0', points:8,
      story:'As a recruiter, I want CVs automatically scored against job description semantics so that I can instantly identify top candidates without manual reading.',
      criteria:['Score 0–100 with confidence band','Explanation of score reasoning per section','Highlight matching semantic clusters','Process 100 CVs in <30 seconds'] },
    { id:'US-002', epic:'Semantic Scoring', title:'Bias Detection Report',      priority:'P0', points:5,
      story:'As an HR Manager, I want a bias analysis report per batch so that I can ensure equitable candidate evaluation.',
      criteria:['Flag keyword-bias patterns','Show demographic-neutral scoring comparison','Exportable compliance report (PDF)'] },
    { id:'US-003', epic:'Workflow',          title:'Bulk Upload & Processing',  priority:'P1', points:3,
      story:'As a recruiter, I want to upload 200 CVs in a ZIP and receive ranked results in one click.',
      criteria:['ZIP + individual PDF support','Max 500 CVs per batch','Async processing with progress','Email notification on completion'] },
    { id:'US-004', epic:'Integration',       title:'ATS API Integration',       priority:'P1', points:8,
      story:'As a technical buyer, I want an API to integrate APS scoring into our existing ATS workflow.',
      criteria:['REST + webhook support','OpenAPI 3.0 spec','SDK for Python, Node, Java','99.9% uptime SLA'] },
  ];

  const FEATURES = [
    { name:'Semantic CV Scoring',  impact:5, effort:3, priority:'P0', status:'in-scope'    },
    { name:'Bias Detection',       impact:5, effort:4, priority:'P0', status:'in-scope'    },
    { name:'Batch Upload',         impact:4, effort:2, priority:'P1', status:'in-scope'    },
    { name:'API Integration',      impact:4, effort:3, priority:'P1', status:'in-scope'    },
    { name:'Analytics Dashboard',  impact:3, effort:3, priority:'P2', status:'v2'          },
    { name:'Candidate Messaging',  impact:2, effort:2, priority:'P3', status:'out-of-scope' },
    { name:'Video Screening',      impact:2, effort:5, priority:'P3', status:'out-of-scope' },
  ];

  return (
    <div className="space-y-8">
      {/* Goals */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <div className="h-px flex-1 bg-white/[0.05]" />
          <span className="font-mono-label text-[10px] text-on-surface-variant/40 uppercase tracking-[0.2em]">Product Goals</span>
          <div className="h-px flex-1 bg-white/[0.05]" />
        </div>
        <div className="space-y-2">
          {[
            { metric:'Reduce time-to-hire',           target:'60% reduction',     evidence:'manual-time' },
            { metric:'Eliminate keyword-bias rejection', target:'<5% bias rate',   evidence:'ats-fnr' },
            { metric:'Candidate quality match',        target:'>85% accuracy',     evidence:'ats-fnr' },
          ].map((g,i)=>(
            <div key={i} className="flex items-center gap-4 p-3 rounded-lg border border-white/[0.04] bg-white/[0.01] hover:border-white/[0.07] transition-colors group">
              <span className="w-5 h-5 rounded-full bg-primary/10 border border-primary/25 flex items-center justify-center flex-shrink-0">
                <span className="font-mono-label text-[9px] text-primary font-bold">{i+1}</span>
              </span>
              <span className="text-[13px] text-on-surface/70 flex-1">{g.metric}</span>
              <span className="font-mono-label text-[11px] font-bold text-secondary-fixed">{g.target}</span>
              <button onClick={()=>onTrace(g.evidence)}
                className="font-mono-label text-[9px] text-primary/40 hover:text-primary opacity-0 group-hover:opacity-100 transition-all flex items-center gap-1">
                <span className="material-symbols-outlined text-[11px]">link</span> trace
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* User Stories */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <div className="h-px flex-1 bg-white/[0.05]" />
          <span className="font-mono-label text-[10px] text-on-surface-variant/40 uppercase tracking-[0.2em]">User Stories</span>
          <div className="h-px flex-1 bg-white/[0.05]" />
        </div>
        <div className="space-y-3">
          {STORIES.map(s=>(
            <div key={s.id} className="rounded-xl border border-white/[0.06] bg-white/[0.015] overflow-hidden group hover:border-white/[0.09] transition-colors">
              <div className="flex items-center gap-3 px-4 py-3 border-b border-white/[0.04]">
                <span className="font-mono-label text-[10px] text-primary/60 flex-shrink-0">{s.id}</span>
                <span className="font-mono-label text-[9px] text-on-surface-variant/30 px-2 py-0.5 rounded-full border border-white/[0.05]">{s.epic}</span>
                <span className="text-[13px] font-semibold text-on-surface flex-1">{s.title}</span>
                <span className={`px-2 py-0.5 rounded-full font-mono-label text-[9px] font-bold
                  ${s.priority==='P0' ? 'bg-[#f59e0b]/10 text-[#f59e0b]' : s.priority==='P1' ? 'bg-primary/10 text-primary' : 'bg-white/[0.05] text-on-surface-variant/40'}`}>
                  {s.priority}
                </span>
                <span className="font-mono-label text-[9px] text-on-surface-variant/30">{s.points}pts</span>
              </div>
              <div className="px-4 py-3">
                <p className="text-[12px] text-on-surface-variant/55 leading-relaxed mb-3 italic">"{s.story}"</p>
                <div className="grid grid-cols-1 gap-1">
                  {s.criteria.map((c,j)=>(
                    <div key={j} className="flex items-start gap-2">
                      <span className="material-symbols-outlined text-secondary-fixed text-[12px] flex-shrink-0 mt-px">check</span>
                      <span className="text-[12px] text-on-surface-variant/50">{c}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Feature Priority Matrix */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <div className="h-px flex-1 bg-white/[0.05]" />
          <span className="font-mono-label text-[10px] text-on-surface-variant/40 uppercase tracking-[0.2em]">Feature Priority Matrix</span>
          <div className="h-px flex-1 bg-white/[0.05]" />
        </div>
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-white/[0.05]">
              {['Feature','Impact','Effort','Priority','Scope'].map(h=>(
                <th key={h} className="pb-2 pr-4 font-mono-label text-[10px] text-on-surface-variant/35 uppercase tracking-[0.12em]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {FEATURES.map((f,i)=>(
              <tr key={i} className={`border-b border-white/[0.03] hover:bg-white/[0.01] transition-colors`}>
                <td className="py-2.5 pr-4 text-[12px] text-on-surface/70">{f.name}</td>
                <td className="py-2.5 pr-4">
                  <div className="flex gap-0.5">
                    {Array.from({length:5}).map((_,j)=>(
                      <div key={j} className="w-2 h-2 rounded-sm" style={{ background: j<f.impact ? 'rgb(var(--c-primary))' : 'rgb(var(--c-overlay) / 0.06)', boxShadow: j<f.impact ? '0 0 3px rgb(var(--c-primary) / 0.4)' : 'none' }} />
                    ))}
                  </div>
                </td>
                <td className="py-2.5 pr-4">
                  <div className="flex gap-0.5">
                    {Array.from({length:5}).map((_,j)=>(
                      <div key={j} className="w-2 h-2 rounded-sm" style={{ background: j<f.effort ? '#f59e0b55' : 'rgb(var(--c-overlay) / 0.06)' }} />
                    ))}
                  </div>
                </td>
                <td className="py-2.5 pr-4">
                  <span className={`px-2 py-0.5 rounded-full font-mono-label text-[9px] font-bold
                    ${f.priority==='P0' ? 'bg-[#f59e0b]/10 text-[#f59e0b]' : f.priority==='P1' ? 'bg-primary/10 text-primary' : 'bg-white/[0.05] text-on-surface-variant/35'}`}>
                    {f.priority}
                  </span>
                </td>
                <td className="py-2.5">
                  <span className={`font-mono-label text-[10px]
                    ${f.status==='in-scope' ? 'text-secondary-fixed' : f.status==='v2' ? 'text-primary/60' : 'text-on-surface-variant/25'}`}>
                    {f.status==='in-scope' ? '✓ In Scope' : f.status==='v2' ? '→ v2' : '✗ Out'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function RoadmapContent() {
  const PHASES = [
    {
      phase:'Phase 1: Foundation', period:'Month 1–3', color:'rgb(var(--c-primary))',
      milestones:[
        { label:'Semantic scoring engine MVP',    week:2, done:false },
        { label:'CV parsing pipeline',             week:4, done:false },
        { label:'Bias detection v1',               week:6, done:false },
        { label:'Private beta: 10 SMB recruiters', week:12, done:false },
      ]
    },
    {
      phase:'Phase 2: Market Fit', period:'Month 4–6', color:'#79ff5b',
      milestones:[
        { label:'ATS API integration',            week:16, done:false },
        { label:'Analytics dashboard',            week:18, done:false },
        { label:'50 paying customers',            week:24, done:false },
      ]
    },
    {
      phase:'Phase 3: Scale', period:'Month 7–9', color:'#f59e0b',
      milestones:[
        { label:'Enterprise tier launch',         week:28, done:false },
        { label:'SOC 2 compliance',               week:32, done:false },
        { label:'Series A ready',                 week:36, done:false },
      ]
    },
  ];

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-2 mb-2">
        <div className="h-px flex-1 bg-white/[0.05]" />
        <span className="font-mono-label text-[10px] text-on-surface-variant/40 uppercase tracking-[0.2em]">Execution Timeline</span>
        <div className="h-px flex-1 bg-white/[0.05]" />
      </div>

      {/* Timeline bar */}
      <div className="relative">
        <div className="flex items-center gap-0 mb-3">
          {Array.from({length:9}).map((_,i)=>(
            <div key={i} className="flex-1 text-center">
              <span className="font-mono-label text-[9px] text-on-surface-variant/25">M{i+1}</span>
            </div>
          ))}
        </div>
        <div className="flex h-2 rounded-full overflow-hidden gap-px">
          <div className="w-1/3 bg-primary/25 rounded-l-full" style={{ boxShadow:'0 0 8px rgb(var(--c-primary) / 0.25)' }} />
          <div className="w-1/3 bg-secondary-fixed/20" style={{ boxShadow:'0 0 8px rgba(121,255,91,0.15)' }} />
          <div className="w-1/3 bg-[#f59e0b]/18 rounded-r-full" />
        </div>
      </div>

      {PHASES.map((ph,pi)=>(
        <div key={pi} className="rounded-xl border border-white/[0.05] bg-white/[0.01] overflow-hidden">
          <div className="flex items-center gap-3 px-4 py-3 border-b border-white/[0.04]" style={{ borderLeftColor:ph.color+'44', borderLeftWidth:3 }}>
            <div className="w-2 h-2 rounded-full" style={{ background:ph.color, boxShadow:`0 0 6px ${ph.color}` }} />
            <span className="font-mono-label text-[12px] font-semibold text-on-surface">{ph.phase}</span>
            <span className="ml-auto font-mono-label text-[10px] text-on-surface-variant/35">{ph.period}</span>
          </div>
          <div className="px-4 py-3 space-y-2">
            {ph.milestones.map((m,mi)=>(
              <div key={mi} className="flex items-center gap-3 group">
                <div className="w-5 h-5 rounded-full border border-white/[0.08] flex items-center justify-center flex-shrink-0"
                  style={{ borderColor:`${ph.color}33` }}>
                  <span className="font-mono-label text-[8px]" style={{ color:ph.color+'99' }}>{mi+1}</span>
                </div>
                <span className="text-[12px] text-on-surface/65 flex-1">{m.label}</span>
                <span className="font-mono-label text-[10px] text-on-surface-variant/25">Wk {m.week}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Architecture (TRD) — live mermaid diagrams from /v1 ──────────────────────

const ARCH_SEED = [
  `flowchart TD
    UI["Web Client"] --> API["API Gateway"]
    API --> AUTH["Auth Service"]
    API --> PARSE["Resume Parser"]
    PARSE --> RANK["Ranking Engine"]
    RANK --> DB[("Postgres")]
    PARSE --> VEC[("Vector Store")]
    RANK --> VEC`,
  `erDiagram
    USER ||--o{ JOB : posts
    JOB ||--o{ CANDIDATE : receives
    CANDIDATE ||--|| SCORE : has
    USER { int id string email }
    CANDIDATE { int id string resume_url float match }`,
];

function ArchitectureContent({ runId }: { runId: string }) {
  const [blocks, setBlocks] = useState<string[]>(ARCH_SEED);
  useEffect(() => {
    let alive = true;
    const run = runId || getActiveRun();
    if (!run) { setBlocks(ARCH_SEED); return; }
    api.artifactMermaid('trd', run)
      .then((d:any) => {
        if (!alive) return;
        const found = extractMermaidBlocks(d?.body ?? '');
        setBlocks(found.length ? found : ARCH_SEED);
      })
      .catch(() => { if (alive) setBlocks(ARCH_SEED); });   // keep seed diagrams offline
    return () => { alive = false; };
  }, [runId]);
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 mb-1">
        <span className="material-symbols-outlined text-primary text-[16px]">schema</span>
        <h3 className="text-[14px] font-semibold text-on-surface">System Architecture</h3>
        <span className="ml-auto font-mono-label text-[9px] text-on-surface-variant/35 uppercase">Live · Mermaid</span>
      </div>
      {blocks.map((b, i) => (
        <div key={i} className="rounded-xl border border-white/[0.06] bg-[#0A0C11]/60 p-4">
          <div className="font-mono-label text-[10px] text-on-surface-variant/40 uppercase tracking-[0.12em] mb-3">
            {b.trimStart().startsWith('er') ? 'Data Model (ER)' : 'Component Flow'}
          </div>
          <MermaidDiagram source={b} />
        </div>
      ))}
      {/* The full per-run TRD (API contract, data model, NFRs) below the diagrams. Renders the
          real backend markdown; shows nothing extra when there's no live content. */}
      <MarkdownArtifact artifactId="trd" run={runId} fallback={null} />
    </div>
  );
}

function BuildingContent({ artifact }: { artifact: typeof ARTIFACTS[0] }) {
  const [pct, setPct] = useState(72);
  const steps = ['Analyzing PRD requirements…','Mapping data models…','Generating API surface…','Designing system architecture…','Validating scalability constraints…'];
  const step = 3;

  useEffect(()=>{
    const iv = setInterval(()=>{ setPct(p=>p>=97?72:p+0.4); }, 250);
    return ()=>clearInterval(iv);
  },[]);

  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-center px-8">
      <div className="relative mb-8">
        <svg width="120" height="120" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="52" fill="none" stroke="rgb(var(--c-overlay) / 0.04)" strokeWidth="4" />
          <circle cx="60" cy="60" r="52" fill="none" stroke="#a5e7ff" strokeWidth="4"
            strokeDasharray={`${2*Math.PI*52}`} strokeDashoffset={`${2*Math.PI*52*(1-pct/100)}`}
            strokeLinecap="round" transform="rotate(-90 60 60)"
            style={{ filter:'drop-shadow(0 0 8px rgb(var(--c-primary) / 0.6))', transition:'stroke-dashoffset 0.3s ease' }} />
          <text x="60" y="56" textAnchor="middle" fill="#a5e7ff" fontSize="20" fontWeight="700" fontFamily="JetBrains Mono,monospace">{Math.round(pct)}%</text>
          <text x="60" y="72" textAnchor="middle" fill="#bbc9cf" fontSize="9" fontFamily="JetBrains Mono,monospace" opacity="0.5">GENERATING</text>
        </svg>
        <div className="absolute inset-0 rounded-full border border-primary/10 animate-ping" style={{ animationDuration:'3s' }} />
      </div>
      <div className="font-mono-label text-[14px] text-on-surface font-bold mb-2">{artifact.name}</div>
      <div className="font-mono-label text-[11px] text-primary/60 mb-6">Intelligence being constructed…</div>
      <div className="w-full max-w-sm space-y-2">
        {steps.map((s,i)=>(
          <div key={i} className={`flex items-center gap-2.5 px-3 py-2 rounded-lg border transition-all
            ${i<step ? 'border-secondary-fixed/12 bg-secondary-fixed/[0.02]' : i===step ? 'border-primary/20 bg-primary/[0.03]' : 'border-transparent opacity-30'}`}>
            {i<step  ? <span className="material-symbols-outlined text-secondary-fixed text-[14px]">check_circle</span> : null}
            {i===step ? <div className="flex gap-0.5">{[0,1,2].map(j=><div key={j} className="w-1 h-1 rounded-full bg-primary/60" style={{ animation:`thinkDot 1.4s ${j*0.2}s ease-in-out infinite` }} />)}</div> : null}
            {i>step   ? <span className="w-3.5 h-3.5 rounded-full border border-white/[0.08] flex-shrink-0" /> : null}
            <span className={`font-mono-label text-[11px] ${i===step?'text-primary':i<step?'text-secondary-fixed/60':'text-on-surface-variant/25'}`}>{s}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function QueuedContent({ artifact }: { artifact: typeof ARTIFACTS[0] }) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-center px-8">
      <div className="w-16 h-16 rounded-2xl bg-white/[0.03] border border-white/[0.07] flex items-center justify-center mb-6">
        <span className="material-symbols-outlined text-on-surface-variant/25 text-[32px]">{artifact.icon}</span>
      </div>
      <div className="font-mono-label text-[14px] text-on-surface/50 font-bold mb-2">{artifact.name}</div>
      <div className="font-mono-label text-[11px] text-on-surface-variant/30 mb-6">Awaiting predecessor artifacts</div>
      <div className="flex items-center gap-2 px-4 py-2 rounded-full border border-white/[0.06] bg-white/[0.02]">
        <span className="material-symbols-outlined text-on-surface-variant/25 text-[14px]">schedule</span>
        <span className="font-mono-label text-[11px] text-on-surface-variant/30">In queue · {artifact.agents.join(', ')} standing by</span>
      </div>
    </div>
  );
}

function EvidenceView({ artifact, activeTrace, onTrace }: { artifact:typeof ARTIFACTS[0]; activeTrace:string|null; onTrace:(id:string)=>void }) {
  const relevantTraces = Object.keys(TRACES).slice(0, artifact.evidenceCount > 0 ? 4 : 0);
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 mb-4">
        <div className="h-px flex-1 bg-white/[0.05]" />
        <span className="font-mono-label text-[10px] text-on-surface-variant/40 uppercase tracking-[0.2em]">Evidence Traceability</span>
        <div className="h-px flex-1 bg-white/[0.05]" />
      </div>
      {relevantTraces.length === 0 && (
        <div className="text-center py-12 text-on-surface-variant/30 font-mono-label text-[12px]">No evidence generated yet</div>
      )}
      {relevantTraces.map(traceId => {
        const trace = TRACES[traceId];
        const isActive = activeTrace === traceId;
        return (
          <div key={traceId}
            className={`rounded-xl border transition-all duration-200 overflow-hidden cursor-pointer
              ${isActive ? 'border-primary/25 bg-primary/[0.03]' : 'border-white/[0.06] hover:border-primary/15'}`}
            onClick={()=>onTrace(traceId)}>
            <div className="px-4 py-3 border-b border-white/[0.04] flex items-start gap-2">
              <span className="material-symbols-outlined text-primary text-[14px] flex-shrink-0 mt-0.5">link</span>
              <span className="text-[12px] text-on-surface/75 leading-snug">"{trace.label}"</span>
            </div>
            {isActive && (
              <div className="px-4 py-3 space-y-2">
                {trace.sources.map((s,i)=>(
                  <div key={i} className="flex items-start gap-3 p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                    <div className="w-6 h-6 rounded-md bg-primary/10 border border-primary/15 flex items-center justify-center flex-shrink-0">
                      <span className="material-symbols-outlined text-primary text-[12px]">{s.icon}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono-label text-[10px] text-primary/70 font-bold">{s.platform}</span>
                        <span className="font-mono-label text-[9px] text-secondary-fixed/60">{s.count} sources</span>
                      </div>
                      <div className="space-y-0.5">
                        {s.examples.slice(0,2).map((e,j)=>(
                          <div key={j} className="font-mono-label text-[10px] text-on-surface-variant/40 truncate">· {e}</div>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
                {/* Chain visualization */}
                <div className="mt-3 pt-3 border-t border-white/[0.04]">
                  <div className="flex items-center gap-2 overflow-x-auto py-1">
                    {['Source','Finding','Requirement','Architecture','Artifact'].map((n,i,arr)=>(
                      <div key={n} className="flex items-center gap-2 flex-shrink-0">
                        <div className="px-2 py-1 rounded bg-white/[0.04] border border-white/[0.07]">
                          <span className="font-mono-label text-[9px] text-on-surface-variant/45">{n}</span>
                        </div>
                        {i<arr.length-1 && <span className="text-primary/30 text-[10px]">→</span>}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function VersionsView({ artifact }: { artifact: typeof ARTIFACTS[0] }) {
  const [comparing, setComparing] = useState(false);
  if (artifact.versions === 0) return (
    <div className="text-center py-12 text-on-surface-variant/30 font-mono-label text-[12px]">No versions yet</div>
  );
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-4">
        <div className="h-px flex-1 bg-white/[0.05]" />
        <span className="font-mono-label text-[10px] text-on-surface-variant/40 uppercase tracking-[0.2em]">Version History</span>
        <div className="h-px flex-1 bg-white/[0.05]" />
      </div>
      <div className="flex items-center justify-end mb-2">
        <button onClick={()=>setComparing(c=>!c)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border font-mono-label text-[10px] transition-all
            ${comparing ? 'bg-primary/10 border-primary/25 text-primary' : 'border-white/[0.07] text-on-surface-variant/40 hover:border-white/10 hover:text-on-surface-variant/60'}`}>
          <span className="material-symbols-outlined text-[13px]">compare</span>
          {comparing ? 'Exit Compare' : 'Compare Versions'}
        </button>
      </div>
      <div className="relative">
        <div className="absolute left-5 top-0 bottom-0 w-px bg-white/[0.06]" />
        <div className="space-y-4">
          {VERSIONS.map((v,i)=>(
            <div key={i} className="flex gap-4 relative">
              <div className={`w-10 h-10 rounded-xl border flex items-center justify-center flex-shrink-0 z-10
                ${v.current ? 'bg-primary/10 border-primary/30' : 'bg-white/[0.03] border-white/[0.07]'}`}>
                <span className={`font-mono-label text-[10px] font-bold ${v.current ? 'text-primary' : 'text-on-surface-variant/35'}`}>v{i+1}</span>
              </div>
              <div className={`flex-1 p-4 rounded-xl border transition-colors ${v.current ? 'border-primary/15 bg-primary/[0.02]' : 'border-white/[0.05]'}`}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono-label text-[12px] font-semibold text-on-surface">{v.label}</span>
                  {v.current && <span className="px-2 py-0.5 rounded-full bg-primary/10 border border-primary/20 font-mono-label text-[9px] text-primary">Current</span>}
                </div>
                <div className="font-mono-label text-[10px] text-on-surface-variant/35 mb-1">{v.time}</div>
                <div className="text-[12px] text-on-surface-variant/50">{v.note}</div>
                {comparing && i===0 && (
                  <div className="mt-3 pt-2 border-t border-white/[0.04] space-y-1">
                    <div className="flex items-center gap-2 text-[11px]">
                      <span className="text-[#f59e0b]/60">−</span>
                      <span className="text-on-surface-variant/40 line-through">Competitor count: 10</span>
                    </div>
                    <div className="flex items-center gap-2 text-[11px]">
                      <span className="text-secondary-fixed/60">+</span>
                      <span className="text-on-surface-variant/55">Competitor count: 14 (Rippling added)</span>
                    </div>
                    <div className="flex items-center gap-2 text-[11px]">
                      <span className="text-secondary-fixed/60">+</span>
                      <span className="text-on-surface-variant/55">TAM revised $7.1B → $8.4B from Gartner 2024</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Center Panel ──────────────────────────────────────────────────────────────

function ArtifactViewer({ artifact, onTrace, activeTrace, runId }: {
  artifact: typeof ARTIFACTS[0]; onTrace:(id:string)=>void; activeTrace:string|null; runId:string;
}) {
  const [tab, setTab] = useState<CenterTab>('overview');
  const [exportOpen, setExportOpen] = useState(false);
  const exportRef = useRef<HTMLDivElement>(null);
  const [exportLoading, setExportLoading] = useState<string|null>(null);
  const [exportMsg, setExportMsg] = useState<{text:string;ok:boolean}|null>(null);

  useEffect(()=>{
    setTab('overview');
    setExportMsg(null);
  },[artifact.id]);

  useEffect(()=>{
    function handler(e:MouseEvent) { if (exportRef.current && !exportRef.current.contains(e.target as Node)) setExportOpen(false); }
    document.addEventListener('mousedown', handler);
    return ()=>document.removeEventListener('mousedown', handler);
  },[]);

  function dlBlob(content:string, filename:string, mime:string) {
    const blob = new Blob([content], { type: mime });
    const url  = URL.createObjectURL(blob);
    const a    = Object.assign(document.createElement('a'), { href: url, download: filename });
    a.click();
    setTimeout(()=>URL.revokeObjectURL(url), 2000);
  }

  async function handleExport(label:string) {
    const exportRun = runId || getActiveRun() || 'RUN_0042';
    setExportOpen(false);
    setExportMsg(null);
    setExportLoading(label);
    try {
      if (label === 'Export PDF') {
        await exportArtifactPDF({ artifactId: artifact.id, artifactName: artifact.name, runId: exportRun });
        setExportMsg({ text: 'Opened a print-ready PDF — choose "Save as PDF".', ok: true });

      } else if (label === 'Export Markdown') {
        let md = `# ${artifact.name}\n\n${artifact.summary}`;
        try { const d = await api.artifactContent(artifact.id, exportRun); md = d?.body ?? md; } catch {}
        dlBlob(md, `${artifact.id}.md`, 'text/markdown');

      } else if (label === 'Export JSON') {
        let payload: any = { id: artifact.id, name: artifact.name, summary: artifact.summary };
        try { payload = await api.artifactContent(artifact.id, exportRun); } catch {}
        dlBlob(JSON.stringify(payload, null, 2), `${artifact.id}.json`, 'application/json');

      } else if (label === 'Export ZIP' || label === 'Investor Package') {
        const kind = label === 'Investor Package' ? 'investor' : 'all';
        const tok  = api.token() ?? '';
        const res  = await fetch(`/v1/runs/${exportRun}/export/zip?kind=${kind}`, {
          headers: tok ? { Authorization: `Bearer ${tok}` } : {},
        });
        if (!res.ok) throw new Error(`ZIP export failed (${res.status})`);
        const blob = await res.blob();
        const url  = URL.createObjectURL(blob);
        const fname = kind === 'investor' ? `aps-investor-package-${exportRun}.zip` : `aps-artifacts-${exportRun}.zip`;
        Object.assign(document.createElement('a'), { href: url, download: fname }).click();
        setTimeout(()=>URL.revokeObjectURL(url), 2000);
        setExportMsg({ text: `Downloaded ${fname}`, ok: true });

      } else if (label === 'Export to GitHub') {
        const result = await api.launch(exportRun, { dryRun: true });
        const msg = result?.repoUrl
          ? `GitHub repo ready: ${result.repoUrl}`
          : (result?.preview ?? 'GitHub preview generated. Add a PAT (APS_GITHUB_PAT) to create a real repo.');
        setExportMsg({ text: msg, ok: true });

      } else if (label === 'Export to Notion') {
        const result = await api.exportNotion(exportRun);
        setExportMsg({
          text: result?.message ?? 'Set NOTION_API_KEY and NOTION_PAGE_ID in .env to enable Notion export.',
          ok: result?.status === 'ok',
        });
      }
    } catch(err:any) {
      setExportMsg({ text: err?.message ?? 'Export failed — is the backend running?', ok: false });
    } finally {
      setExportLoading(null);
    }
  }

  const EXPORT_ITEMS = [
    { label:'Export PDF',        icon:'picture_as_pdf'  },
    { label:'Export Markdown',   icon:'description'     },
    { label:'Export JSON',       icon:'data_object'     },
    { label:'Export to GitHub',  icon:'code'            },
    { label:'Export to Notion',  icon:'article'         },
    { label:'Export ZIP',        icon:'folder_zip'      },
    { label:'Investor Package',  icon:'attach_money'    },
  ];

  return (
    <main className="flex-1 flex flex-col overflow-hidden bg-[#0C0E14]">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-white/[0.05] px-6 py-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center border flex-shrink-0
              ${artifact.status==='complete' ? 'bg-primary/10 border-primary/25' : artifact.status==='building' ? 'bg-primary/[0.06] border-primary/15' : 'bg-white/[0.02] border-white/[0.06]'}`}>
              <span className={`material-symbols-outlined text-[18px] ${artifact.status==='complete' ? 'text-primary' : artifact.status==='building' ? 'text-primary/50' : 'text-on-surface-variant/25'}`}>
                {artifact.icon}
              </span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[18px] font-bold text-on-surface">{artifact.name}</span>
                <StatusChip status={artifact.status} />
              </div>
              <div className="font-mono-label text-[10px] text-on-surface-variant/35 mt-0.5">{artifact.category} · {runId || 'RUN'} · {artifact.generatedAt || 'Pending'}</div>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {artifact.status === 'complete' && (
              <div className="flex flex-col items-end gap-2">
                <div className="relative" ref={exportRef}>
                  <button onClick={()=>setExportOpen(o=>!o)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/[0.08] bg-white/[0.03] hover:border-primary/25 hover:bg-primary/[0.03] transition-all text-on-surface-variant hover:text-primary font-mono-label text-[11px]">
                    {exportLoading
                      ? <span className="w-3 h-3 rounded-full border border-primary/40 border-t-primary animate-spin" />
                      : <span className="material-symbols-outlined text-[14px]">upload</span>
                    }
                    Export
                    <span className="material-symbols-outlined text-[12px]">{exportOpen?'expand_less':'expand_more'}</span>
                  </button>
                  {exportOpen && (
                    <div className="absolute right-0 top-full mt-1 w-52 bg-[#0D0F16] border border-white/[0.08] rounded-xl overflow-hidden shadow-2xl z-10"
                      style={{ animation:'streamIn 0.2s cubic-bezier(0.16,1,0.3,1) forwards' }}>
                      {EXPORT_ITEMS.map(({label,icon})=>(
                        <button key={label} onClick={()=>handleExport(label)}
                          disabled={!!exportLoading}
                          className="w-full text-left px-4 py-2.5 font-mono-label text-[11px] text-on-surface-variant/60 hover:bg-white/[0.04] hover:text-on-surface transition-colors flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed">
                          <span className="material-symbols-outlined text-[13px] text-primary/40">{icon}</span>
                          {label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                {exportMsg && (
                  <div className={`max-w-[280px] px-3 py-2 rounded-lg font-mono-label text-[10px] leading-relaxed border ${exportMsg.ok ? 'bg-secondary-fixed/[0.08] border-secondary-fixed/20 text-secondary-fixed/80' : 'bg-red-500/[0.08] border-red-500/20 text-red-400'}`}
                    style={{ animation:'fadeInUp 0.2s ease forwards' }}>
                    {exportMsg.text}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Tabs */}
        {artifact.status === 'complete' && (
          <div className="flex items-center gap-1">
            {(['overview','evidence','versions'] as CenterTab[]).map(t=>(
              <button key={t} onClick={()=>setTab(t)}
                className={`px-3 py-1.5 rounded-lg font-mono-label text-[11px] uppercase tracking-[0.1em] transition-all
                  ${tab===t ? 'bg-primary/10 text-primary border border-primary/20' : 'text-on-surface-variant/40 hover:text-on-surface-variant/70 hover:bg-white/[0.03]'}`}>
                {t}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-6 scrollbar-thin">
        {artifact.status === 'building' && <BuildingContent artifact={artifact} />}
        {artifact.status === 'queued'   && <QueuedContent artifact={artifact} />}
        {artifact.status === 'complete' && tab === 'overview' && (
          <>
            {/* Bespoke showcases hydrate to the selected run's REAL markdown when the backend has
                it, and fall back to their rich mock otherwise (market-analysis/roadmap have no
                backend artifact, so they always show the showcase). */}
            {artifact.id === 'research-brief'  && <MarkdownArtifact artifactId="research-brief"  run={runId} fallback={<ResearchContent onTrace={onTrace} activeTrace={activeTrace} />} />}
            {artifact.id === 'market-analysis' && <MarkdownArtifact artifactId="market-analysis" run={runId} fallback={<ResearchContent onTrace={onTrace} activeTrace={activeTrace} />} />}
            {artifact.id === 'prd'             && <MarkdownArtifact artifactId="prd"             run={runId} fallback={<PRDContent onTrace={onTrace} activeTrace={activeTrace} />} />}
            {artifact.id === 'trd'             && <ArchitectureContent runId={runId} />}
            {artifact.id === 'roadmap'         && <MarkdownArtifact artifactId="roadmap"         run={runId} fallback={<RoadmapContent />} />}
            {/* Every other artifact (Execution, Pitch, and the Launch Studio set: Brand, Legal,
                Funding, Name Availability, Compliance) renders its REAL markdown from the backend. */}
            {!['research-brief','market-analysis','prd','trd','roadmap'].includes(artifact.id) && (
              <MarkdownArtifact artifactId={artifact.id} run={runId} />
            )}
          </>
        )}
        {artifact.status === 'complete' && tab === 'evidence' && (
          <EvidenceView artifact={artifact} activeTrace={activeTrace} onTrace={onTrace} />
        )}
        {artifact.status === 'complete' && tab === 'versions' && (
          <VersionsView artifact={artifact} />
        )}
      </div>
    </main>
  );
}

function StatusChip({ status }: { status: ArtifactStatus }) {
  const cfg: Record<ArtifactStatus,{label:string;cls:string}> = {
    complete: { label:'Complete', cls:'bg-secondary-fixed/10 border-secondary-fixed/20 text-secondary-fixed' },
    building: { label:'Building', cls:'bg-primary/10 border-primary/20 text-primary' },
    queued:   { label:'Queued',   cls:'bg-white/[0.04] border-white/[0.08] text-on-surface-variant/35' },
  };
  const s = cfg[status];
  return (
    <span className={`px-2 py-0.5 rounded-full border font-mono-label text-[9px] font-bold uppercase tracking-[0.1em] ${s.cls}`}>{s.label}</span>
  );
}

// ─── Right Panel: Artifact Intelligence ───────────────────────────────────────

function ConfidenceRing({ value, size=100 }: { value:number; size?:number }) {
  const R = size*0.4, circ = 2*Math.PI*R;
  const dash = circ * (1 - value/100);
  const color = value >= 90 ? '#79ff5b' : value >= 70 ? 'rgb(var(--c-primary))' : '#f59e0b';
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size/2} cy={size/2} r={R} fill="none" stroke="rgb(var(--c-overlay) / 0.04)" strokeWidth="5" />
      <circle cx={size/2} cy={size/2} r={R} fill="none" stroke={color} strokeWidth="5"
        strokeDasharray={`${circ}`} strokeDashoffset={`${dash}`} strokeLinecap="round"
        transform={`rotate(-90 ${size/2} ${size/2})`}
        style={{ filter:`drop-shadow(0 0 8px ${color}66)`, transition:'stroke-dashoffset 1s ease' }} />
      <text x="50%" y="47%" textAnchor="middle" dominantBaseline="middle" fill={color}
        fontSize={size*0.18} fontWeight="700" fontFamily="JetBrains Mono,monospace">{value}%</text>
      <text x="50%" y="63%" textAnchor="middle" dominantBaseline="middle" fill="#bbc9cf"
        fontSize={size*0.09} fontFamily="JetBrains Mono,monospace" opacity="0.5">CONF</text>
    </svg>
  );
}

function DNAMini({ activeId }: { activeId: string }) {
  const nodes = [
    { id:'market',   label:'Market',    x:90,  y:30  },
    { id:'users',    label:'Users',     x:150, y:60  },
    { id:'compete',  label:'Compete',   x:150, y:115 },
    { id:'mono',     label:'Revenue',   x:90,  y:145 },
    { id:'arch',     label:'Arch',      x:30,  y:115 },
    { id:'features', label:'Features',  x:30,  y:60  },
    { id:'core',     label:'Startup',   x:90,  y:87, core:true },
  ];
  const edges = [
    {a:'core',b:'market'},{a:'core',b:'users'},{a:'core',b:'compete'},
    {a:'core',b:'mono'},{a:'core',b:'arch'},{a:'core',b:'features'},
  ];
  const contributed = {
    'research-brief':  ['market','compete'],
    'market-analysis': ['market','compete','mono'],
    'prd':             ['users','features'],
    'roadmap':         ['arch','features','mono'],
    'trd':             ['arch'],
    'pitch-deck':      ['market','mono'],
  }[activeId] ?? [];

  return (
    <svg viewBox="0 0 180 175" className="w-full" style={{ maxHeight:160 }}>
      {edges.map(e=>{
        const na=nodes.find(n=>n.id===e.a)!, nb=nodes.find(n=>n.id===e.b)!;
        const hot = contributed.includes(e.b)||contributed.includes(e.a);
        return (
          <line key={`${e.a}-${e.b}`} x1={na.x} y1={na.y} x2={nb.x} y2={nb.y}
            stroke={hot?'rgb(var(--c-primary))':'#3c494e'} strokeWidth={hot?1.2:0.6} opacity={hot?0.6:0.3} />
        );
      })}
      {nodes.map(n=>(
        <g key={n.id} transform={`translate(${n.x},${n.y})`}>
          <circle r={(n as any).core?12:8}
            fill={(n as any).core ? 'rgb(var(--c-primary) / 0.08)' : contributed.includes(n.id) ? 'rgb(var(--c-primary) / 0.06)' : 'rgb(var(--c-overlay) / 0.03)'}
            stroke={(n as any).core ? '#a5e7ff55' : contributed.includes(n.id) ? '#a5e7ff35' : '#3c494e33'}
            strokeWidth="1" />
          <circle r={2.5} fill={(n as any).core ? 'rgb(var(--c-primary))' : contributed.includes(n.id) ? 'rgb(var(--c-primary))' : '#3c494e'}
            opacity={(n as any).core ? 0.9 : contributed.includes(n.id) ? 0.7 : 0.3}
            style={contributed.includes(n.id) ? { filter:'drop-shadow(0 0 4px rgb(var(--c-primary) / 0.6))' } : {}} />
          <text y={(n as any).core?20:14} textAnchor="middle" fontSize="6.5" fill="#bbc9cf" opacity="0.45"
            style={{ fontFamily:'JetBrains Mono,monospace' }}>{n.label}</text>
        </g>
      ))}
    </svg>
  );
}

function ArtifactIntelligence({ artifact, activeTrace, onTrace, rightTab, setRightTab }: {
  artifact: typeof ARTIFACTS[0]; activeTrace:string|null; onTrace:(id:string)=>void;
  rightTab:RightTab; setRightTab:(t:RightTab)=>void;
}) {
  const traceData = activeTrace ? TRACES[activeTrace] : null;

  return (
    <aside className="w-[300px] flex-shrink-0 border-l border-white/[0.05] flex flex-col bg-[#09090E]">
      {/* Tab bar */}
      <div className="flex-shrink-0 border-b border-white/[0.04] flex">
        {(['intelligence','evidence','dna'] as RightTab[]).map(t=>(
          <button key={t} onClick={()=>setRightTab(t)}
            className={`flex-1 py-3 font-mono-label text-[10px] uppercase tracking-[0.1em] transition-all border-b-2
              ${rightTab===t ? 'text-primary border-primary' : 'text-on-surface-variant/30 border-transparent hover:text-on-surface-variant/50'}`}>
            {t}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin">

        {/* INTELLIGENCE TAB */}
        {rightTab === 'intelligence' && (
          <div className="p-4 space-y-5">
            {artifact.status === 'complete' ? (
              <>
                {/* Confidence ring + Quality */}
                <div className="flex items-center justify-around py-2">
                  <div className="flex flex-col items-center gap-1">
                    <ConfidenceRing value={artifact.confidence} size={90} />
                  </div>
                  <div className="flex flex-col items-center gap-1">
                    <div className="text-[36px] font-bold text-primary leading-none"
                      style={{ textShadow:'0 0 20px rgb(var(--c-primary) / 0.4)' }}>{artifact.quality}</div>
                    <div className="font-mono-label text-[9px] text-on-surface-variant/35 uppercase tracking-[0.15em]">Quality / 10</div>
                  </div>
                </div>

                {/* Stats grid */}
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { label:'Evidence',     value:`${artifact.evidenceCount}`, unit:'nodes'  },
                    { label:'Sources',      value:`${artifact.sourceCount}`,   unit:'platforms' },
                    { label:'Generated',    value:artifact.genTime,            unit:'runtime' },
                    { label:'Versions',     value:`${artifact.versions}`,      unit:'revisions' },
                  ].map(s=>(
                    <div key={s.label} className="p-3 rounded-xl border border-white/[0.05] bg-white/[0.015]">
                      <div className="font-mono-label text-[10px] text-on-surface-variant/35 uppercase tracking-[0.1em] mb-1">{s.label}</div>
                      <div className="font-mono-label text-[18px] font-bold text-on-surface leading-tight">{s.value}</div>
                      <div className="font-mono-label text-[9px] text-on-surface-variant/25">{s.unit}</div>
                    </div>
                  ))}
                </div>

                {/* Agent contributors */}
                <div>
                  <div className="font-mono-label text-[10px] text-on-surface-variant/35 uppercase tracking-[0.15em] mb-2">Agent Contributors</div>
                  <div className="space-y-1.5">
                    {artifact.agents.map(a=>{
                      const meta = AGENT_META[a] ?? { icon:'smart_toy' };
                      return (
                        <div key={a} className="flex items-center gap-2.5 p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                          <div className="w-7 h-7 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center flex-shrink-0">
                            <span className="material-symbols-outlined text-primary text-[14px]">{meta.icon}</span>
                          </div>
                          <span className="text-[12px] text-on-surface/65">{a}</span>
                          <span className="ml-auto flex h-1.5 w-1.5 rounded-full bg-secondary-fixed shadow-[0_0_4px_rgba(121,255,91,0.7)]" />
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* WHY THIS EXISTS */}
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="material-symbols-outlined text-[#f59e0b] text-[14px]">psychology</span>
                    <div className="font-mono-label text-[10px] text-[#f59e0b]/70 uppercase tracking-[0.15em]">Why This Exists</div>
                  </div>
                  <div className="p-3 rounded-xl border border-[#f59e0b]/12 bg-[#f59e0b]/[0.03] space-y-2">
                    {artifact.id === 'research-brief' && (
                      <>
                        <div className="font-mono-label text-[11px] text-on-surface/60 font-semibold">Resume Screening AI</div>
                        {[
                          { src:'47 GitHub discussions', note:'Engineering pain' },
                          { src:'24 Reddit threads', note:'Recruiter frustration' },
                          { src:'9 competitors analyzed', note:'Market gap confirmed' },
                        ].map((w,i)=>(
                          <div key={i} className="flex items-start gap-2">
                            <span className="material-symbols-outlined text-[#f59e0b]/50 text-[12px] flex-shrink-0 mt-0.5">arrow_forward</span>
                            <div>
                              <span className="font-mono-label text-[10px] text-[#f59e0b]/60">{w.src}</span>
                              <span className="font-mono-label text-[9px] text-on-surface-variant/30 ml-1">— {w.note}</span>
                            </div>
                          </div>
                        ))}
                        <div className="pt-2 border-t border-[#f59e0b]/10 flex items-center gap-2">
                          <span className="font-mono-label text-[10px] text-[#f59e0b]/50">Confidence</span>
                          <span className="font-mono-label text-[12px] font-bold text-[#f59e0b]">94%</span>
                        </div>
                      </>
                    )}
                    {artifact.id === 'prd' && (
                      <>
                        <div className="font-mono-label text-[11px] text-on-surface/60 font-semibold">Product Specification</div>
                        {[
                          { src:'Research Brief finding #1', note:'ATS false-negative problem' },
                          { src:'Research Brief finding #3', note:'SMB market gap' },
                          { src:'Competitor gap analysis', note:'No semantic scoring exists' },
                        ].map((w,i)=>(
                          <div key={i} className="flex items-start gap-2">
                            <span className="material-symbols-outlined text-[#f59e0b]/50 text-[12px] flex-shrink-0 mt-0.5">arrow_forward</span>
                            <div>
                              <span className="font-mono-label text-[10px] text-[#f59e0b]/60">{w.src}</span>
                              <span className="font-mono-label text-[9px] text-on-surface-variant/30 ml-1">— {w.note}</span>
                            </div>
                          </div>
                        ))}
                      </>
                    )}
                    {!['research-brief','prd'].includes(artifact.id) && (
                      <div className="font-mono-label text-[11px] text-on-surface-variant/30">Derived from upstream evidence and agent analysis for {artifact.category} phase.</div>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
                <span className="material-symbols-outlined text-on-surface-variant/20 text-[40px]">{artifact.icon}</span>
                <span className="font-mono-label text-[11px] text-on-surface-variant/30">
                  {artifact.status === 'building' ? 'Intelligence accumulating…' : 'Awaiting generation'}
                </span>
              </div>
            )}
          </div>
        )}

        {/* EVIDENCE TAB */}
        {rightTab === 'evidence' && (
          <div className="p-4">
            {traceData ? (
              <div className="space-y-4">
                <div className="flex items-center gap-2 mb-3">
                  <button onClick={()=>onTrace('')} className="w-6 h-6 rounded-md bg-white/[0.04] border border-white/[0.07] flex items-center justify-center hover:border-primary/20 transition-colors">
                    <span className="material-symbols-outlined text-[13px] text-on-surface-variant/40">arrow_back</span>
                  </button>
                  <span className="font-mono-label text-[10px] text-primary/60 uppercase tracking-[0.12em]">Active Trace</span>
                </div>
                <div className="p-3 rounded-xl border border-primary/15 bg-primary/[0.03] mb-4">
                  <div className="font-mono-label text-[11px] text-primary/70 leading-snug">"{traceData.label}"</div>
                </div>
                {/* Propagation chain */}
                <div className="space-y-1.5">
                  {['Raw Source','Evidence Node','Requirement','Architecture Decision','Artifact Section'].map((n,i)=>(
                    <div key={n} className="flex items-center gap-2">
                      <div className={`w-6 h-6 rounded-full border flex items-center justify-center flex-shrink-0
                        ${i===0 ? 'border-[#f59e0b]/30 bg-[#f59e0b]/10' : i===4 ? 'border-primary/30 bg-primary/10' : 'border-white/[0.08] bg-white/[0.02]'}`}>
                        <span className="font-mono-label text-[8px]" style={{ color: i===0?'#f59e0b':i===4?'rgb(var(--c-primary))':'#bbc9cf', opacity:0.7 }}>{i+1}</span>
                      </div>
                      <span className="font-mono-label text-[10px] text-on-surface-variant/45">{n}</span>
                      {i<4 && <span className="ml-auto text-on-surface-variant/20">↓</span>}
                    </div>
                  ))}
                </div>
                <div className="h-px bg-white/[0.04] my-3" />
                {traceData.sources.map((s,i)=>(
                  <div key={i} className="p-3 rounded-xl border border-white/[0.05] bg-white/[0.01] space-y-2">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-lg bg-primary/10 border border-primary/15 flex items-center justify-center flex-shrink-0">
                        <span className="material-symbols-outlined text-primary text-[13px]">{s.icon}</span>
                      </div>
                      <div>
                        <div className="font-mono-label text-[11px] text-primary/70 font-bold">{s.platform}</div>
                        <div className="font-mono-label text-[9px] text-secondary-fixed/55">{s.count} sources collected</div>
                      </div>
                    </div>
                    <div className="space-y-0.5">
                      {s.examples.map((ex,j)=>(
                        <div key={j} className="font-mono-label text-[10px] text-on-surface-variant/35 leading-snug pl-1">· {ex}</div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                <div className="font-mono-label text-[10px] text-on-surface-variant/35 uppercase tracking-[0.15em] mb-3">Click any underlined text in the viewer to trace its evidence</div>
                <div className="space-y-2">
                  {Object.entries(TRACES).map(([id,t])=>(
                    <button key={id} onClick={()=>{ setRightTab('evidence'); onTrace(id); }}
                      className="w-full text-left p-3 rounded-xl border border-white/[0.05] bg-white/[0.01] hover:border-primary/15 hover:bg-primary/[0.02] transition-all group">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="material-symbols-outlined text-primary/40 text-[13px] group-hover:text-primary/60">link</span>
                        <div className="flex gap-1.5">
                          {t.sources.map(s=>(
                            <span key={s.platform} className="font-mono-label text-[8px] text-on-surface-variant/30 px-1.5 py-0.5 rounded border border-white/[0.05]">{s.platform}</span>
                          ))}
                        </div>
                      </div>
                      <p className="font-mono-label text-[10px] text-on-surface-variant/50 leading-snug group-hover:text-on-surface-variant/70 transition-colors">"{t.label}"</p>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* DNA TAB */}
        {rightTab === 'dna' && (
          <div className="p-4 space-y-4">
            <div>
              <div className="font-mono-label text-[10px] text-on-surface-variant/35 uppercase tracking-[0.15em] mb-1">Startup DNA Contribution</div>
              <div className="font-mono-label text-[9px] text-on-surface-variant/22">Highlighted nodes impacted by this artifact</div>
            </div>
            <div className="rounded-xl border border-white/[0.05] bg-white/[0.01] p-3">
              <DNAMini activeId={artifact.id} />
            </div>
            <div className="space-y-2">
              <div className="font-mono-label text-[10px] text-on-surface-variant/35 uppercase tracking-[0.12em]">All Artifact Contributions</div>
              {ARTIFACTS.filter(a=>a.status==='complete').map(a=>(
                <div key={a.id} className={`flex items-center gap-2.5 p-2.5 rounded-lg border transition-colors cursor-pointer
                  ${a.id===artifact.id ? 'border-primary/20 bg-primary/[0.03]' : 'border-white/[0.04] hover:border-white/[0.07]'}`}>
                  <span className={`material-symbols-outlined text-[14px] ${a.id===artifact.id?'text-primary':'text-on-surface-variant/30'}`}>{a.icon}</span>
                  <span className={`text-[11px] flex-1 ${a.id===artifact.id?'text-on-surface':'text-on-surface-variant/45'}`}>{a.name}</span>
                  <div className="flex gap-0.5">
                    {Array.from({length:5}).map((_,i)=>(
                      <div key={i} className="w-1.5 h-1.5 rounded-sm"
                        style={{ background: i < Math.floor(a.confidence/20) ? 'rgb(var(--c-primary))' : 'rgb(var(--c-overlay) / 0.05)', opacity: i < Math.floor(a.confidence/20) ? 0.5 : 1 }} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ArtifactsPage() {
  // The run whose artifacts we're viewing. Seeded from the active run (localStorage), but the
  // RunSwitcher can repoint it to any run in the user's archive without losing context.
  const [runId, setRunId] = useState<string>(() => getActiveRun() ?? '');
  // The user's run archive (GET /v1/history) → powers the run switcher dropdown.
  const [runList, setRunList] = useState<any[]>([]);

  // Hydrate the catalog from the REAL run (GET /v1/runs/{id}/artifacts), keyed on runId so it
  // re-fetches when the user switches runs. Falls back to the mock seed when there's no live
  // backend, so the design always renders.
  const [artifacts] = useLive<typeof ARTIFACTS>(
    () => (runId ? (api.runArtifacts(runId) as any) : Promise.reject(new Error('no run'))),
    ARTIFACTS,
    [runId],
  );
  const list = (artifacts && artifacts.length ? artifacts : ARTIFACTS);
  const [selectedId, setSelectedId]     = useState('research-brief');
  const [query, setQuery]               = useState('');
  const [activeTrace, setActiveTrace]   = useState<string|null>(null);
  const [rightTab, setRightTab]         = useState<RightTab>('intelligence');

  const artifact = list.find(a=>a.id===selectedId) ?? list[0] ?? ARTIFACTS[0];

  // Load the run archive once (newest first). Quietly no-ops when there's no backend.
  useEffect(() => {
    api.history()
      .then(rows => { if (Array.isArray(rows) && rows.length) setRunList(rows); })
      .catch(() => { /* keep the switcher minimal (current run only) */ });
  }, []);

  // When the run (or its artifact set) changes, snap the selection to the first real artifact so
  // the viewer never points at an id that doesn't exist in this run.
  useEffect(() => {
    if (list.length && !list.find(a => a.id === selectedId)) setSelectedId(list[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, artifacts]);

  function handleTrace(id: string) {
    if (!id) { setActiveTrace(null); return; }
    setActiveTrace(id);
    setRightTab('evidence');
  }

  function handleSelectArtifact(id: string) {
    setSelectedId(id);
    setActiveTrace(null);
    setRightTab('intelligence');
  }

  function handleRunChange(id: string) {
    if (!id || id === runId) return;
    setRunId(id);
    setActiveRun(id);          // keep the rest of the app (Dashboard, exports) in sync
    setActiveTrace(null);
  }

  return (
    <div className="bg-background text-on-surface h-screen overflow-hidden select-none"
      style={{ fontFamily:'Inter,system-ui,sans-serif' }}>
      <style>{`
        @keyframes thinkDot {
          0%,80%,100% { transform:scale(1); opacity:0.35; }
          40% { transform:scale(1.7); opacity:1; }
        }
        @keyframes streamIn {
          from { opacity:0; transform:translateY(-4px); }
          to   { opacity:1; transform:translateY(0); }
        }
        @keyframes fadeInUp {
          from { opacity:0; transform:translateY(6px); }
          to   { opacity:1; transform:translateY(0); }
        }
        .scrollbar-thin::-webkit-scrollbar       { width:3px; }
        .scrollbar-thin::-webkit-scrollbar-track  { background:transparent; }
        .scrollbar-thin::-webkit-scrollbar-thumb  { background:rgb(var(--c-primary) / 0.07); border-radius:2px; }
      `}</style>

      <Nav />

      {/* 3-panel layout below nav */}
      <div className="flex pt-16" style={{ height:'100vh' }}>
        <ArtifactNavigator
          artifacts={list}
          selected={selectedId}
          onSelect={handleSelectArtifact}
          query={query}
          onQuery={setQuery}
          runId={runId}
          runs={runList}
          onRunChange={handleRunChange}
        />
        <ArtifactViewer
          artifact={artifact}
          onTrace={handleTrace}
          activeTrace={activeTrace}
          runId={runId}
        />
        <ArtifactIntelligence
          artifact={artifact}
          activeTrace={activeTrace}
          onTrace={handleTrace}
          rightTab={rightTab}
          setRightTab={setRightTab}
        />
      </div>
    </div>
  );
}
