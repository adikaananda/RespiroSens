<<<<<<< HEAD
# ⚠️ DEMO / SIMULATION DATA ONLY
=======
# DEMO / SIMULATION DATA ONLY
>>>>>>> 7c8f94f08c39755d85d4ff7654fcd79d2d4a503e

Everything under `data/demo/` (and any screening sessions seeded with
`init_db.py --with-demo-sessions`) is **synthetically generated** by
`app/ml/generate_demo_dataset.py` and `app/device_integration/simulation_adapter.py`.

- It is **not** real patient data.
- It is **not** a clinical dataset.
- Any accuracy/sensitivity/specificity/AUC numbers computed from it (see
  `app/ml/model_store/model_metadata.json` after training) describe how well
  the model fits this synthetic data — they are **not** research results and
  must never be cited as clinical performance.

This data exists purely so the full pipeline (device → API → preprocessing →
ML → SHAP → referral → WhatsApp → dashboard) can be built, run, and
demonstrated end-to-end before a real, ethics-cleared clinical dataset is
available (see the proposal's planned validation with UPTD Puskesmas Kuta
Selatan).

Every record carries `is_simulated=True` / `source="simulation"` in the
database so real device data, once connected, can never be confused with it.
