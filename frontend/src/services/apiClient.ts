/* eslint-disable @typescript-eslint/no-explicit-any */
/** Same-origin, cookie-authenticated client for the versioned Flask API. */
export type ApiEnvelope<T> = { data: T; request_id: string };
export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number, public fields?: unknown, public retryAfterSeconds?: number) {
    super(message); this.name = 'ApiError';
  }
}

const base = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
let csrfToken: string | null = null;
const etags = new Map<string, string>();
const idem = () => crypto.randomUUID();
const pendingIdempotency = new Map<string, string>();

async function raw(path: string, init: RequestInit = {}, retrySession = true): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 30_000);
  try {
    const headers = new Headers(init.headers);
    headers.set('Accept', 'application/json');
    if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    if (path !== '/session') await ensureSession();
    if (['POST', 'PATCH', 'PUT', 'DELETE'].includes((init.method ?? 'GET').toUpperCase()) && path !== '/session') {
      headers.set('X-CSRF-Token', csrfToken!);
      if (!headers.has('Idempotency-Key')) {
        const fingerprint = `${(init.method ?? 'GET').toUpperCase()}:${path}:${typeof init.body === 'string' ? init.body : ''}`;
        if (!pendingIdempotency.has(fingerprint)) pendingIdempotency.set(fingerprint, idem());
        headers.set('Idempotency-Key', pendingIdempotency.get(fingerprint)!);
      }
    }
    const response = await fetch(`${base}/api/v1${path}`, { ...init, headers, credentials: 'include', signal: init.signal ?? controller.signal });
    if (response.ok) pendingIdempotency.delete(`${(init.method ?? 'GET').toUpperCase()}:${path}:${typeof init.body === 'string' ? init.body : ''}`);
    if (response.status === 401 && retrySession && path !== '/session') {
      csrfToken = null;
      await initializeSession();
      return raw(path, init, false);
    }
    const tag = response.headers.get('ETag');
    const eventId = path.match(/^\/events\/([^/?]+)/)?.[1];
    if (tag && eventId) etags.set(eventId, tag);
    if (!response.ok) {
      let body: any = null;
      try { body = await response.json(); } catch { /* sanitized fallback below */ }
      const retryAfter = Number(response.headers.get('Retry-After'));
      throw new ApiError(body?.error?.code ?? 'network_error', body?.error?.message ?? `Request failed (${response.status}).`, response.status, body?.error?.fields, Number.isInteger(retryAfter) && retryAfter > 0 ? retryAfter : undefined);
    }
    return response;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError('network_error', error instanceof DOMException && error.name === 'AbortError' ? 'The request timed out. Check your connection and try again.' : 'Could not reach MomentOS. Check that the server is running and try again.', 0);
  } finally { window.clearTimeout(timer); }
}

let sessionPromise: Promise<void> | null = null;
async function initializeSession(): Promise<void> {
  const response = await raw('/session', { method: 'POST' }, false);
  const body = await response.json(); csrfToken = body.data.csrf_token;
}
async function ensureSession(): Promise<void> {
  if (csrfToken) return;
  if (!sessionPromise) sessionPromise = (async () => {
    try {
      const response = await raw('/session', { method: 'GET' }, false);
      const body = await response.json(); csrfToken = body.data.csrf_token;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) await initializeSession(); else throw e;
    } finally { sessionPromise = null; }
  })();
  return sessionPromise;
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<{ body: ApiEnvelope<T>; etag: string | null }> {
  const response = await raw(path, init);
  return { body: await response.json() as ApiEnvelope<T>, etag: response.headers.get('ETag') };
}
export function eventHeaders(eventId: string): HeadersInit {
  const etag = etags.get(eventId);
  if (!etag) throw new ApiError('precondition_required', 'Reload the event before saving changes.', 428);
  return { 'If-Match': etag };
}
export function setEventEtag(eventId: string, etag: string | null): void { if (etag) etags.set(eventId, etag); }
export function clearSessionForTests(): void { csrfToken = null; sessionPromise = null; etags.clear(); pendingIdempotency.clear(); }
