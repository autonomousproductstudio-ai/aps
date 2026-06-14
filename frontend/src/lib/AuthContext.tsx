import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  signOut,
  onAuthStateChanged,
  updateProfile,
} from 'firebase/auth';
import { firebaseAuth, firebaseConfigured, googleProvider, githubProvider } from './firebase';
import { clearToken } from './api';

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  avatarUrl: string;
  role: string;
}

interface AuthCtx {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  firebaseReady: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (name: string, email: string, password: string, role: string) => Promise<void>;
  loginWithGoogle: () => Promise<void>;
  loginWithGithub: () => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthCtx>(null!);
export const useAuth = () => useContext(Ctx);

function toUser(fb: any): AuthUser {
  return {
    id:        fb.uid,
    name:      fb.displayName || fb.email?.split('@')[0] || 'Operator',
    email:     fb.email || '',
    avatarUrl: fb.photoURL || '',
    role:      localStorage.getItem(`aps_role_${fb.uid}`) || 'Operator',
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user,    setUser]    = useState<AuthUser | null>(null);
  const [token,   setToken]   = useState<string | null>(null);
  // If Firebase is configured, start loading=true until onAuthStateChanged fires.
  const [loading, setLoading] = useState(firebaseConfigured);

  function persist(tok: string, u: AuthUser) {
    setToken(tok); setUser(u);
    try {
      localStorage.setItem('aps_token', tok);
      localStorage.setItem('aps_user', JSON.stringify(u));
    } catch {}
  }

  async function wipe() {
    setToken(null); setUser(null);
    clearToken();
    try { localStorage.removeItem('aps_token'); localStorage.removeItem('aps_user'); } catch {}
  }

  // Firebase session listener — keeps the token fresh automatically.
  useEffect(() => {
    if (!firebaseConfigured || !firebaseAuth) { setLoading(false); return; }
    const unsub = onAuthStateChanged(firebaseAuth, async (fb) => {
      if (fb) {
        const tok = await fb.getIdToken();
        persist(tok, toUser(fb));
      } else {
        await wipe();
      }
      setLoading(false);
    });
    return unsub;
  }, []);

  // ── Email / password ────────────────────────────────────────────────────────
  async function login(email: string, password: string) {
    if (firebaseAuth) {
      await signInWithEmailAndPassword(firebaseAuth, email, password);
      // onAuthStateChanged calls persist automatically
    } else {
      // Fallback: APS backend (works when backend is running locally)
      const r = await fetch('/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(body?.error?.message || `Login failed (${r.status})`);
      const d = body?.data ?? body;
      persist(d.token, d.user);
    }
  }

  async function signup(name: string, email: string, password: string, role: string) {
    if (firebaseAuth) {
      const cred = await createUserWithEmailAndPassword(firebaseAuth, email, password);
      await updateProfile(cred.user, { displayName: name });
      localStorage.setItem(`aps_role_${cred.user.uid}`, role);
      // onAuthStateChanged will fire and call persist
    } else {
      const r = await fetch('/v1/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), email: email.trim(), password, role }),
      });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(body?.error?.message || `Signup failed (${r.status})`);
      const d = body?.data ?? body;
      persist(d.token, d.user);
    }
  }

  // ── OAuth ───────────────────────────────────────────────────────────────────
  async function loginWithGoogle() {
    if (!firebaseAuth) throw new Error('Firebase not configured — add VITE_FIREBASE_* to frontend/.env');
    await signInWithPopup(firebaseAuth, googleProvider);
  }

  async function loginWithGithub() {
    if (!firebaseAuth) throw new Error('Firebase not configured — add VITE_FIREBASE_* to frontend/.env');
    await signInWithPopup(firebaseAuth, githubProvider);
  }

  async function logout() {
    if (firebaseAuth) await signOut(firebaseAuth);
    await wipe();
  }

  return (
    <Ctx.Provider value={{ user, token, loading, firebaseReady: firebaseConfigured, login, signup, loginWithGoogle, loginWithGithub, logout }}>
      {children}
    </Ctx.Provider>
  );
}
