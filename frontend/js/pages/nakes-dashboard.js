/* ==========================================================================
   pages/nakes-dashboard.js
   ----------------------------------------------------------------------
   Renders the whole nakes dashboard from real data:
     1. loadNakesDashboard()     -> "Riwayat Skrining" table (list of sessions)
     2. loadNakesPatientOverview() -> the 5 summary cards above it (ID Pasien,
        Overview Vital, Alur Skrining, Diagnosis Paru, Pesan), for whichever
        session is "active".

   Selecting a row in the table (or searching a patient by name) changes
   `activeSessionId` and re-renders the summary cards — this is what makes
   the dashboard show a *real, chosen* patient instead of a fixed demo one.
   ========================================================================== */
let currentPage = 1;
const ROWS_PER_PAGE = 5;
let lastSessions = []; // cache hasil fetch biar ganti halaman gak perlu fetch ulang

async function loadNakesDashboard(search){
  try {
    const query = search ? `?search=${encodeURIComponent(search)}` : '';
    const sessions = await apiFetch('/screening/sessions' + query);
    const body = document.getElementById('riwayatSkriningBody');
    const pill = document.getElementById('riwayatTotalPill');
    if (!body) return;

    lastSessions = sessions;
    currentPage = 1; // reset ke halaman 1 tiap load ulang (search baru dll)

    if (!sessions.length) {
      body.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--ink-600);">${search ? 'Tidak ada pasien yang cocok.' : 'Belum ada riwayat skrining.'}</td></tr>`;
      pill.textContent = 'Total 0';
      activeSessionId = null;
      renderEmptyOverview(search ? 'Tidak ada pasien yang cocok dengan pencarian.' : 'Belum ada pasien terdaftar — mulai dari "Skrining Baru".');
      renderRiwayatPagination();
      return;
    }

    renderRiwayatRows();
    pill.textContent = `Total = ${sessions.length}`;

    const stillPresent = sessions.some(s => s.id === activeSessionId);
    if (!stillPresent) activeSessionId = sessions[0].id;
    loadNakesPatientOverview(activeSessionId);
  } catch (e) {
    console.error(e);
  }
}

function renderRiwayatRows(){
  const body = document.getElementById('riwayatSkriningBody');
  const start = (currentPage - 1) * ROWS_PER_PAGE;
  const pageData = lastSessions.slice(start, start + ROWS_PER_PAGE);

  body.innerHTML = pageData.map((s, i) => {
    const date = new Date(s.created_at).toLocaleDateString('id-ID');
    const scoreLabel = s.risk_score != null ? Math.round(s.risk_score) : '—';
    const tagClass = s.risk_category ? riskTagClass(s.risk_category) : 'low';
    const tagLabel = s.risk_category ? riskLabel(s.risk_category) : STATUS_LABEL_ID[s.status] || s.status;
    const isActive = s.id === activeSessionId;
    return `<tr data-session-id="${s.id}" data-clickable="1" class="${isActive ? 'row-active' : ''}" onclick="selectSession('${s.id}')">
      <td>${String(start + i + 1).padStart(2,'0')}</td>
      <td>${escapeHtml(s.patient_name || 'Pasien #' + s.patient_id.slice(0,8))}</td>
      <td>${date}</td>
      <td>${scoreLabel}</td>
      <td><span class="risk-tag ${tagClass}">${tagLabel}</span></td>
    </tr>`;
  }).join('');

  renderRiwayatPagination();
}

