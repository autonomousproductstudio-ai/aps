import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import AuthLeftPanel from '../components/AuthLeftPanel';
import { useAuth } from '../lib/AuthContext';

const PROVISION_STEPS = [
  'Operator Created',
  'Agent Permissions Assigned',
  'Workspace Provisioned',
  'Memory Initialized',
  'Mission Control Ready',
];

const ROLES = [
  'Founder / CEO',
  'Product Manager',
  'Engineering Lead',
  'Design Lead',
  'Researcher',
  'Investor',
  'Other',
];

const CSS = `
  @keyframes gspin { to { transform: rotate(360deg); } }
  .aps-input-g {
    width: 100%;
    padding: 12px 16px;
    border-radius: 10px;
    font-family: "JetBrains Mono", monospace;
    font-size: 13px;
    color: #e1e2e7;
    background: rgb(var(--c-deep) / 0.9);
    border: 1px solid rgba(121,255,91,0.09);
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
    box-sizing: border-box;
  }
  .aps-input-g::placeholder { color: #343b4d; }
  .aps-input-g:focus {
    border-color: rgba(121,255,91,0.35);
    box-shadow: 0 0 0 3px rgba(121,255,91,0.055), inset 0 1px 0 rgba(121,255,91,0.04);
  }
  .aps-input-g.err { border-color: rgba(239,68,68,0.5) !important; }
  .aps-select-g {
    width: 100%; padding: 12px 36px 12px 16px;
    border-radius: 10px;
    font-family: "JetBrains Mono", monospace;
    font-size: 12px; color: #e1e2e7;
    background: rgb(var(--c-deep) / 0.9);
    border: 1px solid rgba(121,255,91,0.09);
    outline: none; appearance: none; cursor: pointer;
    transition: border-color 0.2s, box-shadow 0.2s;
    box-sizing: border-box;
  }
  .aps-select-g:focus {
    border-color: rgba(121,255,91,0.35);
    box-shadow: 0 0 0 3px rgba(121,255,91,0.055);
  }
  .aps-select-g option { background: #111417; }
  .focus-bar-g {
    height: 1px; margin-top: 3px; transform-origin: left;
    background: linear-gradient(90deg, transparent, rgba(121,255,91,0.48), transparent);
  }
  .btn-init {
    position: relative; overflow: hidden;
    width: 100%; padding: 14px 0;
    border-radius: 10px;
    font-family: "JetBrains Mono", monospace;
    font-size: 12px; font-weight: 700; letter-spacing: 0.15em;
    color: #79ff5b;
    background: linear-gradient(135deg, rgba(121,255,91,0.10), rgba(57,220,20,0.17));
    border: 1px solid rgba(121,255,91,0.30);
    box-shadow: 0 0 22px rgba(121,255,91,0.09);
    cursor: pointer; transition: box-shadow 0.25s, transform 0.12s;
  }
  .btn-init:hover { box-shadow: 0 0 50px rgba(121,255,91,0.26); }
  .btn-init:active { transform: scale(0.99); }
  .btn-init::after {
    content: ''; position: absolute; inset: 0;
    background: linear-gradient(90deg, transparent, rgba(121,255,91,0.09), transparent);
    transform: translateX(-200%);
  }
  .btn-init:hover::after { transform: translateX(200%); transition: transform 0.65s ease-out; }
  .btn-init:disabled { opacity: 0.5; cursor: not-allowed; }
  .scan-sweep-g {
    position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(121,255,91,0.2), transparent);
    animation: scanDownG 5s linear infinite;
  }
  @keyframes scanDownG {
    0%   { top: 0;    opacity: 0; }
    4%   { opacity: 1; }
    96%  { opacity: 0.4; }
    100% { top: 100%; opacity: 0; }
  }
`;

