/* ==========================================================================
   RespiroSens frontend logic.
   UI structure/markup preserved from the original prototype; this file now
   calls the real Flask API (same-origin, served by app/__init__.py) instead
   of only rendering static dummy content. A few small id attributes were
   added to index.html so this script has something to read/write — no
   layout or styling was changed.
   ========================================================================== */

const API_BASE = '/api';

const NAV = {
  nakes: [
    {key:'nakes-dashboard', label:'Dashboard', icon:'ic-grid'},
    {key:'nakes-skrining', label:'Skrining', icon:'ic-clip'},
    {key:'nakes-dashboard', label:'Pasien', icon:'ic-users'},
    {key:'nakes-dashboard', label:'Pengaturan', icon:'ic-gear'},
  ],
  dinkes: [
    {key:'dinkes-dashboard', label:'Dashboard', icon:'ic-grid'},
    {key:'dinkes-faskes', label:'Faskes', icon:'ic-building'},
    {key:'dinkes-dashboard', label:'Laporan', icon:'ic-clip'},
    {key:'dinkes-dashboard', label:'Pengaturan', icon:'ic-gear'},
  ],
  admin: [
    {key:'admin-dashboard', label:'Dashboard', icon:'ic-grid'},
    {key:'admin-users', label:'Kelola Pengguna', icon:'ic-users'},
    {key:'admin-dashboard', label:'Faskes', icon:'ic-building'},
    {key:'admin-dashboard', label:'Pengaturan', icon:'ic-gear'},
  ]
};
const ROLE_META = {
  nakes:{ label:'Nakes', initial:'N', search:'Cari pasien', photo:'https://randomuser.me/api/portraits/men/32.jpg' },
  dinkes:{ label:'Dinkes', initial:'D', search:'Cari faskes / wilayah', photo:'https://randomuser.me/api/portraits/women/12.jpg' },
  admin:{ label:'Admin', initial:'A', search:'Cari pengguna', photo:'https://randomuser.me/api/portraits/men/45.jpg' },
};
// Matches the accounts seeded by init_db.py — see README_INSTALL.md.
const DEMO_CREDENTIALS = {
  nakes: {email:'nakes.demo@respirosens.id', password:'nakes123'},
  dinkes: {email:'dinkes.demo@respirosens.id', password:'dinkes123'},
  admin: {email:'admin.demo@respirosens.id', password:'admin123'},
};

let currentRole = 'nakes';
let authToken = localStorage.getItem('respirosens_token') || null;
let currentUser = JSON.parse(localStorage.getItem('respirosens_user') || 'null');

document.querySelectorAll('.role-tab').forEach(tab=>{
  tab.addEventListener('click', ()=>{
    document.querySelectorAll('.role-tab').forEach(t=>t.classList.remove('active'));
    tab.classList.add('active');
    currentRole = tab.dataset.role;
    document.getElementById('roleLabelBtn').textContent = ROLE_META[currentRole].label;
    const creds = DEMO_CREDENTIALS[currentRole];
    document.getElementById('loginEmail').value = creds.email;
    document.getElementById('loginPassword').value = creds.password;
  });
});

/* ---------------------------- API helper ---------------------------- */
async function apiFetch(path, options = {}) {
  const headers = Object.assign({}, options.headers || {});
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  if (authToken) headers['Authorization'] = 'Bearer ' + authToken;

  const resp = await fetch(API_BASE + path, Object.assign({}, options, { headers }));
  if (resp.status === 401) {
    doLogout();
    throw new Error('Sesi berakhir, silakan masuk kembali.');
  }
  let data = null;
  try { data = await resp.json(); } catch (e) { /* no body */ }
  if (!resp.ok) {
    const message = (data && (data.message || data.error)) || `Permintaan gagal (${resp.status})`;
    throw new Error(message);
  }
  return data;
}

