(async () => {
  const v = $('#view'); const [T, F] = [await API.getTransactions(), await API.getFacilities()], S = {};
  const opts = F.map(f => `<option value="${f.id}">${esc(f.name)}</option>`).join('');
  v.innerHTML = `<div class="grid g3" id="sum"></div><div class="card toolbar"><label class="f grow"><span>Medicine</span><input id="q" type="search" placeholder="Medicine name or ID"></label>
  <label class="f"><span>Request ID</span><input id="rq" placeholder="e.g. R001"></label><label class="f"><span>Source facility</span><select id="sf"><option value="">All</option>${opts}</select></label>
  <label class="f"><span>Destination facility</span><select id="df"><option value="">All</option>${opts}</select></label><label class="f"><span>From date</span><input id="d1" type="date"></label><label class="f"><span>To date</span><input id="d2" type="date"></label>
  <button class="btn ghost" id="clr">Clear filters</button></div><div class="card"><div id="tbl"></div></div>`;
  function draw() {
    const L = T.filter(t => (!S.q || (t.medicineName + t.medicineId).toLowerCase().includes(S.q.toLowerCase())) && (!S.rq || t.requestId.toLowerCase().includes(S.rq.toLowerCase())) && (!S.sf || t.sourceId === S.sf) && (!S.df || t.destId === S.df) && (!S.d1 || t.date >= S.d1) && (!S.d2 || t.date <= S.d2)).sort((a, b) => b.date.localeCompare(a.date));
    $('#sum').innerHTML = [['Transactions shown', L.length, '☰'], ['Units transferred', num(L.reduce((s, t) => s + t.qty, 0)), '⇆']].map(x => `<div class="card stat t-teal"><i aria-hidden="true">${x[2]}</i><div><b>${x[1]}</b><span>${x[0]}</span></div></div>`).join('') + '<div class="card muted sm">Transaction history is read-only. Completed transfers cannot be edited or deleted.</div>';
    $('#tbl').innerHTML = !L.length ? empty('No transactions found', T.length ? 'Adjust or clear the filters.' : 'Completed transfers will appear here.') : table(['Transaction', 'Request', 'Medicine', 'Source batch', 'Source facility', 'Destination', 'Qty', 'Date', 'Details'],
      L.map(t => `<tr><td><b>${t.id}</b></td><td>${t.requestId}</td><td>${t.medicineId} · ${esc(t.medicineName)}</td><td>${t.batchId}</td><td>${esc(t.sourceName)}</td><td>${esc(t.destName)}</td><td>${num(t.qty)}</td><td>${fmt(t.date)}</td><td><button class="btn ghost sm" data-id="${t.id}">View Details</button></td></tr>`));
    $$('[data-id]', $('#tbl')).forEach(b => b.onclick = () => { const t = T.find(x => x.id === b.dataset.id);
      modal('Transaction ' + t.id, `<dl class="kv"><dt>Request</dt><dd>${t.requestId}</dd><dt>Medicine</dt><dd>${esc(t.medicineName)} (${t.medicineId})</dd><dt>Source batch</dt><dd>${t.batchId}</dd><dt>From</dt><dd>${esc(t.sourceName)}</dd><dt>To</dt><dd>${esc(t.destName)}</dd><dt>Quantity</dt><dd>${num(t.qty)}</dd><dt>Date</dt><dd>${fmt(t.date)}</dd></dl>`, [{ label: 'Close', cls: 'ghost', run: d => d.close() }]); });
  }
  [['q', 'q'], ['rq', 'rq'], ['sf', 'sf'], ['df', 'df'], ['d1', 'd1'], ['d2', 'd2']].forEach(([i, k]) => $('#' + i).oninput = e => { S[k] = e.target.value.trim(); draw(); });
  $('#clr').onclick = () => { Object.keys(S).forEach(k => delete S[k]); $$('.toolbar input,.toolbar select').forEach(x => x.value = ''); draw(); }; draw();
})();
