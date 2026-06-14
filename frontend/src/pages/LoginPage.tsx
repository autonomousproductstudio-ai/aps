import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import AuthLeftPanel from '../components/AuthLeftPanel';
import { useAuth } from '../lib/AuthContext';

// ── helpers ──────────────────────────────────────────────────────────
function emailValid(v: string) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v); }
function pwdStrength(v: string): 0 | 1 | 2 {
  if (v.length < 4) return 0;
  if (v.length < 8) return 1;
  return /[A-Z]/.test(v) && /\d/.test(v) ? 2 : 1;
}

const STRENGTH_LABEL = ['WEAK',           'MEDIUM',           'STRONG'] as const;
const STRENGTH_COLOR = ['#EF4444',        '#F59E0B',          '#79ff5b'] as const;

const BOOT_STEPS = [
  { label: 'VERIFYING OPERATOR',            ms: 400 },
  { label: 'SYNCING MEMORY',                ms: 370 },
  { label: 'CONNECTING RESEARCH AGENT',     ms: 350 },
  { label: 'CONNECTING ARCHITECTURE AGENT', ms: 340 },
  { label: 'LOADING WORKSPACE',             ms: 320 },
];

// ── SVG icons ────────────────────────────────────────────────────────
const IconMail = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="4" width="20" height="16" rx="2"/>
    <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
  </svg>
);
const IconLock = () => (
  <svg width="12" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="11" rx="2"/>
    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
  </svg>
);
const IconEye = ({ off }: { off?: boolean }) => off ? (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/>
    <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/>
    <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/>
    <line x1="2" x2="22" y1="2" y2="22"/>
  </svg>
) : (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>
);
const IconShield = () => (
  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
  </svg>
);