export default function SignupPage() {
  const navigate = useNavigate();
  const auth     = useAuth();

  const [name,     setName]     = useState('');
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [confirm,  setConfirm]  = useState('');
  const [role,     setRole]     = useState('');
  const [focused,  setFocused]  = useState<string | null>(null);
  const [step,        setStep]        = useState(-1);
  const [ready,       setReady]       = useState(false);
  const [apiError,    setApiError]    = useState('');
  const [oauthLoading, setOauthLoading] = useState<'google' | 'github' | null>(null);

  const isProvisioning = step >= 0;
  const pwdMismatch    = !!confirm && password !== confirm;

  const runProvision = async () => {
    for (let i = 0; i < PROVISION_STEPS.length; i++) {
      setStep(i);
      await new Promise(r => setTimeout(r, 410));
    }
    await new Promise(r => setTimeout(r, 320));
    setReady(true);
    await new Promise(r => setTimeout(r, 950));
    navigate('/', { replace: true });
  };

  const handleOAuth = async (provider: 'google' | 'github') => {
    setApiError('');
    setOauthLoading(provider);
    try {
      if (provider === 'google') await auth.loginWithGoogle();
      else                        await auth.loginWithGithub();
      await runProvision();
    } catch (err: any) {
      const msg = err?.code === 'auth/popup-closed-by-user' ? '' : (err.message || 'OAuth sign-in failed.');
      setApiError(msg);
    } finally {
      setOauthLoading(null);
    }
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (pwdMismatch) return;
    setApiError('');

    try {
      await auth.signup(name, email, password, role);
    } catch (err: any) {
      setApiError(err.message || 'Signup failed. Please try again.');
      return;
    }
    await runProvision();
  };

  const labelColor = (field: string, base = 'rgba(121,255,91,0.38)') =>
    focused === field ? 'rgba(121,255,91,0.68)' : base;

  return (
    <div style={{ minHeight: '100vh', display: 'flex', overflow: 'hidden', background: 'rgb(var(--c-bg-deep))' }}>
      <style>{CSS}</style>

      {/* LEFT */}
      <div className="hidden lg:flex" style={{ width: '50%', flexShrink: 0 }}>
        <AuthLeftPanel />
      </div>

      {/* RIGHT */}
      <motion.div
        style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px 40px', position: 'relative', overflowY: 'auto' }}
        initial={{ opacity: 0, x: 28 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: 'radial-gradient(ellipse at 25% 50%, rgba(121,255,91,0.025) 0%, transparent 62%)' }} />

        <div style={{ width: '100%', maxWidth: 420, paddingTop: 12, paddingBottom: 12 }}>
          <motion.div
            style={{
              borderRadius: 20,
              background: 'rgb(var(--c-bg-deep) / 0.93)',
              backdropFilter: 'blur(36px)',
              border: '1px solid rgba(121,255,91,0.08)',
              boxShadow: 'inset 0 0 0 1px rgba(121,255,91,0.03), 0 0 55px rgba(121,255,91,0.05), 0 40px 80px rgb(var(--c-deepest) / 0.55)',
              overflow: 'hidden', position: 'relative',
            }}
            initial={{ opacity: 0, y: 22 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="scan-sweep-g" />
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg, transparent 5%, rgba(121,255,91,0.24) 50%, transparent 95%)', zIndex: 1 }} />
            <div style={{ position: 'absolute', top: 0, left: 0, bottom: 0, width: 1, background: 'linear-gradient(180deg, rgba(121,255,91,0.12), transparent 55%)', zIndex: 1 }} />
            <div style={{ position: 'absolute', top: 0, right: 0, bottom: 0, width: 1, background: 'linear-gradient(180deg, rgba(121,255,91,0.12), transparent 55%)', zIndex: 1 }} />

            <div style={{ position: 'relative', zIndex: 2 }}>
              {/* Header */}
              <div style={{ padding: '30px 32px 22px', borderBottom: '1px solid rgba(121,255,91,0.06)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 18 }}>
                  <div style={{ width: 44, height: 44, borderRadius: 13, background: 'rgba(121,255,91,0.07)', border: '1px solid rgba(121,255,91,0.18)', boxShadow: 'inset 0 1px 0 rgba(121,255,91,0.07)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <div style={{ width: 18, height: 18, borderRadius: 5, background: 'linear-gradient(135deg, rgba(121,255,91,0.85), rgba(57,200,20,0.6))' }} />
                  </div>
                  <div>
                    <div style={{ color: '#79ff5b', fontFamily: '"JetBrains Mono", monospace', fontSize: 12, fontWeight: 700, letterSpacing: '0.2em' }}>NEW OPERATOR</div>
                    <div style={{ color: 'rgba(121,255,91,0.32)', fontFamily: '"JetBrains Mono", monospace', fontSize: 8.5, letterSpacing: '0.12em' }}>REGISTRATION PROTOCOL</div>
                  </div>
                </div>
                <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 22, fontWeight: 700, color: 'rgb(var(--c-text))', letterSpacing: '-0.02em', margin: 0, lineHeight: 1.2 }}>
                  Initialize New Operator
                </h1>
                <p style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: '#4A5268', marginTop: 7, letterSpacing: '0.04em', lineHeight: 1.5 }}>
                  Provision access to Autonomous Product Studio
                </p>
              </div>

              {/* Form */}
              <form onSubmit={handleSignup} style={{ padding: '22px 32px 30px' }}>

                {/* ── OAuth ── */}
                <div style={{ display: 'flex', gap: 10, marginBottom: 18 }}>
                  <button type="button" onClick={() => handleOAuth('google')} disabled={!!oauthLoading || isProvisioning}
                    style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '10px 0', borderRadius: 10, background: 'rgb(var(--c-overlay) / 0.03)', border: '1px solid rgb(var(--c-overlay) / 0.10)', color: '#c8cad2', fontFamily: '"JetBrains Mono",monospace', fontSize: 11, letterSpacing: '0.07em', cursor: (oauthLoading || isProvisioning) ? 'not-allowed' : 'pointer', opacity: oauthLoading && oauthLoading !== 'google' ? 0.45 : 1, transition: 'all 0.2s' }}>
                    {oauthLoading === 'google'
                      ? <div style={{ width: 14, height: 14, border: '2px solid rgb(var(--c-overlay) / 0.18)', borderTopColor: '#79ff5b', borderRadius: '50%', animation: 'gspin 0.7s linear infinite' }} />
                      : <svg width="15" height="15" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>
                    }
                    Google
                  </button>
                  <button type="button" onClick={() => handleOAuth('github')} disabled={!!oauthLoading || isProvisioning}
                    style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '10px 0', borderRadius: 10, background: 'rgb(var(--c-overlay) / 0.03)', border: '1px solid rgb(var(--c-overlay) / 0.10)', color: '#c8cad2', fontFamily: '"JetBrains Mono",monospace', fontSize: 11, letterSpacing: '0.07em', cursor: (oauthLoading || isProvisioning) ? 'not-allowed' : 'pointer', opacity: oauthLoading && oauthLoading !== 'github' ? 0.45 : 1, transition: 'all 0.2s' }}>
                    {oauthLoading === 'github'
                      ? <div style={{ width: 14, height: 14, border: '2px solid rgb(var(--c-overlay) / 0.18)', borderTopColor: '#79ff5b', borderRadius: '50%', animation: 'gspin 0.7s linear infinite' }} />
                      : <svg width="15" height="15" viewBox="0 0 24 24" fill="#e1e2e7"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.385-1.335-1.755-1.335-1.755-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.605-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12"/></svg>
                    }
                    GitHub
                  </button>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
                  <div style={{ flex: 1, height: 1, background: 'rgba(121,255,91,0.07)' }} />
                  <span style={{ fontFamily: '"JetBrains Mono",monospace', fontSize: 9.5, color: 'rgba(121,255,91,0.28)', letterSpacing: '0.18em' }}>OR</span>
                  <div style={{ flex: 1, height: 1, background: 'rgba(121,255,91,0.07)' }} />
                </div>

                {/* Name */}
                <div style={{ marginBottom: 14 }}>
                  <label style={{ display: 'block', marginBottom: 7, fontFamily: '"JetBrains Mono", monospace', fontSize: 9.5, color: labelColor('name'), letterSpacing: '0.18em', transition: 'color 0.2s' }}>OPERATOR NAME</label>
                  <input type="text" className="aps-input-g" value={name} onChange={e => setName(e.target.value)} onFocus={() => setFocused('name')} onBlur={() => setFocused(null)} placeholder="Your full name" required />
                  <AnimatePresence>
                    {focused === 'name' && <motion.div className="focus-bar-g" initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} exit={{ scaleX: 0, opacity: 0 }} />}
                  </AnimatePresence>
                </div>

                {/* Email */}
                <div style={{ marginBottom: 14 }}>
                  <label style={{ display: 'block', marginBottom: 7, fontFamily: '"JetBrains Mono", monospace', fontSize: 9.5, color: labelColor('email'), letterSpacing: '0.18em', transition: 'color 0.2s' }}>EMAIL ADDRESS</label>
                  <input type="email" className="aps-input-g" value={email} onChange={e => setEmail(e.target.value)} onFocus={() => setFocused('email')} onBlur={() => setFocused(null)} placeholder="operator@aps.io" required />
                  <AnimatePresence>
                    {focused === 'email' && <motion.div className="focus-bar-g" initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} exit={{ scaleX: 0, opacity: 0 }} />}
                  </AnimatePresence>
                </div>

                {/* Password */}
                <div style={{ marginBottom: 14 }}>
                  <label style={{ display: 'block', marginBottom: 7, fontFamily: '"JetBrains Mono", monospace', fontSize: 9.5, color: labelColor('pwd'), letterSpacing: '0.18em', transition: 'color 0.2s' }}>PASSWORD</label>
                  <input type="password" className="aps-input-g" value={password} onChange={e => setPassword(e.target.value)} onFocus={() => setFocused('pwd')} onBlur={() => setFocused(null)} placeholder="Min. 8 characters" required minLength={8} />
                  <AnimatePresence>
                    {focused === 'pwd' && <motion.div className="focus-bar-g" initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} exit={{ scaleX: 0, opacity: 0 }} />}
                  </AnimatePresence>
                </div>

                {/* Confirm */}
                <div style={{ marginBottom: 14 }}>
                  <label style={{ display: 'block', marginBottom: 7, fontFamily: '"JetBrains Mono", monospace', fontSize: 9.5, color: pwdMismatch ? 'rgba(239,68,68,0.7)' : labelColor('confirm'), letterSpacing: '0.18em', transition: 'color 0.2s' }}>CONFIRM PASSWORD</label>
                  <input type="password" className={`aps-input-g${pwdMismatch ? ' err' : ''}`} value={confirm} onChange={e => setConfirm(e.target.value)} onFocus={() => setFocused('confirm')} onBlur={() => setFocused(null)} placeholder="Repeat password" required />
                  <AnimatePresence>
                    {pwdMismatch && (
                      <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                        style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 10, color: '#EF4444', marginTop: 5, letterSpacing: '0.04em' }}>
                        ✗ Passwords do not match
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                {/* Role */}
                <div style={{ marginBottom: 22 }}>
                  <label style={{ display: 'block', marginBottom: 7, fontFamily: '"JetBrains Mono", monospace', fontSize: 9.5, color: labelColor('role'), letterSpacing: '0.18em', transition: 'color 0.2s' }}>OPERATOR ROLE</label>
                  <div style={{ position: 'relative' }}>
                    <select className="aps-select-g" value={role} onChange={e => setRole(e.target.value)} onFocus={() => setFocused('role')} onBlur={() => setFocused(null)} required>
                      <option value="" disabled>Select your role</option>
                      {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                    </select>
                    <div style={{ position: 'absolute', right: 13, top: '50%', transform: 'translateY(-50%)', color: 'rgba(121,255,91,0.38)', fontSize: 10, pointerEvents: 'none' }}>▾</div>
                  </div>
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
                <button type="submit" className="btn-init" disabled={isProvisioning || pwdMismatch}>
                  {isProvisioning ? 'PROVISIONING...' : 'INITIALIZE ACCOUNT'}
                </button>

                <div style={{ textAlign: 'center', marginTop: 22 }}>
                  <span style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: '#343b4d' }}>Already an operator? </span>
                  <Link to="/login"
                    style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: 'rgb(var(--c-accent-cyan) / 0.62)', textDecoration: 'none', transition: 'color 0.2s' }}
                    onMouseOver={e => (e.currentTarget.style.color = 'rgb(var(--c-accent-cyan))')}
                    onMouseOut={e  => (e.currentTarget.style.color = 'rgb(var(--c-accent-cyan) / 0.62)')}
                  >
                    Access Portal →
                  </Link>
                </div>
              </form>
            </div>
          </motion.div>
        </div>
      </motion.div>

      {/* Provision overlay */}
      <AnimatePresence>
        {isProvisioning && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            style={{ position: 'fixed', inset: 0, zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgb(var(--c-deep) / 0.96)', backdropFilter: 'blur(18px)' }}
          >
            <div style={{ textAlign: 'center', minWidth: 300 }}>
              <AnimatePresence mode="wait">
                {!ready ? (
                  <motion.div key="prov" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -14 }}>
                    <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 34 }}>
                      <div style={{ width: 62, height: 62, borderRadius: 17, background: 'rgba(121,255,91,0.07)', border: '1px solid rgba(121,255,91,0.22)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <motion.div style={{ width: 30, height: 30, border: '2px solid rgba(121,255,91,0.18)', borderTopColor: '#79ff5b', borderRadius: '50%' }} animate={{ rotate: 360 }} transition={{ duration: 0.85, repeat: Infinity, ease: 'linear' }} />
                      </div>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
                      {PROVISION_STEPS.map((s, i) => (
                        <motion.div key={s} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                          style={{ display: 'flex', alignItems: 'center', gap: 10, fontFamily: '"JetBrains Mono", monospace', fontSize: 12, color: i < step ? '#79ff5b' : i === step ? 'rgb(var(--c-text))' : '#2e3648' }}
                        >
                          <span style={{ width: 14, fontSize: 10 }}>{i < step ? '✓' : i === step ? '▶' : '·'}</span>
                          {s}
                        </motion.div>
                      ))}
                    </div>
                  </motion.div>
                ) : (
                  <motion.div key="ready" initial={{ opacity: 0, scale: 0.87 }} animate={{ opacity: 1, scale: 1 }} transition={{ ease: [0.16, 1, 0.3, 1] }}>
                    <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 22 }}>
                      <motion.div
                        style={{ width: 66, height: 66, borderRadius: 18, background: 'rgba(121,255,91,0.09)', border: '1px solid rgba(121,255,91,0.38)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                        animate={{ boxShadow: ['0 0 20px rgba(121,255,91,0.18)', '0 0 65px rgba(121,255,91,0.5)', '0 0 20px rgba(121,255,91,0.18)'] }}
                        transition={{ duration: 1.1, repeat: Infinity }}
                      >
                        <span style={{ color: '#79ff5b', fontSize: 26 }}>✓</span>
                      </motion.div>
                    </div>
                    <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 15, fontWeight: 700, color: '#79ff5b', letterSpacing: '0.16em' }}>MISSION CONTROL READY</div>
                    <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: 'rgb(var(--c-primary) / 0.45)', marginTop: 9, letterSpacing: '0.07em' }}>Entering workspace...</div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
