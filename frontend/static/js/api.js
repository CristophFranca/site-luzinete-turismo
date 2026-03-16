/**
 * api.js — Cliente HTTP centralizado — Luzinete Turismo
 */
const api = {
  async _req(method, url, body) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body !== undefined) opts.body = JSON.stringify(body);
    try {
      const res  = await fetch(url, opts);
      let data = {};
      try { data = await res.json(); } catch (_) {}
      return { ok: res.ok, status: res.status, data };
    } catch {
      return { ok: false, status: 0, data: { erro: 'Sem conexão com o servidor.' } };
    }
  },
  get:    url        => api._req('GET',    url),
  post:   (url, b)   => api._req('POST',   url, b),
  put:    (url, b)   => api._req('PUT',    url, b),
  delete: url        => api._req('DELETE', url),
};
