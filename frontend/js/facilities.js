(async () => {
  const v = $('#view');
  let F = [], currentUser = null;

  v.innerHTML = `
    <div class="card toolbar">
      <label class="f grow"><span>Search</span><input id="q" type="search" placeholder="Facility ID or name"></label>
      <button class="btn" id="add-facility" style="display:none">+ Add facility and hospital account</button>
    </div>
    <div class="card"><div id="tbl">${loader()}</div></div>`;

  async function load() {
    try {
      [F, currentUser] = await Promise.all([API.getFacilities(), API.getCurrentUser()]);
      $('#add-facility').style.display = currentUser?.role === 'admin' ? '' : 'none';
      draw();
    } catch (error) {
      $('#tbl').innerHTML = empty('Could not load facilities', esc(error.message || 'Check the backend and database connection.'));
    }
  }

  function draw() {
    const query = $('#q').value.trim().toLowerCase();
    const rows = F.filter(f => !query || `${f.id} ${f.name} ${f.address}`.toLowerCase().includes(query));
    $('#tbl').innerHTML = rows.length
      ? table(
        ['Facility ID', 'Facility name', 'Location', 'Contact', 'Batches', 'Total units', 'Active requests'],
        rows.map(f => `<tr>
          <td><b>${esc(f.id)}</b></td><td>${esc(f.name)}</td><td>${esc(f.address)}</td>
          <td>${esc(f.contact)}</td><td>${num(f.batches)}</td><td>${num(f.units)}</td><td>${num(f.active)}</td>
        </tr>`)
      )
      : empty('No facilities found', 'Check the ID or name and try again.');
  }

  function addFacilityForm() {
    if (currentUser?.role !== 'admin') {
      toast('Only the system administrator can create a facility from this page.', 'bad');
      return;
    }

    const d = modal('Add facility and hospital account', `
      <p class="muted">This creates a new facility and an immediately active hospital login. No approval step is used.</p>
      <div class="fg">
        <label class="f">Hospital / facility name <span class="req">*</span>
          <input id="f1" maxlength="180" autocomplete="organization">
          <span class="err" id="fe1"></span>
        </label>
        <label class="f">Location / address <span class="req">*</span>
          <input id="f2" maxlength="255" autocomplete="street-address">
          <span class="err" id="fe2"></span>
        </label>
        <label class="f">Contact number <span class="req">*</span>
          <input id="f3" maxlength="80" autocomplete="tel">
          <span class="err" id="fe3"></span>
        </label>
        <label class="f">Hospital email <span class="req">*</span>
          <input id="f4" type="email" maxlength="254" autocomplete="email">
          <span class="err" id="fe4"></span>
        </label>
        <label class="f">Login username <span class="req">*</span>
          <input id="f5" minlength="3" maxlength="40" autocomplete="off">
          <span class="err" id="fe5"></span>
        </label>
        <label class="f">Temporary password <span class="req">*</span>
          <input id="f6" type="password" minlength="8" maxlength="128" autocomplete="new-password">
          <span class="err" id="fe6"></span>
        </label>
      </div>
      <p class="muted sm">Share the new login credentials securely with the hospital. The password is stored as a hash, not as plain text.</p>
    `, [
      { label: 'Cancel', cls: 'ghost', run: dialog => dialog.close() },
      { label: 'Create facility', run: async dialog => {
        const g = id => $(`#f${id}`, dialog).value.trim();
        const showError = (id, message) => {
          $(`#fe${id}`, dialog).textContent = message || '';
          return !!message;
        };
        const facilityName = g(1), location = g(2), contact = g(3);
        const email = g(4), username = g(5), password = $(`#f6`, dialog).value;
        const invalid = [
          showError(1, !facilityName ? 'Facility name is required.' : facilityName.length > 180 ? 'Facility name is too long.' : ''),
          showError(2, !location ? 'Location is required.' : location.length > 255 ? 'Location is too long.' : ''),
          showError(3, !contact ? 'Contact number is required.' : contact.length > 80 ? 'Contact number is too long.' : ''),
          showError(4, !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) ? 'Enter a valid email address.' : ''),
          showError(5, !/^[A-Za-z0-9_.-]{3,40}$/.test(username) ? 'Use 3–40 letters, numbers, dot, underscore or hyphen.' : ''),
          showError(6, password.length < 8 || password.length > 128 ? 'Password must contain 8–128 characters.' : '')
        ].some(Boolean);
        if (invalid) return;

        try {
          const result = await API.createFacility({ facilityName, location, contact, email, username, password });
          dialog.close();
          toast(`Created ${result.facilityId} and active account “${username}”.`);
          await load();
        } catch (error) {
          toast(error.message || 'Could not create facility.', 'bad');
          showError(1, error.message || 'Could not create facility.');
        }
      } }
    ]);
  }

  $('#q').oninput = draw;
  $('#add-facility').onclick = addFacilityForm;
  await load();
})();
