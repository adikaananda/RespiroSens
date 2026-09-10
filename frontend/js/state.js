/* ==========================================================================
   state.js — every piece of mutable, cross-module state lives here so it's
   obvious what's global. Pages read/write these instead of declaring their
   own module-local copies (which used to cause the top dashboard cards to
   drift out of sync with the table below them).
   ========================================================================== */

let currentRole = 'nakes';
let authToken = localStorage.getItem('respirosens_token') || null;
let currentUser = JSON.parse(localStorage.getItem('respirosens_user') || 'null');

// Nakes dashboard: which screening session's data is currently shown in the
// "ID Pasien / Overview Vital / Alur Skrining / Diagnosis Paru" cards.
// This is what makes those cards dynamic instead of a fixed demo patient —
// see js/pages/nakes-dashboard.js.
let activeSessionId = null;

// Skrining wizard progress (per in-progress registration).
let currentStep = 1;
let flowState = { patientId: null, sessionId: null };

let searchDebounceTimer = null;
