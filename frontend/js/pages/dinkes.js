/* ==========================================================================
   pages/dinkes.js — Dinkes dashboard, faskes table, and the TCM (Layer 3)
   confirmation worklist. Already backed by real data via the heatmap API.
   ========================================================================== */

let dinkesMapInstance = null;
let dinkesMarkersLayer = null;

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
