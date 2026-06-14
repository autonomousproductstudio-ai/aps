// Typed client for the Dodo Payments billing API (/api/billing).
//
// Server-side creates the checkout session and owns all secrets; the frontend only POSTs the
// chosen plan with the user's bearer token and redirects to the returned hosted checkout URL.
// Every response is fully typed. Non-invasive: nothing here touches existing pages' state.

import { useCallback, useEffect, useState } from 'react';
import { useAuth } from './AuthContext';

export type PlanId = 'free' | 'operator' | 'command' | string;

/** Mirror of the backend store.public_view() shape. */
export interface Subscription {
  userId: string | null;
  customerId: string | null;
  subscriptionId: string | null;
  plan: PlanId;
  planName: string;          // e.g. "OPERATOR" — ready for the navbar badge
  status: string;            // none | active | on_hold | cancelled | failed | expired
  subscriptionStart: string | null;
  renewalDate: string | null;
  provider: string;          // "dodo"
  providerName: string;      // "Dodo Payments"
}

interface CheckoutResponse {
  checkoutUrl: string;
  sessionId: string | null;
  plan: PlanId;
}

const BASE = (import.meta as any).env?.VITE_API_BASE ?? '';

function authHeaders(token: string | null): HeadersInit {
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

async function parseError(r: Response): Promise<string> {
  try {
    const body = await r.json();
    return body?.detail || body?.error?.message || body?.message || `Request failed (${r.status})`;
  } catch {
    return `Request failed (${r.status})`;
  }
}

/** Create a Dodo checkout session for a paid plan and return its hosted checkout URL. */
export async function createCheckoutSession(plan: PlanId, token: string | null): Promise<CheckoutResponse> {
  const r = await fetch(`${BASE}/api/billing/create-checkout-session`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ plan }),
  });
  if (!r.ok) throw new Error(await parseError(r));
  return r.json() as Promise<CheckoutResponse>;
}

/** Current user's subscription (defaults to a FREE record server-side). */
export async function fetchSubscription(token: string | null): Promise<Subscription> {
  const r = await fetch(`${BASE}/api/billing/subscription`, { headers: authHeaders(token) });
  if (!r.ok) throw new Error(await parseError(r));
  return r.json() as Promise<Subscription>;
}

/** Finalize a subscription after Dodo redirects back to /billing/success. */
export async function confirmCheckout(sessionId: string | null, token: string | null): Promise<Subscription> {
  const r = await fetch(`${BASE}/api/billing/confirm`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ sessionId }),
  });
  if (!r.ok) throw new Error(await parseError(r));
  return r.json() as Promise<Subscription>;
}

interface UseSubscription {
  subscription: Subscription | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

/**
 * Read-only subscription hook for the navbar badge and the System billing card.
 * Fails silently (subscription stays null) when the backend is unreachable, so the existing UI
 * never breaks — exactly the pattern the rest of the app uses (useBackend.ts).
 */
export function useSubscription(): UseSubscription {
  const { token, user } = useAuth();
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!token || !user) { setSubscription(null); return; }
    setLoading(true);
    setError(null);
    try {
      setSubscription(await fetchSubscription(token));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load billing');
      setSubscription(null);
    } finally {
      setLoading(false);
    }
  }, [token, user]);

  useEffect(() => { void refresh(); }, [refresh]);

  return { subscription, loading, error, refresh };
}
