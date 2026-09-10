/* ==========================================================================
   nav.js — sidebar + page routing.

   Pages live as separate files under pages/ (see frontend/README.md) instead
   of all being pre-rendered inside index.html. `goPage()` fetches the right
   fragment into #pageContent (caching the HTML text so repeat visits don't
   re-fetch), then calls that page's load function so it always shows fresh
   data.
   ========================================================================== */

const _pageFragmentCache = {};

async function loadPageFragment(key){
  if (!_pageFragmentCache[key]) {
    const resp = await fetch(`pages/${key}.html`);
    if (!resp.ok) throw new Error(`Halaman "${key}" tidak ditemukan (${resp.status}).`);
    _pageFragmentCache[key] = await resp.text();
  }
  return _pageFragmentCache[key];
}

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

async function goPage(key){
  const container = document.getElementById('pageContent');
  try {
    container.innerHTML = await loadPageFragment(key);
  } catch (e) {
    container.innerHTML = `<div class="card"><p style="color:#e05252;">${e.message}</p></div>`;
    return;
  }

  // Lazily load real data now that the fragment's elements exist in the DOM.
  if (key === 'nakes-dashboard') loadNakesDashboard();
  if (key === 'dinkes-dashboard') { loadDinkesDashboard(); loadTcmWorklist(); }
  if (key === 'dinkes-faskes') loadDinkesFaskes();
  if (key === 'admin-dashboard') loadAdminDashboard();
  if (key === 'admin-users') loadAdminUsers();
  if (key === 'nakes-skrining') resetSkriningFlow();
}
