// Minimal, self-contained toast — no global provider, no design-system changes. Styled to
// match APS surfaces (dark glass, JetBrains Mono, cyan/red accents). Used by the Pricing page
// and the Billing success page for checkout feedback. Auto-dismisses; click to close early.

import { useEffect } from 'react';

export type ToastType = 'success' | 'error' | 'info';

export interface ToastState {
  message: string;
  type: ToastType;
}

const ACCENT: Record<ToastType, { color: string; glow: string; icon: string }> = {
  success: { color: '#79ff5b', glow: 'rgba(121,255,91,0.18)', icon: 'check_circle' },
  error:   { color: '#ef4444', glow: 'rgba(239,68,68,0.18)',  icon: 'error' },
  info:    { color: '#47d6ff', glow: 'rgba(71,214,255,0.18)', icon: 'info' },
};

export function Toast({ toast, onClose, duration = 5000 }: {
  toast: ToastState | null;
  onClose: () => void;
  duration?: number;
}) {
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(onClose, duration);
    return () => clearTimeout(t);
  }, [toast, duration, onClose]);

  if (!toast) return null;
  const a = ACCENT[toast.type];

  return (
    <div
      role="status"
      onClick={onClose}
      style={{
        position: 'fixed', top: 76, right: 24, zIndex: 2000, cursor: 'pointer',
        display: 'flex', alignItems: 'center', gap: 12, maxWidth: 380,
        padding: '13px 16px', borderRadius: 12,
        background: 'rgb(var(--c-deep) / 0.97)',
        border: `1px solid ${a.color}55`,
        boxShadow: `0 12px 40px rgb(var(--c-deepest) / 0.6), 0 0 24px ${a.glow}`,
        backdropFilter: 'blur(24px)',
        animation: 'apsToastIn 0.32s cubic-bezier(0.16,1,0.3,1)',
        fontFamily: '"JetBrains Mono", monospace',
      }}
    >
      <style>{`@keyframes apsToastIn{from{opacity:0;transform:translateX(16px)}to{opacity:1;transform:translateX(0)}}`}</style>
      <span className="material-symbols-outlined" style={{ fontSize: 20, color: a.color, flexShrink: 0 }}>
        {a.icon}
      </span>
      <span style={{ fontSize: 12, lineHeight: 1.5, color: 'rgb(var(--c-text))', letterSpacing: '0.02em' }}>
        {toast.message}
      </span>
    </div>
  );
}
