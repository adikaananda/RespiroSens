"""
Simulation Mode adapter.

Generates DEMO/SIMULATION VOC sensor data that mimics the shape of a
RespiroSens hardware payload (BME688, SGP41, SHT40, SCD40, ammonia) so the
whole backend + ML pipeline + patient flow can be exercised end-to-end
WITHOUT physical hardware.

This data is synthetic. It must never be presented as, or mixed with, real
patient breath samples. Every payload this adapter returns carries
is_simulated=True and source="simulation" so downstream code (and the
database) can always tell the two apart.
"""

import random
import time
import uuid

from app.device_integration.base_adapter import BreathSampleResult, DeviceAdapter

# Reference VOC channels used throughout the pipeline (see ML feature list).
VOC_CHANNELS = [
    "voc_index_bme688",
    "gas_resistance_bme688_ohm",
    "voc_index_sgp41",
    "nox_index_sgp41",
    "co2_ppm_scd40",
    "temperature_c_sht40",
    "humidity_pct_sht40",
    "ammonia_ppm",
    "o_cymene_rel",       # relative intensity, reference biomarker (Mpolokang et al.)
    "methyloctane_rel",   # relative intensity, reference biomarker (Mpolokang et al.)
]


class SimulationAdapter(DeviceAdapter):
    name = "simulation"

    def acquire_breath_sample(self, session_id: str, risk_hint: str = "random", **kwargs) -> BreathSampleResult:
        """
        risk_hint: "low" | "high" | "random" (default) — lets test/demo callers
        bias the synthetic sample toward a low- or high-risk VOC pattern. This
        ONLY affects the simulator; it has no meaning for real device data.
        """
        rng = random.Random(f"{session_id}-{time.time_ns()}")

        if risk_hint == "random":
            risk_hint = rng.choice(["low", "low", "moderate", "high"])
        # Ambient baseline captured by the purge cycle (pompa-katup) before sampling.
        baseline = {
            "voc_index_bme688": rng.uniform(60, 90),
            "gas_resistance_bme688_ohm": rng.uniform(8000, 15000),
            "voc_index_sgp41": rng.uniform(60, 90),
            "nox_index_sgp41": rng.uniform(1, 5),
            "co2_ppm_scd40": rng.uniform(400, 450),
            "temperature_c_sht40": rng.uniform(26, 30),
            "humidity_pct_sht40": rng.uniform(55, 75),
            "ammonia_ppm": rng.uniform(0.05, 0.2),
            "o_cymene_rel": rng.uniform(0.01, 0.05),
            "methyloctane_rel": rng.uniform(0.01, 0.05),
        }

        # Breath (exhaled) signal = baseline + differential shift. A "high" risk
        # hint shifts the two reference biomarkers and ammonia further up, as a
        # loose stand-in for the multivariate VOC pattern described in the
        # literature — this is illustrative only, NOT a validated biomarker model.
        shift = {"low": 0.0, "moderate": 0.5, "high": 1.0}[risk_hint]

        breath = {
            "voc_index_bme688": baseline["voc_index_bme688"] + rng.uniform(10, 40) * (1 + shift),
            "gas_resistance_bme688_ohm": baseline["gas_resistance_bme688_ohm"] * rng.uniform(0.6, 0.9),
            "voc_index_sgp41": baseline["voc_index_sgp41"] + rng.uniform(10, 35) * (1 + shift),
            "nox_index_sgp41": baseline["nox_index_sgp41"] + rng.uniform(0, 3) * (1 + shift),
            "co2_ppm_scd40": rng.uniform(3500, 5500),  # exhaled CO2 as breath-quality indicator
            "temperature_c_sht40": rng.uniform(32, 35),
            "humidity_pct_sht40": rng.uniform(85, 98),
            "ammonia_ppm": baseline["ammonia_ppm"] + rng.uniform(0.05, 0.3) * (1 + shift),
            "o_cymene_rel": baseline["o_cymene_rel"] + rng.uniform(0.02, 0.08) * (1 + 1.5 * shift),
            "methyloctane_rel": baseline["methyloctane_rel"] + rng.uniform(0.02, 0.07) * (1 + 1.5 * shift),
        }

        quality_flag = "valid"
        # Occasionally simulate a failed/too-short breath sample so the
        # sample-quality-control step in the pipeline has something to catch.
        if rng.random() < 0.05:
            quality_flag = "invalid_short_breath"

        # The physical RespiroSens rig (BME688/SGP41/SHT40/SCD40 + ammonia) is
        # a breath-VOC array, not a vitals monitor — so on real hardware
        # (DEVICE_MODE=http) these come from whatever's mapped in
        # device_field_map.json, or stay null and the nakes enters them
        # manually. In Simulation Mode we still generate a plausible reading
        # for every field so the "real-time from device" flow can be
        # exercised end-to-end without a vitals monitor attached.
        vitals_bands = {
            "low": dict(heart_rate=(70, 84), spo2=(96, 99), temp=(36.3, 36.9), resp=(14, 18), fvc=(85, 98), fev1=(85, 97)),
            "moderate": dict(heart_rate=(85, 98), spo2=(92, 96), temp=(37.0, 37.8), resp=(19, 24), fvc=(65, 84), fev1=(60, 82)),
            "high": dict(heart_rate=(96, 112), spo2=(87, 92), temp=(37.6, 38.6), resp=(25, 32), fvc=(45, 66), fev1=(40, 62)),
        }[risk_hint]
        vitals = {
            "heart_rate_bpm": round(rng.uniform(*vitals_bands["heart_rate"]), 1),
            "spo2_pct": round(rng.uniform(*vitals_bands["spo2"]), 1),
            "body_temp_c": round(rng.uniform(*vitals_bands["temp"]), 1),
            "resp_rate_per_min": round(rng.uniform(*vitals_bands["resp"]), 1),
            "fvc_pct": round(rng.uniform(*vitals_bands["fvc"]), 1),
            "fev1_pct": round(rng.uniform(*vitals_bands["fev1"]), 1),
        }

        return BreathSampleResult(
            raw_payload={"channels": breath, "duration_sec": round(rng.uniform(3.0, 8.0), 2)},
            baseline_payload={"channels": baseline},
            device_id=f"SIM-{uuid.uuid4().hex[:8]}",
            source="simulation",
            is_simulated=True,
            quality_flag=quality_flag,
            vitals=vitals,
        )

    def health_check(self) -> dict:
        return {"adapter": self.name, "status": "ok", "note": "DEMO/SIMULATION data source — no physical device."}
