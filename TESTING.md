# Testing

## Automated tests

```bash
source venv/bin/activate
python -m app.ml.generate_demo_dataset   # if not already done
python -m app.ml.train                   # if not already done
pytest -v
```

`tests/test_api_smoke.py` covers, against an in-memory SQLite DB:
- health check
- login (success + bad password)
- the full patient flow: register → session → symptoms → vitals →
  Simulation Mode breath-test → predict → clinical review → (referral path
  exercised via a high-risk simulated sample)
- auth rejection (no token) and role rejection (nakes hitting an admin-only route)

If the model hasn't been trained yet, `test_full_screening_flow` skips
itself with a clear message rather than failing.

## Manual QA checklist (via the UI)

1. `python run.py`, open http://localhost:5000
2. **Login** — click each role tab (Nakes/Dinkes/Admin); the demo
   credentials auto-fill; log in as each and confirm the right dashboard loads.
3. **Nakes → Skrining Baru**:
   - Fill "Data Diri Pasien" (name required) → Lanjut
   - Toggle a few gejala checkboxes → Lanjut
   - Adjust vitals, click "Hitung Skor Risiko" — should show a spinner-like
     disabled state, then land on the result screen with a real score, a
     Hijau/Kuning/Merah tag, and a SHAP factor list
   - Click "Simpan & Buat Rujukan" — for Kuning/Merah this should show a
     referral code and a working "Unduh PDF" link; for Hijau it should just
     confirm completion
   - Go back to the Nakes dashboard — the new session should appear in
     "Riwayat Skrining"
4. **Dinkes dashboard** — stat cards and "Kinerja Faskes" should reflect
   real aggregated numbers (not the original static mockup values); "Data
   Faskes" page should list real facility rows.
5. **Admin → Kelola Pengguna** — "Tambah Pengguna" should create a real user
   (try logging in as them afterward); the trash icon should deactivate a user.
6. **Referral QR flow** — open the downloaded referral PDF, note the
   verification URL encoded in the QR (or hit
   `GET /api/referrals/verify/<token>` directly with the token from the API
   response) and confirm it returns the non-identifying triage summary.

## Testing the real device-ingest flow (before physical hardware exists)

This exercises the exact handshake real hardware will use — confirmed
working during development, including on real MySQL.

```bash
# 1. Enable HTTP device mode and copy the field-map config
#    (in .env): DEVICE_MODE=http, DEVICE_HMAC_SECRET=test-secret-123
cp app/device_integration/device_field_map.example.json app/device_integration/device_field_map.json
python run.py   # restart after changing .env

# 2. Sanity-check the field map
curl http://localhost:5000/api/device/status

# 3. Log in, register a patient, create a session (same as any other flow)
TOKEN=$(curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"nakes.demo@respirosens.id","password":"nakes123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
PID=$(curl -s -X POST http://localhost:5000/api/patients/register -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"full_name":"Test Hardware","consent_given":true}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
SID=$(curl -s -X POST http://localhost:5000/api/screening/sessions -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d "{\"patient_id\":\"$PID\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

# 4. Start the breath-test — in http mode this returns a capture token instead
#    of a result (status 202, "waiting_for_device")
CAPTURE_TOKEN=$(curl -s -X POST http://localhost:5000/api/screening/sessions/$SID/breath-test \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['device_capture_token'])")

# 5. Simulate the device pushing a reading (field names must match
#    device_field_map.json — the example maps to breath.bme688_voc_index etc.)
python3 <<EOF
import json, hmac, hashlib, urllib.request
body = {
    "capture_token": "$CAPTURE_TOKEN", "duration_sec": 5.2,
    "breath": {"bme688_voc_index": 145.0, "bme688_gas_resistance": 6200.0,
               "sgp41_voc_index": 138.0, "sgp41_nox_index": 5.5,
               "scd40_co2_ppm": 4800.0, "sht40_temperature_c": 33.5, "sht40_humidity_pct": 92.0,
               "nh3_ppm": 0.35, "voc_panel": {"o_cymene": 0.09, "methyloctane": 0.08}},
    "baseline": {"bme688_voc_index": 75.0, "bme688_gas_resistance": 11000.0,
                 "sgp41_voc_index": 70.0, "sgp41_nox_index": 2.0,
                 "scd40_co2_ppm": 420.0, "sht40_temperature_c": 28.0, "sht40_humidity_pct": 65.0,
                 "nh3_ppm": 0.1, "voc_panel": {"o_cymene": 0.02, "methyloctane": 0.02}},
}
raw = json.dumps(body).encode()
sig = hmac.new(b"test-secret-123", raw, hashlib.sha256).hexdigest()
req = urllib.request.Request("http://localhost:5000/api/device/ingest", data=raw,
    headers={"Content-Type": "application/json", "X-Device-Token": "bench-tester", "X-Signature": sig}, method="POST")
print(urllib.request.urlopen(req).read().decode())
EOF

# 6. Session should now be breath_test_done — predict works exactly as in Simulation Mode
curl -s -X POST http://localhost:5000/api/screening/sessions/$SID/predict -H "Authorization: Bearer $TOKEN"
```

Also verify the security checks:
```bash
# Wrong signature → 401
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:5000/api/device/ingest \
  -H "X-Device-Token: x" -H "X-Signature: wrongsig" -H "Content-Type: application/json" -d '{"capture_token":"x"}'

# Re-using an already-consumed capture_token → 404
```

## Testing WhatsApp in console mode

With `WHATSAPP_ENABLED=false` (the default), run through the Nakes screening
flow above with a Kuning/Merah result and check the server log
(stdout, or wherever you redirect it) — you should see a line like:
```
[WHATSAPP:console-mode] to=<hash> message='Halo Bpk/Ibu ...' attachment=/path/to/rujukan_....pdf
```
This confirms the notification content and referral attachment are correct
without needing real WhatsApp Business API credentials.

## Retraining after changing features

If you modify `app/ml/features.py` (e.g. adding a new VOC channel), you must
regenerate the dataset and retrain — the saved model's feature order and
normalization stats must always match `FEATURE_NAMES` exactly:

```bash
python -m app.ml.generate_demo_dataset
python -m app.ml.train
```
The app caches the loaded model in memory; restart the server (or call
`app.ml.pipeline.reset_cache()` in a shell) to pick up a freshly retrained model.
