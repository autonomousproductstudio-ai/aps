// Billing card for the System page — additive, self-contained, styled to match the existing
// APS panels (same rounded border / dark surface / mono labels). Shows Current Plan,
// Subscription Status, Renewal Date, and Billing Provider. Reads the subscription read-only;
// if the backend is unreachable it falls back to a FREE display so the page never breaks.

import { useSubscription } from '../lib/billing';

const STATUS_COLOR: Record<string, string> = {
  active: '#79ff5b', trialing: '#47d6ff', on_hold: '#f59e0b',
  past_due: '#f59e0b', failed: '#ef4444', cancelled: '#ef4444',
  expired: 'rgb(var(--c-primary) / 0.5)', none: 'rgb(var(--c-primary) / 0.5)',
};

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d.getTime()) ? '—' : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '9px 0', borderBottom: '1px solid rgb(var(--c-primary) / 0.05)' }}>
      <span style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'rgb(var(--c-primary) / 0.42)' }}>{label}</span>
      <span style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: 'rgb(var(--c-text))', textAlign: 'right' }}>{children}</span>
    </div>
  );
}

export function BillingCard() {
  const { subscription } = useSubscription();
  const plan = (subscription?.plan ?? 'free').toLowerCase();
  const planLabel = (subscription?.planName ?? 'FREE').toUpperCase();
  const status = (subscription?.status ?? 'none').toLowerCase();
  const statusColor = STATUS_COLOR[status] ?? 'rgb(var(--c-primary) / 0.5)';
  const planColor = plan === 'command' ? '#79ff5b' : plan === 'operator' ? '#47d6ff' : 'rgb(var(--c-text))';

  return (
    <div className="rounded-xl border border-white/[0.055] bg-[#0A0C11]/85 overflow-hidden flex flex-col">
      {/* Header — mirrors the other System panels' header treatment */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '14px 16px', borderBottom: '1px solid rgb(var(--c-primary) / 0.06)' }}>
        <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'rgb(var(--c-primary))' }}>credit_card</span>
        <span style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'rgb(var(--c-text))' }}>Billing</span>
        <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: statusColor, boxShadow: `0 0 6px ${statusColor}` }} />
          <span style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 9, letterSpacing: '0.16em', textTransform: 'uppercase', color: statusColor }}>{status}</span>
        </span>
      </div>

      <div style={{ padding: '6px 16px 14px' }}>
        <Row label="Current Plan"><span style={{ color: planColor, fontWeight: 700, letterSpacing: '0.1em' }}>{planLabel}</span></Row>
        <Row label="Subscription Status"><span style={{ color: statusColor, textTransform: 'capitalize' }}>{status === 'none' ? 'Free tier' : status}</span></Row>
        <Row label="Renewal Date">{fmtDate(subscription?.renewalDate ?? null)}</Row>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '9px 0' }}>
          <span style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'rgb(var(--c-primary) / 0.42)' }}>Billing Provider</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: 'rgb(var(--c-text))' }}>
            <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'rgb(var(--c-primary) / 0.6)' }}>bolt</span>
            {subscription?.providerName ?? 'Dodo Payments'}
          </span>
        </div>
      </div>
    </div>
  );
}
