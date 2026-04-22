const API_BASE = import.meta.env.VITE_API_URL ?? '';

// ---------------------------------------------------------------------------
// Token storage
// ---------------------------------------------------------------------------

const TOKEN_KEY = 'caic_access_token';
const REFRESH_KEY = 'caic_refresh_token';

export const auth = {
  getToken: () => localStorage.getItem(TOKEN_KEY),
  getRefreshToken: () => localStorage.getItem(REFRESH_KEY),
  setTokens: (access: string, refresh: string) => {
    localStorage.setItem(TOKEN_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
  isLoggedIn: () => !!localStorage.getItem(TOKEN_KEY),
};

// ---------------------------------------------------------------------------
// Base fetch
// ---------------------------------------------------------------------------

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  _retry = true,
): Promise<T> {
  const token = auth.getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (res.status === 401 && _retry) {
    const refreshToken = auth.getRefreshToken();
    if (refreshToken) {
      try {
        const refreshRes = await fetch(`${API_BASE}/api/auth/jwt/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (refreshRes.ok) {
          const data = await refreshRes.json();
          auth.setTokens(data.access_token, data.refresh_token);
          return apiFetch<T>(path, options, false);
        }
      } catch { /* fall through to throw */ }
    }
    auth.clear();
    window.location.href = '/';
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw Object.assign(new Error(err.detail ?? 'Request failed'), { status: res.status, data: err });
  }

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Types (mirroring backend schemas)
// ---------------------------------------------------------------------------

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: { id: number; email: string; full_name: string };
}

export interface EventMetadata {
  location: string;
  event_type: string;
  event_date: string;
  description?: string;
  coordinates?: [number, number];
}

export interface ScoringOptions {
  profile?: string;
  overrides?: Record<string, number>;
  custom_weights?: Record<string, number>;
}

export interface ScoredSource {
  url: string;
  title: string | null;
  angle: string | null;
  source_type: string | null;
  composite_score: number;
  event_specificity: number;
  actionability: number;
  accountability_signal: number;
  community_proximity: number;
  independence: number;
}

export interface PipelineStatus {
  task_id: string;
  status: 'pending' | 'running' | 'complete' | 'failed';
  progress: Record<string, unknown> | null;
  error: string | null;
}

export interface PipelineResults {
  task_id: string;
  status: string;
  weights_used: Record<string, number>;
  sources: ScoredSource[];
}

// ---------------------------------------------------------------------------
// Auth endpoints
// ---------------------------------------------------------------------------

export const authApi = {
  register: (email: string, password: string, full_name: string) =>
    apiFetch<TokenResponse>('/api/auth/jwt/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name }),
    }),

  login: (email: string, password: string) =>
    apiFetch<TokenResponse>('/api/auth/jwt/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  refresh: (refresh_token: string) =>
    apiFetch<TokenResponse>('/api/auth/jwt/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token }),
    }),

  me: () =>
    apiFetch<{ id: number; email: string; full_name: string; is_active: boolean }>('/api/auth/jwt/me'),

  logout: () =>
    apiFetch<{ message: string }>('/api/auth/jwt/logout', { method: 'POST' }),
};

// ---------------------------------------------------------------------------
// Source discovery endpoints
// ---------------------------------------------------------------------------

export const pipelineApi = {
  run: (
    event: EventMetadata,
    scoring: ScoringOptions = {},
    max_sources = 20,
  ) =>
    apiFetch<{ task_id: string }>('/api/source-discovery/pipeline/run', {
      method: 'POST',
      body: JSON.stringify({ event, scoring, max_sources }),
    }),

  status: (taskId: string) =>
    apiFetch<PipelineStatus>(`/api/source-discovery/pipeline/${taskId}/status`),

  results: (taskId: string) =>
    apiFetch<PipelineResults>(`/api/source-discovery/pipeline/${taskId}/results`),

  rate: (taskId: string, url: string, rating: number) =>
    apiFetch<{ id: number; task_id: string; url: string; rating: number }>(
      `/api/source-discovery/pipeline/${taskId}/rate`,
      { method: 'POST', body: JSON.stringify({ url, rating }) },
    ),

  rescore: (taskId: string, scoring: ScoringOptions) =>
    apiFetch<PipelineResults>(`/api/source-discovery/pipeline/${taskId}/rescore`, {
      method: 'POST',
      body: JSON.stringify({ scoring }),
    }),

  profiles: () =>
    apiFetch<{ profiles: Record<string, Record<string, number>> }>(
      '/api/source-discovery/scoring/profiles',
    ),

  generateReport: (taskId: string) =>
    apiFetch<{ task_id: string; report_text: string }>(
      `/api/source-discovery/pipeline/${taskId}/report`,
      { method: 'POST' },
    ),

  chat: (taskId: string, message: string, history: { role: string; content: string }[]) =>
    apiFetch<{ reply: string }>(
      `/api/source-discovery/pipeline/${taskId}/chat`,
      { method: 'POST', body: JSON.stringify({ message, history }) },
    ),
};
