import { useState, useEffect, useRef } from 'react';
import { NotificationBell } from '../components/NotificationBell';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence, useInView } from 'framer-motion';
import { useTheme } from '../lib/useTheme';
import { useAuth } from '../lib/AuthContext';
import { createCheckoutSession } from '../lib/billing';
import { Toast, ToastState } from '../components/Toast';

// ─── Nav ──────────────────────────────────────────────────────────────────────

function Nav() {
  const [theme, toggleTheme] = useTheme();
  const isLight = theme === 'light';
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
          <Link to="/"         className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">Pipeline</Link>
          <Link to="/dashboard" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">Dashboard</Link>
          <Link to="/artifacts" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">Artifacts</Link>
          <Link to="/system"   className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">System</Link>
          <Link to="/pricing"  className="relative flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-primary bg-primary/10 border border-primary/25 shadow-[0_0_14px_rgba(71,214,255,0.12)]">
            <span className="w-1.5 h-1.5 rounded-full bg-primary shadow-[0_0_5px_rgba(71,214,255,0.9)] animate-pulse" />
            Pricing
          </Link>
          <Link to="/history" className="px-3 py-1.5 rounded-md font-mono-label text-[11px] tracking-[0.15em] uppercase text-on-surface-variant hover:text-on-surface hover:bg-white/[0.05] border border-transparent hover:border-white/[0.06] transition-all duration-200">History</Link>
        </div>
      </div>
      <div className="relative flex items-center gap-1.5">
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-secondary-fixed/[0.08] border border-secondary-fixed/20 mr-2">
          <span className="flex h-1.5 w-1.5 rounded-full bg-secondary-fixed shadow-[0_0_6px_rgba(121,255,91,0.9)] animate-pulse" />
          <span className="text-[10px] font-mono-label text-secondary-fixed/80 uppercase tracking-[0.15em]">Optimal</span>
        </div>

        {/* Theme toggle — sliding sun/moon pill (matches SettingsMenu on other pages) */}
        <button
          onClick={toggleTheme}
          aria-label={isLight ? 'Switch to dark mode' : 'Switch to light mode'}
          title={isLight ? 'Dark mode' : 'Light mode'}
          style={{
            position: 'relative', width: 52, height: 26, borderRadius: 999, cursor: 'pointer',
            padding: 0, border: '1px solid', flexShrink: 0, marginRight: 6,
            borderColor: isLight ? 'rgba(14,116,144,0.30)' : 'rgb(var(--c-primary) / 0.20)',
            background: isLight
              ? 'linear-gradient(135deg, #fde9c8 0%, #ffd9a8 100%)'
              : 'linear-gradient(135deg, #0d1b2a 0%, #11203a 100%)',
            transition: 'all 0.35s cubic-bezier(0.16,1,0.3,1)',
          }}
        >
          <span style={{
            position: 'absolute', top: 2, left: isLight ? 28 : 2, width: 20, height: 20,
            borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: isLight ? '#fff7ed' : '#0a1422',
            boxShadow: isLight ? '0 1px 4px rgba(180,120,40,0.45)' : '0 1px 4px rgb(var(--c-deepest) / 0.6)',
            transition: 'left 0.35s cubic-bezier(0.16,1,0.3,1)',
          }}>
            <span className="material-symbols-outlined" style={{
              fontSize: 14, color: isLight ? '#f59e0b' : 'rgb(var(--c-primary))', lineHeight: 1,
            }}>{isLight ? 'light_mode' : 'dark_mode'}</span>
          </span>
        </button>

        <NotificationBell />
        <button className="w-8 h-8 flex items-center justify-center rounded-lg text-on-surface-variant hover:text-primary hover:bg-white/[0.06] border border-transparent hover:border-white/[0.08] transition-all duration-200">
          <span className="material-symbols-outlined text-[18px]">settings</span>
        </button>
      </div>
    </nav>
  );
}

// ─── Data ─────────────────────────────────────────────────────────────────────

const PLANS = [
  {
    id: 'scout',
    name: 'SCOUT',
    sub: 'For students and solo builders',
    price: 'FREE',
    priceLabel: null,
    popular: false,
    accentColor: 'rgb(var(--c-primary))',
    glowColor: 'rgb(var(--c-primary) / 0.12)',
    borderColor: 'rgb(var(--c-primary) / 0.12)',
    features: [
      '5 startup generations / month',
      'Basic research agents',
      'PRD generation',
      'Architecture generation',
      'Export PDFs',
      'Limited memory',
    ],
    cta: 'DEPLOY SCOUT',
  },
  {
    id: 'operator',
    name: 'OPERATOR',
    sub: 'For indie hackers',
    price: '$29',
    priceLabel: '/mo',
    popular: false,
    accentColor: 'rgb(var(--c-primary))',
    glowColor: 'rgb(var(--c-primary) / 0.12)',
    borderColor: 'rgb(var(--c-primary) / 0.14)',
    features: [
      '50 startup generations',
      'Full research swarm',
      'Competitor analysis',
      'Technical design',
      'Architecture planning',
      'Roadmaps',
      'Investor memo',
    ],
    cta: 'DEPLOY OPERATOR',
  },
  {
    id: 'command',
    name: 'COMMAND',
    sub: 'Full mission capability',
    price: '$99',
    priceLabel: '/mo',
    popular: true,
    accentColor: '#47d6ff',
    glowColor: 'rgba(71,214,255,0.18)',
    borderColor: 'rgba(71,214,255,0.35)',
    features: [
      '300 generations / month',
      'Parallel agents',
      'Multi-model orchestration',
      'Advanced market intelligence',
      'Execution planning',
      'Startup scoring',
      'Team collaboration',
      'Custom exports',
    ],
    cta: 'DEPLOY COMMAND',
  },
  {
    id: 'enterprise',
    name: 'ENTERPRISE',
    sub: 'Dedicated infrastructure',
    price: 'Custom',
    priceLabel: null,
    popular: false,
    accentColor: 'rgb(var(--c-primary))',
    glowColor: 'rgb(var(--c-primary) / 0.1)',
    borderColor: 'rgb(var(--c-primary) / 0.1)',
    features: [
      'Dedicated infrastructure',
      'Private deployment',
      'SSO & SAML',
      'Compliance controls',
      'API access',
      'Unlimited generations (bring your own keys)',
      'Priority support',
      'Custom integrations',
    ],
    cta: 'REQUEST ACCESS',
  },
];

