const BASE = (import.meta.env.VITE_API_BASE || '/api').replace(/\/$/, '');

/** Small fetch wrapper: JSON in/out, bearer token, readable errors. */
export function createApi(getToken, onUnauthorized) {
  return async function api(path, { method = 'GET', body, auth = true } = {}) {
    const token = getToken();
    const headers = { 'Content-Type': 'application/json' };
    if (token && auth) headers.Authorization = `Bearer ${token}`;
    let res;
    try {
      res = await fetch(BASE + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    } catch {
      throw new Error('Cannot reach the JanSetu server. Check that the backend is running and try again.');
    }
    let data = null;
    try { data = await res.json(); } catch { /* empty body */ }
    if (res.status === 401 && token && auth) {
      onUnauthorized();
      throw new Error('Your session has expired. Sign in again to continue.');
    }
    if (!res.ok) throw new Error((data && (data.error || data.msg)) || `Request failed (${res.status})`);
    return data;
  };
}
