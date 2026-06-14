import { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import AuthLeftPanel from '../components/AuthLeftPanel';

const CSS = `
  .aps-input-a {
    width: 100%; padding: 12px 16px;
    border-radius: 10px;
    font-family: "JetBrains Mono", monospace;
    font-size: 13px; color: #e1e2e7;
    background: rgb(var(--c-deep) / 0.9);
    border: 1px solid rgba(245,158,11,0.09);
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
    box-sizing: border-box;
  }
  .aps-input-a::placeholder { color: #343b4d; }
  .aps-input-a:focus {
    border-color: rgba(245,158,11,0.38);
    box-shadow: 0 0 0 3px rgba(245,158,11,0.055), inset 0 1px 0 rgba(245,158,11,0.04);
  }
  .focus-bar-a {
    height: 1px; margin-top: 3px; transform-origin: left;
    background: linear-gradient(90deg, transparent, rgba(245,158,11,0.48), transparent);
  }
  .btn-recover {
    position: relative; overflow: hidden;
    width: 100%; padding: 14px 0;
    border-radius: 10px;
    font-family: "JetBrains Mono", monospace;
    font-size: 12px; font-weight: 700; letter-spacing: 0.15em;
    color: #F59E0B;
    background: linear-gradient(135deg, rgba(245,158,11,0.10), rgba(217,110,6,0.17));
    border: 1px solid rgba(245,158,11,0.30);
    box-shadow: 0 0 22px rgba(245,158,11,0.09);
    cursor: pointer; transition: box-shadow 0.25s, transform 0.12s;
  }
  .btn-recover:hover { box-shadow: 0 0 50px rgba(245,158,11,0.26); }
  .btn-recover:active { transform: scale(0.99); }
  .btn-recover::after {
    content: ''; position: absolute; inset: 0;
    background: linear-gradient(90deg, transparent, rgba(245,158,11,0.09), transparent);
    transform: translateX(-200%);
  }
  .btn-recover:hover::after { transform: translateX(200%); transition: transform 0.65s ease-out; }
  .btn-recover:disabled { opacity: 0.5; cursor: not-allowed; }
  .scan-sweep-a {
    position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(245,158,11,0.2), transparent);
    animation: scanDownA 5s linear infinite;
  }
  @keyframes scanDownA {
    0%   { top: 0;    opacity: 0; }
    4%   { opacity: 1; }
    96%  { opacity: 0.4; }
    100% { top: 100%; opacity: 0; }
  }
`;

export default function ForgotPasswordPage() {
  const [email,   setEmail]   = useState('');
  const [focused, setFocused] = useState(false);
  const [loading, setLoading] = useState(false);
  const [sent,    setSent]    = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await fetch('/v1/auth/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim() }),
      });
    } catch { /* always show sent — don't leak which emails exist */ }
    setSent(true);
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', overflow: 'hidden', background: 'rgb(var(--c-bg-deep))' }}>
      <style>{CSS}</style>

      {/* LEFT */}
      <div className="hidden lg:flex" style={{ width: '50%', flexShrink: 0 }}>
        <AuthLeftPanel />
      </div>

      {/* RIGHT */}
      <motion.div
        style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '32px 40px', position: 'relative' }}
        initial={{ opacity: 0, x: 28 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: 'radial-gradient(ellipse at 25% 50%, rgba(245,158,11,0.025) 0%, transparent 62%)' }} />

        <div style={{ width: '100%', maxWidth: 420 }}>
          <motion.div
            style={{
              borderRadius: 20,
              background: 'rgb(var(--c-bg-deep) / 0.93)',
              backdropFilter: 'blur(36px)',
              border: '1px solid rgba(245,158,11,0.08)',
              boxShadow: 'inset 0 0 0 1px rgba(245,158,11,0.03), 0 0 55px rgba(245,158,11,0.05), 0 40px 80px rgb(var(--c-deepest) / 0.55)',
              overflow: 'hidden', position: 'relative',
            }}
            initial={{ opacity: 0, y: 22 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="scan-sweep-a" />
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg, transparent 5%, rgba(245,158,11,0.24) 50%, transparent 95%)', zIndex: 1 }} />
            <div style={{ position: 'absolute', top: 0, left: 0, bottom: 0, width: 1, background: 'linear-gradient(180deg, rgba(245,158,11,0.12), transparent 55%)', zIndex: 1 }} />
            <div style={{ position: 'absolute', top: 0, right: 0, bottom: 0, width: 1, background: 'linear-gradient(180deg, rgba(245,158,11,0.12), transparent 55%)', zIndex: 1 }} />

            <div style={{ position: 'relative', zIndex: 2 }}>
              {/* Header */}
              <div style={{ padding: '30px 32px 22px', borderBottom: '1px solid rgba(245,158,11,0.06)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 18 }}>
                  <div style={{ width: 44, height: 44, borderRadius: 13, background: 'rgba(245,158,11,0.07)', border: '1px solid rgba(245,158,11,0.18)', boxShadow: 'inset 0 1px 0 rgba(245,158,11,0.07)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <div style={{ width: 18, height: 18, borderRadius: 5, background: 'linear-gradient(135deg, rgba(245,158,11,0.85), rgba(217,110,6,0.6))' }} />
                  </div>
                  <div>
                    <div style={{ color: '#F59E0B', fontFamily: '"JetBrains Mono", monospace', fontSize: 12, fontWeight: 700, letterSpacing: '0.2em' }}>RECOVERY PROTOCOL</div>
                    <div style={{ color: 'rgba(245,158,11,0.32)', fontFamily: '"JetBrains Mono", monospace', fontSize: 8.5, letterSpacing: '0.12em' }}>CREDENTIAL RESET SYSTEM</div>
                  </div>
                </div>
                <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 22, fontWeight: 700, color: 'rgb(var(--c-text))', letterSpacing: '-0.02em', margin: 0, lineHeight: 1.2 }}>
                  Recover Access Node
                </h1>
                <p style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: '#4A5268', marginTop: 7, letterSpacing: '0.04em', lineHeight: 1.5 }}>
                  Reset authentication credentials for your operator account
                </p>
              </div>

              {/* Body */}
              <div style={{ padding: '26px 32px 32px' }}>
                <AnimatePresence mode="wait">
                  {!sent ? (
                    <motion.form key="form" onSubmit={handleSubmit}
                      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, y: -10 }}
                    >
                      <div style={{ marginBottom: 24 }}>
                        <label style={{
                          display: 'block', marginBottom: 8,
                          fontFamily: '"JetBrains Mono", monospace', fontSize: 9.5,
                          color: focused ? 'rgba(245,158,11,0.68)' : 'rgba(245,158,11,0.38)',
                          letterSpacing: '0.18em', transition: 'color 0.2s',
                        }}>
                          REGISTERED EMAIL
                        </label>
                        <input
                          type="email" className="aps-input-a"
                          value={email} onChange={e => setEmail(e.target.value)}
                          onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
                          placeholder="operator@aps.io" required
                        />
                        <AnimatePresence>
                          {focused && (
                            <motion.div className="focus-bar-a"
                              initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} exit={{ scaleX: 0, opacity: 0 }}
                            />
                          )}
                        </AnimatePresence>
                        <p style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 10, color: '#343b4d', marginTop: 9, letterSpacing: '0.04em', lineHeight: 1.55 }}>
                          A recovery transmission will be dispatched to this address.
                        </p>
                      </div>

                      <button type="submit" className="btn-recover" disabled={loading}>
                        {loading ? (
                          <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 9 }}>
                            <motion.span
                              style={{ display: 'inline-block', width: 13, height: 13, border: '2px solid rgba(245,158,11,0.25)', borderTopColor: '#F59E0B', borderRadius: '50%' }}
                              animate={{ rotate: 360 }}
                              transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
                            />
                            TRANSMITTING...
                          </span>
                        ) : 'SEND RECOVERY PROTOCOL'}
                      </button>

                      <div style={{ textAlign: 'center', marginTop: 22 }}>
                        <Link to="/login"
                          style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: 'rgb(var(--c-accent-cyan) / 0.52)', textDecoration: 'none', transition: 'color 0.2s' }}
                          onMouseOver={e => (e.currentTarget.style.color = 'rgb(var(--c-accent-cyan))')}
                          onMouseOut={e  => (e.currentTarget.style.color = 'rgb(var(--c-accent-cyan) / 0.52)')}
                        >
                          ← Return to Access Portal
                        </Link>
                      </div>
                    </motion.form>
                  ) : (
                    <motion.div key="sent"
                      initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
                      transition={{ ease: [0.16, 1, 0.3, 1] }}
                      style={{ textAlign: 'center', padding: '8px 0' }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 22 }}>
                        <motion.div
                          style={{ width: 64, height: 64, borderRadius: 18, background: 'rgba(245,158,11,0.09)', border: '1px solid rgba(245,158,11,0.36)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                          animate={{ boxShadow: ['0 0 20px rgba(245,158,11,0.18)', '0 0 60px rgba(245,158,11,0.45)', '0 0 20px rgba(245,158,11,0.18)'] }}
                          transition={{ duration: 1.5, repeat: Infinity }}
                        >
                          <span style={{ color: '#F59E0B', fontSize: 26 }}>⟳</span>
                        </motion.div>
                      </div>

                      <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 13, fontWeight: 700, color: '#F59E0B', letterSpacing: '0.12em', marginBottom: 12 }}>
                        RECOVERY LINK TRANSMITTED
                      </div>
                      <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: '#5A6175', lineHeight: 1.65, letterSpacing: '0.04em' }}>
                        Recovery protocol dispatched to<br />
                        <span style={{ color: 'rgb(var(--c-primary))' }}>{email}</span>
                      </div>
                      <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 10, color: '#343b4d', marginTop: 11, letterSpacing: '0.04em' }}>
                        Check your inbox. Link expires in 15 minutes.
                      </div>

                      <div style={{ marginTop: 26 }}>
                        <Link to="/login"
                          style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: 'rgb(var(--c-accent-cyan) / 0.52)', textDecoration: 'none', transition: 'color 0.2s' }}
                          onMouseOver={e => (e.currentTarget.style.color = 'rgb(var(--c-accent-cyan))')}
                          onMouseOut={e  => (e.currentTarget.style.color = 'rgb(var(--c-accent-cyan) / 0.52)')}
                        >
                          ← Return to Access Portal
                        </Link>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </motion.div>
        </div>
      </motion.div>
    </div>
  );
}
