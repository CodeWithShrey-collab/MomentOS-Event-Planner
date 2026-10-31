import { afterEach, describe, expect, it, vi } from 'vitest';
import { clearSessionForTests, request } from './apiClient';

describe('same-origin session API client', () => {
  afterEach(() => { clearSessionForTests(); vi.restoreAllMocks(); });
  it('initializes a cookie session and attaches CSRF, idempotency, ETag credentials for writes', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: 'session_required', message: 'Sign in' } }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: { csrf_token: 'csrf-test', expires_at: 'later' } }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: { id: 'event-id' }, request_id: 'r' }), { status: 201, headers: { ETag: '"event-v1"' } }));
    vi.stubGlobal('fetch', fetchMock);

    await request('/events', { method: 'POST', body: JSON.stringify({ title: 'Test' }) });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/v1/session');
    expect(fetchMock.mock.calls[2]?.[1]?.credentials).toBe('include');
    const headers = new Headers(fetchMock.mock.calls[2]?.[1]?.headers);
    expect(headers.get('X-CSRF-Token')).toBe('csrf-test');
    expect(headers.get('Idempotency-Key')).toBeTruthy();
  });

  it('preserves Retry-After on rate-limit responses', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: 'session_required', message: 'Sign in' } }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: { csrf_token: 'csrf-test', expires_at: 'later' } }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: 'ai_daily_limit', message: 'Daily limit reached.' } }), { status: 429, headers: { 'Retry-After': '86400' } }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(request('/events/one/plan-drafts', { method: 'POST', body: '{}' })).rejects.toMatchObject({
      code: 'ai_daily_limit', retryAfterSeconds: 86400,
    });
  });
});
