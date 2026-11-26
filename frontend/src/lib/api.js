const BASE = (import.meta.env.VITE_API_BASE || '/api').replace(/\/$/, '');

// The free Render server sleeps after 15 idle minutes and takes about a minute
// to start again. While it is asleep, requests that come through Vercel's proxy
// get an instant 502 and may not wake it; a visit straight to the Render address
// does. So on the first failure the visitor's browser pings Render directly
// ('no-cors': the request only has to arrive, nobody reads the reply), and GET
// requests keep retrying until the server is up.
const WAKE_URL = import.meta.env.VITE_WAKE_URL || 'https://jansetu-ai-v0-2.onrender.com/api/health';
const RETRY_STATUSES = new Set([502, 503, 504]);
const RETRY_DELAYS_MS = [2000, 3000, 5000, 5000, 5000, 5000, 10000, 10000, 10000, 10000, 10000, 10000];

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

let lastWake = 0;
function wakeBackend() {
  if (!import.meta.env.PROD || Date.now() - lastWake < 30000) return;
  lastWake = Date.now();
  try { fetch(WAKE_URL, { mode: 'no-cors', cache: 'no-store' }).catch(() => {}); } catch { /* ignore */ }
}

/** Small fetch wrapper: JSON in/out, bearer token, readable errors, cold-start retries. */
export function createApi(getToken, onUnauthorized) {
  return async function api(path, { method = 'GET', body, auth = true } = {}) {
    const token = getToken();
    const headers = { 'Content-Type': 'application/json' };
    if (token && auth) headers.Authorization = `Bearer ${token}`;
    const canRetry = method === 'GET';

    let res;
    for (let attempt = 0; ; attempt += 1) {
      const lastTry = !canRetry || attempt >= RETRY_DELAYS_MS.length;
      try {
        res = await fetch(BASE + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
      } catch {
        wakeBackend();
        if (lastTry) throw new Error('Cannot reach the JanSetu server. Check your internet connection and try again.');
        await wait(RETRY_DELAYS_MS[attempt]);
        continue;
      }
      if (!RETRY_STATUSES.has(res.status)) break;
      wakeBackend();
      if (lastTry) break;
      await wait(RETRY_DELAYS_MS[attempt]);
    }

    let data = null;
    try { data = await res.json(); } catch { /* empty or HTML body */ }
    if (res.status === 401 && token && auth) {
      onUnauthorized();
      throw new Error('Your session has expired. Sign in again to continue.');
    }
    if (RETRY_STATUSES.has(res.status)) {
      throw new Error('The JanSetu server is still starting up. Wait a minute and press Try again.');
    }
    if (!res.ok) throw new Error((data && (data.error || data.msg)) || `Request failed (${res.status})`);
    return data;
  };
}
