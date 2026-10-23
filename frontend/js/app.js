/* Shared layout + helpers */
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const NEAR_DAYS = 60; // project near-expiry threshold
const daysLeft = d => Math.round((new Date(d + 'T00:00:00') - new Date(new Date().toDateString())) / 864e5);
const expiryStatus = d => { const n = daysLeft(d); return n < 0 ? 'Expired' : n <= NEAR_DAYS ? 'Near Expiry' : 'Valid'; };
const daysText = d => { const n = daysLeft(d); return n < 0 ? `Expired ${-n} d ago` : n === 0 ? 'Expires today' : `${n} days`; };
const fmt = d => !d ? 'Not recorded' : new Date(d + 'T00:00:00').toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
const isSource = b => b.stock === 'Available' && b.qty > 0 && expiryStatus(b.expiry) !== 'Expired';
const BK = { Available: 'ok', Valid: 'ok', 'Out of Stock': 'mute', 'Near Expiry': 'warn', Expired: 'bad', Pending: 'warn', Fulfilled: 'ok',
  'Partially Fulfilled': 'info', Rejected: 'bad', Eligible: 'ok', Excluded: 'bad', Critical: 'bad', Warning: 'warn' };
const BI = { ok: '✓', warn: '!', bad: '✕', mute: '–', info: '◐' };
const badge = t => { const k = BK[t] || 'mute'; return `<span class="badge ${k}"><i aria-hidden="true">${BI[k]}</i>${esc(t)}</span>`; };
const loader = () => '<div class="loader" role="status"><span></span>Loading data…</div>';
const empty = (t, m) => `<div class="empty"><div class="pill-art" aria-hidden="true"></div><h3>${t}</h3><p>${m}</p></div>`;
const table = (h, rows) => `<div class="tw"><table><thead><tr>${h.map(x => `<th scope="col">${x}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
const num = n => Number(n).toLocaleString('en-IN');

function toast(msg, type = 'ok') {
  let box = $('#toasts'); if (!box) { box = document.createElement('div'); box.id = 'toasts'; box.setAttribute('aria-live', 'polite'); document.body.append(box); }
  const t = document.createElement('div'); t.className = 'toast ' + type; t.innerHTML = `<i aria-hidden="true">${BI[type] || '✓'}</i>${esc(msg)}`;
  box.append(t); setTimeout(() => t.remove(), 4200);
}
function modal(title, body, actions = []) {
  const d = document.createElement('dialog');
  d.innerHTML = `<div class="mh"><h2>${title}</h2><button type="button" class="x" aria-label="Close dialog">✕</button></div><div class="mb">${body}</div><div class="mf"></div>`;
  $('.x', d).onclick = () => d.close();
  actions.forEach(a => { const b = document.createElement('button'); b.type = 'button'; b.className = 'btn ' + (a.cls || ''); b.textContent = a.label; b.onclick = () => a.run(d); $('.mf', d).append(b); });
  d.addEventListener('close', () => d.remove()); document.body.append(d); d.showModal(); return d;
}
const confirmBox = (msg, label, run) => modal('Please confirm', `<p>${msg}</p><p class="muted">This action changes records in the configured test database.</p>`,
  [{ label: 'Cancel', cls: 'ghost', run: d => d.close() }, { label, cls: 'danger', run: d => { d.close(); run(); } }]);
function bars(el, items) { const max = Math.max(...items.map(i => i.v), 1);
  $(el).innerHTML = items.map(i => `<div class="bar"><span>${i.l}</span><div class="track"><div style="width:${i.v / max * 100}%;background:${i.c}"></div></div><b>${i.v}</b></div>`).join(''); }
function donut(el, items) { const tot = items.reduce((s, i) => s + i.v, 0); let a = 0;
  const g = tot ? items.map(i => { const s = a; a += i.v / tot * 100; return `${i.c} ${s}% ${a}%`; }).join(',') : '#e3ece7 0 100%';
  $(el).innerHTML = `<div class="donut" style="background:conic-gradient(${g})" role="img" aria-label="Donut chart"><b>${tot}</b></div><ul class="legend">${items.map(i => `<li><i style="background:${i.c}"></i>${i.l}: <b>${i.v}</b></li>`).join('')}</ul>`; }
function pager(el, total, page, ps, go) { const n = Math.max(1, Math.ceil(total / ps));
  $(el).innerHTML = total ? `<span>Showing ${(page - 1) * ps + 1}–${Math.min(total, page * ps)} of ${total}</span><button class="btn ghost sm" ${page <= 1 ? 'disabled' : ''} data-p="${page - 1}">Previous</button><span>Page ${page} of ${n}</span><button class="btn ghost sm" ${page >= n ? 'disabled' : ''} data-p="${page + 1}">Next</button>` : '';
  $$('button', $(el)).forEach(b => b.onclick = () => go(+b.dataset.p)); }

(function shell() {
  const b = document.body, pg = b.dataset.page, view = $('#view');
  const NAV = [['dashboard', 'index.html', 'Dashboard', '▦'], ['inventory', 'inventory.html', 'Medicine Inventory', '▤'], ['requests', 'requests.html', 'Redistribution Requests', '⇆'],
    ['candidates', 'candidates.html', 'Eligible Medicine Sources', '⌕'], ['transactions', 'transactions.html', 'Transaction History', '☰'], ['facilities', 'facilities.html', 'Healthcare Facilities', '⌂']];
  b.insertAdjacentHTML('afterbegin', `<a class="skip" href="#view">Skip to content</a><div class="layout">
  <aside class="side" id="side" aria-label="Main navigation"><a class="brand" href="index.html"><img src="assets/logo/logo.svg" alt="" width="42" height="42"><span>Medi<b>Redistribute</b><small>Stock &amp; expiry</small></span></a>
  <nav>${NAV.map(n => `<a href="${n[1]}" ${n[0] === pg ? 'class="on" aria-current="page"' : ''}><i aria-hidden="true">${n[3]}</i>${n[2]}</a>`).join('')}</nav><div class="blister-art" aria-hidden="true"></div></aside>
  <div class="main"><header class="top"><button class="btn ghost sm menu" id="menu" aria-label="Open menu" aria-controls="side">☰ Menu</button>
  <span class="grow"></span></header>
  <div class="content"><div class="ph"><nav aria-label="Breadcrumb" class="crumb"><a href="index.html">Home</a> / <span>${esc(b.dataset.title)}</span></nav><h1><span class="rx" aria-hidden="true">℞</span> ${esc(b.dataset.title)}</h1><p>${esc(b.dataset.sub)}</p></div><div id="slot"></div></div>
  <footer>Medicine Stock &amp; Expiry-Based Redistribution System — Academic Project Prototype</footer></div></div>`);
  $('#slot').append(view);
  $('#menu').onclick = () => $('#side').classList.toggle('open');
})();
