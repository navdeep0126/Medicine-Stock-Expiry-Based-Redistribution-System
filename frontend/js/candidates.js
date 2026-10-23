(async () => {
  const v = $('#view'); let reqs = [];
  try { reqs = (await API.getRequests()).filter(r => r.status === 'Pending' || r.status === 'Partially Fulfilled'); }
  catch (error) { v.innerHTML = `<div class="card">${empty('Could not load candidate requests', esc(error.message || 'Check the backend and database connection.'))}</div>`; return; }
  v.innerHTML = `<label class="f" style="max-width:420px;margin-bottom:16px">Request<select id="sel">${reqs.map(r => `<option value="${r.id}">${r.id} · ${esc(r.medicineName)} → ${esc(r.facilityName)} (${r.status})</option>`).join('')}</select></label><div id="out"></div>`;
  if (!reqs.length) { $('#out').innerHTML = `<div class="card">${empty('No active requests', 'Create a request first, then come back to see which batches can supply it.')}</div>`; $('#sel').disabled = true; return; }
  const want = new URLSearchParams(location.search).get('req'); if (reqs.some(r => r.id === want)) $('#sel').value = want;
  async function show() {
    $('#out').innerHTML = loader(); const e = await API.getEligible($('#sel').value), r = e.request, el = e.rows.filter(x => x.eligible), ex = e.rows.filter(x => !x.eligible);
    const msg = { full: 'The request can be fully fulfilled from the proposed batches.', partial: `The request can only be partially fulfilled. ${num(Math.max(0, e.remaining - e.supply))} units would remain unmet.`, none: 'No eligible medicine batches were found for this request. Nothing can be supplied right now.' };
    $('#out').innerHTML = `<section class="card" style="margin-bottom:16px"><h2>Request ${r.id}</h2><dl class="kv"><dt>Medicine</dt><dd>${esc(r.medicineName)} (${r.medicineId})</dd><dt>Destination</dt><dd>${esc(r.facilityName)}</dd><dt>Requested</dt><dd>${num(r.qty)}</dd><dt>Allocated</dt><dd>${num(r.allocated)}</dd><dt>Remaining</dt><dd>${num(r.remaining)}</dd></dl></section>
    <section class="card" style="margin-bottom:16px"><h2>Eligible sources, in expiry-priority order</h2>${!e.hasResult ? empty('No candidate result', 'The backend could not return a candidate analysis for this request.') : table(['Priority', 'Source batch', 'Source facility', 'Available qty', 'Expiry date', 'Days remaining', 'Stock status', 'Eligibility', 'Suggested qty'],
      el.map((x, i) => `<tr><td>${i + 1}</td><td><b>${x.batchId}</b></td><td>${esc(x.facilityName)}</td><td>${num(x.qty)}</td><td>${fmt(x.expiry)}</td><td>${daysText(x.expiry)}${expiryStatus(x.expiry) === 'Near Expiry' ? ' ' + badge('Near Expiry') : ''}</td><td>${badge(x.stock)}</td><td>${badge('Eligible')}</td><td><b>${num(x.suggested)}</b></td></tr>`).concat(
      ex.map(x => `<tr class="dim"><td>–</td><td><b>${x.batchId}</b></td><td>${esc(x.facilityName)}</td><td>${num(x.qty)}</td><td>${fmt(x.expiry)}</td><td>${daysText(x.expiry)}</td><td>${badge(x.stock)}</td><td>${badge('Excluded')}<small>${esc(x.reason)}</small></td><td>–</td></tr>`)))}</section>
    ${e.hasResult ? `<section class="card"><h2>Summary</h2><dl class="kv"><dt>Total eligible stock</dt><dd>${num(e.eligibleTotal)}</dd><dt>Requested (remaining)</dt><dd>${num(e.remaining)}</dd><dt>Can be supplied</dt><dd>${num(e.supply)}</dd></dl><div class="outcome ${e.outcome}">${msg[e.outcome]}</div></section>` : ''}`;
  }
  $('#sel').onchange = show; show();
})();
