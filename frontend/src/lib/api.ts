// Typed client for the rich /v1 Frontend Data Contract (docs/backenddatacontract.md).
//
// Design goal: NON-INVASIVE. The animated pages keep their own hardcoded mock seeds; this
// client only *hydrates* them. Every call returns real data when the backend is up and throws
// otherwise — the hooks in useBackend.ts swallow the error and keep the page's mock fallback,
// so the design + animations always render whether or not a backend is running.

const BASE = (import.meta as any).env?.VITE_API_BASE ?? '';
const DEMO = { email: 'operator@aps.io', password: 'demo1234' };

let _token: string | null = null;
let _loginPromise: Promise<string | null> | null = null;

/** Clear the in-memory token (called by AuthContext on logout). */
export function clearToken() { _token = null; }

function _getStored(): string | null {
  try { return localStorage.getItem('aps_token'); } catch { return null; }
}

function unwrap<T>(body: any): T {
  // Contract envelope: { success, data, meta }. Be lenient if a raw object slips through.
  return (body && typeof body === 'object' && 'data' in body) ? body.data : body;
}

async function login(): Promise<string | null> {
  try {
    const r = await fetch(`${BASE}/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(DEMO),
    });
    if (!r.ok) return null;
    _token = unwrap<{ token: string }>(await r.json()).token;
    return _token;
  } catch {
    return null;
  }
}

export async function ensureToken(): Promise<string | null> {
  if (_token) return _token;
  const stored = _getStored();
  if (stored) { _token = stored; return _token; }
  // Fallback: auto-login with demo seed so pages hydrate even without a user session.
  if (!_loginPromise) _loginPromise = login().finally(() => { _loginPromise = null; });
  return _loginPromise;
}

export function token(): string | null {
  return _token ?? _getStored();
}

async function authedGet<T>(path: string): Promise<T> {
  const tok = await ensureToken();
  const r = await fetch(`${BASE}${path}`, {
    headers: tok ? { Authorization: `Bearer ${tok}` } : {},
  });
  if (r.status === 401) {            // token rotated/expired → one retry after re-login
    _token = null;
    const t2 = await ensureToken();
    const r2 = await fetch(`${BASE}${path}`, {
      headers: t2 ? { Authorization: `Bearer ${t2}` } : {},
    });
    if (!r2.ok) throw new Error(`GET ${path} → ${r2.status}`);
    return unwrap<T>(await r2.json());
  }
  if (!r.ok) throw new Error(`GET ${path} → ${r.status}`);
  return unwrap<T>(await r.json());
}

async function authedPost<T>(path: string, body: unknown): Promise<T> {
  const tok = await ensureToken();
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`POST ${path} → ${r.status}`);
  return unwrap<T>(await r.json());
}

export const api = {
  // auth
  ensureToken,
  token,
  // pipeline
  systemStatus: () => authedGet<any>('/v1/system/status'),
  agentsReady: () => authedGet<any[]>('/v1/agents'),
  startRun: (prompt: string, opts?: { model?: string; provider?: string }) =>
    authedPost<{ runId: string; status: string }>('/v1/runs', { prompt, ...(opts ?? {}) }),
  models: () => authedGet<any>('/v1/models'),
  // dashboard
  run: (id: string) => authedGet<any>(`/v1/runs/${id}`),
  runAgents: (id: string) => authedGet<any[]>(`/v1/runs/${id}/agents`),
  runStream: (id: string) => authedGet<any[]>(`/v1/runs/${id}/stream`),
  runArtifacts: (id: string) => authedGet<any[]>(`/v1/runs/${id}/artifacts`),
  viability: (id: string) => authedGet<any>(`/v1/runs/${id}/viability`),
  debate: (id: string) => authedGet<any[]>(`/v1/runs/${id}/debate`),
  explain: (id: string) => authedGet<any>(`/v1/runs/${id}/explain`),
  // GitHub Launch Mode — POST. Preview by default (dryRun); pass a PAT to create a real repo.
  launch: (id: string, opts?: { dryRun?: boolean; token?: string }) =>
    authedPost<any>(`/v1/runs/${id}/launch`, { dryRun: opts?.dryRun ?? true, ...(opts?.token ? { token: opts.token } : {}) }),
  evidenceGraph: (id: string) => authedGet<any>(`/v1/runs/${id}/evidence-graph`),
  dna: (id: string) => authedGet<any>(`/v1/runs/${id}/dna`),
  timeline: (id: string) => authedGet<any[]>(`/v1/runs/${id}/timeline`),
  // artifacts
  artifactContent: (artifactId: string, run: string) =>
    authedGet<any>(`/v1/artifacts/${artifactId}/content?run=${run}`),
  // Architecture diagrams: TRD rendered as mermaid (flowchart + ER). 404s for non-diagram artifacts.
  artifactMermaid: (artifactId: string, run: string) =>
    authedGet<any>(`/v1/artifacts/${artifactId}/content?run=${run}&format=mermaid`),
  evidenceTraces: (artifactId: string, run: string) =>
    authedGet<any[]>(`/v1/artifacts/${artifactId}/evidence-traces?run=${run}`),
  versions: (artifactId: string, run: string) =>
    authedGet<any[]>(`/v1/artifacts/${artifactId}/versions?run=${run}`),
  // history — the signed-in user's personal run archive
  history: () => authedGet<any[]>('/v1/history'),
  historyStats: () => authedGet<any>('/v1/history/stats'),
  historyDetail: (id: string) => authedGet<any>(`/v1/history/${id}`),
  // exports
  exportNotion: (runId: string) =>
    authedPost<any>(`/v1/runs/${runId}/export/notion`, {}),
  // system
  systemHealth: () => authedGet<any>('/v1/system/health'),
  systemAgents: () => authedGet<any[]>('/v1/system/agents'),
  systemModels: () => authedGet<any[]>('/v1/system/models'),
  systemProviders: () => authedGet<any>('/v1/system/providers'),
  systemTools: () => authedGet<any[]>('/v1/system/tools'),
  systemMemory: () => authedGet<any[]>('/v1/system/memory'),
  systemKnowledgeGraph: () => authedGet<any[]>('/v1/system/knowledge-graph'),
  systemQuality: () => authedGet<any[]>('/v1/system/quality'),
  systemCost: () => authedGet<any[]>('/v1/system/cost'),
  systemObservability: () => authedGet<any>('/v1/system/observability'),
  systemHeatmap: () => authedGet<any>('/v1/system/activity-heatmap'),
  telemetry: () => fetch(`${BASE}/v1/system/telemetry/live`).then(r => r.json()).then(unwrap),
};

// Download a run's artifact bundle as a ZIP (auth header → blob → save). Used by the History
// page Export action. Returns false if the export isn't available (e.g. run produced nothing).
export async function downloadRunZip(runId: string, kind: 'all' | 'investor' = 'all'): Promise<boolean> {
  const tok = await ensureToken();
  const r = await fetch(`${BASE}/v1/runs/${runId}/export/zip?kind=${kind}`, {
    headers: tok ? { Authorization: `Bearer ${tok}` } : {},
  });
  if (!r.ok) return false;
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${runId}.zip`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return true;
}

// Open a run/global WebSocket with the auth token as a query param (WS can't set headers).
export async function openRunSocket(runId: string, onMessage: (type: string, payload: any) => void): Promise<WebSocket | null> {
  const tok = await ensureToken();
  if (!tok) return null;
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${scheme}://${location.host}/v1/ws/runs/${runId}/stream?token=${tok}`);
  ws.onmessage = (e) => {
    try { const m = JSON.parse(e.data); onMessage(m.type, m.payload); } catch { /* ignore */ }
  };
  return ws;
}

export type Api = typeof api;