const MATRIX_ROWS = [
  { label: 'Research Agents',    scout: '1 basic',      operator: '3 agents',    command: '5 parallel',  enterprise: 'Dedicated' },
  { label: 'PRD Generation',     scout: true,           operator: true,           command: true,          enterprise: true },
  { label: 'TRD Generation',     scout: false,          operator: true,           command: true,          enterprise: true },
  { label: 'Architecture Design',scout: true,           operator: true,           command: true,          enterprise: true },
  { label: 'Market Validation',  scout: false,          operator: true,           command: true,          enterprise: true },
  { label: 'Investor Memo',      scout: false,          operator: true,           command: true,          enterprise: true },
  { label: 'Multi-Agent Swarm',  scout: false,          operator: false,          command: true,          enterprise: true },
  { label: 'Parallel Execution', scout: false,          operator: false,          command: true,          enterprise: true },
  { label: 'API Access',         scout: false,          operator: false,          command: true,          enterprise: true },
  { label: 'Private Deployment', scout: false,          operator: false,          command: false,         enterprise: true },
  { label: 'Custom Models',      scout: false,          operator: false,          command: false,         enterprise: true },
];

// ─── Animated Counter ─────────────────────────────────────────────────────────

function AnimCount({ to, duration = 1800, prefix = '', suffix = '' }: { to: number; duration?: number; prefix?: string; suffix?: string }) {
  const [val, setVal] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: '-80px' });

  useEffect(() => {
    if (!inView) return;
    const start = performance.now();
    const raf = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - p, 3);
      setVal(Math.round(ease * to));
      if (p < 1) requestAnimationFrame(raf);
    };
    requestAnimationFrame(raf);
  }, [inView, to, duration]);

  return <span ref={ref}>{prefix}{val.toLocaleString()}{suffix}</span>;
}

// ─── Matrix cell ──────────────────────────────────────────────────────────────

function MatrixCell({ val, delay }: { val: boolean | string; delay: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-40px' });

  if (typeof val === 'string') {
    return (
      <div ref={ref} className="flex items-center justify-center">
        <motion.span
          initial={{ opacity: 0 }} animate={inView ? { opacity: 1 } : {}}
          transition={{ delay, duration: 0.4 }}
          style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 10, color: 'rgb(var(--c-primary) / 0.55)', letterSpacing: '0.06em' }}
        >{val}</motion.span>
      </div>
    );
  }

  if (!val) {
    return (
      <div ref={ref} className="flex items-center justify-center">
        <motion.div
          initial={{ opacity: 0 }} animate={inView ? { opacity: 1 } : {}}
          transition={{ delay, duration: 0.3 }}
          style={{ width: 14, height: 1.5, background: 'rgb(var(--c-primary) / 0.1)', borderRadius: 1 }}
        />
      </div>
    );
  }

  return (
    <div ref={ref} className="flex items-center justify-center">
      <motion.div
        initial={{ scale: 0, opacity: 0 }}
        animate={inView ? { scale: 1, opacity: 1 } : {}}
        transition={{ delay, duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
        style={{ width: 18, height: 18, borderRadius: '50%', background: 'rgba(71,214,255,0.1)', border: '1px solid rgba(71,214,255,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      >
        <motion.span
          initial={{ opacity: 0 }} animate={inView ? { opacity: 1 } : {}}
          transition={{ delay: delay + 0.1 }}
          style={{ color: '#47d6ff', fontSize: 9, fontWeight: 700, fontFamily: '"JetBrains Mono", monospace' }}
        >✓</motion.span>
      </motion.div>
    </div>
  );
}

// ─── ROI Calculator ───────────────────────────────────────────────────────────

function ROICalculator() {
  const [team, setTeam] = useState(3);
  const [projects, setProjects] = useState(2);

  const hoursPerProject   = 40;
  const ratePerHour       = 120;
  const hoursSaved        = Math.round(team * projects * hoursPerProject * 0.72);
  const costSaved         = Math.round(hoursSaved * ratePerHour);
  const artifacts         = projects * 8;
  const executions        = projects * team * 34;

  return (
    <div style={{ background: 'rgb(var(--c-deepest) / 0.8)', border: '1px solid rgb(var(--c-primary) / 0.08)', borderRadius: 20, padding: '36px 40px', position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: 'radial-gradient(ellipse at 50% 0%, rgba(71,214,255,0.04) 0%, transparent 65%)' }} />
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg, transparent 5%, rgba(71,214,255,0.25) 50%, transparent 95%)' }} />

      <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 9, color: 'rgba(71,214,255,0.5)', letterSpacing: '0.3em', marginBottom: 6 }}>INTERACTIVE</div>
      <h3 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 22, fontWeight: 700, color: 'rgb(var(--c-text))', letterSpacing: '-0.02em', margin: '0 0 28px' }}>
        ROI Calculator
      </h3>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 32 }}>
        {[
          { label: 'TEAM SIZE', val: team, setter: setTeam, min: 1, max: 50, unit: 'operators' },
          { label: 'PROJECTS / MONTH', val: projects, setter: setProjects, min: 1, max: 20, unit: 'projects' },
        ].map(s => (
          <div key={s.label}>
            <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 9.5, color: 'rgb(var(--c-primary) / 0.4)', letterSpacing: '0.2em', marginBottom: 12 }}>{s.label}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <input type="range" min={s.min} max={s.max} value={s.val} onChange={e => s.setter(Number(e.target.value))}
                style={{ flex: 1, height: 3, appearance: 'none', WebkitAppearance: 'none', background: `linear-gradient(to right, rgba(71,214,255,0.7) 0%, rgba(71,214,255,0.7) ${(s.val - s.min) / (s.max - s.min) * 100}%, rgb(var(--c-primary) / 0.1) ${(s.val - s.min) / (s.max - s.min) * 100}%, rgb(var(--c-primary) / 0.1) 100%)`, borderRadius: 2, outline: 'none', cursor: 'pointer' }}
              />
              <div style={{ minWidth: 52, textAlign: 'right' }}>
                <span style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 18, fontWeight: 700, color: '#47d6ff' }}>{s.val}</span>
                <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 8.5, color: 'rgb(var(--c-primary) / 0.3)', letterSpacing: '0.08em', marginTop: 2 }}>{s.unit}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
        {[
          { label: 'HOURS SAVED',          val: hoursSaved, suffix: 'h',   color: '#47d6ff' },
          { label: 'PLANNING COST SAVED',  val: costSaved,  prefix: '$', suffix: '', color: '#79ff5b' },
          { label: 'ARTIFACTS GENERATED',  val: artifacts,  suffix: '',   color: 'rgb(var(--c-primary))' },
          { label: 'AGENT EXECUTIONS',     val: executions, suffix: '',   color: 'rgb(var(--c-primary))' },
        ].map(m => (
          <motion.div key={m.label}
            style={{ background: 'rgb(var(--c-primary) / 0.03)', border: '1px solid rgb(var(--c-primary) / 0.07)', borderRadius: 12, padding: '16px 18px' }}
            animate={{ opacity: 1 }} initial={{ opacity: 0.9 }}
          >
            <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 22, fontWeight: 700, color: m.color, lineHeight: 1.1, marginBottom: 6 }}>
              {m.prefix}{m.val.toLocaleString()}{m.suffix}
            </div>
            <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 8.5, color: 'rgb(var(--c-primary) / 0.3)', letterSpacing: '0.14em' }}>{m.label}</div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

