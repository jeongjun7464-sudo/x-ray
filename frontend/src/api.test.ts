import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiFetch, clearSession, getSession, setSession } from './api';

describe('signed session API client', () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => vi.unstubAllGlobals());

  it('stores a token only in sessionStorage and attaches Bearer authentication', async () => {
    setSession({ access_token: 'signed-token', expires_at: Math.floor(Date.now() / 1000) + 60, role: 'REVIEWER' });
    const fetchMock = vi.fn(async (_input, init) => ({ ok: true, status: 200, headers: new Headers(init?.headers) } as Response));
    vi.stubGlobal('fetch', fetchMock);
    await apiFetch('/api/private');
    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers);
    expect(headers.get('Authorization')).toBe('Bearer signed-token');
    expect(localStorage.length).toBe(0);
  });

  it('clears an expired session and does not send its token', async () => {
    setSession({ access_token: 'expired', expires_at: 1, role: 'ADMIN' });
    let sentHeaders = new Headers();
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      sentHeaders = new Headers(init?.headers);
      return { ok: true, status: 200 } as Response;
    });
    vi.stubGlobal('fetch', fetchMock);
    await apiFetch('/api/private');
    expect(getSession()).toBeNull();
    expect(sentHeaders.has('Authorization')).toBe(false);
  });

  it('clears the session and emits a reauthentication event on 401', async () => {
    setSession({ access_token: 'signed-token', expires_at: Math.floor(Date.now() / 1000) + 60, role: 'USER' });
    const handler = vi.fn();
    window.addEventListener('auth:required', handler, { once: true });
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 401 } as Response)));
    await apiFetch('/api/private');
    expect(getSession()).toBeNull();
    expect(handler).toHaveBeenCalledOnce();
    clearSession();
  });
  it('does not force a Content-Type boundary for FormData', async () => {
    let sentHeaders = new Headers();
    vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => { sentHeaders = new Headers(init?.headers); return { ok: true, status: 200 } as Response }));
    await apiFetch('/api/upload', { method: 'POST', body: new FormData() });
    expect(sentHeaders.has('Content-Type')).toBe(false);
  });
  it('emits permission denied without deleting a valid session on 403', async () => {
    setSession({ access_token: 'signed-token', expires_at: Math.floor(Date.now() / 1000) + 60, role: 'USER' });
    const handler = vi.fn(); window.addEventListener('auth:forbidden', handler, { once: true });
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 403 } as Response)));
    await apiFetch('/api/admin');
    expect(handler).toHaveBeenCalledOnce(); expect(getSession()?.role).toBe('USER');
  });
});
