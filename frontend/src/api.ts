export type Session = {
  access_token: string;
  expires_at: number;
  role: string;
  subject?: string;
};

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
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
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
  const response = await fetch(input, { ...init, headers });
  if (response.status === 401) {
    clearSession();
    window.dispatchEvent(new CustomEvent('auth:required'));
  } else if (response.status === 403) {
    window.dispatchEvent(new CustomEvent('auth:forbidden'));
  }
  return response;
}