// ── CSS ───────────────────────────────────────────────────────────────
const CSS = `
  @keyframes spin { to { transform: rotate(360deg); } }
  /* ── Card shell ─────────────────────────── */
  .aps-card {
    position: relative; border-radius: 22px; overflow: hidden;
    background: rgb(var(--c-deep) / 0.95);
    backdrop-filter: blur(44px);
    border: 1px solid rgb(var(--c-primary) / 0.08);
    box-shadow:
      inset 0 0 0 1px rgb(var(--c-accent-cyan) / 0.025),
      inset 0 1px 0 rgb(var(--c-primary) / 0.045),
      0 0 70px rgb(var(--c-accent-cyan) / 0.055),
      0 52px 100px rgb(var(--c-deepest) / 0.65);
  }

  /* Rotating light refraction */
  .card-refraction {
    position: absolute; inset: 0; pointer-events: none;
    border-radius: 22px; overflow: hidden; z-index: 0;
  }
  .card-refraction::before {
    content: '';
    position: absolute; top: -80%; left: -80%;
    width: 260%; height: 260%;
    background: conic-gradient(from 0deg,
      transparent 325deg, rgb(var(--c-accent-cyan) / 0.022) 345deg, transparent 360deg);
    animation: refractSpin 12s linear infinite;
  }
  @keyframes refractSpin { to { transform: rotate(360deg); } }

  /* Edge lighting */
  .card-edge-top   { position:absolute;top:0;left:0;right:0;height:1px;z-index:1;background:linear-gradient(90deg,transparent 5%,rgb(var(--c-accent-cyan) / 0.32) 50%,transparent 95%); }
  .card-edge-left  { position:absolute;top:0;left:0;bottom:0;width:1px;z-index:1;background:linear-gradient(180deg,rgb(var(--c-accent-cyan) / 0.18) 0%,rgb(var(--c-accent-cyan) / 0.05) 45%,transparent 72%); }
  .card-edge-right { position:absolute;top:0;right:0;bottom:0;width:1px;z-index:1;background:linear-gradient(180deg,rgb(var(--c-accent-cyan) / 0.13) 0%,rgb(var(--c-accent-cyan) / 0.03) 45%,transparent 72%); }

  /* Scan sweep */
  .card-scan {
    position:absolute;top:0;left:0;right:0;height:1.5px;z-index:3;
    background:linear-gradient(90deg,transparent 10%,rgb(var(--c-accent-cyan) / 0.24) 50%,transparent 90%);
    animation:cardScan 7s linear infinite;
  }
  @keyframes cardScan {
    0%   { top:0;    opacity:0; }
    3%   { opacity:1; }
    97%  { opacity:0.35; }
    100% { top:100%; opacity:0; }
  }

  /* ── Header ────────────────────────────── */
  .card-header { padding:28px 28px 0; }
  .aps-logo-icon {
    width:42px;height:42px;border-radius:12px;
    background:rgb(var(--c-accent-cyan) / 0.07);
    border:1px solid rgb(var(--c-accent-cyan) / 0.17);
    box-shadow:inset 0 1px 0 rgb(var(--c-primary) / 0.07),0 0 14px rgb(var(--c-accent-cyan) / 0.06);
    display:flex;align-items:center;justify-content:center;
  }
  .aps-logo-inner {
    width:17px;height:17px;border-radius:5px;
    background:linear-gradient(135deg,rgb(var(--c-accent-cyan) / 0.9),rgba(0,150,200,0.65));
  }
  .aps-wordmark { color:#a5e7ff;font-family:"JetBrains Mono",monospace;font-size:13px;font-weight:700;letter-spacing:0.22em; }
  .aps-subtext  { color:rgb(var(--c-primary) / 0.28);font-family:"JetBrains Mono",monospace;font-size:8px;letter-spacing:0.11em; }
  .card-title   { font-family:'Space Grotesk',sans-serif;font-size:21px;font-weight:700;color:#e1e2e7;letter-spacing:-0.02em;margin:0 0 8px;line-height:1.2; }

  .health-pill  { display:flex;align-items:center;gap:6px;padding:5px 11px;border-radius:20px;background:rgba(121,255,91,0.05);border:1px solid rgba(121,255,91,0.14); }
  .health-dot   { width:5px;height:5px;border-radius:50%;background:#79ff5b;box-shadow:0 0 6px rgba(121,255,91,0.7); }
  .health-val   { font-family:"JetBrains Mono",monospace;font-size:10px;color:rgba(121,255,91,0.78);letter-spacing:0.06em; }

  .online-row   { display:flex;align-items:center;gap:6px;font-family:"JetBrains Mono",monospace; }
  .online-dot   { width:6px;height:6px;border-radius:50%;background:#00E5FF;box-shadow:0 0 8px rgb(var(--c-accent-cyan) / 0.7); }
  .online-lbl   { font-size:9.5px;font-weight:700;color:rgb(var(--c-accent-cyan) / 0.68);letter-spacing:0.18em; }
  .online-sep   { font-size:9.5px;color:rgb(var(--c-primary) / 0.18); }
  .online-sub   { font-size:8.5px;color:rgb(var(--c-primary) / 0.26);letter-spacing:0.1em; }

  /* ── Status strip ──────────────────────── */
  .status-strip {
    display:flex;align-items:center;gap:18px;
    margin-top:16px;
    border-top:1px solid rgb(var(--c-primary) / 0.05);
    border-bottom:1px solid rgb(var(--c-primary) / 0.05);
    background:rgb(var(--c-accent-cyan) / 0.018);
    padding:8px 28px;
  }
  .status-badge { display:flex;align-items:center;gap:5px; }
  .badge-dot    { width:5px;height:5px;border-radius:50%;background:#00E5FF;box-shadow:0 0 5px rgb(var(--c-accent-cyan) / 0.6); }
  .badge-txt    { font-family:"JetBrains Mono",monospace;font-size:9.5px;color:rgb(var(--c-primary) / 0.46);letter-spacing:0.11em; }

  /* ── Inputs ────────────────────────────── */
  .field-label { display:block;font-family:"JetBrains Mono",monospace;font-size:9.5px;letter-spacing:0.18em;color:rgb(var(--c-primary) / 0.34);transition:color 0.2s; }
  .field-label.on { color:rgb(var(--c-accent-cyan) / 0.65); }

  .input-wrap { position:relative; }
  .input-icon { position:absolute;left:13px;top:50%;transform:translateY(-50%);color:rgb(var(--c-primary) / 0.22);pointer-events:none;display:flex;align-items:center; }
  .aps-input {
    width:100%;padding:12px 14px;
    border-radius:10px;
    font-family:"JetBrains Mono",monospace;
    font-size:13px;color:#e1e2e7;
    background:rgb(var(--c-deep) / 0.92);
    border:1px solid rgb(var(--c-primary) / 0.07);
    outline:none;
    transition:border-color 0.22s,box-shadow 0.22s;
    box-sizing:border-box;
  }
  .aps-input::placeholder { color:#252c3b; }
  .aps-input.on {
    border-color:rgb(var(--c-accent-cyan) / 0.3);
    box-shadow:0 0 0 3px rgb(var(--c-accent-cyan) / 0.048),inset 0 1px 0 rgb(var(--c-accent-cyan) / 0.04),inset 0 0 18px rgb(var(--c-accent-cyan) / 0.015);
  }
  .focus-bar {
    position:absolute;bottom:0;left:0;right:0;height:1.5px;
    border-radius:0 0 10px 10px;
    background:linear-gradient(90deg,transparent 5%,rgb(var(--c-accent-cyan) / 0.45) 50%,transparent 95%);
    transform-origin:left;
  }
  .valid-check {
    position:absolute;right:13px;top:50%;transform:translateY(-50%);
    width:19px;height:19px;border-radius:50%;
    background:rgba(121,255,91,0.12);
    border:1px solid rgba(121,255,91,0.38);
    display:flex;align-items:center;justify-content:center;
    font-size:9px;font-weight:700;color:#79ff5b;
    font-family:"JetBrains Mono",monospace;
  }
  .pwd-toggle {
    position:absolute;right:12px;top:50%;transform:translateY(-50%);
    background:none;border:none;cursor:pointer;padding:4px;
    color:rgb(var(--c-primary) / 0.28);transition:color 0.2s;
    display:flex;align-items:center;
  }
  .pwd-toggle:hover { color:rgb(var(--c-primary) / 0.68); }

  /* Strength bar */
  .strength-bar { display:flex;gap:4px;margin-top:7px; }
  .strength-seg { flex:1;height:2.5px;border-radius:2px;transition:background 0.3s; }

  /* ── Toggle switch ─────────────────────── */
  .toggle-track {
    width:34px;height:19px;border-radius:10px;padding:2px;
    display:flex;align-items:center;cursor:pointer;
    transition:background 0.25s,border 0.25s,box-shadow 0.25s;
    flex-shrink:0;
  }
  .toggle-thumb { width:13px;height:13px;border-radius:50%; }

  /* ── Button ────────────────────────────── */
  .btn-mission {
    position:relative;overflow:hidden;
    width:100%;padding:14px 0;
    border-radius:11px;
    font-family:"JetBrains Mono",monospace;
    font-size:12px;font-weight:700;letter-spacing:0.16em;
    color:#00E5FF;
    background:linear-gradient(135deg,rgb(var(--c-accent-cyan) / 0.11),rgba(0,155,210,0.19));
    border:1px solid rgb(var(--c-accent-cyan) / 0.28);
    box-shadow:0 0 24px rgb(var(--c-accent-cyan) / 0.1),inset 0 1px 0 rgb(var(--c-primary) / 0.06);
    cursor:pointer;transition:box-shadow 0.25s;
  }
  .btn-mission:hover { box-shadow:0 0 58px rgb(var(--c-accent-cyan) / 0.3),inset 0 1px 0 rgb(var(--c-primary) / 0.09); }
  .btn-mission:active { transform:scale(0.986); }
  .btn-sweep {
    position:absolute;inset:0;
    background:linear-gradient(90deg,transparent,rgb(var(--c-accent-cyan) / 0.09),transparent);
    transform:translateX(-200%);
  }
  .btn-mission:hover .btn-sweep { transform:translateX(200%);transition:transform 0.65s ease-out; }

  /* ── Trust strip ───────────────────────── */
  .trust-strip {
    display:flex;align-items:center;justify-content:center;gap:14px;
    padding:12px 28px;
    border-top:1px solid rgb(var(--c-primary) / 0.05);
  }
  .trust-item { display:flex;align-items:center;gap:5px;font-family:"JetBrains Mono",monospace;font-size:8.5px;color:rgb(var(--c-primary) / 0.28);letter-spacing:0.1em; }
  .trust-sep  { width:1px;height:12px;background:rgb(var(--c-primary) / 0.09); }
  .trust-hi   { color:#79ff5b;font-weight:700;margin-left:3px; }

  /* ── Boot sequence ─────────────────────── */
  .boot-ring-outer {
    position:absolute;inset:0;border-radius:50%;
    border:1.5px solid transparent;
    border-top-color:#00E5FF;
    border-right-color:rgb(var(--c-accent-cyan) / 0.28);
  }
  .boot-ring-inner {
    position:absolute;inset:9px;border-radius:50%;
    border:1px solid transparent;
    border-top-color:rgb(var(--c-accent-cyan) / 0.5);
    border-left-color:rgb(var(--c-accent-cyan) / 0.18);
  }
  .boot-step-icon {
    width:17px;height:17px;border-radius:50%;
    display:flex;align-items:center;justify-content:center;
    flex-shrink:0;transition:all 0.3s;
  }
`;

