/* Live API data layer for Medicine Stock & Expiry-Based Redistribution System.
   This file replaces the localStorage demo layer. The Flask API and website must
   be served from the same origin (use run_web_api.ps1; do not use http.server). */
const API = (() => {
  const fail = message => Promise.reject(new Error(message));

  async function call(path, options = {}) {
    let response;
    try {
      response = await fetch(path, {
        credentials: 'same-origin',
        ...options,
        headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) }
      });
    } catch (error) {
      throw new Error('Cannot reach the Python backend. Start it with run_web_api.ps1 and open http://127.0.0.1:5000.');
    }
    const text = await response.text();
    let data = null;
    if (text) {
      try { data = JSON.parse(text); } catch (_) { data = { error: text }; }
    }
    if (response.status === 401 && !['/login.html', '/register.html'].includes(window.location.pathname)) {
      window.location.replace('/login.html');
      throw new Error('Please sign in to continue.');
    }
    if (!response.ok) throw new Error((data && data.error) || `Request failed (${response.status}).`);
    return data;
  }

  const json = value => JSON.stringify(value);
  // The MySQL schema has no request-created date, so the API returns null.
  // Normalize it to an empty string because existing page scripts sort dates with localeCompare.
  // app.js formats an empty date as 'Not recorded'.
  const withRequestHelpers = r => ({ ...r, date: r.date || '', remaining: Number(r.remaining ?? (Number(r.qty) - Number(r.allocated))) });

  return {
    // GET /api/batches
    getBatches: () => call('/api/batches'),
    getMedicines: () => call('/api/medicines'),

    // POST /api/batches
    addBatch(batch) {
      return call('/api/batches', { method: 'POST', body: json(batch) }).then(() => true);
    },

    // PUT /api/batches/<batchId>
    updateBatch(batch) {
      if (!batch || !batch.batchId) return fail('Batch ID is required.');
      return call(`/api/batches/${encodeURIComponent(batch.batchId)}`, {
        method: 'PUT', body: json(batch)
      }).then(() => true);
    },

    // DELETE /api/batches/<batchId>
    deleteBatch(batchId) {
      return call(`/api/batches/${encodeURIComponent(batchId)}`, { method: 'DELETE' }).then(() => true);
    },

    // GET /api/requests
    async getRequests() {
      // The backend returns active requests in persistent FIFO order. Preserve it;
      // sorting here by ID would undo re-queueing after an unsuccessful attempt.
      return (await call('/api/requests')).map(withRequestHelpers);
    },

    // POST /api/requests
    async createRequest({ medicineId, facilityId, qty }) {
      const data = await call('/api/requests', {
        method: 'POST', body: json({ medicineId, facilityId, qty: Number(qty) })
      });
      return data.id || data.requestId;
    },

    // GET /api/requests/<id>/eligible; calculations come from Python DSA classes.
    getEligible(id) {
      return call(`/api/requests/${encodeURIComponent(id)}/eligible`);
    },

    // POST /api/redistribution/process-next; Python processes one FIFO request.
    processNext: () => call('/api/redistribution/process-next', { method: 'POST' }),

    // GET /api/transactions
    // Some existing MySQL transaction rows may have no transaction_date.
    // Normalize missing dates so dashboard sorting with localeCompare never crashes.
    async getTransactions() {
      const rows = await call('/api/transactions');
      return rows.map(t => ({ ...t, date: t.date || '' }));
    },

    // GET /api/facilities
    getFacilities: () => call('/api/facilities'),

    // POST /api/facilities; administrators create a facility and its active hospital account.
    createFacility(facility) {
      return call('/api/facilities', { method: 'POST', body: json(facility) });
    },

    // GET /api/auth/me; the backend derives the facility from the signed-in session.
    getCurrentUser: () => call('/api/auth/me'),

    // The demo reset must never clear real MySQL data. No-op is intentional.
    reset() {
      console.warn('Demo reset is disabled while connected to the MySQL database. No database data was changed.');
      return Promise.resolve(false);
    }
  };
})();


/* Add a signed-in user badge to the shared application header. */
(() => {
  const path = window.location.pathname;
  if (path === '/login.html' || path === '/register.html') return;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  fetch('/api/auth/me', { credentials: 'same-origin' }).then(async response => {
    if (response.status === 401) { window.location.replace('/login.html'); return null; }
    if (!response.ok) return null;
    return response.json();
  }).then(user => {
    if (!user) return;
    const addBadge = () => {
      const header = document.querySelector('.top');
      if (!header) return false;
      const reset = header.querySelector('#reset');
      if (reset) reset.remove();
      if (document.getElementById('auth-account-pill')) return true;
      const account = document.createElement('div');
      account.id = 'auth-account-pill';
      account.style.cssText = 'display:flex;align-items:center;gap:9px;padding:5px 8px 5px 12px;border:1px solid #dceae2;border-radius:11px;background:#fff;max-width:270px;margin-left:10px;z-index:30';
      const subline = user.facilityId ? `${user.facilityId} · ${user.facilityName}` : 'System administrator';
      account.innerHTML = `<div style="min-width:0"><div style="font-size:11px;font-weight:800;color:#285d4a;max-width:155px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(user.username)}</div><div style="font-size:10px;color:#7a9187;max-width:155px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(subline)}</div></div><button id="auth-logout" type="button" style="background:#f1f7f3;border:1px solid #dceae2;border-radius:7px;padding:7px 8px;font-size:10px;font-weight:800;color:#215c4b;cursor:pointer">Sign out</button>`;
      header.appendChild(account);
      account.querySelector('#auth-logout').addEventListener('click', async () => {
        try { await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' }); }
        finally { window.location.replace('/login.html'); }
      });
      return true;
    };
    if (!addBadge()) {
      const observer = new MutationObserver(() => { if (addBadge()) observer.disconnect(); });
      observer.observe(document.documentElement, { childList: true, subtree: true });
      setTimeout(() => observer.disconnect(), 5000);
    }
  }).catch(() => window.location.replace('/login.html'));
})();