function renderRiwayatPagination(){
  const table = document.getElementById('riwayatSkriningBody')?.closest('table');
  if (!table) return;
  let wrap = document.getElementById('riwayatPaginationWrap');
  if (!wrap) {
    wrap = document.createElement('div');
    wrap.id = 'riwayatPaginationWrap';
    wrap.style.display = 'flex';
    wrap.style.justifyContent = 'center';
    wrap.style.alignItems = 'center';
    wrap.style.gap = '12px';
    wrap.style.marginTop = '10px';
    table.insertAdjacentElement('afterend', wrap);
  }

  const totalPages = Math.max(1, Math.ceil(lastSessions.length / ROWS_PER_PAGE));

  if (lastSessions.length === 0) {
    wrap.innerHTML = '';
    return;
  }

  wrap.innerHTML = `
    <span class="btn-ghost" style="cursor:${currentPage <= 1 ? 'default' : 'pointer'};opacity:${currentPage <= 1 ? '0.4' : '1'};" onclick="${currentPage <= 1 ? '' : 'goToRiwayatPage(currentPage - 1)'}">Prev</span>
    <span style="font-size:13px;color:var(--ink-600);">Halaman ${currentPage} dari ${totalPages}</span>
    <span class="btn-ghost" style="cursor:${currentPage >= totalPages ? 'default' : 'pointer'};opacity:${currentPage >= totalPages ? '0.4' : '1'};" onclick="${currentPage >= totalPages ? '' : 'goToRiwayatPage(currentPage + 1)'}">Next</span>
  `;
}

function goToRiwayatPage(page){
  currentPage = page;
  renderRiwayatRows();
}

function selectSession(sessionId){
  activeSessionId = sessionId;
  document.querySelectorAll('#riwayatSkriningBody tr[data-session-id]').forEach(tr=>{
    tr.classList.toggle('row-active', tr.dataset.sessionId === sessionId);
  });
  loadNakesPatientOverview(sessionId);
}

async function loadNakesPatientOverview(sessionId){
  if (!sessionId) { renderEmptyOverview('Pilih pasien dari tabel Riwayat Skrining di bawah.'); return; }
  try {
    const session = await apiFetch(`/screening/sessions/${sessionId}`);
    renderPatientCard(session);
    renderVitalsOverview(session);
    renderStepper(session);
    renderDiagnosis(session);
    renderMessageCard(session);
    renderTrendChart(session); // separate fetch: needs this patient's other sessions
  } catch (e) {
    console.error(e);
    renderEmptyOverview('Gagal memuat data pasien.');
  }
}

/* ---------------------------- ID Pasien ---------------------------- */
function renderPatientCard(session){
  const patient = session.patient || {};
  const age = calcAge(patient);
  const smoking = smokingLabel(session.smoking_history);

  document.getElementById('patientIdPill').textContent = '#' + session.id.slice(0,8).toUpperCase();
  document.getElementById('patientPhotoImg').src = avatarForPatient(patient);
  document.getElementById('patientNameEl').textContent = patient.full_name || 'Pasien';
  document.getElementById('patientSubEl').textContent =
    `${age != null ? age + ' Tahun' : 'Usia belum tercatat'}, ${patient.occupation || 'Pekerjaan belum tercatat'} — ${smoking}`;

  const badge = document.getElementById('patientStatusBadge');
  const dot = document.getElementById('patientStatusDot');
  const text = document.getElementById('patientStatusText');
  if (!session.prediction) {
    badge.className = 'status-badge neutral';
    text.textContent = 'Belum Ada Hasil';
  } else if (session.risk_category === 'hijau') {
    badge.className = 'status-badge ok';
    text.textContent = 'Kondisi Baik';
  } else {
    badge.className = 'status-badge watch';
    dot.textContent = '!';
    text.textContent = 'Perlu Pemantauan';
  }

  document.getElementById('vitalHeightVal').innerHTML = patient.height_cm != null ? `${patient.height_cm} <span>cm</span>` : '—';
  document.getElementById('vitalWeightVal').innerHTML = patient.weight_kg != null ? `${patient.weight_kg} <span>kg</span>` : '—';
  document.getElementById('vitalBmiVal').innerHTML = patient.bmi != null ? `${patient.bmi} <span>${bmiCategoryLabel(patient.bmi_category)}</span>` : '—';
}

