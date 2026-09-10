// Friendly labels for the SHAP feature keys returned by app/ml/features.py
// (FEATURE_NAMES) — used to render the "Dekomposisi Senyawa VOC" bar chart.
const VOC_FEATURE_LABELS = {
  diff_voc_index_bme688: 'Indeks VOC (BME688)',
  diff_gas_resistance_drop_pct: 'Penurunan Resistansi Gas',
  diff_voc_index_sgp41: 'Indeks VOC (SGP41)',
  diff_nox_index_sgp41: 'Indeks NOx (SGP41)',
  diff_ammonia_ppm: 'Amonia (NH3)',
  diff_o_cymene_rel: 'o-Cymene',
  diff_methyloctane_rel: '4-Methyloctane',
  breath_co2_ppm: 'CO2 Napas (SCD40)',
  breath_temperature_c: 'Suhu Napas (SHT40)',
  breath_humidity_pct: 'Kelembapan Napas (SHT40)',
};

// Label + unit for each vitals field — used both for the read-only device
// readout grid and the manual-fallback inputs for whatever the device didn't send.
const VITALS_FIELD_META = {
  heart_rate_bpm: {label:'Detak Jantung', unit:'bpm', icon:'ic-heart'},
  spo2_pct: {label:'SpO2', unit:'%', icon:'ic-drop'},
  body_temp_c: {label:'Suhu Tubuh', unit:'°C', icon:'ic-therm'},
  resp_rate_per_min: {label:'Frekuensi Napas', unit:'x/menit', icon:'ic-wind'},
  fvc_pct: {label:'Kapasitas Paru (FVC)', unit:'%', icon:'ic-lung'},
  fev1_pct: {label:'Kapasitas Paru (FEV1)', unit:'%', icon:'ic-lung'},
};

/* ==========================================================================
   pages/nakes-skrining.js — the 4-step screening wizard.

   Step 3 pulls vitals + the VOC breath reading straight from the RespiroSens
   device (or Simulation Mode standing in for it) via POST .../breath-test —
   see BreathSampleResult.vitals in the backend. Manual text entry is kept
   ONLY as a fallback for whichever individual field the device didn't
   report, never as the default path.
   ========================================================================== */

