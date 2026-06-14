import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../lib/AuthContext';
import { useTheme } from '../lib/useTheme';
import { PlanBadge } from './PlanBadge';

export function SettingsMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [theme, toggleTheme] = useTheme();
  const isLight = theme === 'light';

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc); };
  }, []);

  const handleSignOut = async () => {
    setOpen(false);
    await logout();
    navigate('/login', { replace: true });
  };

  const initials = user?.name?.charAt(0).toUpperCase() ?? 'O';

  return (
    <div ref={ref} style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 6 }}>

      {/* Theme toggle — sliding sun/moon pill */}
      <button
        onClick={toggleTheme}
        aria-label={isLight ? 'Switch to dark mode' : 'Switch to light mode'}
        title={isLight ? 'Dark mode' : 'Light mode'}
        style={{
          position: 'relative', width: 52, height: 26, borderRadius: 999, cursor: 'pointer',
          padding: 0, border: '1px solid', flexShrink: 0,
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

      {/* Settings gear */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-8 h-8 flex items-center justify-center rounded-lg border transition-all duration-200"
        style={{
          color:       open ? 'var(--color-primary, #00E5FF)' : 'rgb(var(--c-primary) / 0.5)',
          background:  open ? 'rgb(var(--c-overlay) / 0.06)' : 'transparent',
          borderColor: open ? 'rgb(var(--c-overlay) / 0.08)' : 'transparent',
        }}
        onMouseEnter={e => { if (!open) { e.currentTarget.style.color = 'var(--color-primary, #00E5FF)'; e.currentTarget.style.background = 'rgb(var(--c-overlay) / 0.06)'; e.currentTarget.style.borderColor = 'rgb(var(--c-overlay) / 0.08)'; }}}
        onMouseLeave={e => { if (!open) { e.currentTarget.style.color = 'rgb(var(--c-primary) / 0.5)'; e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'transparent'; }}}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 18 }}>settings</span>
      </button>

      {/* Current-plan badge (additive — does not alter header layout) */}
      <PlanBadge />

      {/* Avatar */}
      <div className="relative group cursor-pointer" onClick={() => setOpen(o => !o)}>
        <div className="absolute inset-0 rounded-full blur-md opacity-0 group-hover:opacity-100 transition-opacity duration-300" style={{ background: 'rgb(var(--c-accent-cyan) / 0.2)' }} />
        <div className="relative w-8 h-8 rounded-full p-0.5 overflow-hidden transition-colors duration-300" style={{ border: open ? '1px solid rgb(var(--c-accent-cyan) / 0.6)' : '1px solid rgb(var(--c-accent-cyan) / 0.3)' }}>
          {user?.avatarUrl
            ? <img src={user.avatarUrl} alt={user.name} className="w-full h-full rounded-full object-cover" onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }} />
            : <div className="w-full h-full rounded-full flex items-center justify-center" style={{ background: 'rgb(var(--c-accent-cyan) / 0.15)', fontFamily: '"JetBrains Mono",monospace', fontSize: 13, color: 'rgb(var(--c-accent-cyan))', fontWeight: 700 }}>{initials}</div>
          }
        </div>
      </div>

      {/* Dropdown */}
      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 10px)', right: 0,
          minWidth: 220, zIndex: 1000,
          background: 'rgb(var(--c-deep) / 0.97)',
          border: '1px solid rgb(var(--c-primary) / 0.10)',
          borderRadius: 14,
          boxShadow: '0 12px 40px rgb(var(--c-deepest) / 0.6), 0 0 0 1px rgb(var(--c-accent-cyan) / 0.04)',
          backdropFilter: 'blur(24px)',
          overflow: 'hidden',
        }}>
          {/* User info */}
          {user && (
            <div style={{ padding: '14px 16px', borderBottom: '1px solid rgb(var(--c-primary) / 0.07)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 34, height: 34, borderRadius: '50%', border: '1px solid rgb(var(--c-accent-cyan) / 0.25)', overflow: 'hidden', flexShrink: 0 }}>
                  {user.avatarUrl
                    ? <img src={user.avatarUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    : <div style={{ width: '100%', height: '100%', background: 'rgb(var(--c-accent-cyan) / 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: '"JetBrains Mono",monospace', fontSize: 14, color: 'rgb(var(--c-accent-cyan))', fontWeight: 700 }}>{initials}</div>
                  }
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontFamily: '"JetBrains Mono",monospace', fontSize: 12, color: 'rgb(var(--c-text))', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.name}</div>
                  <div style={{ fontFamily: '"JetBrains Mono",monospace', fontSize: 10, color: 'rgb(var(--c-primary) / 0.4)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.email}</div>
                </div>
              </div>
            </div>
          )}

          {/* Sign out */}
          <button
            onClick={handleSignOut}
            style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', background: 'none', border: 'none', cursor: 'pointer', color: '#EF4444', fontFamily: '"JetBrains Mono",monospace', fontSize: 11, letterSpacing: '0.10em', textAlign: 'left', transition: 'background 0.15s' }}
            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(239,68,68,0.08)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'none')}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
              <polyline points="16 17 21 12 16 7"/>
              <line x1="21" x2="9" y1="12" y2="12"/>
            </svg>
            SIGN OUT
          </button>
        </div>
      )}
    </div>
  );
}
