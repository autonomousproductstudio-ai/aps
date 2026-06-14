import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { SettingsMenu } from '../components/SettingsMenu';
import { useAuth } from '../lib/AuthContext';
import { api } from '../lib/api';
import { setActiveRun } from '../lib/useBackend';

export default function PipelinePage() {
  const terminalRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { token } = useAuth();
  const [prompt, setPrompt] = useState('');
  const [starting, setStarting] = useState(false);
  const [catalog, setCatalog] = useState<any | null>(null);
  const [provider, setProvider] = useState('');
  const [model, setModel] = useState('');

  // Load the REAL model catalog (providers → models) for the selector; default is pre-selected.
  useEffect(() => {
    let alive = true;
    api.models().then((c) => {
      if (!alive || !c) return;
      setCatalog(c);
      if (c.default) { setProvider(c.default.provider); setModel(c.default.model); }
    }).catch(() => { /* selector hides if backend is down */ });
    return () => { alive = false; };
  }, []);

  const modelOptions: { value: string; label: string }[] = (catalog?.providers ?? []).flatMap(
    (p: any) => (p.models ?? []).map((m: any) => ({ value: `${p.id}|${m.id}`, label: `${p.label} · ${m.label}` })),
  );

  // Wire the command center to the real backend: start an orchestrator run with the selected
  // model/provider, remember its id, and jump to the dashboard. Silent if the backend is down.
  const handleStart = async () => {
    const idea = prompt.trim();
    if (!idea || starting) return;
    if (!token) { navigate('/login'); return; }
    setStarting(true);
    try {
      const opts = provider && model ? { provider, model } : undefined;
      const { runId } = await api.startRun(idea, opts);
      setActiveRun(runId);
      navigate('/dashboard');
    } catch {
      setStarting(false);
    }
  };

  useEffect(() => {
    const terminal = terminalRef.current;
    if (!terminal) return;

    const logs = [
      "[12:46:10] RUN_776: Vector db sync complete.",
      "[12:46:15] RUN_772: Optimization phase started.",
      "[12:46:22] RUN_777: Security audit node ping...",
      "[12:46:30] RUN_773: Finalizing PRD documentation.",
      "[12:46:45] RUN_776: Indexing metadata..."
    ];
    let logIndex = 0;

    const interval = setInterval(() => {
      const newLog = document.createElement('div');
      newLog.className = Math.random() > 0.5 ? 'text-primary' : 'opacity-50';
      newLog.textContent = logs[logIndex % logs.length];
      terminal.appendChild(newLog);
      terminal.style.transform = `translateY(-${terminal.children.length * 1}px)`;
      logIndex++;
      if (terminal.children.length > 20) {
        terminal.removeChild(terminal.firstChild as Node);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    // Stagger animation trigger
    const elements = document.querySelectorAll('.stagger-in > *');
    elements.forEach((el, i) => {
      (el as HTMLElement).style.animationDelay = `${i * 0.1}s`;
    });
  }, []);

  return (
    <div className="bg-background text-on-surface font-body-lg overflow-x-hidden selection:bg-primary/30 min-h-screen">
      <style>{`
        .glass-panel {
            background: rgb(var(--c-bg) / 0.7);
            backdrop-filter: blur(16px);
            border: 1px solid rgb(var(--c-primary) / 0.15);
        }
        .glow-blue {
            box-shadow: 0 0 30px rgba(71, 214, 255, 0.15);
        }
        .pipeline-connector {
            background: linear-gradient(90deg, transparent, #47d6ff, transparent);
            background-size: 200% 100%;
            animation: flow 3s linear infinite;
        }
        @keyframes flow {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }
        .stagger-in > * {
            opacity: 0;
            transform: translateY(30px);
            animation: fadeInUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        @keyframes fadeInUp {
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        .terminal-scroll {
            mask-image: linear-gradient(to bottom, transparent, black 15%, black 85%, transparent);
        }
        .node-active {
            box-shadow: 0 0 25px rgba(71, 214, 255, 0.4);
            border-color: rgba(71, 214, 255, 0.6);
        }
        .ambient-glow {
            background: radial-gradient(circle at 50% 50%, rgba(71, 214, 255, 0.05) 0%, transparent 70%);
        }
        @media (max-width: 768px) {
          section.relative.min-h-\\[90vh\\] h1 {
            font-size: clamp(32px, 8vw, 80px) !important;
          }
          section.relative.min-h-\\[90vh\\] h1 span.block {
            font-size: clamp(32px, 8vw, 80px) !important;
          }
          .w-full.max-w-5xl.glass-panel {
            margin-left: 8px !important;
            margin-right: 8px !important;
            width: calc(100% - 16px) !important;
          }
          .w-full.max-w-5xl.glass-panel > .flex.flex-col.md\\:flex-row {
            flex-direction: column !important;
          }
          .w-full.md\\:w-\\[280px\\] {
            width: 100% !important;
            border-left: none !important;
            border-top: 1px solid rgb(var(--c-overlay) / 0.05);
          }
          .flex.flex-wrap.gap-3 {
            flex-wrap: wrap !important;
          }
        }
      `}</style>

      {/* Global Navigation */}
      <nav className="fixed top-0 w-full z-[60] h-16 px-container-margin flex justify-between items-center">
        {/* Frosted glass background with gradient */}
        <div className="absolute inset-0 bg-gradient-to-r from-[#06080D]/95 via-[#0A0C14]/90 to-[#06080D]/95 backdrop-blur-2xl border-b border-white/[0.05]" />
        {/* Top-edge prismatic highlight */}
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent" />

        {/* Left: Logo + nav */}
        <div className="relative flex items-center gap-6">
          {/* Logo */}
          <div className="flex items-center gap-3 group cursor-pointer select-none">
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
          </div>

          {/* Vertical rule */}
          <div className="w-px h-5 bg-white/[0.08]" />

          {/* Nav links */}
          <div className="hidden md:flex items-center gap-1">
            <Link to="/" className="relative flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-primary bg-primary/10 border border-primary/25 shadow-[0_0_14px_rgba(71,214,255,0.12)] transition-all duration-200">
              <span className="w-1.5 h-1.5 rounded-full bg-primary shadow-[0_0_5px_rgba(71,214,255,0.9)] animate-pulse" />
              Pipeline
            </Link>
            <Link to="/dashboard" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">Dashboard</Link>
            <Link to="/artifacts" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">Artifacts</Link>
            <Link to="/system" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">System</Link>
            <Link to="/pricing" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">Pricing</Link>
            <Link to="/history" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">History</Link>
          </div>
        </div>

        {/* Right: status + actions + avatar */}
        <div className="relative flex items-center gap-1.5">
          {/* Live status pill */}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-secondary-fixed/[0.08] border border-secondary-fixed/20 mr-2">
            <span className="flex h-1.5 w-1.5 rounded-full bg-secondary-fixed shadow-[0_0_6px_rgba(121,255,91,0.9)] animate-pulse" />
            <span className="text-[10px] font-mono-label text-secondary-fixed/80 uppercase tracking-[0.15em]">Optimal</span>
          </div>

          <button className="w-8 h-8 flex items-center justify-center rounded-lg text-on-surface-variant hover:text-primary hover:bg-white/[0.06] border border-transparent hover:border-white/[0.08] transition-all duration-200">
            <span className="material-symbols-outlined text-[18px]">terminal</span>
          </button>
          <SettingsMenu />
        </div>
      </nav>

      <main className="relative pt-16">
        {/* Hero Section */}
        <section className="relative min-h-[90vh] flex flex-col items-center justify-center px-container-margin py-xl overflow-hidden">
          <div className="absolute inset-0 ambient-glow pointer-events-none"></div>
          <div className="stagger-in flex flex-col items-center text-center z-10">
            <div className="inline-flex items-center gap-sm px-md py-1 rounded-full bg-primary/10 border border-primary/20 mb-lg backdrop-blur-sm">
              <span className="flex h-2 w-2 rounded-full bg-secondary-fixed animate-pulse"></span>
              <span className="font-mono-label text-mono-label text-primary uppercase tracking-[0.2em]">System Status: Optimal</span>
            </div>
            <h1 className="font-display-lg text-[64px] md:text-[96px] leading-[0.9] tracking-tighter mb-md max-w-5xl">
              <span className="block text-on-surface">THE AUTONOMOUS</span>
              <span className="block text-primary drop-shadow-[0_0_30px_rgb(var(--c-primary) / 0.4)]">PRODUCT STUDIO</span>
            </h1>
            <p className="font-body-lg text-body-lg text-on-surface-variant max-w-2xl mb-xl opacity-80">
              Synthesize venture-scale products at the speed of thought. Our swarm of autonomous agents handles the entire lifecycle—from deep market analysis to architecture deployment.
            </p>
            {/* Command Center Card */}
            <div className="w-full max-w-5xl glass-panel rounded-[24px] overflow-hidden border-primary/20 hover:border-primary/40 transition-all duration-700 shadow-[0_0_40px_rgba(71,214,255,0.05)] group relative bg-[#0B0D12] text-left mt-8">
              {/* Background neural/gradient mesh */}
              <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(71,214,255,0.08),transparent_50%)] pointer-events-none"></div>
              
              {/* Header */}
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center px-lg py-md border-b border-white/5 bg-white/[0.01] relative z-10">
                <div className="flex items-center gap-md">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10 border border-primary/20 shadow-[0_0_15px_rgba(71,214,255,0.1)]">
                    <span className="material-symbols-outlined text-primary text-[18px]">hub</span>
                  </div>
                  <div>
                    <h3 className="font-mono-label text-on-surface text-[13px] font-semibold tracking-wider">Startup Creation Protocol</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="flex h-1.5 w-1.5 rounded-full bg-secondary-fixed shadow-[0_0_8px_rgba(121,255,91,0.6)] animate-pulse"></span>
                      <span className="text-[10px] font-mono-label text-on-surface-variant uppercase tracking-[0.15em]">System Ready</span>
                    </div>
                  </div>
                </div>
                <div className="mt-4 sm:mt-0 flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20 shadow-[0_0_10px_rgba(71,214,255,0.05)]">
                  <span className="material-symbols-outlined text-primary text-[14px]">groups</span>
                  <span className="text-[11px] font-mono-label text-primary uppercase font-bold tracking-wider">5 Agents Available</span>
                </div>
              </div>

              {/* Main Body Layout */}
              <div className="flex flex-col md:flex-row relative z-10">
                
                {/* Left Side: Input & Deliverables */}
                <div className="flex-1 p-xl border-b md:border-b-0 md:border-r border-white/5 flex flex-col justify-between">
                  <div>
                    <label className="block font-display-lg text-[28px] text-on-surface mb-lg">What startup should APS build?</label>
                    
                    {/* Premium Input */}
                    <div className="relative group/input mt-2">
                      <div className="absolute -inset-0.5 bg-gradient-to-r from-primary/30 via-surface-tint/20 to-primary/30 rounded-xl blur opacity-20 group-focus-within/input:opacity-100 transition duration-500"></div>
                      <div className="relative flex items-center bg-[#05070A]/80 backdrop-blur-md border border-white/10 rounded-xl overflow-hidden focus-within:border-primary/50 transition-colors shadow-inner">
                        <div className="pl-4 pr-2">
                          <span className="material-symbols-outlined text-primary/50 text-[22px]">magic_button</span>
                        </div>
                        <input
                          type="text"
                          className="w-full bg-transparent border-none focus:ring-0 py-5 pl-2 pr-4 text-on-surface text-[17px] placeholder-primary/30 font-body-lg focus:outline-none"
                          placeholder="Build an AI SaaS for resume screening..."
                          autoComplete="off"
                          value={prompt}
                          onChange={(e) => setPrompt(e.target.value)}
                          onKeyDown={(e) => { if (e.key === 'Enter') handleStart(); }}
                        />
                        <div className="absolute right-6 top-1/2 -translate-y-1/2 flex items-center gap-2 pointer-events-none opacity-0 group-focus-within/input:opacity-100 transition-opacity">
                          <div className="h-5 w-[2px] bg-primary/80 animate-pulse"></div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Model selector — real catalog (providers → models), wired to start config */}
                  {modelOptions.length > 0 && (
                    <div className="mt-8">
                      <span className="text-[11px] font-mono-label text-on-surface-variant uppercase tracking-[0.2em] mb-3 block">Model</span>
                      <div className="relative">
                        <span className="material-symbols-outlined text-primary/50 text-[18px] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none">memory</span>
                        <select
                          value={provider && model ? `${provider}|${model}` : ''}
                          onChange={(e) => { const [pid, mid] = e.target.value.split('|'); setProvider(pid); setModel(mid); }}
                          className="w-full bg-[#05070A]/80 border border-white/10 rounded-xl py-3 pl-10 pr-10 text-on-surface text-[14px] font-body-lg focus:outline-none focus:border-primary/50 appearance-none cursor-pointer hover:border-white/20 transition-colors"
                        >
                          {modelOptions.map((o) => (
                            <option key={o.value} value={o.value} className="bg-[#0B0D12] text-on-surface">{o.label}</option>
                          ))}
                        </select>
                        <span className="material-symbols-outlined text-on-surface-variant/50 text-[18px] absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">expand_more</span>
                      </div>
                    </div>
                  )}

                  {/* Deliverables */}
                  <div className="mt-12">
                    <span className="text-[11px] font-mono-label text-on-surface-variant uppercase tracking-[0.2em] mb-4 block">Expected Deliverables</span>
                    <div className="flex flex-wrap gap-3">
                      {['Market Research', 'Competitor Analysis', 'PRD', 'Technical Design', 'Roadmap', 'Investor Memo'].map(item => (
                        <div key={item} className="flex items-center gap-2 px-3 py-2 rounded-md bg-white/5 border border-white/5 text-on-surface-variant text-[13px] font-medium hover:bg-white/10 hover:text-on-surface transition-colors cursor-default hover:border-white/10 shadow-sm">
                          <span className="material-symbols-outlined text-secondary-fixed text-[14px]">check</span>
                          {item}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Right Side Panel: Agent Readiness */}
                <div className="w-full md:w-[280px] p-xl bg-black/40 flex flex-col justify-center border-l border-white/5">
                  <span className="text-[11px] font-mono-label text-on-surface-variant uppercase tracking-[0.2em] mb-6 block text-center md:text-left">Live Telemetry</span>
                  <div className="space-y-4">
                    {[
                      { name: 'Research Agent', icon: 'travel_explore' },
                      { name: 'Product Agent', icon: 'architecture' },
                      { name: 'Architecture', icon: 'hub' },
                      { name: 'Execution', icon: 'data_object' },
                      { name: 'Presentation', icon: 'smart_display' },
                    ].map((agent, i) => (
                      <div key={agent.name} className="flex items-center justify-between group/agent p-2.5 rounded-lg hover:bg-white/5 transition-colors border border-transparent hover:border-white/5" style={{ animationDelay: `${i * 0.1}s` }}>
                        <div className="flex items-center gap-3">
                          <span className="material-symbols-outlined text-primary/40 group-hover/agent:text-primary transition-colors text-[18px]">{agent.icon}</span>
                          <span className="text-[14px] font-body-lg text-on-surface-variant group-hover/agent:text-on-surface transition-colors">{agent.name}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-mono-label text-secondary-fixed uppercase font-bold tracking-wider">Ready</span>
                          <span className="flex h-1.5 w-1.5 rounded-full bg-secondary-fixed shadow-[0_0_8px_rgba(121,255,91,0.6)] animate-pulse" style={{ animationDelay: `${i * 0.2}s` }}></span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                
              </div>

              {/* Bottom CTA */}
              <div className="p-md border-t border-white/5 bg-white/[0.02] flex justify-end relative z-10">
                <button
                  onClick={handleStart}
                  disabled={starting}
                  className="relative group/btn overflow-hidden rounded-xl bg-primary text-[#003543] font-mono-label text-[14px] px-8 py-4 flex items-center gap-3 font-bold tracking-[0.15em] uppercase transition-all duration-300 shadow-[0_0_20px_rgba(71,214,255,0.4)] hover:shadow-[0_0_40px_rgba(71,214,255,0.8)] hover:scale-[1.02] active:scale-95 border border-white/20 hover:border-white/60 disabled:opacity-60 disabled:cursor-wait disabled:hover:scale-100">
                  <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/50 to-transparent -translate-x-[150%] group-hover/btn:translate-x-[150%] transition-transform duration-[800ms] ease-in-out"></span>
                  <span className="relative z-10">{starting ? 'Initiating…' : 'Initiate Startup'}</span>
                  <span className="material-symbols-outlined relative z-10 text-[20px] group-hover/btn:rotate-12 transition-transform">bolt</span>
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* Swarm Pipeline Visualization */}
        <section className="py-24 px-container-margin border-y border-outline-variant/10 bg-surface-container-lowest/30 overflow-hidden">
          <div className="max-w-7xl mx-auto text-center mb-16">
            <h2 className="font-display-lg text-headline-md text-on-surface mb-sm">The Swarm Pipeline</h2>
            <p className="font-mono-label text-mono-label text-primary uppercase tracking-[0.3em]">Multi-Agent Synchronous State</p>
          </div>
          <div className="max-w-6xl mx-auto relative px-md">
            {/* Desktop Connector Lines */}
            <div className="hidden md:block absolute top-[44px] left-0 w-full h-[2px] bg-outline-variant/20 z-0">
              <div className="absolute inset-0 pipeline-connector"></div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-5 gap-xl relative z-10">
              {/* Node 1: Research */}
              <div className="flex flex-col items-center group">
                <div className="w-20 h-20 glass-panel rounded-2xl flex items-center justify-center mb-md node-active group-hover:-translate-y-1 transition-all">
                  <span className="material-symbols-outlined text-primary text-[32px]">insights</span>
                </div>
                <span className="font-mono-label text-mono-label text-on-surface mb-1">RESEARCH</span>
                <span className="text-[10px] text-secondary-fixed uppercase font-bold tracking-tighter">Running</span>
              </div>
              {/* Node 2: Product */}
              <div className="flex flex-col items-center group">
                <div className="w-20 h-20 glass-panel rounded-2xl flex items-center justify-center mb-md border-primary/20 group-hover:-translate-y-1 transition-all">
                  <span className="material-symbols-outlined text-on-surface-variant text-[32px]">architecture</span>
                </div>
                <span className="font-mono-label text-mono-label text-on-surface-variant mb-1">PRODUCT</span>
                <span className="text-[10px] text-on-surface-variant/40 uppercase font-bold tracking-tighter">Queued</span>
              </div>
              {/* Node 3: Architecture */}
              <div className="flex flex-col items-center group">
                <div className="w-20 h-20 glass-panel rounded-2xl flex items-center justify-center mb-md border-primary/20 group-hover:-translate-y-1 transition-all">
                  <span className="material-symbols-outlined text-on-surface-variant text-[32px]">hub</span>
                </div>
                <span className="font-mono-label text-mono-label text-on-surface-variant mb-1">ARCHITECTURE</span>
                <span className="text-[10px] text-on-surface-variant/40 uppercase font-bold tracking-tighter">Standby</span>
              </div>
              {/* Node 4: Execution */}
              <div className="flex flex-col items-center group">
                <div className="w-20 h-20 glass-panel rounded-2xl flex items-center justify-center mb-md border-primary/20 group-hover:-translate-y-1 transition-all">
                  <span className="material-symbols-outlined text-on-surface-variant text-[32px]">data_object</span>
                </div>
                <span className="font-mono-label text-mono-label text-on-surface-variant mb-1">EXECUTION</span>
                <span className="text-[10px] text-on-surface-variant/40 uppercase font-bold tracking-tighter">Standby</span>
              </div>
              {/* Node 5: Presentation */}
              <div className="flex flex-col items-center group">
                <div className="w-20 h-20 glass-panel rounded-2xl flex items-center justify-center mb-md border-primary/20 group-hover:-translate-y-1 transition-all">
                  <span className="material-symbols-outlined text-on-surface-variant text-[32px]">smart_display</span>
                </div>
                <span className="font-mono-label text-mono-label text-on-surface-variant mb-1">PRESENTATION</span>
                <span className="text-[10px] text-on-surface-variant/40 uppercase font-bold tracking-tighter">Standby</span>
              </div>
            </div>
          </div>
        </section>

        {/* Core Engine Deep-Dive */}
        <section className="py-24 px-container-margin max-w-7xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-xl items-center">
            <div className="lg:col-span-7 relative group">
              <div className="absolute -inset-4 bg-primary/10 blur-2xl rounded-full opacity-30 group-hover:opacity-50 transition-opacity"></div>
              <div className="relative glass-panel rounded-2xl overflow-hidden border-primary/20 glow-blue">
                <img alt="Synaptic Engine" className="w-full aspect-video object-cover transition-transform duration-[2s] group-hover:scale-105" src="https://lh3.googleusercontent.com/aida-public/AB6AXuALxLeu_qLuJ0nXk4nUG_yrSA_2QjEAyXuPw9m4mGQaOKRkDWC7JfScO73etauB4r52unt4X0iwk0UP63mJ-PaJx5WuhjUTYd91s0FpTRbXHP9-ReGxgSG8oBHhUSNsHwbKUgGasDVzQ4EbjKcZfv3UNpAAVCW-EkOEKyfJJUGA4j4RDBbZ2w5FkaHEKdxelW6ev09fuqgBr5kzF-Y0KiL3Mvk3O6QL7209m8kt_XYCgATtKE8li4QIZaxtrQr82NekD6yGPHRx0M8" />
                <div className="absolute inset-0 bg-gradient-to-t from-surface via-transparent to-transparent"></div>
                <div className="absolute bottom-lg left-lg">
                  <div className="bg-primary/20 backdrop-blur-md px-md py-1 rounded border border-primary/30 font-mono-label text-[10px] text-primary">SECURE_CORE_ACCESS_01</div>
                </div>
              </div>
            </div>
            <div className="lg:col-span-5">
              <span className="font-mono-label text-mono-label text-primary uppercase mb-md block">Proprietary Technology</span>
              <h3 className="font-display-lg text-headline-md text-on-surface mb-lg">Synaptic Swarm Intelligence</h3>
              <p className="text-on-surface-variant text-body-lg mb-xl leading-relaxed">
                Our orchestration layer uses a revolutionary asynchronous task-mesh that allows thousands of specialized agents to collaborate. No hierarchy, only hyper-efficient consensus.
              </p>
              <div className="space-y-md">
                <div className="flex gap-md items-start">
                  <span className="material-symbols-outlined text-primary">dynamic_feed</span>
                  <div>
                    <h4 className="font-headline-sm text-body-lg text-on-surface font-bold">Dynamic Resourcing</h4>
                    <p className="text-on-surface-variant text-body-md">Auto-scaling compute clusters based on mission complexity.</p>
                  </div>
                </div>
                <div className="flex gap-md items-start">
                  <span className="material-symbols-outlined text-primary">verified_user</span>
                  <div>
                    <h4 className="font-headline-sm text-body-lg text-on-surface font-bold">Zero-Trust Synthesis</h4>
                    <p className="text-on-surface-variant text-body-md">Cryptographically verified code and architecture generation.</p>
                  </div>
                </div>
              </div>
              <button className="mt-xl text-primary font-mono-label text-mono-label flex items-center gap-sm group">
                EXPLORE ARCHITECTURE <span className="material-symbols-outlined group-hover:translate-x-1 transition-transform">arrow_right_alt</span>
              </button>
            </div>
          </div>
        </section>

        {/* Analytics & Stream */}
        <section className="py-24 px-container-margin bg-surface-container-low/20">
          <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-lg">
            {/* Terminal Stream */}
            <div className="md:col-span-2 glass-panel rounded-2xl flex flex-col h-[400px]">
              <div className="px-md py-sm border-b border-outline-variant/20 flex justify-between items-center bg-surface-container-high/40">
                <div className="flex items-center gap-sm">
                  <span className="material-symbols-outlined text-[16px] text-primary">terminal</span>
                  <span className="font-mono-label text-mono-label">LIVE_RUN_STREAM</span>
                </div>
                <div className="flex items-center gap-sm">
                  <span className="flex h-1.5 w-1.5 rounded-full bg-secondary-fixed"></span>
                  <span className="text-[10px] text-secondary-fixed uppercase font-bold tracking-widest">Connected</span>
                </div>
              </div>
              <div className="flex-1 p-md font-mono-log overflow-hidden relative terminal-scroll">
                <div className="space-y-sm" id="terminal-content" ref={terminalRef}>
                  <div className="opacity-50">[12:45:01] RUN_772: Agent_Research spawned...</div>
                  <div className="text-primary">[12:45:03] RUN_772: Synthesizing tokenomics model v2.1</div>
                  <div className="opacity-50">[12:45:12] RUN_771: Deployment to production successful.</div>
                  <div className="text-secondary-fixed">[12:45:20] RUN_773: Market_Analysis consensus achieved.</div>
                  <div className="opacity-50">[12:45:33] RUN_774: Agent_Arch initializing workspace...</div>
                  <div className="text-primary">[12:45:45] RUN_772: Running structural validation...</div>
                  <div className="opacity-50">[12:45:50] RUN_775: Scraping global liquidity pools...</div>
                </div>
              </div>
            </div>
            {/* Metrics Card */}
            <div className="flex flex-col gap-lg">
              <div className="glass-panel rounded-2xl p-xl flex-1 flex flex-col justify-center border-secondary-fixed/20 relative overflow-hidden group">
                <div className="absolute top-0 right-0 p-lg opacity-10 group-hover:opacity-20 transition-opacity">
                  <span className="material-symbols-outlined text-[120px]">bolt</span>
                </div>
                <span className="font-mono-label text-mono-label text-secondary-fixed uppercase mb-xs">Active Swarms</span>
                <div className="font-display-lg text-[64px] text-on-surface leading-none mb-md">1,204</div>
                <div className="w-full bg-surface-variant h-1 rounded-full overflow-hidden">
                  <div className="bg-secondary-fixed w-1/3 h-full"></div>
                </div>
                <p className="mt-md text-on-surface-variant text-body-md font-mono-label uppercase opacity-60">System Load: 14%</p>
              </div>
              <div className="glass-panel rounded-2xl p-xl flex flex-col justify-center border-primary/20">
                <span className="font-mono-label text-mono-label text-primary uppercase mb-xs">Uptime</span>
                <div className="font-headline-md text-on-surface">99.9992%</div>
                <p className="text-on-surface-variant text-[11px] font-mono-label uppercase mt-1">SLA Compliant // Global Mesh</p>
              </div>
            </div>
          </div>
        </section>

        {/* Final CTA */}
        <section className="py-xl px-container-margin max-w-7xl mx-auto mb-24">
          <div className="glass-panel rounded-[2rem] p-xl md:p-32 text-center relative overflow-hidden group">
            <div className="absolute inset-0 bg-primary/5 opacity-0 group-hover:opacity-100 transition-opacity duration-700"></div>
            <div className="absolute -top-32 -left-32 w-64 h-64 bg-primary/10 rounded-full blur-[100px] pointer-events-none"></div>
            <div className="absolute -bottom-32 -right-32 w-64 h-64 bg-primary/10 rounded-full blur-[100px] pointer-events-none"></div>
            <div className="relative z-10">
              <h2 className="font-display-lg text-headline-md md:text-display-lg text-on-surface mb-md">Ready to deploy your next venture?</h2>
              <p className="text-on-surface-variant text-body-lg max-w-xl mx-auto mb-xl opacity-70">
                Skip the hiring process. Skip the infrastructure setup. APS agents are standing by to build your vision at production scale.
              </p>
              <div className="flex flex-col sm:flex-row justify-center gap-md">
                <button
                  onClick={() => navigate(token ? '/dashboard' : '/login')}
                  className="bg-primary text-on-primary font-mono-label text-mono-label px-xl py-lg rounded-full hover:scale-105 active:scale-95 transition-all shadow-xl hover:shadow-primary/20">
                  START MISSION
                </button>
                <button className="glass-panel border-outline-variant/40 text-on-surface font-mono-label text-mono-label px-xl py-lg rounded-full hover:bg-surface-variant/30 transition-all">
                  READ WHITE PAPER
                </button>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-surface-container-lowest border-t border-outline-variant/10 py-lg px-container-margin">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-lg">
          <div className="flex flex-col items-center md:items-start gap-1">
            <span className="font-mono-label text-mono-label text-primary">© 2024 AUTONOMOUS PRODUCT STUDIO</span>
            <span className="text-[10px] text-on-surface-variant font-mono-label opacity-40">PROTOCOL VERSION 4.0.2-STABLE</span>
          </div>
          <div className="flex gap-xl">
            <a className="text-on-surface-variant hover:text-primary font-mono-label text-[11px] transition-colors" href="#">PRIVACY</a>
            <a className="text-on-surface-variant hover:text-primary font-mono-label text-[11px] transition-colors" href="#">TERMS</a>
            <div className="flex items-center gap-sm">
              <span className="font-mono-label text-[11px] text-on-surface-variant">API STATUS:</span>
              <span className="text-secondary-fixed font-mono-label text-[11px] uppercase font-bold">Optimal</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