export default function LoginPage() {
  const navigate = useNavigate();
  const auth     = useAuth();
  const btnRef   = useRef<HTMLButtonElement>(null);

  const [email,       setEmail]       = useState('');
  const [password,    setPassword]    = useState('');
  const [remember,    setRemember]    = useState(false);
  const [showPwd,     setShowPwd]     = useState(false);
  const [focused,     setFocused]     = useState<string | null>(null);
  const [apiError,    setApiError]    = useState('');
  const [oauthLoading, setOauthLoading] = useState<'google' | 'github' | null>(null);

  const [health, setHealth] = useState(99.98);
  const [memory, setMemory] = useState(326);

  useEffect(() => {
    const id = setInterval(() => {
      setHealth(parseFloat((99.94 + Math.random() * 0.06).toFixed(2)));
      setMemory(m => m + Math.floor(Math.random() * 3 - 1));
    }, 2800);
    return () => clearInterval(id);
  }, []);

  const [phase,    setPhase]    = useState<'idle' | 'booting' | 'granted'>('idle');
  const [bootStep, setBootStep] = useState(-1);
  const [progress, setProgress] = useState(0);
  const [ripple,   setRipple]   = useState<{ x: number; y: number; id: number } | null>(null);

  const strength = pwdStrength(password);
  const isEmailOk = emailValid(email);

  const handleMagnet = (e: React.MouseEvent<HTMLButtonElement>) => {
    const btn = btnRef.current;
    if (!btn) return;
    const r = btn.getBoundingClientRect();
    btn.style.transform = `translate(${(e.clientX - r.left - r.width / 2) * 0.13}px, ${(e.clientY - r.top - r.height / 2) * 0.13}px)`;
  };
  const resetMagnet = () => { if (btnRef.current) btnRef.current.style.transform = ''; };

  const handleOAuth = async (provider: 'google' | 'github') => {
    setApiError('');
    setOauthLoading(provider);
    try {
      if (provider === 'google') await auth.loginWithGoogle();
      else                        await auth.loginWithGithub();
      setPhase('booting');
      const total = BOOT_STEPS.reduce((s, b) => s + b.ms, 0);
      let elapsed = 0;
      for (let i = 0; i < BOOT_STEPS.length; i++) {
        setBootStep(i);
        elapsed += BOOT_STEPS[i].ms;
        setProgress(Math.round((elapsed / total) * 95));
        await new Promise(r => setTimeout(r, BOOT_STEPS[i].ms));
      }
      setProgress(100);
      await new Promise(r => setTimeout(r, 260));
      setPhase('granted');
      await new Promise(r => setTimeout(r, 950));
      navigate('/dashboard', { replace: true });
    } catch (err: any) {
      const msg = err?.code === 'auth/popup-closed-by-user' ? '' : (err.message || 'OAuth sign-in failed.');
      setApiError(msg);
    } finally {
      setOauthLoading(null);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setApiError('');

    const btn = btnRef.current;
    if (btn) {
      const r = btn.getBoundingClientRect();
      setRipple({ x: r.width / 2, y: r.height / 2, id: Date.now() });
      setTimeout(() => setRipple(null), 700);
    }

    try {
      await auth.login(email, password);
    } catch (err: any) {
      setApiError(err.message || 'Authentication failed. Check your credentials.');
      return;
    }

    setPhase('booting');
    const total = BOOT_STEPS.reduce((s, b) => s + b.ms, 0);
    let elapsed = 0;
    for (let i = 0; i < BOOT_STEPS.length; i++) {
      setBootStep(i);
      elapsed += BOOT_STEPS[i].ms;
      setProgress(Math.round((elapsed / total) * 95));
      await new Promise(r => setTimeout(r, BOOT_STEPS[i].ms));
    }
    setProgress(100);
    await new Promise(r => setTimeout(r, 260));
    setPhase('granted');
    await new Promise(r => setTimeout(r, 950));
    navigate('/dashboard', { replace: true });
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', overflow: 'hidden', background: 'rgb(var(--c-bg-deep))' }}>
      <style>{CSS}</style>

      {/* ── LEFT: untouched ──────────────────────────────── */}
      <div className="hidden lg:flex" style={{ width: '50%', flexShrink: 0 }}>
        <AuthLeftPanel />
      </div>

      {/* ── RIGHT ────────────────────────────────────────── */}
      <motion.div
        style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '28px 40px', position: 'relative', overflowY: 'auto' }}
        initial={{ opacity: 0, x: 28 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: 'radial-gradient(ellipse at 25% 50%, rgb(var(--c-accent-cyan) / 0.028) 0%, transparent 62%)' }} />

        <div style={{ width: '100%', maxWidth: 440, paddingTop: 8, paddingBottom: 8 }}>
          <motion.div
            className="aps-card"
            style={{ minHeight: 540 }}
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="card-refraction" />
            <div className="card-edge-top" />
            <div className="card-edge-left" />
            <div className="card-edge-right" />
            <div className="card-scan" />

            <div style={{ position: 'relative', zIndex: 2 }}>
              <AnimatePresence mode="wait">

                {/* ════════════════════════════════════════════
                    PHASE: IDLE — full form
                ════════════════════════════════════════════ */}
                {phase === 'idle' && (
                  <motion.div key="form"
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                    exit={{ opacity: 0, scale: 0.97, filter: 'blur(3px)' }}
                    transition={{ duration: 0.22 }}
                  >
                    {/* ── Header ── */}
                    <div className="card-header">
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <div className="aps-logo-icon">
                            <div className="aps-logo-inner" />
                          </div>
                          <div>
                            <div className="aps-wordmark">APS</div>
                            <div className="aps-subtext">AUTONOMOUS PRODUCT STUDIO</div>
                          </div>
                        </div>
                        {/* Live health pill */}
                        <div className="health-pill">
                          <motion.div className="health-dot"
                            animate={{ opacity: [1, 0.4, 1] }}
                            transition={{ duration: 1.9, repeat: Infinity, ease: 'easeInOut' }}
                          />
                          <span className="health-val">{health}%</span>
                        </div>
                      </div>

                      <h1 className="card-title">Operator Access Terminal</h1>

                      <div className="online-row" style={{ marginBottom: 0 }}>
                        <motion.div className="online-dot"
                          animate={{ scale: [1, 1.45, 1], opacity: [1, 0.5, 1] }}
                          transition={{ duration: 2.1, repeat: Infinity, ease: 'easeInOut' }}
                        />
                        <span className="online-lbl">SYSTEM ONLINE</span>
                        <span className="online-sep"> · </span>
                        <span className="online-sub">AUTHENTICATION REQUIRED</span>
                      </div>
                    </div>

                    {/* ── Live status strip ── */}
                    <div className="status-strip">
                      {[
                        { label: 'ONLINE',  val: null,          dot: true  },
                        { label: 'AGENTS',  val: '5',           dot: false },
                        { label: 'TOOLS',   val: '84',          dot: false },
                        { label: 'MEM',     val: String(memory), dot: false },
                      ].map(s => (
                        <div key={s.label} className="status-badge">
                          {s.dot && (
                            <motion.div className="badge-dot"
                              animate={{ opacity: [1, 0.3, 1] }}
                              transition={{ duration: 1.7, repeat: Infinity }}
                            />
                          )}
                          <span className="badge-txt">{s.val ? `${s.val} ${s.label}` : s.label}</span>
                        </div>
                      ))}
                    </div>

                    {/* ── Form ── */}
                    <form onSubmit={handleLogin} style={{ padding: '20px 28px 0' }}>

                      {/* ── OAuth buttons ── */}
                      <div style={{ display: 'flex', gap: 10, marginBottom: 18 }}>
                        {/* Google */}
                        <button type="button" onClick={() => handleOAuth('google')} disabled={!!oauthLoading}
                          style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '10px 0', borderRadius: 10, background: 'rgb(var(--c-overlay) / 0.03)', border: '1px solid rgb(var(--c-overlay) / 0.10)', color: '#c8cad2', fontFamily: '"JetBrains Mono",monospace', fontSize: 11, letterSpacing: '0.07em', cursor: oauthLoading ? 'not-allowed' : 'pointer', opacity: oauthLoading && oauthLoading !== 'google' ? 0.45 : 1, transition: 'all 0.2s' }}
                          onMouseEnter={e => { if (!oauthLoading) (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgb(var(--c-overlay) / 0.22)'; }}
                          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgb(var(--c-overlay) / 0.10)'; }}
                        >
                          {oauthLoading === 'google'
                            ? <div style={{ width: 14, height: 14, border: '2px solid rgb(var(--c-overlay) / 0.18)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
                            : <svg width="15" height="15" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>
                          }
                          Google
                        </button>

                        {/* GitHub */}
                        <button type="button" onClick={() => handleOAuth('github')} disabled={!!oauthLoading}
                          style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '10px 0', borderRadius: 10, background: 'rgb(var(--c-overlay) / 0.03)', border: '1px solid rgb(var(--c-overlay) / 0.10)', color: '#c8cad2', fontFamily: '"JetBrains Mono",monospace', fontSize: 11, letterSpacing: '0.07em', cursor: oauthLoading ? 'not-allowed' : 'pointer', opacity: oauthLoading && oauthLoading !== 'github' ? 0.45 : 1, transition: 'all 0.2s' }}
                          onMouseEnter={e => { if (!oauthLoading) (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgb(var(--c-overlay) / 0.22)'; }}
                          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgb(var(--c-overlay) / 0.10)'; }}
                        >
                          {oauthLoading === 'github'
                            ? <div style={{ width: 14, height: 14, border: '2px solid rgb(var(--c-overlay) / 0.18)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
                            : <svg width="15" height="15" viewBox="0 0 24 24" fill="#e1e2e7"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.385-1.335-1.755-1.335-1.755-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.605-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12"/></svg>
                          }
                          GitHub
                        </button>
                      </div>

                      {/* Divider */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
                        <div style={{ flex: 1, height: 1, background: 'rgb(var(--c-primary) / 0.07)' }} />
                        <span style={{ fontFamily: '"JetBrains Mono",monospace', fontSize: 9.5, color: 'rgb(var(--c-primary) / 0.28)', letterSpacing: '0.18em' }}>OR</span>
                        <div style={{ flex: 1, height: 1, background: 'rgb(var(--c-primary) / 0.07)' }} />
                      </div>

                      {/* Email */}
                      <div style={{ marginBottom: 14 }}>
                        <label className={`field-label${focused === 'email' ? ' on' : ''}`} style={{ marginBottom: 7 }}>EMAIL ADDRESS</label>
                        <div className="input-wrap">
                          <div className="input-icon"><IconMail /></div>
                          <input
                            type="email"
                            className={`aps-input${focused === 'email' ? ' on' : ''}`}
                            style={{ paddingLeft: 38, paddingRight: email && isEmailOk ? 40 : 14 }}
                            value={email} onChange={e => setEmail(e.target.value)}
                            onFocus={() => setFocused('email')} onBlur={() => setFocused(null)}
                            placeholder="operator@aps.io" required
                          />
                          <AnimatePresence>
                            {email && isEmailOk && (
                              <motion.div className="valid-check"
                                initial={{ opacity: 0, scale: 0.5 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.5 }}
                              >✓</motion.div>
                            )}
                          </AnimatePresence>
                          <AnimatePresence>
                            {focused === 'email' && (
                              <motion.div className="focus-bar"
                                initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} exit={{ scaleX: 0, opacity: 0 }}
                              />
                            )}
                          </AnimatePresence>
                        </div>
                      </div>

                      {/* Password */}
                      <div style={{ marginBottom: 14 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 7 }}>
                          <label className={`field-label${focused === 'pwd' ? ' on' : ''}`}>PASSWORD</label>
                          <AnimatePresence>
                            {password && (
                              <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                                style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 8.5, color: STRENGTH_COLOR[strength], letterSpacing: '0.14em' }}>
                                {STRENGTH_LABEL[strength]}
                              </motion.span>
                            )}
                          </AnimatePresence>
                        </div>
                        <div className="input-wrap">
                          <div className="input-icon"><IconLock /></div>
                          <input
                            type={showPwd ? 'text' : 'password'}
                            className={`aps-input${focused === 'pwd' ? ' on' : ''}`}
                            style={{ paddingLeft: 38, paddingRight: 40 }}
                            value={password} onChange={e => setPassword(e.target.value)}
                            onFocus={() => setFocused('pwd')} onBlur={() => setFocused(null)}
                            placeholder="••••••••••••" required
                          />
                          <button type="button" className="pwd-toggle" onClick={() => setShowPwd(s => !s)}>
                            <IconEye off={showPwd} />
                          </button>
                          <AnimatePresence>
                            {focused === 'pwd' && (
                              <motion.div className="focus-bar"
                                initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} exit={{ scaleX: 0, opacity: 0 }}
                              />
                            )}
                          </AnimatePresence>
                        </div>
                        {/* Strength segments */}
                        <AnimatePresence>
                          {password && (
                            <motion.div className="strength-bar" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                              {[0, 1, 2].map(i => (
                                <motion.div key={i} className="strength-seg"
                                  animate={{ backgroundColor: i <= strength ? STRENGTH_COLOR[strength] : 'rgb(var(--c-primary) / 0.07)', opacity: i <= strength ? 1 : 0.35 }}
                                  transition={{ delay: i * 0.05, duration: 0.25 }}
                                />
                              ))}
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>

                      {/* Remember toggle + Forgot */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 22 }}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
                          {/* Custom toggle */}
                          <div
                            className="toggle-track"
                            onClick={() => setRemember(r => !r)}
                            style={{
                              background: remember ? 'rgb(var(--c-accent-cyan) / 0.15)' : 'rgb(var(--c-bg-deep) / 0.9)',
                              border: remember ? '1px solid rgb(var(--c-accent-cyan) / 0.42)' : '1px solid rgb(var(--c-primary) / 0.09)',
                              boxShadow: remember ? '0 0 10px rgb(var(--c-accent-cyan) / 0.14)' : 'none',
                            }}
                          >
                            <motion.div
                              className="toggle-thumb"
                              animate={{
                                x: remember ? 15 : 0,
                                backgroundColor: remember ? 'rgb(var(--c-accent-cyan))' : 'rgb(var(--c-primary) / 0.22)',
                                boxShadow: remember ? '0 0 8px rgb(var(--c-accent-cyan) / 0.65)' : 'none',
                              }}
                              transition={{ type: 'spring', stiffness: 420, damping: 28 }}
                            />
                          </div>
                          <span style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: remember ? 'rgb(var(--c-primary) / 0.62)' : '#2e3648', transition: 'color 0.2s' }}>
                            Remember Session
                          </span>
                        </label>

                        <Link to="/forgot-password"
                          style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: 'rgb(var(--c-accent-cyan) / 0.48)', textDecoration: 'none', transition: 'color 0.2s' }}
                          onMouseOver={e => (e.currentTarget.style.color = 'rgb(var(--c-accent-cyan))')}
                          onMouseOut={e  => (e.currentTarget.style.color = 'rgb(var(--c-accent-cyan) / 0.48)')}
                        >
                          Recover Access →
                        </Link>
                      </div>

                      {/* API error */}
                      {apiError && (
                        <motion.div
                          initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
                          style={{ marginBottom: 14, padding: '9px 13px', borderRadius: 8, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.28)', fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: '#EF4444', letterSpacing: '0.04em' }}
                        >
                          ✗ {apiError}
                        </motion.div>
                      )}

                      {/* CTA */}
                      <div style={{ marginBottom: 0 }}>
                        <button
                          ref={btnRef} type="submit"
                          className="btn-mission"
                          onMouseMove={handleMagnet}
                          onMouseLeave={resetMagnet}
                        >
                          <AnimatePresence>
                            {ripple && (
                              <motion.div key={ripple.id}
                                initial={{ width: 0, height: 0, opacity: 0.45 }}
                                animate={{ width: 500, height: 500, opacity: 0 }}
                                transition={{ duration: 0.7, ease: 'easeOut' }}
                                style={{ position: 'absolute', left: ripple.x, top: ripple.y, borderRadius: '50%', background: 'rgb(var(--c-accent-cyan) / 0.18)', transform: 'translate(-50%,-50%)', pointerEvents: 'none' }}
                              />
                            )}
                          </AnimatePresence>
                          <span style={{ position: 'relative', zIndex: 1 }}>ACCESS MISSION CONTROL</span>
                          <div className="btn-sweep" />
                        </button>
                      </div>

                      {/* Trust strip */}
                      <div className="trust-strip" style={{ marginTop: 18 }}>
                        <div className="trust-item">
                          <IconShield />
                          <span>AES-256</span>
                        </div>
                        <div className="trust-sep" />
                        <div className="trust-item">
                          <motion.div style={{ width: 5, height: 5, borderRadius: '50%', background: '#79ff5b', boxShadow: '0 0 4px rgba(121,255,91,0.7)' }}
                            animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 1.8, repeat: Infinity }} />
                          <span>NETWORK ONLINE</span>
                        </div>
                        <div className="trust-sep" />
                        <div className="trust-item">
                          <span>INCIDENT</span>
                          <span className="trust-hi">0 DAYS</span>
                        </div>
                      </div>

                      {/* Signup link */}
                      <div style={{ textAlign: 'center', padding: '14px 0 28px' }}>
                        <span style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: '#252c3b' }}>No operator account? </span>
                        <Link to="/signup"
                          style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: 'rgb(var(--c-accent-cyan) / 0.55)', textDecoration: 'none', transition: 'color 0.2s' }}
                          onMouseOver={e => (e.currentTarget.style.color = 'rgb(var(--c-accent-cyan))')}
                          onMouseOut={e  => (e.currentTarget.style.color = 'rgb(var(--c-accent-cyan) / 0.55)')}
                        >
                          Initialize →
                        </Link>
                      </div>
                    </form>
                  </motion.div>
                )}

                {/* ════════════════════════════════════════════
                    PHASE: BOOTING — in-card boot sequence
                ════════════════════════════════════════════ */}
                {phase === 'booting' && (
                  <motion.div key="boot"
                    initial={{ opacity: 0, filter: 'blur(4px)' }}
                    animate={{ opacity: 1, filter: 'blur(0px)' }}
                    transition={{ duration: 0.28 }}
                    style={{ padding: '44px 32px 48px' }}
                  >
                    <div style={{ textAlign: 'center', marginBottom: 36 }}>
                      <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 9, color: 'rgb(var(--c-accent-cyan) / 0.42)', letterSpacing: '0.3em', marginBottom: 28 }}>
                        SYSTEM BOOT SEQUENCE
                      </div>

                      {/* Dual-ring spinner */}
                      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 32 }}>
                        <div style={{ position: 'relative', width: 60, height: 60 }}>
                          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'rgb(var(--c-accent-cyan) / 0.05)', border: '1px solid rgb(var(--c-accent-cyan) / 0.16)' }} />
                          <motion.div className="boot-ring-outer"
                            animate={{ rotate: 360 }}
                            transition={{ duration: 1.1, repeat: Infinity, ease: 'linear' }}
                          />
                          <motion.div className="boot-ring-inner"
                            animate={{ rotate: -360 }}
                            transition={{ duration: 1.9, repeat: Infinity, ease: 'linear' }}
                          />
                          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <motion.div
                              style={{ width: 8, height: 8, borderRadius: '50%', background: 'rgb(var(--c-accent-cyan))' }}
                              animate={{ boxShadow: ['0 0 8px rgb(var(--c-accent-cyan) / 0.6)', '0 0 20px rgb(var(--c-accent-cyan) / 0.95)', '0 0 8px rgb(var(--c-accent-cyan) / 0.6)'] }}
                              transition={{ duration: 1.1, repeat: Infinity }}
                            />
                          </div>
                        </div>
                      </div>

                      {/* Progress bar */}
                      <div style={{ height: 2.5, background: 'rgb(var(--c-primary) / 0.06)', borderRadius: 2, overflow: 'hidden', marginBottom: 6 }}>
                        <motion.div
                          style={{ height: '100%', borderRadius: 2, background: 'linear-gradient(90deg, rgb(var(--c-accent-cyan) / 0.55), #00E5FF)', boxShadow: '0 0 8px rgb(var(--c-accent-cyan) / 0.5)' }}
                          animate={{ width: `${progress}%` }}
                          transition={{ duration: 0.32, ease: 'easeOut' }}
                        />
                      </div>
                      <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 9, color: 'rgb(var(--c-accent-cyan) / 0.38)', letterSpacing: '0.1em' }}>
                        {progress}%
                      </div>
                    </div>

                    {/* Steps */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      {BOOT_STEPS.map((s, i) => {
                        const done    = i < bootStep;
                        const active  = i === bootStep;
                        return (
                          <motion.div key={s.label}
                            initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.04 }}
                            style={{ display: 'flex', alignItems: 'center', gap: 12, fontFamily: '"JetBrains Mono", monospace', fontSize: 11.5,
                              color: done ? 'rgb(var(--c-accent-cyan))' : active ? 'rgb(var(--c-text))' : '#1e2535' }}
                          >
                            <div className="boot-step-icon"
                              style={{
                                border: `1px solid ${done ? 'rgb(var(--c-accent-cyan) / 0.45)' : active ? 'rgb(var(--c-primary) / 0.18)' : 'rgb(var(--c-primary) / 0.05)'}`,
                                background: done ? 'rgb(var(--c-accent-cyan) / 0.1)' : 'transparent',
                              }}
                            >
                              {done  && <span style={{ fontSize: 8, color: 'rgb(var(--c-accent-cyan))', fontWeight: 700 }}>✓</span>}
                              {active && (
                                <motion.div style={{ width: 5, height: 5, borderRadius: '50%', background: 'rgb(var(--c-text))' }}
                                  animate={{ opacity: [1, 0.25, 1] }} transition={{ duration: 0.65, repeat: Infinity }}
                                />
                              )}
                            </div>
                            {s.label}
                          </motion.div>
                        );
                      })}
                    </div>
                  </motion.div>
                )}

                {/* ════════════════════════════════════════════
                    PHASE: GRANTED
                ════════════════════════════════════════════ */}
                {phase === 'granted' && (
                  <motion.div key="granted"
                    initial={{ opacity: 0, scale: 0.9, filter: 'blur(4px)' }}
                    animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }}
                    transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.4 }}
                    style={{ padding: '72px 32px', textAlign: 'center' }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 28 }}>
                      <motion.div
                        style={{ width: 72, height: 72, borderRadius: 20, background: 'rgb(var(--c-accent-cyan) / 0.08)', border: '1px solid rgb(var(--c-accent-cyan) / 0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                        animate={{ boxShadow: ['0 0 20px rgb(var(--c-accent-cyan) / 0.2)', '0 0 75px rgb(var(--c-accent-cyan) / 0.58)', '0 0 20px rgb(var(--c-accent-cyan) / 0.2)'] }}
                        transition={{ duration: 1.1, repeat: Infinity }}
                      >
                        <span style={{ color: 'rgb(var(--c-accent-cyan))', fontSize: 30 }}>✓</span>
                      </motion.div>
                    </div>
                    <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 18, fontWeight: 700, color: 'rgb(var(--c-accent-cyan))', letterSpacing: '0.2em', marginBottom: 10 }}>
                      ACCESS GRANTED
                    </div>
                    <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: 'rgb(var(--c-primary) / 0.38)', letterSpacing: '0.08em' }}>
                      Entering Mission Control...
                    </div>
                  </motion.div>
                )}

              </AnimatePresence>
            </div>
          </motion.div>
        </div>
      </motion.div>
    </div>
  );
}
