/* ==========================================================================
   search.js — debounced search boxes. The top bar search mirrors into
   whichever page-local search box is relevant for the current role, so
   typing in one place always drives the same result everywhere.
   ========================================================================== */

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
