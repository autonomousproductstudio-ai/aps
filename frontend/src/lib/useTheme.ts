// Light/dark theme. Dark is the default (the original look, untouched); light swaps the CSS
// variables in index.css via a `.light` class on <html>. Persisted to localStorage.
import { useEffect, useState } from 'react';

const KEY = 'aps_theme';
export type Theme = 'dark' | 'light';

export function getInitialTheme(): Theme {
  try { return (localStorage.getItem(KEY) as Theme) === 'light' ? 'light' : 'dark'; } catch { return 'dark'; }
}

export function applyTheme(t: Theme): void {
  const el = document.documentElement;
  el.classList.toggle('light', t === 'light');
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  useEffect(() => {
    applyTheme(theme);
    try { localStorage.setItem(KEY, theme); } catch { /* ignore */ }
  }, [theme]);
  return [theme, () => setTheme(t => (t === 'dark' ? 'light' : 'dark'))];
}
