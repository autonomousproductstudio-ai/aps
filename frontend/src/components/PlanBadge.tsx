// Current-plan badge shown beside the avatar in the shared header (SettingsMenu). Additive and
// self-contained: it reads the subscription and renders a small mono chip (FREE / OPERATOR /
// COMMAND). Renders nothing until a plan is known, so it never shifts the header layout on load.

import { useSubscription } from '../lib/billing';

const STYLES: Record<string, { color: string; bg: string; border: string }> = {
  free:     { color: 'rgb(var(--c-primary) / 0.55)', bg: 'rgb(var(--c-primary) / 0.06)', border: 'rgb(var(--c-primary) / 0.18)' },
  operator: { color: '#47d6ff', bg: 'rgba(71,214,255,0.10)', border: 'rgba(71,214,255,0.30)' },
  command:  { color: '#79ff5b', bg: 'rgba(121,255,91,0.10)', border: 'rgba(121,255,91,0.32)' },
};

export function PlanBadge() {
  const { subscription } = useSubscription();
  if (!subscription) return null;

  const plan = (subscription.plan || 'free').toLowerCase();
  const s = STYLES[plan] ?? STYLES.free;
  const label = (subscription.planName || plan).toUpperCase();

  return (
    <span
      title={`Current plan: ${label}`}
      style={{
        display: 'inline-flex', alignItems: 'center', flexShrink: 0,
        height: 22, padding: '0 9px', borderRadius: 999,
        fontFamily: '"JetBrains Mono", monospace', fontSize: 9, fontWeight: 700,
        letterSpacing: '0.16em', lineHeight: 1, whiteSpace: 'nowrap',
        color: s.color, background: s.bg, border: `1px solid ${s.border}`,
      }}
    >
      {label}
    </span>
  );
}
