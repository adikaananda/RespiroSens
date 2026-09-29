/* ==========================================================================
   utils.js — small pure functions (no DOM, no fetch). Formatting, labels,
   and the handful of "derive a display value from real vitals" formulas
   used by the nakes dashboard patient card.
   ========================================================================== */

function riskLabel(category){
  return {hijau:'Rendah', kuning:'Sedang', merah:'Tinggi'}[category] || '—';
}
function riskTagClass(category){
  return {hijau:'low', kuning:'mid', merah:'high'}[category] || 'low';
}
function riskColor(category){
  return {merah:'#EA5A6B', kuning:'#F0A93A', hijau:'#26B978'}[category] || '#8A93A6';
}

function clamp(value, min, max){
  return Math.max(min, Math.min(max, value));
}

function formatDateId(isoString){
  if (!isoString) return '—';
  return new Date(isoString).toLocaleDateString('id-ID', { day:'2-digit', month:'short', year:'numeric' });
}

function addDays(isoString, days){
  const d = new Date(isoString);
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

/** Deterministic avatar built from the patient's own name/sex (not a fixed
 * stock photo) — changes as soon as a different patient is selected. */
function avatarForPatient(patient){
  const name = encodeURIComponent((patient && patient.full_name) || 'Pasien');
  return `https://ui-avatars.com/api/?name=${name}&background=E8F0FF&color=1651C7&bold=true&size=128`;
}

/** 0-100 "how normal is this vital" index — used to color/size the ring &
 * lung-figure indicators from real vitals instead of a hardcoded percentage.
 * `value` is the reading, `normalMin/normalMax` the healthy band; readings
 * further outside the band score lower. */
function normalcyIndex(value, normalMin, normalMax, spread){
  if (value == null || isNaN(value)) return null;
  if (value >= normalMin && value <= normalMax) return 96;
  const distance = value < normalMin ? (normalMin - value) : (value - normalMax);
  return Math.round(clamp(96 - (distance / spread) * 96, 5, 96));
}

function scoreColor(pct){
  if (pct == null) return '#8A93A6';
  if (pct >= 75) return '#26B978';
  if (pct >= 50) return '#F0A93A';
  return '#EA5A6B';
}

function calcAge(patient){
  if (!patient) return null;
  if (patient.age != null) return patient.age;
  if (patient.date_of_birth) {
    const dob = new Date(patient.date_of_birth);
    const diffMs = Date.now() - dob.getTime();
    return Math.floor(diffMs / (1000 * 60 * 60 * 24 * 365.25));
  }
  return null;
}

function bmiCategoryLabel(category){
  return {kurang:'kurang', normal:'normal', berlebih:'berlebih', obesitas:'obesitas'}[category] || '';
}

function smokingLabel(value){
  return SMOKING_LABEL_ID[value] || 'Belum tercatat';
}

function escapeHtml(str){
  const div = document.createElement('div');
  div.textContent = str == null ? '' : String(str);
  return div.innerHTML;
}