/* ---------------------------- Auth / nav ---------------------------- */
function buildSidebar(role){
  const nav = document.getElementById('sbNav');
  nav.innerHTML = '';
  NAV[role].forEach((item, idx)=>{
    const btn = document.createElement('button');
    btn.className = 'sb-item' + (idx===0 ? ' active' : '');
    btn.title = item.label;
    btn.dataset.target = item.key;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><use href="#${item.icon}"/></svg>`;
    btn.addEventListener('click', ()=>{
      nav.querySelectorAll('.sb-item').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      goPage(item.key);
    });
    nav.appendChild(btn);
  });
}

function goPage(key){
  document.querySelectorAll('.page').forEach(p=>p.classList.add('hidden'));
  const target = document.querySelector(`.page[data-page="${key}"]`);
  if(target) target.classList.remove('hidden');

  // Lazily load real data the first time a page is shown / each time it's revisited.
  if (key === 'nakes-dashboard') loadNakesDashboard();
  if (key === 'dinkes-dashboard') { loadDinkesDashboard(); loadTcmWorklist(); }
  if (key === 'dinkes-faskes') loadDinkesFaskes();
  if (key === 'admin-dashboard') loadAdminDashboard();
  if (key === 'admin-users') loadAdminUsers();
  if (key === 'nakes-skrining') resetSkriningFlow();
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

  const meta = ROLE_META[currentRole];
  document.getElementById('loginScreen').classList.add('hidden');
  document.getElementById('appShell').classList.remove('hidden');
  document.getElementById('roleBadge').textContent = meta.label;
  document.getElementById('topAvatarImg').src = meta.photo;
  document.getElementById('topSearchInput').placeholder = meta.search;
  buildSidebar(currentRole);
  goPage(currentRole + '-dashboard');
}

function doLogout(){
  authToken = null;
  currentUser = null;
  localStorage.removeItem('respirosens_token');
  localStorage.removeItem('respirosens_user');
  document.getElementById('appShell').classList.add('hidden');
  document.getElementById('loginScreen').classList.remove('hidden');
}

function toggleModal(show){
  document.getElementById('userModalBg').classList.toggle('hidden', !show);
  if (show) loadFacilityOptions();
}

function toggleFacilityModal(show){
  document.getElementById('facilityModalBg').classList.toggle('hidden', !show);
}

async function submitNewFacility(){
  const errEl = document.getElementById('newFacilityError');
  errEl.style.display = 'none';
  const name = document.getElementById('newFacilityName').value.trim();
  if (!name) {
    errEl.textContent = 'Nama faskes wajib diisi.';
    errEl.style.display = 'block';
    return;
  }
  const lat = document.getElementById('newFacilityLat').value.trim();
  const lng = document.getElementById('newFacilityLng').value.trim();
  try {
    await apiFetch('/facilities', {
      method: 'POST',
      body: JSON.stringify({
        name,
        district: document.getElementById('newFacilityDistrict').value,
        subdistrict: document.getElementById('newFacilitySubdistrict').value,
        latitude: lat ? parseFloat(lat) : null,
        longitude: lng ? parseFloat(lng) : null,
      }),
    });
    toggleFacilityModal(false);
    document.getElementById('newFacilityName').value = '';
    document.getElementById('newFacilityDistrict').value = '';
    document.getElementById('newFacilitySubdistrict').value = '';
    document.getElementById('newFacilityLat').value = '';
    document.getElementById('newFacilityLng').value = '';
    loadDinkesFaskes();
  } catch (e) {
    errEl.textContent = e.message;
    errEl.style.display = 'block';
  }
}

/* ---------------------------- Search (debounced, context-aware) ---------------------------- */
let searchDebounceTimer = null;

function debouncedSearch(kind){
  clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(() => {
    if (kind === 'sessions') loadNakesDashboard(document.getElementById('nakesPatientSearchInput').value.trim());
    if (kind === 'users') loadAdminUsers(document.getElementById('usersSearchInput').value.trim());
    if (kind === 'faskes') loadDinkesFaskes(document.getElementById('faskesSearchInput').value.trim());
  }, 300);
}

function handleTopSearch(){
  const value = document.getElementById('topSearchInput').value.trim();
  if (currentRole === 'nakes') {
    const mirror = document.getElementById('nakesPatientSearchInput');
    if (mirror) mirror.value = value;
    debouncedSearch('sessions');
  } else if (currentRole === 'admin') {
    const mirror = document.getElementById('usersSearchInput');
    if (mirror) mirror.value = value;
    debouncedSearch('users');
  } else if (currentRole === 'dinkes') {
    const mirror = document.getElementById('faskesSearchInput');
    if (mirror) mirror.value = value;
    debouncedSearch('faskes');
  }
}

/* ---------------------------- Nakes: dashboard ---------------------------- */
function riskLabel(category){
  return {hijau:'Rendah', kuning:'Sedang', merah:'Tinggi'}[category] || '—';
}
function riskTagClass(category){
  return {hijau:'low', kuning:'mid', merah:'high'}[category] || 'low';
}
const STATUS_LABEL_ID = {
  registered: 'Terdaftar', symptoms_done: 'Gejala Tercatat', risk_factors_done: 'Faktor Risiko Tercatat',
  vitals_done: 'Vital Tercatat', breath_test_pending: 'Menunggu Perangkat', breath_test_done: 'Napas Selesai',
  processing: 'Memproses', predicted: 'Skor Keluar', clinical_review: 'Ditinjau Nakes',
  referred: 'Dirujuk', completed: 'Selesai', invalid_sample: 'Sampel Tidak Valid',
};

async function loadNakesDashboard(search){
  try {
    const query = search ? `?search=${encodeURIComponent(search)}` : '';
    const sessions = await apiFetch('/screening/sessions' + query);
    const body = document.getElementById('riwayatSkriningBody');
    const pill = document.getElementById('riwayatTotalPill');
    if (!body) return;
    if (!sessions.length) {
      body.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--ink-600);">${search ? 'Tidak ada pasien yang cocok.' : 'Belum ada riwayat skrining.'}</td></tr>`;
      pill.textContent = 'Total — 0';
      return;
    }
    body.innerHTML = sessions.slice(0, 15).map((s, i) => {
      const date = new Date(s.created_at).toLocaleDateString('id-ID');
      const scoreLabel = s.risk_score != null ? Math.round(s.risk_score) : '—';
      const tagClass = s.risk_category ? riskTagClass(s.risk_category) : 'low';
      const tagLabel = s.risk_category ? riskLabel(s.risk_category) : STATUS_LABEL_ID[s.status] || s.status;
      return `<tr>
        <td>${String(i+1).padStart(2,'0')}</td>
        <td>${s.patient_name || 'Pasien #' + s.patient_id.slice(0,8)}</td>
        <td>${date}</td>
        <td>${scoreLabel}</td>
        <td><span class="risk-tag ${tagClass}">${tagLabel}</span></td>
      </tr>`;
    }).join('');
    pill.textContent = `Total — ${sessions.length}`;
  } catch (e) {
    console.error(e);
  }
}

