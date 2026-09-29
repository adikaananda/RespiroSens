"""
Firebase (Realtime Database) device adapter.

Alur data nyata RespiroSens:
    Alat (ESP32) --push--> Firebase RTDB /dataset/<pushId> --poll--> Flask (adapter ini)

Setiap rekaman di Firebase berisi: nama, label, device_id, baseline_gas,
duration_ms, csv (deret waktu 60 dtk). Push-ID Firebase menyimpan waktu
pembuatan rekaman, jadi Flask bisa mencocokkan rekaman dengan sesi skrining
hanya dengan aturan: "rekaman pertama yang dibuat SESUDAH nakes menekan tombol
mulai" -- firmware tidak perlu mengirim capture_token/HMAC.

Parsing/QC/AI-validator memakai modul yang sama dengan folder `files`
(rs_core/), jadi tidak ada logika ganda.
"""

import os
import statistics as st

from app.device_integration.base_adapter import DeviceAdapter
from app.device_integration.rs_core import analysis, firebase, parse

SKEW_MS = int(os.environ.get("FIREBASE_CLOCK_SKEW_MS", "5000"))
SCAN_LIMIT = int(os.environ.get("FIREBASE_SCAN_LIMIT", "15"))

# Kanal yang model demo (app/ml/features.py) butuhkan tetapi TIDAK dikirim alat.
MODEL_ONLY_CHANNELS = [
    "voc_index_bme688", "voc_index_sgp41", "nox_index_sgp41",
    "ammonia_ppm", "o_cymene_rel", "methyloctane_rel",
]


class FirebaseDeviceAdapter(DeviceAdapter):
    name = "firebase_device"

    def acquire_breath_sample(self, session_id: str, **kwargs):
        raise NotImplementedError(
            "FirebaseDeviceAdapter bersifat polling: data diambil lewat "
            "GET /api/screening/sessions/<id> saat status breath_test_pending."
        )

    def health_check(self) -> dict:
        try:
            keys = list(firebase.recent(1))
            ts = firebase.push_ts_ms(keys[0]) if keys else None
            return {"adapter": self.name, "status": "ok", "latest_key": keys[0] if keys else None,
                    "latest_ts_ms": ts}
        except Exception as e:  # noqa: BLE001
            return {"adapter": self.name, "status": "error", "error": f"{type(e).__name__}: {e}"[:200]}


def find_new_record(since_ms, exclude_keys=(), device_id=None):
    """Rekaman Firebase paling awal yang dibuat setelah `since_ms` dan belum dipakai sesi lain."""
    recs = firebase.recent(SCAN_LIMIT)  # sudah terurut naik menurut key (= urut waktu)
    for key, raw in recs.items():
        if key in exclude_keys or not isinstance(raw, dict):
            continue
        try:
            if firebase.push_ts_ms(key) < since_ms - SKEW_MS:
                continue
        except (ValueError, IndexError):
            continue
        if (raw.get("nama") or "").lower().startswith("chamber"):  # rekaman chamber kosong
            continue
        if device_id and raw.get("device_id") and raw["device_id"] != device_id:
            continue
        if not raw.get("csv"):
            continue
        return key, raw
    return None


def _mean(xs):
    return round(sum(xs) / len(xs), 3) if xs else None


def _v(xs):
    return [x for x in xs if x is not None]


def record_to_payloads(key, raw):
    """Rekaman Firebase -> (raw_payload, baseline_payload, device_id, qc) format pipeline RespiroSens."""
    rec = parse.build(key, raw)
    s = rec["series"]
    qc = analysis.qc(rec)

    gas, eco, temp, rh = _v(s["gas"]), _v(s["eco2"]), _v(s["temp"]), _v(s["rh"])
    nh3 = _v(analysis.despike(s["nh3"])[0])
    gas0 = round(st.median(gas[:5]), 2) if gas else None
    baseline_kohm = rec["baseline_gas"] or gas0

    breath, baseline = {}, {}
    if gas and baseline_kohm:
        breath["gas_resistance_bme688_ohm"] = min(gas) * 1000.0      # firmware: kOhm -> pipeline: Ohm
        baseline["gas_resistance_bme688_ohm"] = baseline_kohm * 1000.0
    if eco:
        breath["co2_ppm_scd40"] = max(eco)          # PROXY: eCO2 ENS160, bukan CO2 SCD40
        baseline["co2_ppm_scd40"] = st.median(eco[:5])
    if temp:
        breath["temperature_c_sht40"] = _mean(temp)  # PROXY: suhu BME688
        baseline["temperature_c_sht40"] = st.median(temp[:5])
    if rh:
        breath["humidity_pct_sht40"] = _mean(rh)     # PROXY: RH BME688
        baseline["humidity_pct_sht40"] = st.median(rh[:5])

    feats = analysis.features(rec)
    raw_payload = {
        "channels": breath,
        "duration_sec": (rec["duration_ms"] or 0) / 1000.0,
        "firebase_key": key,
        "firebase_label": rec["label"],          # label lapangan (TBC/Sehat/Blind) -- BUKAN untuk model saat inferensi
        "coverage": {
            "mapped": sorted(breath),
            "missing_for_demo_model": MODEL_ONLY_CHANNELS,
            "proxies": {"co2_ppm_scd40": "ENS160 eCO2", "temperature_c_sht40": "BME688 temp",
                        "humidity_pct_sht40": "BME688 RH"},
        },
        "device_extra": {  # sinyal nyata alat yang belum dipakai model demo
            "nh3_mean_mv": feats.get("nh3_mean_mv"), "tvoc_max_ppb": feats.get("tvoc_max_ppb"),
            "gas_drop_pct": feats.get("gas_drop_pct"), "eco2_max_ppm": feats.get("eco2_max_ppm"),
        },
        "qc_status": qc["status"],
    }
    return raw_payload, {"channels": baseline}, rec["device_id"] or "firebase", qc
