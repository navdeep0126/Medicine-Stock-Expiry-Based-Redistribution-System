(async () => {
  const v = $('#view');
  const PS = 8;
  let B = [], F = [], M = [], U = null, pg = 1;
  const S = { q: '', fac: '', stock: '', exp: '', sort: 'asc' };

  v.innerHTML = `
    <div class="card toolbar">
      <label class="f grow"><span>Search</span><input id="q" type="search" placeholder="Medicine name, medicine ID or batch ID"></label>
      <label class="f"><span>Facility</span><select id="ff"><option value="">All facilities</option></select></label>
      <label class="f"><span>Stock status</span><select id="fs"><option value="">All</option><option>Available</option><option>Out of Stock</option><option>Expired</option></select></label>
      <label class="f"><span>Expiry status</span><select id="fe"><option value="">All</option><option>Valid</option><option>Near Expiry</option><option>Expired</option></select></label>
      <label class="f"><span>Sort by expiry date</span><select id="so"><option value="asc">Earliest first</option><option value="desc">Latest first</option></select></label>
      <button class="btn ghost" id="clr">Clear all filters</button>
      <button class="btn" id="add">+ Add medicine batch</button>
    </div>
    <div class="card"><div id="tbl">${loader()}</div><div id="pager" class="pager"></div></div>`;

  async function load() {
    try {
      [B, F, M, U] = await Promise.all([
        API.getBatches(), API.getFacilities(), API.getMedicines(), API.getCurrentUser()
      ]);
      if (!$('#ff').options.length || $('#ff').options.length === 1) {
        F.forEach(f => $('#ff').add(new Option(f.name, f.id)));
      }
      draw();
    } catch (error) {
      $('#tbl').innerHTML = empty('Could not load inventory', esc(error.message || 'Check the backend and database connection.'));
    }
  }

  const list = () => B.filter(b =>
    (!S.fac || b.facilityId === S.fac) &&
    (!S.stock || b.stock === S.stock) &&
    (!S.exp || expiryStatus(b.expiry) === S.exp) &&
    (!S.q || [b.batchId, b.medicineId, b.medicineName].some(x => String(x ?? '').toLowerCase().includes(S.q.toLowerCase())))
  ).sort((a, b) => S.sort === 'asc' ? a.expiry.localeCompare(b.expiry) : b.expiry.localeCompare(a.expiry));

  function draw() {
    const L = list();
    const rows = L.slice((pg - 1) * PS, pg * PS);
    $('#tbl').innerHTML = !B.length
      ? empty('No medicine batches yet', 'Use “Add medicine batch” to record the first medicine batch.')
      : !L.length
        ? empty('No batches match', 'Try a different search or clear all filters.')
        : table(
          ['Batch ID', 'Medicine ID', 'Medicine', 'Facility ID', 'Facility', 'Qty', 'Expiry date', 'Expiry status', 'Stock status', 'Actions'],
          rows.map(b => `<tr class="${isSource(b) ? '' : 'dim'}">
            <td><b>${esc(b.batchId)}</b></td>
            <td>${esc(b.medicineId)}</td>
            <td>${esc(b.medicineName)}</td>
            <td>${esc(b.facilityId)}</td>
            <td>${esc(b.facilityName)}</td>
            <td>${num(b.qty)}</td>
            <td>${fmt(b.expiry)}<small>${daysText(b.expiry)}</small></td>
            <td>${badge(expiryStatus(b.expiry))}</td>
            <td>${badge(b.stock)}${isSource(b) ? '' : '<small>Not an eligible source</small>'}</td>
            <td><div class="acts">
              <button class="btn ghost sm" data-a="v" data-id="${esc(b.batchId)}">View Details</button>
              ${(!U || U.role === 'admin' || b.facilityId === U.facilityId)
                ? `<button class="btn ghost sm" data-a="e" data-id="${esc(b.batchId)}">Edit Batch</button><button class="btn ghost sm" data-a="d" data-id="${esc(b.batchId)}">Delete Batch</button>`
                : '<small>Managed by source hospital</small>'}
            </div></td>
          </tr>`)
        );
    pager('#pager', L.length, pg, PS, p => { pg = p; draw(); });
    $$('[data-a]', $('#tbl')).forEach(x => x.onclick = () => act(x.dataset.a, B.find(b => b.batchId === x.dataset.id)));
  }

  function act(action, batch) {
    if (!batch) return;
    if (action === 'v') {
      modal('Batch ' + esc(batch.batchId), `<dl class="kv">
        <dt>Medicine</dt><dd>${esc(batch.medicineName)} (${esc(batch.medicineId)})</dd>
        <dt>Facility</dt><dd>${esc(batch.facilityName)} (${esc(batch.facilityId)})</dd>
        <dt>Quantity</dt><dd>${num(batch.qty)}</dd>
        <dt>Expiry</dt><dd>${fmt(batch.expiry)} · ${daysText(batch.expiry)}</dd>
        <dt>Expiry status</dt><dd>${badge(expiryStatus(batch.expiry))}</dd>
        <dt>Stock status</dt><dd>${badge(batch.stock)}</dd>
        <dt>Redistribution source?</dt><dd>${isSource(batch) ? 'Yes, it can be a source' : 'No, it is excluded'}</dd>
      </dl>`, [{ label: 'Close', cls: 'ghost', run: d => d.close() }]);
    }
    if (action === 'e') form(batch);
    if (action === 'd') confirmBox(`Delete batch <b>${esc(batch.batchId)}</b> (${esc(batch.medicineName)})?`, 'Delete batch', async () => {
      try {
        await API.deleteBatch(batch.batchId);
        toast('Batch ' + batch.batchId + ' deleted.');
        await load();
      } catch (error) { toast(error.message || 'Could not delete batch.', 'bad'); }
    });
  }

  function form(batch) {
    const editing = !!batch;
    const x = batch || { batchId: '', medicineId: '', facilityId: '', qty: '', expiry: '' };
    const medOptions = M.map(m => `<option value="${esc(m.id)}" ${m.id === x.medicineId ? 'selected' : ''}>${esc(m.id)} · ${esc(m.name)}</option>`).join('');
    const d = modal(editing ? 'Edit batch ' + esc(batch.batchId) : 'Add medicine batch', `
      <div class="fg">
        <label class="f">Batch ID <span class="req">*</span>
          <input id="a1" value="${esc(x.batchId)}" ${editing ? 'readonly' : ''}>
          <span class="err" id="e1"></span>
        </label>
        <label class="f">Medicine <span class="req">*</span>
          <select id="a2">
            <option value="">Select existing medicine</option>
            ${medOptions}
            <option value="__new__">+ Add a new medicine</option>
          </select>
          <span class="err" id="e2"></span>
        </label>
        <div id="new-med-fields" class="fg" style="display:none;grid-column:1/-1">
          <label class="f">New medicine ID <span class="req">*</span>
            <input id="a7" maxlength="32" placeholder="For example, M002">
            <span class="err" id="e7"></span>
          </label>
          <label class="f">New medicine name <span class="req">*</span>
            <input id="a8" maxlength="180" placeholder="Enter medicine name">
            <span class="err" id="e8"></span>
          </label>
          <p class="muted sm" style="grid-column:1/-1;margin:0">A medicine is added to the catalogue when its first batch is saved successfully.</p>
        </div>
        ${U?.role === 'hospital'
          ? `<label class="f">Your healthcare facility
              <input id="a3" type="hidden" value="${esc(U.facilityId)}">
              <input value="${esc(U.facilityId)} · ${esc(U.facilityName)}" readonly>
              <small class="muted">This stock will belong to your hospital.</small>
            </label>`
          : `<label class="f">Healthcare facility <span class="req">*</span>
              <select id="a3"><option value="">Select facility</option>${F.map(f => `<option value="${esc(f.id)}" ${f.id === x.facilityId ? 'selected' : ''}>${esc(f.id)} · ${esc(f.name)}</option>`).join('')}</select>
              <span class="err" id="e3"></span>
              <small class="muted"><a href="facilities.html">Need to add a new facility? Open Healthcare Facilities.</a></small>
            </label>`}
        <label class="f">Quantity <span class="req">*</span>
          <input id="a4" type="number" min="${editing ? 0 : 1}" step="1" value="${esc(x.qty)}">
          <span class="err" id="e4"></span>
        </label>
        <label class="f">Expiry date <span class="req">*</span>
          <input id="a5" type="date" value="${esc(x.expiry)}">
          <span class="err" id="e5"></span>
        </label>
        <div class="f"><span>Availability</span><div id="status-preview" class="muted">Availability is calculated automatically from quantity and expiry date.</div></div>
      </div>
      <p class="muted sm">Availability is calculated automatically: positive quantity with a future expiry is Available; zero quantity is Out of Stock; past expiry is Expired.</p>
    `, [
      { label: 'Cancel', cls: 'ghost', run: dialog => dialog.close() },
      { label: editing ? 'Save changes' : 'Add batch', run: async dialog => {
        const g = i => $(`#a${i}`, dialog)?.value.trim() ?? '';
        const err = (i, message) => {
          const target = $(`#e${i}`, dialog);
          if (target) target.textContent = message || '';
          return !!message;
        };
        const isNewMedicine = g(2) === '__new__';
        const qty = g(4);
        const medicineId = isNewMedicine ? g(7) : g(2);
        const medicineName = isNewMedicine ? g(8) : (M.find(m => m.id === medicineId)?.name || '');
        const quantityMin = editing ? 0 : 1;
        const invalid = [
          err(1, !g(1) ? 'Batch ID is required.' : !/^[\w-]+$/.test(g(1)) ? 'Use letters, numbers, - or _ only.' : ''),
          err(2, !medicineId ? 'Choose a medicine or add a new one.' : ''),
          isNewMedicine ? err(7, !medicineId ? 'Medicine ID is required.' : !/^[A-Za-z0-9_-]{1,32}$/.test(medicineId) ? 'Use letters, numbers, - or _ only.' : '') : false,
          isNewMedicine ? err(8, !medicineName ? 'Medicine name is required.' : medicineName.length > 180 ? 'Medicine name is too long.' : '') : false,
          err(3, !g(3) ? 'Choose a facility.' : ''),
          err(4, qty === '' ? 'Quantity is required.' : (!Number.isInteger(+qty) || +qty < quantityMin) ? (editing ? 'Enter a whole number, 0 or more.' : 'A new batch must have at least 1 unit.') : ''),
          err(5, !g(5) || !/^\d{4}-\d{2}-\d{2}$/.test(g(5)) || Number.isNaN(Date.parse(g(5))) ? 'Enter a valid expiry date.' : '')
        ].some(Boolean);
        if (invalid) return;

        const record = {
          batchId: g(1), medicineId, medicineName,
          facilityId: g(3), qty: Number(qty), expiry: g(5)
        };
        try {
          await (editing ? API.updateBatch(record) : API.addBatch(record));
          dialog.close();
          toast(`Batch ${record.batchId} ${editing ? 'updated' : 'added'}.`);
          await load();
        } catch (error) {
          err(1, error.message || 'Could not save batch.');
          toast(error.message || 'Could not save batch.', 'bad');
        }
      } }
    ]);

    const medicineSelect = $('#a2', d);
    const newMedFields = $('#new-med-fields', d);
    function showNewMedicineFields() {
      const show = medicineSelect.value === '__new__';
      newMedFields.style.display = show ? 'grid' : 'none';
      if (!show) {
        $('#a7', d).value = '';
        $('#a8', d).value = '';
        $('#e7', d).textContent = '';
        $('#e8', d).textContent = '';
      }
    }
    medicineSelect.addEventListener('change', showNewMedicineFields);

    const updateStatusPreview = () => {
      const quantityText = $('#a4', d).value;
      const expiryText = $('#a5', d).value;
      const target = $('#status-preview', d);
      if (!expiryText || quantityText === '') {
        target.textContent = 'Enter quantity and expiry date to calculate availability.';
        return;
      }
      const now = new Date();
      const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
      target.textContent = expiryText < today ? 'Expired' : Number(quantityText) <= 0 ? 'Out of Stock' : 'Available';
    };
    $('#a4', d).addEventListener('input', updateStatusPreview);
    $('#a5', d).addEventListener('change', updateStatusPreview);
    showNewMedicineFields();
    updateStatusPreview();
  }

  $('#q').oninput = event => { S.q = event.target.value; pg = 1; draw(); };
  [['ff', 'fac'], ['fs', 'stock'], ['fe', 'exp'], ['so', 'sort']].forEach(([id, key]) => {
    $('#' + id).onchange = event => { S[key] = event.target.value; pg = 1; draw(); };
  });
  $('#clr').onclick = () => {
    Object.assign(S, { q: '', fac: '', stock: '', exp: '', sort: 'asc' });
    $('#q').value = '';
    ['ff', 'fs', 'fe'].forEach(id => $('#' + id).value = '');
    $('#so').value = 'asc';
    pg = 1;
    draw();
  };
  $('#add').onclick = () => form();
  await load();
})();