/* ---------------------------- Nakes: skrining flow ---------------------------- */
let currentStep = 1;
const stepLabels = ['Data Diri','Gejala Klinis','Vital & Napas','Hasil'];
let flowState = { patientId: null, sessionId: null };

function renderProgress(){
  const wrap = document.getElementById('screenProgress');
  wrap.innerHTML = '';
  stepLabels.forEach((label, i)=>{
    const n = i+1;
    const state = n < currentStep ? 'done' : (n === currentStep ? 'on' : '');
    const step = document.createElement('div');
    step.className = 'sp-step';
    step.innerHTML = `<div class="sp-circle ${state}">${n < currentStep ? '✓' : n}</div><div class="sp-label ${n===currentStep?'on':''}">${label}</div>`;
    wrap.appendChild(step);
    if(n < stepLabels.length){
      const line = document.createElement('div');
      line.className = 'sp-line';
      wrap.appendChild(line);
    }
  });
}
function showStepPanel(){
  for(let i=1;i<=4;i++){
    document.getElementById('stepPanel'+i).classList.toggle('hidden', i!==currentStep);
  }
  renderProgress();
}
function resetSkriningFlow(){
  currentStep = 1;
  flowState = { patientId: null, sessionId: null };
  document.getElementById('referralStatus').textContent = '';
  showStepPanel();
}

