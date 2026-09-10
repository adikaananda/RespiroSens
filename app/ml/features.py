"""
Feature engineering used identically at TRAINING time and INFERENCE time.

This is the one place that turns a raw {breath, baseline} VOC payload into
the numeric feature vector the model actually sees. Keeping training and
inference on the exact same function is what the proposal calls out
explicitly ("seluruh preprocessing saat inference harus konsisten dengan
preprocessing saat training") — do not duplicate this logic elsewhere.
"""

# Ordered feature list the model is trained on. Order matters: it must match
# the column order used in train.py and the array fed to the model at
# inference time.
FEATURE_NAMES = [
    "diff_voc_index_bme688",
    "diff_gas_resistance_drop_pct",   # resistance drops as VOC rises -> expressed as % drop
    "diff_voc_index_sgp41",
    "diff_nox_index_sgp41",
    "diff_ammonia_ppm",
    "diff_o_cymene_rel",
    "diff_methyloctane_rel",
    "breath_co2_ppm",
    "breath_temperature_c",
    "breath_humidity_pct",
]

MIN_BREATH_DURATION_SEC = 2.5


def quality_control(raw_payload: dict) -> str:
    """Mirrors proposal step (1): verify sample volume/duration before any
    further processing. Returns a quality_flag string."""
    duration = (raw_payload or {}).get("duration_sec")
    if duration is None or duration < MIN_BREATH_DURATION_SEC:
        return "invalid_short_breath"
    return "valid"


def extract_features(raw_payload: dict, baseline_payload: dict) -> dict:
    """
    Steps (2)-(5) from the proposal's pipeline, simplified for a single-sample
    (non-streaming) reading:
      (2) baseline calibration -> differential signal
      (3) noise reduction / cross-compensation -> not meaningful for a single
          scalar reading; hook is here for when raw device telemetry streams
          are available (see docstring at bottom)
      (4) normalization -> handled separately in pipeline.py using stored
          training mean/std so it can be identical at train and inference time
      (5) feature extraction -> this function
    """
    breath = (raw_payload or {}).get("channels", {})
    baseline = (baseline_payload or {}).get("channels", {})

    def diff(key):
        return float(breath.get(key, 0.0)) - float(baseline.get(key, 0.0))

    gas_r_breath = breath.get("gas_resistance_bme688_ohm")
    gas_r_baseline = baseline.get("gas_resistance_bme688_ohm")
    if gas_r_breath and gas_r_baseline:
        resistance_drop_pct = max(0.0, (gas_r_baseline - gas_r_breath) / gas_r_baseline * 100.0)
    else:
        resistance_drop_pct = 0.0

    features = {
        "diff_voc_index_bme688": diff("voc_index_bme688"),
        "diff_gas_resistance_drop_pct": resistance_drop_pct,
        "diff_voc_index_sgp41": diff("voc_index_sgp41"),
        "diff_nox_index_sgp41": diff("nox_index_sgp41"),
        "diff_ammonia_ppm": diff("ammonia_ppm"),
        "diff_o_cymene_rel": diff("o_cymene_rel"),
        "diff_methyloctane_rel": diff("methyloctane_rel"),
        "breath_co2_ppm": float(breath.get("co2_ppm_scd40", 0.0)),
        "breath_temperature_c": float(breath.get("temperature_c_sht40", 0.0)),
        "breath_humidity_pct": float(breath.get("humidity_pct_sht40", 0.0)),
    }
    return features


def features_to_vector(features: dict) -> list:
    return [float(features.get(name, 0.0)) for name in FEATURE_NAMES]