// ─── PricingPage ──────────────────────────────────────────────────────────────

// CSS for the periodic light sweep (every 10s) and glassmorphism reflection
const CARD_CSS = `
  @keyframes periodicSweep {
    0%, 82%  { transform: translateX(-120%); opacity: 0; }
    84%      { opacity: 1; }
    100%     { transform: translateX(220%); opacity: 0; }
  }
  .card-sweep { animation: periodicSweep 10s ease-in-out infinite; }
  .card-sweep-delayed { animation: periodicSweep 10s ease-in-out infinite 3.3s; }
  .card-sweep-delayed2 { animation: periodicSweep 10s ease-in-out infinite 6.7s; }
  .card-sweep-delayed3 { animation: periodicSweep 10s ease-in-out infinite 1.5s; }
  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none; width: 14px; height: 14px; border-radius: 50%;
    background: #47d6ff; cursor: pointer;
    box-shadow: 0 0 8px rgba(71,214,255,0.6);
  }
`;

export default function PricingPage() {
  const [billing, setBilling] = useState<'monthly' | 'annual'>('monthly');
  const [hovered, setHovered] = useState<string | null>(null);

  // ── Dodo Payments checkout wiring (additive — does not alter the card visuals) ──
  const navigate = useNavigate();
  const { token, user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [checkoutPlan, setCheckoutPlan] = useState<string | null>(null);   // plan id mid-checkout
  const [toast, setToast] = useState<ToastState | null>(null);

  // Returning from a cancelled Dodo checkout (or a failed confirm) lands here with ?cancelled=true.
  useEffect(() => {
    if (searchParams.get('cancelled') === 'true') {
      setToast({ type: 'info', message: 'Checkout cancelled — no charge was made.' });
      searchParams.delete('cancelled');
      setSearchParams(searchParams, { replace: true });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleCTA(planId: string) {
    // Scout = free, immediate access. Enterprise = contact sales only. Operator/Command = Dodo.
    if (planId === 'scout') { navigate(user ? '/dashboard' : '/signup'); return; }
    if (planId === 'enterprise') { window.location.href = 'mailto:sales@aps.io?subject=APS%20Enterprise'; return; }
    if (planId !== 'operator' && planId !== 'command') return;

    if (!user || !token) {
      setToast({ type: 'info', message: 'Please sign in to subscribe.' });
      navigate('/login');
      return;
    }
    if (checkoutPlan) return;            // guard against double-clicks
    setCheckoutPlan(planId);
    try {
      const { checkoutUrl } = await createCheckoutSession(planId, token);
      // Redirect to Dodo's hosted checkout (processing state stays visible until navigation).
      window.location.assign(checkoutUrl);
    } catch (e) {
      setCheckoutPlan(null);
      setToast({ type: 'error', message: e instanceof Error ? e.message : 'Could not start checkout. Please try again.' });
    }
  }

  const sweepClass = ['card-sweep', 'card-sweep-delayed', 'card-sweep-delayed2', 'card-sweep-delayed3'];

  const cardVariants = {
    initial: { opacity: 0, y: 28 },
    enter:   (i: number) => ({ opacity: 1, y: 0, transition: { delay: i * 0.09 + 0.1, duration: 0.52, ease: [0.16, 1, 0.3, 1] as [number,number,number,number] } }),
  };

  return (
    <div className="min-h-screen" style={{ background: 'rgb(var(--c-deep))', paddingTop: 64 }}>
      <style>{CARD_CSS}</style>
      <Nav />
      <Toast toast={toast} onClose={() => setToast(null)} />

      {/* ── Ambient particles ─────────────────────────────────────────────── */}
      <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 0 }}>
        {[...Array(18)].map((_, i) => (
          <motion.div key={i}
            style={{ position: 'absolute', width: 1.5, height: 1.5, borderRadius: '50%', background: 'rgba(71,214,255,0.35)', left: `${(i * 37 + 11) % 100}%`, top: `${(i * 53 + 7) % 100}%` }}
            animate={{ y: [0, -24, 0], opacity: [0.15, 0.45, 0.15] }}
            transition={{ duration: 4 + (i % 5) * 1.1, repeat: Infinity, delay: i * 0.38, ease: 'easeInOut' }}
          />
        ))}
      </div>

      <div className="page-content-wrapper" style={{ position: 'relative', zIndex: 1 }}>

        {/* ── HERO ────────────────────────────────────────────────────────── */}
        <div style={{ maxWidth: 1400, margin: '0 auto', padding: '64px 48px 0', textAlign: 'center' }}>
          <div style={{ position: 'absolute', top: 64, left: '50%', transform: 'translateX(-50%)', width: 600, height: 300, borderRadius: '50%', background: 'radial-gradient(ellipse, rgba(71,214,255,0.07) 0%, transparent 70%)', pointerEvents: 'none' }} />

          <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 14px', borderRadius: 20, background: 'rgba(71,214,255,0.06)', border: '1px solid rgba(71,214,255,0.15)', marginBottom: 28 }}>
              <motion.div style={{ width: 6, height: 6, borderRadius: '50%', background: '#79ff5b' }}
                animate={{ opacity: [1, 0.4, 1], scale: [1, 1.3, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
              />
              <span style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 10, color: 'rgba(121,255,91,0.8)', letterSpacing: '0.22em' }}>SYSTEM STATUS: OPERATIONAL</span>
            </div>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.07, duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
            style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 'clamp(36px, 5vw, 58px)', fontWeight: 700, color: 'rgb(var(--c-text))', letterSpacing: '-0.03em', lineHeight: 1.06, margin: '0 0 16px' }}
          >
            APS Deployment Plans
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.13, duration: 0.5 }}
            style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 14, color: 'rgb(var(--c-primary) / 0.45)', letterSpacing: '0.04em', maxWidth: 480, margin: '0 auto 36px', lineHeight: 1.65 }}
          >
            Choose the operational scale of your autonomous product studio.
          </motion.p>

          {/* Real compute economics — each generation runs on gpt-4o-mini + live retrieval. */}
          <motion.p
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.16, duration: 0.5 }}
            style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: 'rgb(var(--c-text-muted))', letterSpacing: '0.03em', maxWidth: 540, margin: '0 auto 30px', lineHeight: 1.6 }}
          >
            Transparent compute: each generation costs ≈ <span style={{ color: 'rgb(var(--c-primary))', fontWeight: 600 }}>$0.12</span> to run
            (gpt-4o-mini + live web/GitHub retrieval). Plans are priced on real usage, not vanity tiers.
          </motion.p>

          {/* Billing toggle */}
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 0, padding: 3, borderRadius: 10, background: 'rgb(var(--c-primary) / 0.04)', border: '1px solid rgb(var(--c-primary) / 0.08)', marginBottom: 64 }}
          >
            {(['monthly', 'annual'] as const).map(b => (
              <button key={b} onClick={() => setBilling(b)}
                style={{ padding: '7px 22px', borderRadius: 8, fontFamily: '"JetBrains Mono", monospace', fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', cursor: 'pointer', border: 'none', transition: 'all 0.22s',
                  background: billing === b ? 'rgba(71,214,255,0.1)' : 'transparent',
                  color:      billing === b ? '#47d6ff' : 'rgb(var(--c-primary) / 0.35)',
                  boxShadow:  billing === b ? 'inset 0 0 0 1px rgba(71,214,255,0.25)' : 'none',
                }}
              >
                {b === 'annual' ? 'Annual  –20%' : 'Monthly'}
              </button>
            ))}
          </motion.div>
        </div>

        {/* ── PRICING CARDS — full-width, equal height ───────────────────── */}
        <div style={{ maxWidth: 1400, margin: '0 auto', padding: '0 48px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 20, alignItems: 'stretch' }}>
            {PLANS.map((plan, i) => {
              const isHovered = hovered === plan.id;
              const price = billing === 'annual' && plan.priceLabel
                ? (plan.id === 'operator' ? '$23' : plan.id === 'command' ? '$79' : plan.price)
                : plan.price;

              return (
                <motion.div key={plan.id}
                  custom={i} variants={cardVariants} initial="initial" animate="enter"
                  onMouseEnter={() => setHovered(plan.id)}
                  onMouseLeave={() => setHovered(null)}
                  style={{
                    position: 'relative', borderRadius: 20, overflow: 'hidden', cursor: 'default',
                    display: 'flex', flexDirection: 'column',
                    background: plan.popular
                      ? 'linear-gradient(160deg, rgb(var(--c-bg-deep) / 0.98) 0%, rgb(var(--c-bg-deep) / 0.97) 100%)'
                      : 'rgb(var(--c-bg-deep) / 0.92)',
                    border: `1px solid ${
                      plan.popular
                        ? isHovered ? 'rgba(71,214,255,0.55)' : 'rgba(71,214,255,0.38)'
                        : isHovered ? 'rgb(var(--c-primary) / 0.2)' : 'rgb(var(--c-primary) / 0.08)'
                    }`,
                    boxShadow: plan.popular
                      ? isHovered
                        ? '0 0 72px rgba(71,214,255,0.28), 0 0 140px rgba(71,214,255,0.1), 0 32px 64px rgb(var(--c-deepest) / 0.55)'
                        : '0 0 48px rgba(71,214,255,0.18), 0 0 96px rgba(71,214,255,0.07), 0 24px 48px rgb(var(--c-deepest) / 0.45)'
                      : isHovered
                        ? '0 0 36px rgb(var(--c-primary) / 0.08), 0 24px 48px rgb(var(--c-deepest) / 0.45)'
                        : '0 4px 24px rgb(var(--c-deepest) / 0.3)',
                    transform: isHovered ? 'translateY(-5px)' : 'translateY(0)',
                    transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
                  }}
                >
                  {/* Animated pulse border ring for COMMAND */}
                  {plan.popular && (
                    <motion.div style={{ position: 'absolute', inset: -1, borderRadius: 21, pointerEvents: 'none', border: '1px solid rgba(71,214,255,0.45)' }}
                      animate={{ opacity: [0.4, 0.9, 0.4] }}
                      transition={{ duration: 2.8, repeat: Infinity, ease: 'easeInOut' }}
                    />
                  )}

                  {/* Top edge glow — stronger for COMMAND */}
                  <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: plan.popular ? 2 : 1, zIndex: 2,
                    background: plan.popular
                      ? 'linear-gradient(90deg, transparent 5%, rgba(71,214,255,0.9) 50%, transparent 95%)'
                      : `linear-gradient(90deg, transparent 10%, rgb(var(--c-primary) / 0.22) 50%, transparent 90%)` }} />

                  {/* Spotlight radial for COMMAND */}
                  {plan.popular && (
                    <div style={{ position: 'absolute', top: -80, left: '50%', transform: 'translateX(-50%)', width: '140%', height: 200, background: 'radial-gradient(ellipse at 50% 0%, rgba(71,214,255,0.1) 0%, transparent 70%)', pointerEvents: 'none', zIndex: 0 }} />
                  )}

                  {/* Glass reflection layer */}
                  <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '45%', background: 'linear-gradient(180deg, rgb(var(--c-overlay) / 0.025) 0%, transparent 100%)', pointerEvents: 'none', zIndex: 0, borderRadius: '20px 20px 0 0' }} />

                  {/* Periodic light sweep */}
                  <div className={sweepClass[i]} style={{ position: 'absolute', inset: 0, zIndex: 1, pointerEvents: 'none',
                    background: 'linear-gradient(105deg, transparent 30%, rgb(var(--c-primary) / 0.055) 50%, transparent 70%)',
                    borderRadius: 20 }} />

                  {/* Hover background bloom */}
                  {isHovered && (
                    <motion.div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 0,
                        background: plan.popular
                          ? 'radial-gradient(ellipse at 50% 0%, rgba(71,214,255,0.07) 0%, transparent 65%)'
                          : 'radial-gradient(ellipse at 50% 0%, rgb(var(--c-primary) / 0.04) 0%, transparent 65%)' }}
                      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                    />
                  )}

                  {/* ── Card content (flex-column so CTA pins to bottom) ── */}
                  <div style={{ padding: '28px 26px 26px', position: 'relative', zIndex: 2, display: 'flex', flexDirection: 'column', flex: 1 }}>

                    {/* Badge row — always present, fixed height so all cards align */}
                    <div style={{ height: 36, display: 'flex', alignItems: 'center', marginBottom: 18 }}>
                      {plan.popular ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 11px', borderRadius: 20,
                          background: 'rgba(71,214,255,0.1)', border: '1px solid rgba(71,214,255,0.3)',
                          fontFamily: '"JetBrains Mono", monospace', fontSize: 9, color: '#47d6ff', letterSpacing: '0.2em' }}>
                          <motion.span style={{ width: 5, height: 5, borderRadius: '50%', background: '#47d6ff', display: 'inline-block' }}
                            animate={{ opacity: [1, 0.35, 1] }} transition={{ duration: 1.6, repeat: Infinity }} />
                          MOST POPULAR
                        </span>
                      ) : null}
                    </div>

                    {/* Plan identity */}
                    <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 10, fontWeight: 700,
                      color: plan.popular ? '#47d6ff' : 'rgb(var(--c-primary) / 0.45)', letterSpacing: '0.3em', marginBottom: 6 }}>
                      {plan.name}
                    </div>
                    <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: 'rgb(var(--c-primary) / 0.32)',
                      letterSpacing: '0.03em', lineHeight: 1.55, marginBottom: 24, minHeight: 34 }}>
                      {plan.sub}
                    </div>

                    {/* Price */}
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginBottom: 24 }}>
                      <span style={{ fontFamily: "'Space Grotesk', sans-serif",
                        fontSize: price === 'FREE' || price === 'Custom' ? 30 : 38,
                        fontWeight: 700, letterSpacing: '-0.03em', lineHeight: 1,
                        color: plan.popular ? '#47d6ff' : 'rgb(var(--c-text))' }}>
                        {price}
                      </span>
                      {plan.priceLabel && (
                        <span style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11.5, color: 'rgb(var(--c-primary) / 0.28)', letterSpacing: '0.05em' }}>
                          {plan.priceLabel}
                        </span>
                      )}
                    </div>

                    {/* Divider */}
                    <div style={{ height: 1, background: plan.popular ? 'rgba(71,214,255,0.12)' : 'rgb(var(--c-primary) / 0.06)', marginBottom: 22 }} />

                    {/* Features — flex:1 so it fills space, CTA stays at bottom */}
                    <ul style={{ listStyle: 'none', margin: 0, padding: 0, flex: 1, display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 28 }}>
                      {plan.features.map((f, fi) => (
                        <motion.li key={fi}
                          initial={{ opacity: 0, x: -5 }} animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: i * 0.09 + fi * 0.035 + 0.3 }}
                          style={{ display: 'flex', alignItems: 'flex-start', gap: 10,
                            fontFamily: '"JetBrains Mono", monospace', fontSize: 11,
                            color: plan.popular ? 'rgb(var(--c-primary) / 0.7)' : 'rgb(var(--c-primary) / 0.5)',
                            letterSpacing: '0.025em', lineHeight: 1.5 }}
                        >
                          <span style={{ color: plan.popular ? '#47d6ff' : 'rgb(var(--c-primary) / 0.25)', flexShrink: 0, marginTop: 2, fontSize: 13 }}>›</span>
                          {f}
                        </motion.li>
                      ))}
                    </ul>

                    {/* CTA — always at bottom */}
                    <button
                      onClick={() => handleCTA(plan.id)}
                      disabled={checkoutPlan !== null}
                      style={{ width: '100%', padding: '13px 0', borderRadius: 11,
                        fontFamily: '"JetBrains Mono", monospace', fontSize: 11, fontWeight: 700, letterSpacing: '0.15em',
                        cursor: checkoutPlan ? 'not-allowed' : 'pointer', border: 'none', transition: 'all 0.25s',
                        opacity: checkoutPlan && checkoutPlan !== plan.id ? 0.5 : 1,
                        color:      plan.popular ? '#060A12' : '#47d6ff',
                        background: plan.popular
                          ? 'linear-gradient(135deg, #47d6ff 0%, rgba(71,214,255,0.82) 100%)'
                          : 'rgba(71,214,255,0.06)',
                        boxShadow: plan.popular
                          ? '0 0 32px rgba(71,214,255,0.35), inset 0 1px 0 rgb(var(--c-overlay) / 0.15)'
                          : 'inset 0 0 0 1px rgba(71,214,255,0.18)',
                      }}
                      onMouseOver={e => {
                        if (!plan.popular) {
                          e.currentTarget.style.background = 'rgba(71,214,255,0.11)';
                          e.currentTarget.style.boxShadow = 'inset 0 0 0 1px rgba(71,214,255,0.32), 0 0 20px rgba(71,214,255,0.1)';
                        } else {
                          e.currentTarget.style.boxShadow = '0 0 52px rgba(71,214,255,0.5), inset 0 1px 0 rgb(var(--c-overlay) / 0.18)';
                        }
                      }}
                      onMouseOut={e => {
                        if (!plan.popular) {
                          e.currentTarget.style.background = 'rgba(71,214,255,0.06)';
                          e.currentTarget.style.boxShadow = 'inset 0 0 0 1px rgba(71,214,255,0.18)';
                        } else {
                          e.currentTarget.style.boxShadow = '0 0 32px rgba(71,214,255,0.35), inset 0 1px 0 rgb(var(--c-overlay) / 0.15)';
                        }
                      }}
                    >
                      {checkoutPlan === plan.id ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                          <span style={{ width: 12, height: 12, borderRadius: '50%', border: '2px solid currentColor', borderTopColor: 'transparent', display: 'inline-block', animation: 'apsBtnSpin 0.7s linear infinite' }} />
                          PROCESSING…
                          <style>{`@keyframes apsBtnSpin{to{transform:rotate(360deg)}}`}</style>
                        </span>
                      ) : plan.cta}
                    </button>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>

        {/* ── CAPABILITY MATRIX ─────────────────────────────────────────────── */}
        <div style={{ maxWidth: 1400, margin: '80px auto 0', padding: '0 48px' }}>
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-60px' }} transition={{ duration: 0.5 }}>
            <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 9, color: 'rgba(71,214,255,0.45)', letterSpacing: '0.32em', marginBottom: 8, textAlign: 'center' }}>FULL BREAKDOWN</div>
            <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 28, fontWeight: 700, color: 'rgb(var(--c-text))', letterSpacing: '-0.02em', textAlign: 'center', margin: '0 0 40px' }}>
              Mission Capability Matrix
            </h2>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-40px' }} transition={{ duration: 0.5, delay: 0.1 }}
            style={{ background: 'rgb(var(--c-deepest) / 0.85)', border: '1px solid rgb(var(--c-primary) / 0.07)', borderRadius: 18, overflow: 'hidden' }}
          >
            {/* Header row */}
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr', borderBottom: '1px solid rgb(var(--c-primary) / 0.08)', background: 'rgb(var(--c-primary) / 0.02)', padding: '14px 28px' }}>
              <div />
              {['Scout', 'Operator', 'Command', 'Enterprise'].map(col => (
                <div key={col} style={{ textAlign: 'center', fontFamily: '"JetBrains Mono", monospace', fontSize: 10, fontWeight: 700, letterSpacing: '0.2em', color: col === 'Command' ? '#47d6ff' : 'rgb(var(--c-primary) / 0.45)' }}>
                  {col.toUpperCase()}
                </div>
              ))}
            </div>

            {/* Data rows */}
            {MATRIX_ROWS.map((row, ri) => (
              <div key={row.label}
                style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr', padding: '13px 28px', borderBottom: ri < MATRIX_ROWS.length - 1 ? '1px solid rgb(var(--c-primary) / 0.04)' : 'none', background: ri % 2 === 0 ? 'transparent' : 'rgb(var(--c-primary) / 0.01)' }}
              >
                <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: 'rgb(var(--c-primary) / 0.55)', letterSpacing: '0.04em', display: 'flex', alignItems: 'center' }}>{row.label}</div>
                <MatrixCell val={row.scout}      delay={ri * 0.03} />
                <MatrixCell val={row.operator}   delay={ri * 0.03 + 0.04} />
                <MatrixCell val={row.command}    delay={ri * 0.03 + 0.08} />
                <MatrixCell val={row.enterprise} delay={ri * 0.03 + 0.12} />
              </div>
            ))}
          </motion.div>
        </div>

        {/* ── ROI CALCULATOR ───────────────────────────────────────────────── */}
        <div style={{ maxWidth: 1400, margin: '72px auto 0', padding: '0 48px' }}>
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-60px' }} transition={{ duration: 0.5 }}>
            <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 9, color: 'rgba(71,214,255,0.45)', letterSpacing: '0.32em', marginBottom: 8, textAlign: 'center' }}>EFFICIENCY METRICS</div>
            <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 28, fontWeight: 700, color: 'rgb(var(--c-text))', letterSpacing: '-0.02em', textAlign: 'center', margin: '0 0 40px' }}>
              Mission ROI Estimator
            </h2>
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-40px' }} transition={{ duration: 0.5, delay: 0.1 }}>
            <ROICalculator />
          </motion.div>
        </div>

        {/* ── SOCIAL PROOF METRICS ─────────────────────────────────────────── */}
        <div style={{ maxWidth: 1400, margin: '72px auto 0', padding: '0 48px' }}>
          <motion.div
            initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-40px' }} transition={{ duration: 0.5 }}
            style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}
          >
            {[
              { label: 'ACTIVE OPERATORS',   to: 2847,    suffix: '+',  prefix: '' },
              { label: 'STARTUPS ANALYZED',  to: 184000,  suffix: '+',  prefix: '' },
              { label: 'HOURS SAVED',        to: 1200000, suffix: '+',  prefix: '' },
              { label: 'AGENT EXECUTIONS',   to: 9400000, suffix: 'M+', prefix: '' },
            ].map((m, mi) => (
              <motion.div key={m.label}
                initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }} transition={{ delay: mi * 0.08 }}
                style={{ background: 'rgb(var(--c-deepest) / 0.8)', border: '1px solid rgb(var(--c-primary) / 0.07)', borderRadius: 16, padding: '28px 24px', textAlign: 'center', position: 'relative', overflow: 'hidden' }}
              >
                <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg, transparent 15%, rgba(71,214,255,0.2) 50%, transparent 85%)' }} />
                <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 36, fontWeight: 700, color: '#47d6ff', letterSpacing: '-0.03em', marginBottom: 8, lineHeight: 1 }}>
                  {m.to >= 1000000
                    ? <AnimCount to={Math.round(m.to / 1000000)} suffix="M+" />
                    : <AnimCount to={m.to} suffix={m.suffix} />
                  }
                </div>
                <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 9, color: 'rgb(var(--c-primary) / 0.35)', letterSpacing: '0.18em' }}>{m.label}</div>
              </motion.div>
            ))}
          </motion.div>
        </div>

        {/* ── ENTERPRISE CTA ───────────────────────────────────────────────── */}
        <div style={{ maxWidth: 1400, margin: '72px auto 0', padding: '0 48px' }}>
          <motion.div
            initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-40px' }} transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
            style={{ position: 'relative', borderRadius: 24, overflow: 'hidden', padding: '72px 60px', textAlign: 'center',
              background: 'rgb(var(--c-deepest) / 0.92)',
              border: '1px solid rgba(71,214,255,0.12)',
              boxShadow: '0 0 80px rgba(71,214,255,0.06), 0 40px 80px rgb(var(--c-deepest) / 0.5)',
            }}
          >
            {/* Background glow */}
            <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: 'radial-gradient(ellipse at 50% 100%, rgba(71,214,255,0.06) 0%, transparent 60%)' }} />
            {/* Top edge */}
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg, transparent 5%, rgba(71,214,255,0.35) 50%, transparent 95%)' }} />
            {/* Scan line */}
            <motion.div style={{ position: 'absolute', left: 0, right: 0, height: 1, background: 'linear-gradient(90deg, transparent 10%, rgba(71,214,255,0.18) 50%, transparent 90%)' }}
              animate={{ top: ['0%', '100%', '0%'] }}
              transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
            />
            {/* Corner accents */}
            <div style={{ position: 'absolute', top: 18, left: 22, width: 24, height: 24, borderTop: '1px solid rgba(71,214,255,0.22)', borderLeft: '1px solid rgba(71,214,255,0.22)' }} />
            <div style={{ position: 'absolute', top: 18, right: 22, width: 24, height: 24, borderTop: '1px solid rgba(71,214,255,0.22)', borderRight: '1px solid rgba(71,214,255,0.22)' }} />
            <div style={{ position: 'absolute', bottom: 18, left: 22, width: 24, height: 24, borderBottom: '1px solid rgba(71,214,255,0.22)', borderLeft: '1px solid rgba(71,214,255,0.22)' }} />
            <div style={{ position: 'absolute', bottom: 18, right: 22, width: 24, height: 24, borderBottom: '1px solid rgba(71,214,255,0.22)', borderRight: '1px solid rgba(71,214,255,0.22)' }} />

            <div style={{ position: 'relative', zIndex: 1 }}>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '5px 14px', borderRadius: 20, background: 'rgb(var(--c-primary) / 0.04)', border: '1px solid rgb(var(--c-primary) / 0.1)', marginBottom: 24 }}>
                <span className="material-symbols-outlined" style={{ fontSize: 12, color: 'rgb(var(--c-primary) / 0.4)' }}>shield</span>
                <span style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 9, color: 'rgb(var(--c-primary) / 0.4)', letterSpacing: '0.22em' }}>ENTERPRISE GRADE</span>
              </div>

              <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 'clamp(28px, 4vw, 44px)', fontWeight: 700, color: 'rgb(var(--c-text))', letterSpacing: '-0.025em', margin: '0 0 16px', lineHeight: 1.1 }}>
                Deploy Your Autonomous<br />Product Studio
              </h2>
              <p style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 13, color: 'rgb(var(--c-primary) / 0.38)', letterSpacing: '0.04em', maxWidth: 520, margin: '0 auto 44px', lineHeight: 1.65 }}>
                Private infrastructure, compliance controls, SSO, and dedicated support — built for enterprise product teams.
              </p>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16, flexWrap: 'wrap' }}>
                <motion.button
                  whileHover={{ scale: 1.02, boxShadow: '0 0 48px rgba(71,214,255,0.35)' }}
                  whileTap={{ scale: 0.98 }}
                  style={{ padding: '14px 32px', borderRadius: 12, fontFamily: '"JetBrains Mono", monospace', fontSize: 12, fontWeight: 700, letterSpacing: '0.15em', cursor: 'pointer', border: 'none', color: 'rgb(var(--c-deepest))', background: 'linear-gradient(135deg, #47d6ff, rgba(71,214,255,0.82))', boxShadow: '0 0 28px rgba(71,214,255,0.28)' }}
                >
                  REQUEST ENTERPRISE ACCESS
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.02, borderColor: 'rgba(71,214,255,0.4)', boxShadow: '0 0 24px rgba(71,214,255,0.12)' }}
                  whileTap={{ scale: 0.98 }}
                  style={{ padding: '14px 32px', borderRadius: 12, fontFamily: '"JetBrains Mono", monospace', fontSize: 12, fontWeight: 700, letterSpacing: '0.15em', cursor: 'pointer', color: '#47d6ff', background: 'rgba(71,214,255,0.06)', border: '1px solid rgba(71,214,255,0.2)', transition: 'all 0.22s' }}
                >
                  SCHEDULE DEMO
                </motion.button>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 28, marginTop: 36, flexWrap: 'wrap' }}>
                {['SOC 2 Type II', 'GDPR Compliant', 'SSO / SAML', '99.99% SLA', 'Private VPC'].map(badge => (
                  <div key={badge} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ color: 'rgb(var(--c-primary) / 0.22)', fontSize: 11 }}>✓</span>
                    <span style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 10, color: 'rgb(var(--c-primary) / 0.3)', letterSpacing: '0.1em' }}>{badge}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        </div>

        {/* ── FAQ ──────────────────────────────────────────────────────────── */}
        <div style={{ maxWidth: 780, margin: '72px auto 0', padding: '0 40px' }}>
          <motion.div initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.5 }}>
            <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 9, color: 'rgba(71,214,255,0.45)', letterSpacing: '0.32em', marginBottom: 8, textAlign: 'center' }}>OPERATOR GUIDE</div>
            <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 26, fontWeight: 700, color: 'rgb(var(--c-text))', letterSpacing: '-0.02em', textAlign: 'center', margin: '0 0 36px' }}>
              Frequently Asked
            </h2>
          </motion.div>
          <FAQ />
        </div>

        {/* Footer spacer */}
        <div style={{ height: 96 }} />
      </div>
    </div>
  );
}

