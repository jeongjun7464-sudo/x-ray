export type Session = {
  access_token: string;
  expires_at: number;
  role: string;
  subject?: string;
};
export type Principal = { subject: string; role: string; issued_at: number | null; expires_at: number | null; authentication_method: string };
export type ApiProblem = { status: number; code: string; message: string };

const SESSION_KEY = 'xray-demo-session-v1';

export function getSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as Session;
    if (!session.access_token || session.expires_at <= Math.floor(Date.now() / 1000)) {
      clearSession();
      return null;
    }
    return session;
  } catch {
    clearSession();
    return null;
  }
}

export function setSession(session: Session): void {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify({ access_token: session.access_token, role: session.role, expires_at: session.expires_at }));
  window.dispatchEvent(new CustomEvent('auth:changed'));
}

export function clearSession(): void {
  sessionStorage.removeItem(SESSION_KEY);
  window.dispatchEvent(new CustomEvent('auth:changed'));
}

export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const session = getSession();
  if (session && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${session.access_token}`);
  if (typeof init.body === 'string' && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(input, { ...init, headers });
  if (response.status === 401) {
    clearSession();
    window.dispatchEvent(new CustomEvent('auth:required'));
  } else if (response.status === 403) {
    window.dispatchEvent(new CustomEvent('auth:forbidden'));
  }
  return response;
}

export async function apiProblem(response: Response): Promise<ApiProblem> {
  try {
    const body = await response.clone().json();
    const detail = body.error ?? body.detail ?? body;
    return { status: response.status, code: detail.code ?? `HTTP_${response.status}`, message: typeof detail === 'string' ? detail : detail.message ?? '요청을 처리하지 못했습니다.' };
  } catch {
    return { status: response.status, code: `HTTP_${response.status}`, message: '요청을 처리하지 못했습니다.' };
  }
}

export async function loginWithDemoSession(baseUrl: string, anonymousUserId: string, role: string): Promise<Session> {
  const response = await apiFetch(`${baseUrl}/api/auth/demo-token`, { method: 'POST', body: JSON.stringify({ anonymous_user_id: anonymousUserId, role }) });
  if (!response.ok) throw await apiProblem(response);
  const session = await response.json() as Session;
  setSession(session);
  return session;
}

export async function getCurrentPrincipal(baseUrl: string): Promise<Principal> {
  const response = await apiFetch(`${baseUrl}/api/auth/me`);
  if (!response.ok) throw await apiProblem(response);
  return response.json();
}

export async function logout(baseUrl: string): Promise<void> {
  try {
    const response = await apiFetch(`${baseUrl}/api/auth/logout`, { method: 'POST' });
    if (!response.ok && response.status !== 401) throw await apiProblem(response);
  } finally {
    clearSession();
  }
}
