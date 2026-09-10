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
let currentRole = 'nakes';

document.querySelectorAll('.role-tab').forEach(tab=>{
  tab.addEventListener('click', ()=>{
    document.querySelectorAll('.role-tab').forEach(t=>t.classList.remove('active'));
    tab.classList.add('active');
    currentRole = tab.dataset.role;
    document.getElementById('roleLabelBtn').textContent = ROLE_META[currentRole].label;
  });
});

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
}

function doLogin(){
  const meta = ROLE_META[currentRole];
  document.getElementById('loginScreen').classList.add('hidden');
  document.getElementById('appShell').classList.remove('hidden');
  document.getElementById('roleBadge').textContent = meta.label;
  document.getElementById('topAvatarImg').src = meta.photo;
  document.getElementById('searchPlaceholder').textContent = meta.search;
  buildSidebar(currentRole);
  goPage(currentRole + '-dashboard');
}

function doLogout(){
  document.getElementById('appShell').classList.add('hidden');
  document.getElementById('loginScreen').classList.remove('hidden');
}

function toggleModal(show){
  document.getElementById('userModalBg').classList.toggle('hidden', !show);
}

/* Skrining stepper */
let currentStep = 1;
const stepLabels = ['Data Diri','Gejala Klinis','Vital & Napas','Hasil'];
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
function nextStep(){ currentStep = Math.min(currentStep+1, 4); showStepPanel(); }
function showResult(){ currentStep = 4; showStepPanel(); }

/* init */
renderProgress();
showStepPanel();