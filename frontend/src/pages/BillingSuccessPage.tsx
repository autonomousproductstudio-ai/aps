// /billing/success — where Dodo redirects after a completed hosted checkout.
//
// Finalizes the subscription server-side (confirm endpoint), shows a success state + toast, and
// links back into the app. Self-contained and styled to match APS surfaces; it adds NO global
// state and touches no existing page. If confirmation fails, it routes to /pricing?cancelled=true
// so the user lands somewhere sensible.

import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../lib/AuthContext';
import { confirmCheckout, Subscription } from '../lib/billing';
import { Toast, ToastState } from '../components/Toast';

export default function BillingSuccessPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { token, loading: authLoading } = useAuth();
  const [state, setState] = useState<'confirming' | 'done' | 'error'>('confirming');
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);
  const ran = useRef(false);

  useEffect(() => {
    if (authLoading || ran.current) return;
    ran.current = true;
    const sessionId = params.get('session_id');
    (async () => {
      try {
        const sub = await confirmCheckout(sessionId, token);
        setSubscription(sub);
        setState('done');
        setToast({ type: 'success', message: `Payment successful — ${sub.planName} plan is now active.` });
      } catch (e) {
        setState('error');
        setToast({ type: 'error', message: e instanceof Error ? e.message : 'Could not confirm payment.' });
        setTimeout(() => navigate('/pricing?cancelled=true', { replace: true }), 2200);
      }
    })();
  }, [authLoading, token, params, navigate]);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, background: 'rgb(var(--c-bg-deep))', fontFamily: '"JetBrains Mono", monospace' }}>
      <Toast toast={toast} onClose={() => setToast(null)} />

      <div style={{ width: '100%', maxWidth: 460, borderRadius: 20, padding: '40px 36px', textAlign: 'center',
        background: 'rgb(var(--c-deep) / 0.9)', border: '1px solid rgb(var(--c-primary) / 0.12)',
        boxShadow: '0 24px 64px rgb(var(--c-deepest) / 0.5)' }}>

        {state === 'confirming' && (
          <>
            <div style={{ width: 48, height: 48, margin: '0 auto 22px', borderRadius: '50%', border: '2px solid rgb(var(--c-primary) / 0.18)', borderTopColor: '#47d6ff', animation: 'apsSpin 0.8s linear infinite' }} />
            <style>{`@keyframes apsSpin{to{transform:rotate(360deg)}}`}</style>
            <div style={{ fontSize: 13, color: 'rgb(var(--c-text))', letterSpacing: '0.04em' }}>Confirming your payment…</div>
          </>
        )}

        {state === 'done' && (
          <>
            <span className="material-symbols-outlined" style={{ fontSize: 56, color: '#79ff5b' }}>check_circle</span>
            <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 24, fontWeight: 700, color: 'rgb(var(--c-text))', margin: '16px 0 6px' }}>Payment Successful</h1>
            <p style={{ fontSize: 12, color: 'rgb(var(--c-primary) / 0.55)', lineHeight: 1.6, marginBottom: 24 }}>
              Your <span style={{ color: '#47d6ff', fontWeight: 700 }}>{subscription?.planName ?? ''}</span> subscription is now active.
              {subscription?.renewalDate ? ` Renews ${new Date(subscription.renewalDate).toLocaleDateString()}.` : ''}
            </p>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
              <Link to="/dashboard" style={btn(true)}>Go to Dashboard</Link>
              <Link to="/system" style={btn(false)}>View Billing</Link>
            </div>
          </>
        )}

        {state === 'error' && (
          <>
            <span className="material-symbols-outlined" style={{ fontSize: 56, color: '#ef4444' }}>error</span>
            <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 22, fontWeight: 700, color: 'rgb(var(--c-text))', margin: '16px 0 6px' }}>Payment Not Confirmed</h1>
            <p style={{ fontSize: 12, color: 'rgb(var(--c-primary) / 0.55)', lineHeight: 1.6 }}>Redirecting you back to pricing…</p>
          </>
        )}
      </div>
    </div>
  );
}

function btn(primary: boolean): React.CSSProperties {
  return {
    padding: '11px 18px', borderRadius: 10, textDecoration: 'none',
    fontFamily: '"JetBrains Mono", monospace', fontSize: 11, fontWeight: 700, letterSpacing: '0.12em',
    color: primary ? '#060A12' : '#47d6ff',
    background: primary ? 'linear-gradient(135deg, #47d6ff 0%, rgba(71,214,255,0.82) 100%)' : 'rgba(71,214,255,0.06)',
    boxShadow: primary ? '0 0 24px rgba(71,214,255,0.3)' : 'inset 0 0 0 1px rgba(71,214,255,0.18)',
  };
}