async function scanKtp(){
  const fileInput = document.getElementById('ktpFile');
  const statusEl = document.getElementById('ktpScanStatus');
  if (!fileInput.files.length) {
    statusEl.textContent = 'Pilih foto KTP terlebih dahulu.';
    return;
  }
  statusEl.textContent = 'Memindai...';
  const form = new FormData();
  form.append('image', fileInput.files[0]);
  try {
    const result = await apiFetch('/patients/ocr-scan', { method: 'POST', body: form });
    if (result.ocr_success) {
      if (result.full_name) document.getElementById('pName').value = result.full_name;
      document.getElementById('pName').dataset.nik = result.nik;
      statusEl.textContent = `Berhasil — NIK terdeteksi: ${result.nik}`;
    } else {
      statusEl.textContent = 'Gagal memindai KTP — silakan isi formulir manual di bawah.';
    }
  } catch (e) {
    statusEl.textContent = 'Gagal memindai KTP — silakan isi formulir manual di bawah.';
  }
}

async function nextStep(){
  const errEl1 = document.getElementById('step1Error');
  if (currentStep === 1) {
    const fullName = document.getElementById('pName').value.trim();
    if (!fullName) {
      errEl1.textContent = 'Nama lengkap wajib diisi.';
      errEl1.style.display = 'block';
      return;
    }
    errEl1.style.display = 'none';
    try {
      const patient = await apiFetch('/patients/register', {
        method: 'POST',
        body: JSON.stringify({
          full_name: fullName,
          nik: document.getElementById('pName').dataset.nik || null,
          consent_given: true,
          occupation: document.getElementById('pJob').value,
          whatsapp_number: document.getElementById('pWhatsapp').value,
        }),
      });
      const session = await apiFetch('/screening/sessions', {
        method: 'POST',
        body: JSON.stringify({ patient_id: patient.id }),
      });
      flowState.patientId = patient.id;
      flowState.sessionId = session.id;
    } catch (e) {
      errEl1.textContent = e.message;
      errEl1.style.display = 'block';
      return;
    }
  }

  if (currentStep === 2) {
    await apiFetch(`/screening/sessions/${flowState.sessionId}/symptoms`, {
      method: 'PATCH',
      body: JSON.stringify({
        cough_gt_2weeks: document.getElementById('g1').checked,
        fever: document.getElementById('g2').checked,
        night_sweats: document.getElementById('g3').checked,
        weight_loss: document.getElementById('g4').checked,
        shortness_of_breath: document.getElementById('g5').checked,
        chest_pain: document.getElementById('g6').checked,
      }),
    });
  }

  currentStep = Math.min(currentStep+1, 4);
  showStepPanel();
}

async function pollForDeviceReading(errEl, btn){
  const maxAttempts = 90; // 90 * 2s = 3 minutes, matches DEVICE_CAPTURE_TIMEOUT_SEC default
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    await new Promise(r => setTimeout(r, 2000));
    const session = await apiFetch(`/screening/sessions/${flowState.sessionId}`);
    if (session.status === 'breath_test_done') return true;
    if (session.status === 'invalid_sample') {
      errEl.textContent = 'Sampel napas dari perangkat tidak valid. Ulangi pengambilan sampel di alat.';
      errEl.style.display = 'block';
      return false;
    }
    btn.textContent = `Menunggu perangkat... (${attempt + 1}x)`;
  }
  errEl.textContent = 'Waktu tunggu perangkat habis. Pastikan perangkat RespiroSens mengirim data, lalu coba lagi.';
  errEl.style.display = 'block';
  return false;
}