/* ---------------------------- Overview Vital & chart ---------------------------- */
function renderVitalsOverview(session){
  const v = session.vitals || {};
  document.getElementById('vitalHeartRate').textContent = v.heart_rate_bpm != null ? Math.round(v.heart_rate_bpm) : '—';
  document.getElementById('vitalSpo2').textContent = v.spo2_pct != null ? Math.round(v.spo2_pct) : '—';
  document.getElementById('vitalRespRate').textContent = v.resp_rate_per_min != null ? Math.round(v.resp_rate_per_min) : '—';
  document.getElementById('vitalTemp').textContent = v.body_temp_c != null ? v.body_temp_c.toFixed(1) : '—';
}

async function renderTrendChart(session){
  const svg = document.getElementById('vitalTrendSvg');
  const polyline = document.getElementById('vitalTrendPolyline');
  const emptyEl = document.getElementById('vitalTrendEmpty');
  const labelsEl = document.getElementById('vitalTrendLabels');

  try {
    const history = await apiFetch(`/screening/sessions?patient_id=${session.patient_id}`);
    // API returns newest-first; the chart reads left-to-right chronologically.
    const points = history
      .filter(s => s.vitals && s.vitals.resp_rate_per_min != null)
      .sort((a,b) => new Date(a.created_at) - new Date(b.created_at))
      .slice(-7);

    if (points.length < 2) {
      svg.classList.add('hidden');
      labelsEl.classList.add('hidden');
      emptyEl.classList.remove('hidden');
      return;
    }
    svg.classList.remove('hidden');
    labelsEl.classList.remove('hidden');
    emptyEl.classList.add('hidden');

    const values = points.map(p => p.vitals.resp_rate_per_min);
    const min = Math.min(...values), max = Math.max(...values);
    const range = (max - min) || 1;
    const stepX = 320 / (values.length - 1);
    const coords = values.map((v, i) => {
      const x = i * stepX;
      const y = 112 - ((v - min) / range) * 88; // padded within the 132-tall viewBox
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    polyline.setAttribute('points', coords.join(' '));

    labelsEl.innerHTML = points.map(p =>
      `<span>${new Date(p.created_at).toLocaleDateString('id-ID', {day:'2-digit', month:'2-digit'})}</span>`
    ).join('');
  } catch (e) {
    console.error(e);
    svg.classList.add('hidden');
    labelsEl.classList.add('hidden');
    emptyEl.classList.remove('hidden');
  }
}

/* ---------------------------- Alur Skrining Awal ---------------------------- */
function renderStepper(session){
  const rank = statusRank(session.status);
  const symptomsTrue = Object.values(session.symptoms || {}).filter(Boolean).length;
  const symptomsTotal = Object.keys(session.symptoms || {}).length || 6;
  const v = session.vitals || {};

  const steps = [
    {
      done: true, // a session always implies step 1 (registration) is complete
      desc: `Identitas terisi — ${formatDateId(session.created_at)}`,
    },
    {
      done: rank >= statusRank('symptoms_done'),
      desc: rank >= statusRank('symptoms_done')
        ? `${symptomsTrue} dari ${symptomsTotal} pertanyaan gejala terjawab`
        : 'Belum dimulai',
    },
    {
      done: rank >= statusRank('vitals_done'),
      desc: rank >= statusRank('vitals_done')
        ? `SpO2 ${v.spo2_pct != null ? Math.round(v.spo2_pct)+'%' : '—'}, Suhu ${v.body_temp_c != null ? v.body_temp_c.toFixed(1)+'°C' : '—'}`
        : 'Belum diperiksa',
    },
    {
      done: !!session.prediction,
      desc: session.prediction
        ? `Skor risiko ${Math.round(session.risk_score)} — ${riskLabel(session.risk_category)}`
        : 'Skor risiko belum tersedia',
    },
  ];

  const firstTodoIndex = steps.findIndex(s => !s.done);
  steps.forEach((step, i) => {
    const n = i + 1;
    const icon = document.getElementById('stepIcon'+n);
    const state = step.done ? 'done' : (i === firstTodoIndex ? 'now' : 'todo');
    icon.className = 'step-icon ' + state;
    document.getElementById('stepDesc'+n).textContent = step.desc;
  });
}

/* ---------------------------- Diagnosis Paru ---------------------------- */
// Which vital reading best reflects how "under control" a given symptom is —
// used to size each symptom's progress ring from real numbers.
const SYMPTOM_VITAL_CONFIG = {
  shortness_of_breath: (v)=> normalcyIndex(v.spo2_pct, 95, 100, 15),
  cough_gt_2weeks: (v)=> normalcyIndex(v.resp_rate_per_min, 12, 20, 12),
  chest_pain: (v)=> normalcyIndex(v.heart_rate_bpm, 60, 100, 40),
  fever: (v)=> normalcyIndex(v.body_temp_c, 36.1, 37.2, 3),
  night_sweats: (v)=> normalcyIndex(v.body_temp_c, 36.1, 37.2, 3),
  weight_loss: (v)=> normalcyIndex(v.fvc_pct, 80, 120, 40),
};

function progressRingSvg(pct, color){
  const circumference = 113; // 2*pi*18, matches the r=18 circle markup below
  const offset = pct == null ? circumference : circumference * (1 - pct / 100);
  return `<div class="progress-ring"><svg><circle cx="22" cy="22" r="18" stroke="#E9EDF5" stroke-width="4" fill="none"/>` +
    `<circle cx="22" cy="22" r="18" stroke="${color}" stroke-width="4" fill="none" stroke-dasharray="${circumference}" stroke-dashoffset="${offset.toFixed(0)}" stroke-linecap="round"/></svg>` +
    `<span>${pct != null ? Math.round(pct) + '%' : '—'}</span></div>`;
}

function renderDiagnosis(session){
  const patient = session.patient || {};
  const age = calcAge(patient);
  document.getElementById('diagSub').textContent = `${age != null ? age + ' Tahun' : 'Usia belum tercatat'}, ${smokingLabel(session.smoking_history)}`;

  const container = document.getElementById('diagItemsContainer');
  const flagged = SYMPTOM_PRIORITY.filter(key => session.symptoms && session.symptoms[key]);

  if (!flagged.length) {
    container.innerHTML = `<div class="diag-empty">${session.symptoms ? 'Tidak ada gejala signifikan yang dilaporkan.' : 'Gejala klinis belum diisi untuk pasien ini.'}</div>`;
  } else {
    container.innerHTML = flagged.slice(0, 2).map(key => {
      const meta = SYMPTOM_META[key];
      const pct = SYMPTOM_VITAL_CONFIG[key] ? SYMPTOM_VITAL_CONFIG[key](session.vitals || {}) : null;
      const color = scoreColor(pct);
      return `<div class="diag-item">
        <div class="diag-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><use href="#${meta.icon}"/></svg></div>
        <div class="diag-info">
          <h4>${meta.label}</h4>
          <div class="diag-dates"><div>Dilaporkan<b>${formatDateId(session.created_at)}</b></div><div>Kontrol<b>${formatDateId(addDays(session.created_at, 7))}</b></div></div>
        </div>
        <div>
          ${progressRingSvg(pct, color)}
          <div class="view-btn" onclick="selectSession('${session.id}')">LIHAT</div>
        </div>
      </div>`;
    }).join('');
  }

  // Lung figure + organ list: derived from real SpO2/FVC/FEV1, not fixed numbers.
  const v = session.vitals || {};
  const baseIndex = normalcyIndex(v.spo2_pct, 95, 100, 15);
  const asym = (v.fvc_pct != null && v.fev1_pct != null) ? (v.fvc_pct - v.fev1_pct) / 4 : 0;
  const rightPct = baseIndex != null ? clamp(baseIndex + asym, 0, 100) : null;
  const leftPct = baseIndex != null ? clamp(baseIndex - asym, 0, 100) : null;
  const saluranPct = v.fev1_pct != null ? clamp(v.fev1_pct, 0, 100) : null;
  const fvcPct = v.fvc_pct != null ? clamp(v.fvc_pct, 0, 100) : null;

  const setOrgan = (dotId, pctId, pct) => {
    document.getElementById(dotId).setAttribute('fill', scoreColor(pct));
    const el = document.getElementById(pctId);
    el.textContent = pct != null ? Math.round(pct) + '%' : '—';
    el.style.color = scoreColor(pct);
  };
  setOrgan('lungDotKanan', 'organPctKanan', rightPct);
  setOrgan('lungDotKiri', 'organPctKiri', leftPct);
  setOrgan('lungDotSaluran', 'organPctSaluran', saluranPct);
  setOrgan('lungDotFvc', 'organPctFvc', fvcPct);
}

/* ---------------------------- Pesan (catatan klinis) ---------------------------- */
function renderMessageCard(session){
  const bubble = document.getElementById('msgBubbleText');
  const dateLabel = document.getElementById('msgDateLabel');
  const avatar = document.getElementById('msgAvatarImg');
  const nakesName = (session.nakes_id && currentUser && currentUser.id === session.nakes_id) ? currentUser.full_name : 'Nakes';
  avatar.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(nakesName)}&background=0EA5A0&color=fff&bold=true&size=128`;

  if (session.clinician_note) {
    bubble.textContent = session.clinician_note;
    dateLabel.textContent = formatDateId(session.updated_at);
  } else {
    bubble.textContent = 'Belum ada catatan klinis untuk pasien ini. Catatan akan muncul setelah nakes menyimpan hasil rujukan.';
    dateLabel.textContent = '—';
  }
}

/* ---------------------------- Empty state (no patient selected) ---------------------------- */
function renderEmptyOverview(message){
  document.getElementById('patientIdPill').textContent = '—';
  document.getElementById('patientPhotoImg').src = avatarForPatient({full_name:'Pasien'});
  document.getElementById('patientNameEl').textContent = 'Belum ada pasien';
  document.getElementById('patientSubEl').textContent = message;
  const badge = document.getElementById('patientStatusBadge');
  badge.className = 'status-badge neutral';
  document.getElementById('patientStatusDot').textContent = '•';
  document.getElementById('patientStatusText').textContent = 'Tidak Ada Data';
  ['vitalHeightVal','vitalWeightVal','vitalBmiVal'].forEach(id => document.getElementById(id).textContent = '—');
  ['vitalHeartRate','vitalSpo2','vitalRespRate','vitalTemp'].forEach(id => document.getElementById(id).textContent = '—');

  document.getElementById('vitalTrendSvg').classList.add('hidden');
  document.getElementById('vitalTrendLabels').classList.add('hidden');
  document.getElementById('vitalTrendEmpty').classList.remove('hidden');

  for (let n=1; n<=4; n++){
    document.getElementById('stepIcon'+n).className = 'step-icon todo';
    document.getElementById('stepDesc'+n).textContent = '—';
  }

  document.getElementById('diagSub').textContent = message;
  document.getElementById('diagItemsContainer').innerHTML = `<div class="diag-empty">${message}</div>`;
  ['lungDotKanan','lungDotKiri','lungDotSaluran','lungDotFvc'].forEach(id => document.getElementById(id).setAttribute('fill', '#8A93A6'));
  ['organPctKanan','organPctKiri','organPctSaluran','organPctFvc'].forEach(id => {
    const el = document.getElementById(id);
    el.textContent = '—'; el.style.color = '#8A93A6';
  });

  document.getElementById('msgBubbleText').textContent = message;
  document.getElementById('msgDateLabel').textContent = '—';
}