// ─── FAQ accordion ────────────────────────────────────────────────────────────

const FAQ_ITEMS = [
  { q: 'What counts as a "generation"?', a: 'One generation is a complete APS run — from idea input through research, product, architecture, and presentation agents. All artifacts produced in a single run count as one generation.' },
  { q: 'Can I upgrade or downgrade plans?', a: 'Yes. Plan changes take effect immediately. When upgrading, you\'re charged the prorated difference. Downgrades apply at the next billing cycle.' },
  { q: 'Is my data private?', a: 'Scout and Operator plans use shared infrastructure with strict tenant isolation. Command includes dedicated memory namespaces. Enterprise offers fully private VPC deployment with no data leaving your perimeter.' },
  { q: 'What happens if I hit my generation limit?', a: 'You\'ll receive a warning at 80% usage. Once the limit is reached, new runs are queued until the next billing cycle or you upgrade. Existing artifacts remain accessible.' },
  { q: 'Do agents use my API keys or APS infrastructure?', a: 'By default, agents run on APS-managed infrastructure with pooled model access. Enterprise can bring their own API keys and route calls through their own accounts.' },
];

function FAQ() {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {FAQ_ITEMS.map((item, i) => (
        <motion.div key={i}
          initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }} transition={{ delay: i * 0.06 }}
          style={{ background: 'rgb(var(--c-deepest) / 0.8)', border: `1px solid ${open === i ? 'rgba(71,214,255,0.2)' : 'rgb(var(--c-primary) / 0.07)'}`, borderRadius: 14, overflow: 'hidden', transition: 'border-color 0.22s' }}
        >
          <button
            onClick={() => setOpen(open === i ? null : i)}
            style={{ width: '100%', padding: '18px 22px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left' }}
          >
            <span style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 12, color: open === i ? '#47d6ff' : 'rgb(var(--c-primary) / 0.65)', letterSpacing: '0.03em', lineHeight: 1.5 }}>{item.q}</span>
            <motion.span animate={{ rotate: open === i ? 45 : 0 }} transition={{ duration: 0.22 }}
              style={{ color: open === i ? '#47d6ff' : 'rgb(var(--c-primary) / 0.3)', fontSize: 18, flexShrink: 0, marginLeft: 14, lineHeight: 1 }}>+</motion.span>
          </button>
          <AnimatePresence initial={false}>
            {open === i && (
              <motion.div
                initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
                style={{ overflow: 'hidden' }}
              >
                <div style={{ padding: '0 22px 20px', fontFamily: '"JetBrains Mono", monospace', fontSize: 11.5, color: 'rgb(var(--c-primary) / 0.42)', letterSpacing: '0.03em', lineHeight: 1.7 }}>
                  {item.a}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      ))}
    </div>
  );
}