async function showResult(){
  const errEl = document.getElementById('step3Error');
  const btn = document.getElementById('computeScoreBtn');
  errEl.style.display = 'none';
  btn.disabled = true;
  btn.textContent = 'Memproses...';

  try {
    await apiFetch(`/screening/sessions/${flowState.sessionId}/vitals`, {
      method: 'PATCH',
      body: JSON.stringify({
        heart_rate_bpm: document.getElementById('vHeartRate').value,
        spo2_pct: document.getElementById('vSpo2').value,
        body_temp_c: document.getElementById('vTemp').value,
        resp_rate_per_min: document.getElementById('vRespRate').value,
        fvc_pct: document.getElementById('vFvc').value,
        fev1_pct: document.getElementById('vFev1').value,
      }),
    });

    const breathResult = await apiFetch(`/screening/sessions/${flowState.sessionId}/breath-test`, {
      method: 'POST',
      body: JSON.stringify({}), // real device mode ignores _simulation_risk_hint entirely
    });
    if (breathResult.status === 'invalid_sample') {
      errEl.textContent = breathResult.message;
      errEl.style.display = 'block';
      btn.disabled = false;
      btn.textContent = 'Hitung Skor Risiko';
      return;
    }
    if (breathResult.status === 'waiting_for_device') {
      // Real hardware mode (DEVICE_MODE=http): wait for the device to push
      // its reading to /api/device/ingest, then continue automatically.
      const ok = await pollForDeviceReading(errEl, btn);
      if (!ok) { btn.disabled = false; btn.textContent = 'Hitung Skor Risiko'; return; }
    }

    const session = await apiFetch(`/screening/sessions/${flowState.sessionId}/predict`, { method: 'POST' });
    renderResult(session.prediction);
    currentStep = 4;
    showStepPanel();
  } catch (e) {
    errEl.textContent = e.message;
    errEl.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Hitung Skor Risiko';
  }
}

function renderResult(prediction){
  const score = prediction.risk_score;
  document.getElementById('riskScoreNum').textContent = Math.round(score);

  const circumference = 402;
  const offset = circumference * (1 - score / 100);
  document.getElementById('riskRingArc').setAttribute('stroke-dashoffset', offset.toFixed(0));

  const tag = document.getElementById('riskCategoryTag');
  const labels = {hijau:'Risiko Rendah — Edukasi & Observasi', kuning:'Risiko Sedang — Rujukan Prioritas', merah:'Risiko Tinggi — Perlu Rujukan Segera'};
  tag.textContent = labels[prediction.risk_category] || prediction.risk_category;
  tag.className = 'risk-tag ' + riskTagClass(prediction.risk_category);
  tag.style.fontSize = '13px';
  tag.style.padding = '8px 18px';

  const shapList = document.getElementById('shapList');
  const entries = Object.entries(prediction.shap_values || {}).slice(0, 5);
  shapList.innerHTML = '<b>Faktor VOC paling berpengaruh (SHAP):</b><ul style="margin-top:6px;padding-left:18px;">' +
    entries.map(([name, val]) => {
      const direction = val > 0 ? '↑ menaikkan risiko' : '↓ menurunkan risiko';
      return `<li>${name}: ${val.toFixed(3)} (${direction})</li>`;
    }).join('') + '</ul>' +
    (prediction.trained_on_demo_data ? '<p style="margin-top:6px;font-style:italic;">Model dilatih pada data DEMO/SIMULASI — bukan hasil klinis tervalidasi.</p>' : '');

  const saveBtn = document.getElementById('saveReferralBtn');
  saveBtn.disabled = false;
  saveBtn.textContent = 'Simpan & Buat Rujukan';
}

async function saveAndReferral(){
  const statusEl = document.getElementById('referralStatus');
  const btn = document.getElementById('saveReferralBtn');
  btn.disabled = true;
  statusEl.textContent = 'Menyimpan...';
  try {
    const result = await apiFetch(`/screening/sessions/${flowState.sessionId}/review`, {
      method: 'POST',
      body: JSON.stringify({
        note: 'Ditinjau melalui aplikasi nakes.',
        target_facility_name: 'Puskesmas / RS rujukan terdekat',
        whatsapp_number_for_sending: document.getElementById('pWhatsapp').value,
      }),
    });
    if (result.referral) {
      statusEl.innerHTML = `Rujukan <b>${result.referral.referral_code}</b> dibuat & notifikasi WhatsApp terkirim (lihat log server pada mode demo). ` +
        `<a href="${API_BASE}/referrals/${result.referral.id}/pdf" target="_blank">Unduh PDF</a>`;
    } else {
      statusEl.textContent = 'Hasil disimpan sebagai kategori risiko rendah — notifikasi edukasi terkirim.';
    }
  } catch (e) {
    statusEl.textContent = 'Gagal menyimpan: ' + e.message;
  } finally {
    btn.disabled = false;
  }
}

