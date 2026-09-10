/* ==========================================================================
   pages/admin.js — Admin dashboard + user management.
   ========================================================================== */

async function loadAdminDashboard(){
  try {
    const summary = await apiFetch('/dashboard/admin/summary');
    document.getElementById('adminTotalUsers').textContent = summary.total_users;
    document.getElementById('adminNakesCount').textContent = summary.users_by_role.nakes || 0;
    document.getElementById('adminDinkesCount').textContent = summary.users_by_role.dinkes || 0;
    document.getElementById('adminAdminCount').textContent = summary.users_by_role.admin || 0;
    document.getElementById('adminTotalScreenings').textContent = `${summary.total_screenings} total skrining tercatat`;
    document.getElementById('adminTotalFacilities').textContent = `${summary.total_facilities} faskes terdaftar`;
  } catch (e) {
    console.error(e);
  }
}

async function loadAdminUsers(search){
  try {
    const query = search ? `?search=${encodeURIComponent(search)}` : '';
    const users = await apiFetch('/users' + query);
    const body = document.getElementById('usersTableBody');
    const pill = document.getElementById('usersTotalPill');
    if (!users.length) {
      body.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--ink-600);">${search ? 'Tidak ada pengguna yang cocok.' : 'Belum ada pengguna.'}</td></tr>`;
      pill.textContent = 'Total — 0';
      return;
    }
    body.innerHTML = users.map(u => `<tr>
      <td><div class="table-name">${u.full_name}</div></td>
      <td><span class="risk-tag ${riskTagClass({nakes:'hijau',dinkes:'kuning',admin:'merah'}[u.role])}">${u.role}</span></td>
      <td>${u.facility ? u.facility.name : '-'}</td>
      <td><span class="status-tag ${u.is_active ? 'active' : 'inactive'}">${u.is_active ? 'Aktif' : 'Nonaktif'}</span></td>
      <td><button class="icon-btn" onclick="deactivateUser('${u.id}')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><use href="#ic-trash"/></svg></button></td>
    </tr>`).join('');
    pill.textContent = `Total — ${users.length}`;
  } catch (e) {
    console.error(e);
  }
}

async function loadFacilityOptions(){
  try {
    const facilities = await apiFetch('/facilities');
    const select = document.getElementById('newUserFacility');
    select.innerHTML = '<option value="">— Tidak ada —</option>' +
      facilities.map(f => `<option value="${f.id}">${f.name}</option>`).join('');
  } catch (e) {
    console.error(e);
  }
}

function toggleModal(show){
  document.getElementById('userModalBg').classList.toggle('hidden', !show);
  if (show) loadFacilityOptions();
}

async function submitNewUser(){
  const errEl = document.getElementById('newUserError');
  errEl.style.display = 'none';
  try {
    await apiFetch('/users', {
      method: 'POST',
      body: JSON.stringify({
        full_name: document.getElementById('newUserName').value,
        email: document.getElementById('newUserEmail').value,
        role: document.getElementById('newUserRole').value,
        facility_id: document.getElementById('newUserFacility').value || null,
        password: document.getElementById('newUserPassword').value,
      }),
    });
    toggleModal(false);
    loadAdminUsers();
  } catch (e) {
    errEl.textContent = e.message;
    errEl.style.display = 'block';
  }
}

async function deactivateUser(userId){
  if (!confirm('Nonaktifkan pengguna ini?')) return;
  try {
    await apiFetch(`/users/${userId}`, { method: 'DELETE' });
    loadAdminUsers();
  } catch (e) {
    alert(e.message);
  }
}
