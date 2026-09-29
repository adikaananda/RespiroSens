/* ==========================================================================
   auth.js — login screen + session lifecycle.

   pages/login.html is fetched into #loginScreen at runtime (see app.js), so
   the role-tab click handling below uses event delegation on document.body
   instead of querySelectorAll-at-parse-time — the tabs don't exist in the
   DOM yet when this file first runs.
   ========================================================================== */

document.body.addEventListener('click', (e) => {
  const tab = e.target.closest('.role-tab');
  if (!tab) return;
  document.querySelectorAll('.role-tab').forEach(t=>t.classList.remove('active'));
  tab.classList.add('active');
  currentRole = tab.dataset.role;
  const roleLabelBtn = document.getElementById('roleLabelBtn');
  if (roleLabelBtn) roleLabelBtn.textContent = ROLE_META[currentRole].label;
  const creds = DEMO_CREDENTIALS[currentRole];
  const emailEl = document.getElementById('loginEmail');
  const passEl = document.getElementById('loginPassword');
  if (emailEl) emailEl.value = creds.email;
  if (passEl) passEl.value = creds.password;
});

async function loadLoginScreen(){
  document.getElementById('loginScreen').innerHTML = await loadPageFragment('login');
}

async function doLogin(){
  const email = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value;
  const errEl = document.getElementById('loginError');
  errEl.style.display = 'none';

  try {
    const data = await apiFetch('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    authToken = data.token;
    currentUser = data.user;
    localStorage.setItem('respirosens_token', authToken);
    localStorage.setItem('respirosens_user', JSON.stringify(currentUser));
    currentRole = currentUser.role;
  } catch (e) {
    errEl.textContent = e.message;
    errEl.style.display = 'block';
    return;
  }

  enterApp();
}

function enterApp(){
  const meta = ROLE_META[currentRole];
  activeSessionId = null;
  document.getElementById('loginScreen').classList.add('hidden');
  document.getElementById('appShell').classList.remove('hidden');
  document.getElementById('roleBadge').textContent = meta.label;
  document.getElementById('topAvatarImg').src =
    `https://ui-avatars.com/api/?name=${encodeURIComponent(currentUser.full_name || meta.label)}&background=1651C7&color=fff&bold=true&size=128`;
  document.getElementById('topSearchInput').placeholder = meta.search;
  buildSidebar(currentRole);
  goPage(currentRole + '-dashboard');
}

function doLogout(){
  authToken = null;
  currentUser = null;
  activeSessionId = null;
  localStorage.removeItem('respirosens_token');
  localStorage.removeItem('respirosens_user');
  document.getElementById('appShell').classList.add('hidden');
  document.getElementById('loginScreen').classList.remove('hidden');
}