function renderProgress(){
  const wrap = document.getElementById('screenProgress');
  wrap.innerHTML = '';
  STEP_LABELS.forEach((label, i)=>{
    const n = i+1;
    const state = n < currentStep ? 'done' : (n === currentStep ? 'on' : '');
    const step = document.createElement('div');
    step.className = 'sp-step';
    step.innerHTML = `<div class="sp-circle ${state}">${n < currentStep ? '✓' : n}</div><div class="sp-label ${n===currentStep?'on':''}">${label}</div>`;
    wrap.appendChild(step);
    if(n < STEP_LABELS.length){
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
  if (currentStep === 3) initDeviceModeBadge();
}
function resetSkriningFlow(){
  currentStep = 1;
  flowState = { patientId: null, sessionId: null, lastReading: null };
  document.getElementById('referralStatus').textContent = '';
  setKtpMode('camera');
  showStepPanel();
}

/* ---------------------------- KTP: camera + file capture ---------------------------- */
let ktpCameraStream = null;

function setKtpMode(mode){
  document.getElementById('ktpModeCameraTab').classList.toggle('active', mode === 'camera');
  document.getElementById('ktpModeFileTab').classList.toggle('active', mode === 'file');
  document.getElementById('ktpCameraPanel').classList.toggle('hidden', mode !== 'camera');
  document.getElementById('ktpFilePanel').classList.toggle('hidden', mode !== 'file');
  if (mode !== 'camera') closeKtpCamera();
}

async function openKtpCamera(){
  const statusEl = document.getElementById('ktpScanStatus');
  const video = document.getElementById('ktpCameraVideo');
  try {
    ktpCameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    video.srcObject = ktpCameraStream;
    video.classList.remove('hidden');
    document.getElementById('ktpCapturedPreview').classList.add('hidden');
    document.getElementById('ktpCameraOverlay').classList.remove('hidden');
    document.getElementById('ktpOpenCameraBtn').classList.add('hidden');
    document.getElementById('ktpCaptureBtn').classList.remove('hidden');
    document.getElementById('ktpCloseCameraBtn').classList.remove('hidden');
    document.getElementById('ktpRetakeBtn').classList.add('hidden');
    statusEl.textContent = '';
  } catch (e) {
    statusEl.textContent = 'Tidak bisa mengakses kamera (izin ditolak atau tidak tersedia). Gunakan "Unggah File" sebagai alternatif.';
  }
}

function closeKtpCamera(){
  if (ktpCameraStream) {
    ktpCameraStream.getTracks().forEach(t => t.stop());
    ktpCameraStream = null;
  }
  document.getElementById('ktpOpenCameraBtn').classList.remove('hidden');
  document.getElementById('ktpCaptureBtn').classList.add('hidden');
  document.getElementById('ktpCloseCameraBtn').classList.add('hidden');
}

function captureKtpPhoto(){
  const video = document.getElementById('ktpCameraVideo');
  const canvas = document.getElementById('ktpCameraCanvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);

  const preview = document.getElementById('ktpCapturedPreview');
  preview.src = canvas.toDataURL('image/jpeg', 0.92);
  preview.classList.remove('hidden');
  video.classList.add('hidden');
  document.getElementById('ktpCameraOverlay').classList.add('hidden');
  document.getElementById('ktpCaptureBtn').classList.add('hidden');
  document.getElementById('ktpRetakeBtn').classList.remove('hidden');

  canvas.toBlob(blob => {
    scanKtpBlob(blob, 'ktp-camera.jpg');
  }, 'image/jpeg', 0.92);
}

function retakeKtpPhoto(){
  document.getElementById('ktpCapturedPreview').classList.add('hidden');
  document.getElementById('ktpCameraVideo').classList.remove('hidden');
  document.getElementById('ktpCameraOverlay').classList.remove('hidden');
  document.getElementById('ktpCaptureBtn').classList.remove('hidden');
  document.getElementById('ktpRetakeBtn').classList.add('hidden');
  document.getElementById('ktpScanStatus').textContent = '';
}

function scanKtpFromFile(){
  const fileInput = document.getElementById('ktpFile');
  if (!fileInput.files.length) {
    document.getElementById('ktpScanStatus').textContent = 'Pilih foto KTP terlebih dahulu.';
    return;
  }
  scanKtpBlob(fileInput.files[0], fileInput.files[0].name);
}

async function scanKtpBlob(blob, filename){
  const statusEl = document.getElementById('ktpScanStatus');
  statusEl.textContent = 'Memindai KTP...';
  const form = new FormData();
  form.append('image', blob, filename || 'ktp.jpg');
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

/* ---------------------------- Step 1 -> 2 -> 3 ---------------------------- */
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
      const ageVal = document.getElementById('pAge').value.trim();
      const heightVal = document.getElementById('pHeight').value.trim();
      const weightVal = document.getElementById('pWeight').value.trim();
      const patient = await apiFetch('/patients/register', {
        method: 'POST',
        body: JSON.stringify({
          full_name: fullName,
          nik: document.getElementById('pName').dataset.nik || null,
          consent_given: true,
          age: ageVal ? parseInt(ageVal, 10) : null,
          sex: document.getElementById('pSex').value || null,
          occupation: document.getElementById('pJob').value,
          height_cm: heightVal ? parseFloat(heightVal) : null,
          weight_kg: weightVal ? parseFloat(weightVal) : null,
          whatsapp_number: document.getElementById('pWhatsapp').value,
        }),
      });
      const session = await apiFetch('/screening/sessions', {
        method: 'POST',
        body: JSON.stringify({ patient_id: patient.id }),
      });
      flowState.patientId = patient.id;
      flowState.sessionId = session.id;
      await apiFetch(`/screening/sessions/${session.id}/risk-factors`, {
        method: 'PATCH',
        body: JSON.stringify({ smoking_history: document.getElementById('pSmoking').value }),
      });
    } catch (e) {
      errEl1.textContent = e.message;
      errEl1.style.display = 'block';
      return;
    }
    closeKtpCamera();
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

/* ---------------------------- Step 3: real-time device capture ---------------------------- */
async function initDeviceModeBadge(){
  const dot = document.getElementById('deviceModeDot');
  const label = document.getElementById('deviceModeLabel');
  try {
    const health = await apiFetch('/health');
    const isSim = health.device_mode !== 'http';
    dot.className = 'device-dot ' + (isSim ? 'sim' : 'live');
    label.textContent = isSim ? 'Simulation Mode (data demo)' : 'Perangkat RespiroSens Terhubung';
  } catch (e) {
    dot.className = 'device-dot';
    label.textContent = 'Status perangkat tidak diketahui';
  }
  // Reset the capture panel each time this step is (re-)entered.
  document.getElementById('deviceCaptureBox').classList.remove('hidden');
  document.getElementById('deviceReadingPanel').classList.add('hidden');
  document.getElementById('computeScoreBtn').classList.add('hidden');
  document.getElementById('startDeviceReadBtn').disabled = false;
  document.getElementById('startDeviceReadBtn').textContent = 'Mulai Pembacaan Perangkat';
  setDeviceIconState('idle');
}

function setDeviceIconState(state){
  const icon = document.getElementById('deviceCaptureIcon');
  icon.className = 'device-capture-icon' + (state !== 'idle' ? ' ' + state : '');
}

async function pollForDeviceReading(errEl, btn){
  const maxAttempts = 90; // 90 * 2s = 3 minutes, matches DEVICE_CAPTURE_TIMEOUT_SEC default
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    await new Promise(r => setTimeout(r, 2000));
    const session = await apiFetch(`/screening/sessions/${flowState.sessionId}`);
    if (session.status === 'breath_test_done') return session;
    if (session.status === 'invalid_sample') {
      errEl.textContent = 'Sampel napas dari perangkat tidak valid. Ulangi pengambilan sampel di alat.';
      errEl.style.display = 'block';
      return null;
    }
    btn.textContent = `Menunggu perangkat... (${attempt + 1}x)`;
  }
  errEl.textContent = 'Waktu tunggu perangkat habis. Pastikan perangkat RespiroSens mengirim data, lalu coba lagi.';
  errEl.style.display = 'block';
  return null;
}

async function startDeviceCapture(){
  const errEl = document.getElementById('step3Error');
  const btn = document.getElementById('startDeviceReadBtn');
  errEl.style.display = 'none';
  btn.disabled = true;
  btn.textContent = 'Membaca sensor VOC...';
  setDeviceIconState('reading');
  document.getElementById('deviceCaptureTitle').textContent = 'Membaca profil napas...';
  document.getElementById('deviceCaptureSub').textContent = 'Sensor sedang mengambil dan menganalisis sampel embusan napas pasien secara real-time.';

  try {
    const breathResult = await apiFetch(`/screening/sessions/${flowState.sessionId}/breath-test`, {
      method: 'POST',
      body: JSON.stringify({}),
    });

    let session;
    if (breathResult.status === 'invalid_sample') {
      setDeviceIconState('error');
      document.getElementById('deviceCaptureTitle').textContent = 'Sampel tidak valid';
      document.getElementById('deviceCaptureSub').textContent = breathResult.message;
      btn.disabled = false;
      btn.textContent = 'Ulangi Pembacaan';
      return;
    }
    if (breathResult.status === 'waiting_for_device') {
      // Real hardware mode: wait for the device to push its reading.
      session = await pollForDeviceReading(errEl, btn);
      if (!session) {
        setDeviceIconState('error');
        btn.disabled = false;
        btn.textContent = 'Ulangi Pembacaan';
        return;
      }
    } else {
      session = breathResult.session;
      flowState.lastReading = breathResult.reading;
    }
    if (!flowState.lastReading) {
      flowState.lastReading = (await apiFetch(`/screening/sessions/${flowState.sessionId}`)).voc_reading || null;
    }

    setDeviceIconState('done');
    document.getElementById('deviceCaptureTitle').textContent = 'Pembacaan selesai';
    document.getElementById('deviceCaptureSub').textContent = 'Profil napas berhasil diambil. Tinjau nilai di bawah, lalu hitung skor risiko.';
    btn.disabled = false;
    btn.textContent = 'Ambil Ulang Sampel';
    renderDeviceVitals(session);
  } catch (e) {
    setDeviceIconState('error');
    errEl.textContent = e.message;
    errEl.style.display = 'block';
    btn.disabled = false;
    btn.textContent = 'Ulangi Pembacaan';
  }
}

function renderDeviceVitals(session){
  const v = session.vitals || {};
  const grid = document.getElementById('vitalReadoutGrid');
  const missing = [];

  grid.innerHTML = Object.entries(VITALS_FIELD_META).map(([field, meta]) => {
    const value = v[field];
    if (value == null) missing.push(field);
    return `<div class="vital-readout-item">
      <div class="vr-label">${meta.label.toUpperCase()}</div>
      <div class="vr-value">${value != null ? (Math.round(value * 10) / 10) : '—'} <span>${meta.unit}</span></div>
      <div class="vr-source ${value != null ? 'device' : 'manual'}">${value != null ? '● Dari Perangkat' : '○ Perlu Input Manual'}</div>
    </div>`;
  }).join('');

  const fallbackWrap = document.getElementById('manualVitalsFallback');
  const fallbackFields = document.getElementById('manualVitalsFields');
  if (missing.length) {
    fallbackWrap.classList.remove('hidden');
    fallbackFields.innerHTML = missing.map(field => {
      const meta = VITALS_FIELD_META[field];
      return `<div class="field"><label>${meta.label} (${meta.unit})</label><input type="text" id="manualVital_${field}" placeholder="cth. ${meta.unit === '%' ? '90' : '80'}"></div>`;
    }).join('');
  } else {
    fallbackWrap.classList.add('hidden');
    fallbackFields.innerHTML = '';
  }

  const reading = flowState.lastReading || {};
  const qualityPill = document.getElementById('sampleQualityPill');
  const isValid = (reading.quality_flag || 'valid') === 'valid';
  qualityPill.textContent = isValid ? 'Sampel Valid' : (reading.quality_flag || 'Tidak diketahui');
  qualityPill.style.color = isValid ? 'var(--green)' : 'var(--red)';
  qualityPill.style.background = isValid ? 'var(--green-100)' : 'var(--red-100)';

  const duration = reading.duration_sec;
  document.getElementById('sampleMetaLine').textContent =
    `ID Perangkat: ${reading.device_id || session.device_id || '—'} · ` +
    `Durasi embusan: ${duration != null ? duration.toFixed ? duration.toFixed(1) : duration : '—'} detik · ` +
    `Sumber: ${session.is_simulated ? 'Simulation Mode (data demo)' : 'Perangkat RespiroSens'}`;

  document.getElementById('deviceReadingPanel').classList.remove('hidden');
  document.getElementById('computeScoreBtn').classList.remove('hidden');
}

async function showResult(){
  const errEl = document.getElementById('step3Error');
  const btn = document.getElementById('computeScoreBtn');
  errEl.style.display = 'none';
  btn.disabled = true;
  btn.textContent = 'Memproses...';

  try {
    // Apply any manual-fallback values for fields the device didn't report.
    const fallbackInputs = document.querySelectorAll('#manualVitalsFields input');
    if (fallbackInputs.length) {
      const manualPatch = {};
      fallbackInputs.forEach(input => {
        const field = input.id.replace('manualVital_', '');
        if (input.value.trim() !== '') manualPatch[field] = input.value.trim();
      });
      if (Object.keys(manualPatch).length) {
        await apiFetch(`/screening/sessions/${flowState.sessionId}/vitals`, {
          method: 'PATCH',
          body: JSON.stringify(manualPatch),
        });
      }
    }

    const session = await apiFetch(`/screening/sessions/${flowState.sessionId}/predict`, { method: 'POST' });
    renderResult(session);
    currentStep = 4;
    showStepPanel();
  } catch (e) {
    errEl.textContent = e.message;
    errEl.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Hitung Skor Risiko (Analisis AI)';
  }
}

/* ---------------------------- Step 4: professional result / validation UI ---------------------------- */
const RISK_RECOMMENDATION = {
  hijau: 'Probabilitas risiko rendah. Rekomendasi: edukasi tanda bahaya TB dan observasi rutin — tidak menyingkirkan kemungkinan TB bila presentasi klinis kuat.',
  kuning: 'Probabilitas risiko sedang. Rekomendasi: rujukan prioritas untuk pemeriksaan konfirmasi (TCM/Xpert MTB-RIF) dalam waktu dekat.',
  merah: 'Probabilitas risiko tinggi. Rekomendasi: rujukan segera untuk pemeriksaan konfirmasi (TCM/Xpert MTB-RIF) — jangan tunda tindak lanjut klinis.',
};

function renderResult(session){
  const prediction = session.prediction;
  const score = prediction.risk_score;
  document.getElementById('riskScoreNum').textContent = Math.round(score);
  document.getElementById('resultTimestamp').textContent = 'Dianalisis ' + formatDateId(session.updated_at) + ' · Model ' + prediction.model_version;
  document.getElementById('resultModelBadge').textContent = prediction.trained_on_demo_data ? 'XGBoost + SHAP (Demo)' : 'XGBoost + SHAP';

  const circumference = 402;
  const offset = circumference * (1 - score / 100);
  const ringColor = riskColor(prediction.risk_category);
  const ring = document.getElementById('riskRingArc');
  ring.setAttribute('stroke-dashoffset', offset.toFixed(0));
  ring.setAttribute('stroke', ringColor);

  const tag = document.getElementById('riskCategoryTag');
  const labels = {hijau:'Risiko Rendah', kuning:'Risiko Sedang — Rujukan Prioritas', merah:'Risiko Tinggi — Rujukan Segera'};
  tag.textContent = labels[prediction.risk_category] || prediction.risk_category;
  tag.className = 'risk-tag ' + riskTagClass(prediction.risk_category);
  tag.style.fontSize = '13px';
  tag.style.padding = '8px 18px';

  document.getElementById('riskRecommendationText').textContent = RISK_RECOMMENDATION[prediction.risk_category] || '';

  // Validation panel: makes the sample provenance and model version explicit
  // — this is what "profesional & tervalidasi" means in practice: showing
  // exactly what the score is (and isn't) based on.
  const reading = flowState.lastReading || {};
  document.getElementById('valSampleSource').textContent = session.is_simulated ? 'Simulation Mode' : 'Perangkat RespiroSens';
  const isValidSample = (reading.quality_flag || 'valid') === 'valid';
  document.getElementById('valQuality').textContent = isValidSample ? 'Valid' : (reading.quality_flag || '—');
  document.getElementById('valQuality').style.color = isValidSample ? 'var(--green)' : 'var(--red)';
  const duration = reading.duration_sec;
  document.getElementById('valDuration').textContent = duration != null ? `${(duration.toFixed ? duration.toFixed(1) : duration)} detik` : '—';
  document.getElementById('valModelVersion').textContent = prediction.model_version || '—';

  // SHAP bar chart — top 5 contributing VOC features, signed and scaled.
  const entries = Object.entries(prediction.shap_values || {})
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 5);
  const maxAbs = Math.max(...entries.map(([, v]) => Math.abs(v)), 0.0001);
  document.getElementById('shapBars').innerHTML = entries.map(([name, val]) => {
    const pct = Math.max(6, Math.round(Math.abs(val) / maxAbs * 100));
    const color = val > 0 ? 'var(--red)' : 'var(--blue-600)';
    const label = VOC_FEATURE_LABELS[name] || name;
    return `<div class="shap-bar-row">
      <div class="sb-label">${label}</div>
      <div class="shap-bar-track"><div class="shap-bar-fill" style="width:${pct}%;background:${color};"></div></div>
      <div class="sb-value">${val > 0 ? '+' : ''}${val.toFixed(3)}</div>
    </div>`;
  }).join('');

  document.getElementById('clinicalNoteBox').innerHTML =
    `Hasil ini adalah skor <b>skrining/triase AI</b> (${session.is_simulated ? 'Simulation Mode — data demo, bukan pasien nyata' : 'dari pembacaan perangkat RespiroSens'}), ` +
    `<b>bukan diagnosis medis</b>. Skor rendah tidak menyingkirkan diagnosis pada presentasi klinis kuat. ` +
    `Setiap skor wajib ditinjau tenaga kesehatan bersama konteks klinis pasien dan ditindaklanjuti dengan pemeriksaan konfirmasi baku (mis. TCM/Xpert MTB-RIF) sebelum keputusan klinis diambil.` +
    (prediction.trained_on_demo_data ? ' <i>Model saat ini dilatih pada data DEMO/SIMULASI — belum tervalidasi klinis.</i>' : '');

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
    // The nakes dashboard's top summary cards should reflect this
    // freshly-completed session next time it's opened.
    activeSessionId = flowState.sessionId;
  } catch (e) {
    statusEl.textContent = 'Gagal menyimpan: ' + e.message;
  } finally {
    btn.disabled = false;
  }
}

