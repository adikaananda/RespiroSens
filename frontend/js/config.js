/* ==========================================================================
   config.js — constants only. No logic, no state. Safe to read top-to-bottom
   to see "what roles/pages/labels exist" without wading through behaviour.
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
  nakes:{ label:'Nakes', initial:'N', search:'Cari pasien' },
  dinkes:{ label:'Dinkes', initial:'D', search:'Cari faskes / wilayah' },
  admin:{ label:'Admin', initial:'A', search:'Cari pengguna' },
};

// Matches the accounts seeded by init_db.py — see README_INSTALL.md.
const DEMO_CREDENTIALS = {
  nakes: {email:'nakes.demo@respirosens.id', password:'nakes123'},
  dinkes: {email:'dinkes.demo@respirosens.id', password:'dinkes123'},
  admin: {email:'admin.demo@respirosens.id', password:'admin123'},
};

const STATUS_LABEL_ID = {
  registered: 'Terdaftar', symptoms_done: 'Gejala Tercatat', risk_factors_done: 'Faktor Risiko Tercatat',
  vitals_done: 'Vital Tercatat', breath_test_pending: 'Menunggu Perangkat', breath_test_done: 'Napas Selesai',
  processing: 'Memproses', predicted: 'Skor Keluar', clinical_review: 'Ditinjau Nakes',
  referred: 'Dirujuk', completed: 'Selesai', invalid_sample: 'Sampel Tidak Valid',
};

// Ordered so we can compare "how far" a session has progressed — used to
// drive the "Alur Skrining Awal" stepper on the nakes dashboard from the
// session's real `status` instead of a hardcoded step.
const STATUS_ORDER = [
  'registered', 'symptoms_done', 'risk_factors_done', 'vitals_done',
  'breath_test_pending', 'breath_test_done', 'processing', 'predicted',
  'clinical_review', 'referred', 'completed',
];
function statusRank(status){
  const idx = STATUS_ORDER.indexOf(status);
  return idx === -1 ? 0 : idx;
}

const SMOKING_LABEL_ID = { never: 'Tidak Merokok', former: 'Mantan Perokok', active: 'Perokok Aktif' };

// label + icon for each of the 6 boolean symptom flags collected in the
// skrining wizard — used to render the "Diagnosis Paru" cards from whichever
// symptoms are actually true for the selected patient, instead of always
// showing "Batuk Kronis" / "Sesak Napas".
const SYMPTOM_META = {
  shortness_of_breath: {label:'Sesak Napas', icon:'ic-wind'},
  cough_gt_2weeks: {label:'Batuk Kronis (>2 minggu)', icon:'ic-cough'},
  chest_pain: {label:'Nyeri Dada', icon:'ic-heart'},
  fever: {label:'Demam Hilang Timbul', icon:'ic-therm'},
  night_sweats: {label:'Keringat Malam Berlebih', icon:'ic-drop'},
  weight_loss: {label:'Penurunan Berat Badan', icon:'ic-alert'},
};
// Clinical priority order used to pick which 2 flagged symptoms to feature.
const SYMPTOM_PRIORITY = ['shortness_of_breath','cough_gt_2weeks','chest_pain','fever','night_sweats','weight_loss'];

const STEP_LABELS = ['Data Diri','Gejala Klinis','Vital & Napas','Hasil'];
