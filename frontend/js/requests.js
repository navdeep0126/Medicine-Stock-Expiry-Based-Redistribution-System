/* Live redistribution request page.
   Uses the existing Flask API and its FIFO processing endpoint.
   The DSA implementation in main.py is not changed by this frontend file. */
(async () => {
  const v = $('#view');
  let R = [], M = [], F = [], queue = [], busy = false, currentUser = null;

  v.innerHTML = `
    <div class="row">
      <button class="btn" id="new">+ Create request</button>
      <button class="btn ghost" id="next">Process Next Request</button>
    </div>
    <section class="card" style="margin-bottom:18px">
      <h2>Next in the queue</h2>
      <div id="panel">${loader()}</div>
    </section>
    <section class="card">
      <h2>All requests</h2>
      <div id="tbl">${loader()}</div>
    </section>`;

  const isOutstanding = r => r.status === 'Pending' && Number(r.remaining) > 0;
  const requestNumber = r => {
    const match = String(r.id ?? '').match(/^R(\d+)$/i);
    return match ? Number(match[1]) : Number.MAX_SAFE_INTEGER;
  };
  const fifoSort = rows => [...rows].sort((a, b) => {
    const an = requestNumber(a), bn = requestNumber(b);
    return an - bn || String(a.id).localeCompare(String(b.id));
  });

  async function load() {
    $('#tbl').innerHTML = loader();
    $('#panel').innerHTML = loader();
    try {
      [R, M, F, currentUser] = await Promise.all([
        API.getRequests(), API.getMedicines(), API.getFacilities(), API.getCurrentUser()
      ]);
      // API order is the durable FIFO sequence; do not re-sort by request ID.
      queue = R.filter(isOutstanding);
      renderTable();
      await renderNextPanel();
    } catch (error) {
      queue = [];
      $('#tbl').innerHTML = empty('Could not load requests', esc(error.message || 'The backend request failed.'));
      $('#panel').innerHTML = `<div class="note amber">${esc(error.message || 'Could not load queue information.')}<br>Check that the Flask API is running and its database request succeeded, then refresh this page.</div>`;
      toast(error.message || 'Could not load request data.', 'bad');
    }
    updateProcessButton();
  }

  function renderTable() {
    if (!R.length) {
      $('#tbl').innerHTML = empty('No requests yet', 'Create a request when a facility needs medicine.');
      return;
    }
    const position = new Map(queue.map((r, i) => [r.id, i]));
    const rows = [...R].sort((a, b) => {
      const aq = position.has(a.id), bq = position.has(b.id);
      if (aq && bq) return position.get(a.id) - position.get(b.id);
      if (aq) return -1;
      if (bq) return 1;
      return requestNumber(a) - requestNumber(b) || String(a.id).localeCompare(String(b.id));
    });
    $('#tbl').innerHTML = table(
      ['Queue', 'Request', 'Medicine', 'Destination facility', 'Requested', 'Allocated', 'Request date', 'Status', 'Actions'],
      rows.map(r => {
        const p = position.has(r.id) ? position.get(r.id) : -1;
        return `<tr class="${p === 0 ? 'front' : ''}">
          <td>${p < 0 ? '<small>Not queued</small>' : p === 0 ? '<b>#1 front</b>' : '#' + (p + 1)}</td>
          <td><b>${esc(r.id)}</b></td>
          <td>${esc(r.medicineId)} · ${esc(r.medicineName)}</td>
          <td>${esc(r.facilityName)}</td>
          <td>${num(r.qty)}</td>
          <td>${num(r.allocated)}</td>
          <td>${fmt(r.date)}</td>
          <td>${badge(r.status)}</td>
          <td>${isOutstanding(r) ? `<a class="btn ghost sm" href="candidates.html?req=${encodeURIComponent(r.id)}">View Eligible Sources</a>` : '<small>No action</small>'}</td>
        </tr>`;
      })
    );
  }

  const outcomeText = {
    full: 'Eligible stock appears sufficient to fulfil this request.',
    partial: 'Eligible stock may fulfil only part of this request.',
    none: 'No eligible stock was found for this request.'
  };

  function panel(e) {
    const r = e.request;
    const el = (e.rows || []).filter(x => x.eligible);
    const sourceTable = el.length
      ? table(
          ['Eligible source batch', 'Facility', 'Expiry date', 'Indicative quantity'],
          el.map(x => `<tr><td><b>${esc(x.batchId)}</b></td><td>${esc(x.facilityName)}</td><td>${fmt(x.expiry)}</td><td>${num(x.suggested)}</td></tr>`)
        )
      : empty('No eligible source batches', 'The request may remain pending until suitable stock becomes available.');
    return `<p><b>${esc(r.id)}</b> · ${esc(r.medicineName)} for ${esc(r.facilityName)} · requested <b>${num(r.qty)}</b> · remaining <b>${num(r.remaining)}</b></p>
      ${sourceTable}
      <p class="sm">Eligible stock identified: <b>${num(e.eligibleTotal ?? e.supply ?? 0)}</b> · Indicative allocation: <b>${num(e.supply || 0)}</b></p>
      <div class="outcome ${esc(e.outcome || 'none')}">${esc(outcomeText[e.outcome] || 'Check the eligible stock before processing.')}</div>
      <p class="sm muted">This is a read-only preview. Stock is changed only when you choose “Process Next Request” and confirm.</p>`;
  }

  async function renderNextPanel() {
    if (!queue.length) {
      $('#panel').innerHTML = empty('Queue is empty', 'There are no pending requests to process.');
      return;
    }
    const next = queue[0];
    try {
      const result = await API.getEligible(next.id);
      $('#panel').innerHTML = `<p class="muted sm"><b>Next request:</b> ${esc(next.id)}</p>` + panel(result);
    } catch (error) {
      $('#panel').innerHTML = `<div class="note amber">Could not load eligible sources for ${esc(next.id)}: ${esc(error.message || 'Unknown error')}</div>`;
    }
  }

  function updateProcessButton() {
    const button = $('#next');
    if (!button) return;
    button.disabled = busy || queue.length === 0;
    button.textContent = busy ? 'Processing…' : 'Process Next Request';
    button.title = queue.length ? `Process queue-front request ${queue[0].id}` : 'There are no outstanding requests.';
  }

  async function processNextRequest() {
    if (busy) return;
    if (!queue.length) {
      toast('There are no pending requests in the queue.', 'warn');
      return;
    }
    busy = true;
    updateProcessButton();
    try {
      const result = await API.processNext();
      if (!result || !result.processed) {
        toast(result?.message || 'There was no request to process.', 'warn');
      } else {
        const tx = Array.isArray(result.transactions) ? result.transactions : [];
        const details = tx.length
          ? table(
              ['Source batch', 'Source facility', 'Destination', 'Quantity'],
              tx.map(t => `<tr><td>${esc(t.batchId)}</td><td>${esc(t.sourceId)}</td><td>${esc(t.destId)}</td><td>${num(t.qty)}</td></tr>`)
            )
          : '<p>No stock was transferred. The request remains outstanding until eligible stock can be allocated.</p>';
        modal(
          `Request ${esc(result.requestId)} processed`,
          `<div class="note">${esc(result.message || 'The FIFO request was processed.')}</div>
           <p><b>Status:</b> ${badge(result.status)}</p>
           <p><b>Requested:</b> ${num(result.requested)} · <b>Total allocated:</b> ${num(result.allocated)} · <b>Remaining:</b> ${num(result.remaining)}</p>
           <p><b>Transferred in this processing run:</b> ${num(result.transferred || 0)}</p>
           ${details}`,
          [{ label: 'Close', cls: 'ghost', run: d => d.close() }]
        );
      }
      await load();
    } catch (error) {
      toast(error.message || 'The request could not be processed.', 'bad');
      await load();
    } finally {
      busy = false;
      updateProcessButton();
    }
  }

  $('#next').onclick = () => {
    if (busy || !queue.length) return;
    const r = queue[0];
    modal(
      'Process next FIFO request?',
      `<p>The queue-front request <b>${esc(r.id)}</b> will be processed by the Python backend using the existing DSA implementation.</p>
       <p class="note amber">This action can update stock, request status and transaction history in the configured test database.</p>`,
      [
        { label: 'Cancel', cls: 'ghost', run: d => d.close() },
        { label: 'Process request', run: d => { d.close(); processNextRequest(); } }
      ]
    );
  };

  function form() {
    modal(
      'Create redistribution request',
      `<div class="fg">
        <label class="f">Medicine <span class="req">*</span><select id="r1"><option value="">Select medicine</option>${M.map(m => `<option value="${esc(m.id)}">${esc(m.id)} · ${esc(m.name)}</option>`).join('')}</select><span class="err" id="x1"></span></label>
        ${currentUser?.role === 'hospital' ? `<label class="f">Requesting hospital<input value="${esc(currentUser.facilityId)} · ${esc(currentUser.facilityName)}" readonly><input id="r2" type="hidden" value="${esc(currentUser.facilityId)}"><span class="err" id="x2"></span><span class="muted sm">Your request will be linked to your hospital automatically.</span></label>` : `<label class="f">Destination facility <span class="req">*</span><select id="r2"><option value="">Select facility</option>${F.map(f => `<option value="${esc(f.id)}">${esc(f.id)} · ${esc(f.name)}</option>`).join('')}</select><span class="err" id="x2"></span></label>`}
        <label class="f">Requested quantity <span class="req">*</span><input id="r3" type="number" min="1" step="1"><span class="err" id="x3"></span></label>
        <label class="f">Request date<input value="${fmt(new Date().toISOString().slice(0, 10))}" readonly></label>
      </div>`,
      [
        { label: 'Cancel', cls: 'ghost', run: d => d.close() },
        { label: 'Create request', run: async d => {
          const g = i => $(`#r${i}`, d).value;
          const er = (i, message) => { $(`#x${i}`, d).textContent = message || ''; return !!message; };
          const q = g(3);
          if ([
            er(1, g(1) ? '' : 'Choose a medicine.'),
            er(2, g(2) ? '' : 'Choose a destination facility.'),
            er(3, q === '' ? 'Quantity is required.' : (!Number.isInteger(+q) || +q < 1) ? 'Enter a whole number greater than 0.' : '')
          ].some(Boolean)) return;
          try {
            const id = await API.createRequest({ medicineId: g(1), facilityId: g(2), qty: +q });
            d.close();
            toast(`Request ${id} was saved to the FIFO queue.`);
            await load();
          } catch (error) {
            toast(error.message || 'Could not create the request.', 'bad');
          }
        } }
      ]
    );
  }

  $('#new').onclick = () => {
    if (!M.length || !F.length) {
      toast('Medicine and facility lists have not loaded. Check the backend first.', 'warn');
      return;
    }
    form();
  };

  await load();
  if (new URLSearchParams(location.search).get('new')) form();
})();
