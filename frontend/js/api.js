/* ==========================================================================
   api.js — the ONLY place that talks to the Flask backend. Every page module
   calls apiFetch(); nothing else touches fetch()/Authorization headers.
   ========================================================================== */

async function apiFetch(path, options = {}) {
  const headers = Object.assign({}, options.headers || {});
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  if (authToken) headers['Authorization'] = 'Bearer ' + authToken;

  const resp = await fetch(API_BASE + path, Object.assign({}, options, { headers }));
  if (resp.status === 401) {
    doLogout();
    throw new Error('Sesi berakhir, silakan masuk kembali.');
  }
  let data = null;
  try { data = await resp.json(); } catch (e) { /* no body */ }
  if (!resp.ok) {
    const message = (data && (data.message || data.error)) || `Permintaan gagal (${resp.status})`;
    throw new Error(message);
  }
  return data;
}
