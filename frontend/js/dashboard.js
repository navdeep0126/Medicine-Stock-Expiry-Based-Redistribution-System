(async () => {
  const v = $('#view');
  v.innerHTML = loader();
  try {
    const [B, R, T] = await Promise.all([
      API.getBatches(),
      API.getRequests(),
      API.getTransactions()
    ]);
  const c = (a, f) => a.filter(f).length, es = b => expiryStatus(b.expiry);
  const cards = [['Total medicine batches', B.length, '▤', 'teal'], ['Total units recorded', num(B.reduce((s, b) => s + b.qty, 0)), 'Σ', 'teal'],
    ['Available batches (in date)', c(B, isSource), '✓', 'ok'], ['Near-expiry batches', c(B, b => es(b) === 'Near Expiry'), '!', 'warn'],
    ['Expired batches', c(B, b => es(b) === 'Expired'), '✕', 'bad'], ['Pending requests', c(R, r => r.status === 'Pending'), '⏳', 'warn'],
    ['Fulfilled requests', c(R, r => r.status === 'Fulfilled'), '✓', 'ok'], ['Partially fulfilled', c(R, r => r.status === 'Partially Fulfilled'), '◐', 'info']];
  const sev = b => es(b) === 'Expired' ? 'Expired' : daysLeft(b.expiry) <= 14 ? 'Critical' : 'Warning';
  const alerts = B.filter(b => b.qty > 0 && es(b) !== 'Valid').sort((a, b) => a.expiry.localeCompare(b.expiry)).slice(0, 6);
  const capc = b => es(b) === 'Expired' ? 'bad' : es(b) === 'Near Expiry' ? 'warn' : b.stock === 'Available' ? 'ok' : 'mute';
  v.innerHTML = `<div class="row"><a class="btn" href="inventory.html">View Inventory</a><a class="btn ghost" href="requests.html?new=1">Create Redistribution Request</a></div>
  <div class="grid g4">${cards.map(x => `<div class="card stat t-${x[3]}"><i aria-hidden="true">${x[2]}</i><div><b>${x[1]}</b><span>${x[0]}</span></div></div>`).join('')}</div>
  <section class="card" style="margin-bottom:18px"><h2>Batch blister pack</h2><p class="muted sm" style="margin:-6px 0 4px">One capsule per batch, ordered by expiry date. Hover or focus a capsule for details.</p>
   <div class="blister">${[...B].sort((a, b) => a.expiry.localeCompare(b.expiry)).map(b => `<span class="cap ${capc(b)}" tabindex="0" title="${b.batchId} · ${esc(b.medicineName)} · ${es(b)} · ${b.stock}"></span>`).join('')}</div>
   <div class="key"><span><i style="background:#d33a3a"></i>Expired</span><span><i style="background:#e09100"></i>Near expiry (≤ ${NEAR_DAYS} days)</span><span><i style="background:#2f9e77"></i>Valid and available</span><span><i style="background:#9fb3ad"></i>Valid but out of stock</span></div></section>
  <div class="grid g3"><section class="card"><h2>Batches by stock status</h2><div class="chart" id="c1"></div></section>
   <section class="card"><h2>Batches by expiry category</h2><div id="c2"></div></section><section class="card"><h2>Requests by status</h2><div id="c3"></div></section></div>
  <section class="card" style="margin-bottom:18px"><h2>Urgent expiry alerts</h2>${alerts.length ? table(['Medicine / batch', 'Facility', 'Quantity', 'Expiry date', 'Days remaining', 'Severity'],
    alerts.map(b => `<tr><td><b>${esc(b.medicineName)}</b><small>${b.batchId}</small></td><td>${esc(b.facilityName)}</td><td>${num(b.qty)}</td><td>${fmt(b.expiry)}</td><td>${daysText(b.expiry)}</td><td>${badge(sev(b))}</td></tr>`)) : empty('No urgent alerts', 'No batch with stock is expired or near expiry.')}</section>
  <div class="grid g2"><section class="card"><h2>Recent redistribution requests</h2>${table(['Request', 'Medicine', 'Destination', 'Qty', 'Date', 'Status'],
    [...R].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 5).map(r => `<tr><td><b>${r.id}</b></td><td>${esc(r.medicineName)}</td><td>${esc(r.facilityName)}</td><td>${num(r.qty)}</td><td>${fmt(r.date)}</td><td>${badge(r.status)}</td></tr>`))}</section>
   <section class="card"><h2>Recent transactions</h2>${T.length ? table(['ID', 'From → To', 'Medicine / batch', 'Qty', 'Date'],
    [...T].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 5).map(t => `<tr><td><b>${t.id}</b></td><td>${esc(t.sourceName)} → ${esc(t.destName)}</td><td>${esc(t.medicineName)}<small>${t.batchId}</small></td><td>${num(t.qty)}</td><td>${fmt(t.date)}</td></tr>`)) : empty('No transactions yet', 'Completed transfers will appear here.')}</section></div>`;
  const st = s => c(B, b => b.stock === s);
  donut('#c1', [{ l: 'Available', v: st('Available'), c: '#2f9e77' }, { l: 'Out of Stock', v: st('Out of Stock'), c: '#9fb3ad' }, { l: 'Expired', v: st('Expired'), c: '#d33a3a' }]);
  bars('#c2', [{ l: 'Valid', v: c(B, b => es(b) === 'Valid'), c: '#2f9e77' }, { l: 'Near Expiry', v: c(B, b => es(b) === 'Near Expiry'), c: '#e09100' }, { l: 'Expired', v: c(B, b => es(b) === 'Expired'), c: '#d33a3a' }]);
  bars('#c3', ['Pending', 'Fulfilled', 'Partially Fulfilled', 'Rejected'].map((s, i) => ({ l: s, v: c(R, r => r.status === s), c: ['#e09100', '#2f9e77', '#3b78c4', '#d33a3a'][i] })));
  } catch (error) {
    const message = esc(error && error.message ? error.message : 'The dashboard could not load data.');
    v.innerHTML = `
      <section class="card" role="alert">
        <h2>Dashboard data could not be loaded</h2>
        <p class="muted">The page is connected to the web interface, but one of its API requests failed.</p>
        <div class="note amber" style="overflow-wrap:anywhere">${message}</div>
        <div class="row" style="margin-top:14px">
          <button class="btn" id="retry-dashboard">Retry loading</button>
          <a class="btn ghost" href="/api/health" target="_blank" rel="noopener">Check API health</a>
        </div>
      </section>`;
    const retry = document.getElementById('retry-dashboard');
    if (retry) retry.addEventListener('click', () => window.location.reload());
    console.error('Dashboard API load failed:', error);
  }
})();