/* ---------------------------- TCM confirmation worklist (Lapisan 3) ---------------------------- */
async function loadTcmWorklist(){
  try {
    const referrals = await apiFetch('/referrals?tcm_result=pending');
    const list = document.getElementById('tcmPendingList');
    const pill = document.getElementById('tcmPendingPill');
    if (!list) return;
    pill.textContent = `${referrals.length} menunggu`;
    if (!referrals.length) {
      list.innerHTML = '<p style="font-size:13px;color:var(--ink-600);">Tidak ada rujukan yang menunggu konfirmasi TCM.</p>';
      return;
    }
    list.innerHTML = referrals.map(r => `
      <div class="faskes-item">
        <div class="fi-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><use href="#ic-clip"/></svg></div>
        <div class="fi-info">
          <h4>${r.patient_name || 'Pasien'} — ${r.referral_code}</h4>
          <p>${r.facility_name || '-'} · Skor: ${r.risk_score != null ? Math.round(r.risk_score) : '—'} (${r.risk_category ? riskLabel(r.risk_category) : '-'})</p>
        </div>
        <div style="display:flex;gap:8px;">
          <button class="btn-ghost" style="padding:8px 14px;font-size:12.5px;color:#1a9f5c;" onclick="setTcmResult('${r.id}','positive')">TCM Positif</button>
          <button class="btn-ghost" style="padding:8px 14px;font-size:12.5px;" onclick="setTcmResult('${r.id}','negative')">TCM Negatif</button>
        </div>
      </div>
    `).join('');
  } catch (e) {
    console.error(e);
  }
}

async function setTcmResult(referralId, result){
  try {
    await apiFetch(`/referrals/${referralId}/tcm-result`, {
      method: 'PATCH',
      body: JSON.stringify({ tcm_result: result }),
    });
    loadTcmWorklist();
    loadDinkesDashboard();
  } catch (e) {
    alert(e.message);
  }
}

/* ---------------------------- Dinkes dashboards ---------------------------- */
let dinkesMapInstance = null;
let dinkesMarkersLayer = null;

function riskColor(category){
  return {merah:'#EA5A6B', kuning:'#F0A93A', hijau:'#26B978'}[category] || '#8A93A6';
}

function renderDinkesMap(heatmap){
  const mapEl = document.getElementById('dinkesLeafletMap');
  if (!mapEl || typeof L === 'undefined') return;

  if (!dinkesMapInstance) {
    // Centered on Kabupaten Badung, Bali — adjust to your deployment region.
    dinkesMapInstance = L.map('dinkesLeafletMap').setView([-8.55, 115.18], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 18,
    }).addTo(dinkesMapInstance);
    dinkesMarkersLayer = L.layerGroup().addTo(dinkesMapInstance);
  } else {
    dinkesMarkersLayer.clearLayers();
    // Leaflet miscalculates its size if the container was hidden (display:none)
    // when initialized — this fixes the grey-tile issue when re-opening the page.
    setTimeout(() => dinkesMapInstance.invalidateSize(), 100);
  }

  const bounds = [];
  heatmap.forEach(row => {
    const { latitude, longitude } = row.facility;
    if (latitude == null || longitude == null) return;

    const { kuning_count, merah_count, total_screenings } = row.layer1_field_screening;
    const dominant = merah_count > 0 ? 'merah' : (kuning_count > 0 ? 'kuning' : 'hijau');
    const radius = 8 + Math.min(20, total_screenings * 1.5);

    const marker = L.circleMarker([latitude, longitude], {
      radius,
      color: riskColor(dominant),
      fillColor: riskColor(dominant),
      fillOpacity: 0.55,
      weight: 2,
    });
    marker.bindPopup(
      `<b>${row.facility.name}</b><br>` +
      `Total skrining: ${total_screenings}<br>` +
      `Kuning: ${kuning_count} · Merah: ${merah_count}<br>` +
      `TCM positif: ${row.layer3_tcm_confirmation.tcm_positive}`
    );
    marker.addTo(dinkesMarkersLayer);
    bounds.push([latitude, longitude]);
  });

  if (bounds.length) {
    dinkesMapInstance.fitBounds(bounds, { padding: [30, 30], maxZoom: 13 });
  }
}

