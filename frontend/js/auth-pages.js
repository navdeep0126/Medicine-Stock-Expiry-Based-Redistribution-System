(() => {
  const $ = (selector) => document.querySelector(selector);
  const message = (text, type = 'error') => {
    const box = $('#auth-message');
    if (!box) return;
    box.textContent = text;
    box.className = `auth-message show ${type}`;
  };
  const post = async (url, body) => {
    let response;
    try {
      response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(body)
      });
    } catch (_) {
      throw new Error('Cannot reach the backend. Start it with run_web_api.ps1.');
    }
    const raw = await response.text();
    let data = {};
    try { data = raw ? JSON.parse(raw) : {}; }
    catch (_) { data = { error: raw || 'Unexpected server response.' }; }
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
    return data;
  };

  const loginForm = $('#login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const button = loginForm.querySelector('button[type="submit"]');
      button.disabled = true;
      try {
        await post('/api/auth/login', {
          username: $('#username').value.trim(),
          password: $('#password').value
        });
        message('Signed in successfully. Opening your workspace…', 'success');
        window.location.replace('/index.html');
      } catch (error) {
        message(error.message);
        button.disabled = false;
      }
    });
  }

  const registerForm = $('#register-form');
  if (registerForm) {
    registerForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const button = registerForm.querySelector('button[type="submit"]');
      button.disabled = true;
      const body = Object.fromEntries(new FormData(registerForm).entries());
      try {
        const data = await post('/api/auth/register', body);
        message(data.message || 'Hospital registered successfully. Your account is active.', 'success');
        // The registration endpoint creates the facility, activates the account,
        // and starts the signed-in session atomically.
        window.location.replace('/index.html');
      } catch (error) {
        message(error.message);
        button.disabled = false;
      }
    });
  }
})();