async function loadDinkesDashboard(){
  try {
    const heatmap = await apiFetch('/dashboard/dinkes/heatmap');
    let totalScreenings = 0, merah = 0, totalReferrals = 0, verified = 0;
    heatmap.forEach(row => {
      totalScreenings += row.layer1_field_screening.total_screenings;
      merah += row.layer1_field_screening.merah_count;
      totalReferrals += row.layer2_clinical_validation.total_referrals;
      verified += row.layer2_clinical_validation.verified_referrals;
    });
    document.getElementById('dinkesTotalSkrining').textContent = totalScreenings;
    document.getElementById('dinkesHighRisk').textContent = merah;
    document.getElementById('dinkesFaskesAktif').textContent = heatmap.length;
    document.getElementById('dinkesReferralRate').textContent = totalReferrals ? Math.round(100*verified/totalReferrals) + '%' : '—';

    renderDinkesMap(heatmap);

    const list = document.getElementById('faskesPerformanceList');
    if (!heatmap.length) {
      list.innerHTML = '<p style="font-size:13px;color:var(--ink-600);">Belum ada data faskes.</p>';
      return;
    }
    const maxScreenings = Math.max(...heatmap.map(r => r.layer1_field_screening.total_screenings), 1);
    list.innerHTML = heatmap.map(row => {
      const pct = Math.round(100 * row.layer1_field_screening.total_screenings / maxScreenings);
      return `<div class="faskes-item">
        <div class="fi-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><use href="#ic-building"/></svg></div>
        <div class="fi-info"><h4>${row.facility.name}</h4><p>${row.facility.subdistrict || row.facility.district || '-'} — Kuning: ${row.layer1_field_screening.kuning_count}, Merah: ${row.layer1_field_screening.merah_count}</p></div>
        <div class="bar-wrap"><div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div><div class="bar-cap"><span>${row.layer1_field_screening.total_screenings} skrining</span><span>TCM+: ${row.layer3_tcm_confirmation.tcm_positive}</span></div></div>
      </div>`;
    }).join('');
  } catch (e) {
    console.error(e);
  }
}

async function loadDinkesFaskes(search){
  try {
    const heatmap = await apiFetch('/dashboard/dinkes/heatmap');
    const filtered = search
      ? heatmap.filter(row => {
          const haystack = `${row.facility.name} ${row.facility.district || ''} ${row.facility.subdistrict || ''}`.toLowerCase();
          return haystack.includes(search.toLowerCase());
        })
      : heatmap;
    const body = document.getElementById('faskesTableBody');
    if (!filtered.length) {
      body.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--ink-600);">${search ? 'Tidak ada faskes yang cocok.' : 'Belum ada data.'}</td></tr>`;
      return;
    }
    body.innerHTML = filtered.map(row => `<tr>
      <td>${row.facility.name}</td>
      <td>${row.facility.subdistrict || '-'}</td>
      <td>${row.layer1_field_screening.total_screenings}</td>
      <td>${row.layer1_field_screening.kuning_count}</td>
      <td>${row.layer1_field_screening.merah_count}</td>
      <td><span class="status-tag ${row.facility.is_active ? 'active' : 'inactive'}">${row.facility.is_active ? 'Aktif' : 'Nonaktif'}</span></td>
    </tr>`).join('');
  } catch (e) {
    console.error(e);
  }
}

/* ---------------------------- Admin ---------------------------- */
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

/* ---------------------------- init ---------------------------- */
renderProgress();
showStepPanel();

// If a token is already stored (page refresh), skip straight back into the app.
if (authToken && currentUser) {
  currentRole = currentUser.role;
  const meta = ROLE_META[currentRole];
  document.getElementById('loginScreen').classList.add('hidden');
  document.getElementById('appShell').classList.remove('hidden');
  document.getElementById('roleBadge').textContent = meta.label;
  document.getElementById('topAvatarImg').src = meta.photo;
  document.getElementById('topSearchInput').placeholder = meta.search;
  buildSidebar(currentRole);
  goPage(currentRole + '-dashboard');
}
