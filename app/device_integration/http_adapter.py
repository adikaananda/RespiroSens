"""
HTTP device adapter — ready to integrate real RespiroSens hardware.

Since a live device is push-based (it uploads a reading whenever it finishes
a purge/sample cycle) rather than pull-based, the flow is a two-step
handshake instead of the single synchronous call Simulation Mode uses:

  1. Nakes app calls POST /screening/sessions/<id>/breath-test.
     In DEVICE_MODE=http this issues a short-lived `device_capture_token`
     and returns immediately with status "waiting_for_device" — it does NOT
     block waiting for hardware.
  2. The device (or a small bridge script sitting between the device's
     native protocol and this API) POSTs the raw reading to
     /api/device/ingest, including that token, once the breath sample is
     ready.
  3. This module verifies the request (per-device token + HMAC-SHA256
     signature), maps the device's raw JSON into RespiroSens' canonical
     channel names using device_field_map.json (see
     device_field_map.example.json — copy it to device_field_map.json and
     edit the "path" values once you know your firmware's real field names;
     no Python code changes needed), then hands the result back to the
     screening route to run through the SAME quality-control / feature
     extraction / ML pipeline Simulation Mode uses.
  4. The nakes app's UI polls GET /screening/sessions/<id> until status
     moves past "breath_test_pending".

TLS is expected to terminate at your reverse proxy (nginx/Caddy), not here.
"""

import hashlib
import hmac
import json
import os

from flask import current_app

from app.device_integration.base_adapter import BreathSampleResult, DeviceAdapter


class DeviceAuthError(Exception):
    pass


def verify_hmac_signature(raw_body: bytes, signature_header: str) -> bool:
    """Verify an HMAC-SHA256 signature the same way the proposal specifies
    for the ESP32 -> Flask ingest path."""
    secret = current_app.config["DEVICE_HMAC_SECRET"].encode("utf-8")
    expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header or "")


class HttpDeviceAdapter(DeviceAdapter):
    name = "http_device"

    def acquire_breath_sample(self, session_id: str, **kwargs) -> BreathSampleResult:
        """Not used — HTTP device data arrives via the push endpoint
        POST /api/device/ingest instead. See module docstring."""
        raise NotImplementedError(
            "HttpDeviceAdapter is push-based. The breath-test route issues a "
            "device_capture_token and waits for POST /api/device/ingest instead "
            "of calling this method synchronously."
        )

    def health_check(self) -> dict:
        map_path = _field_map_path()
        configured = map_path.endswith("device_field_map.json") and os.path.exists(map_path)
        return {
            "adapter": self.name,
            "status": "ok" if configured else "not_configured",
            "note": (
                "Using app/device_integration/device_field_map.json"
                if configured else
                "No device_field_map.json found — copy device_field_map.example.json "
                "to device_field_map.json and edit the field paths for your hardware."
            ),
        }


def _field_map_path() -> str:
    configured = os.environ.get("DEVICE_FIELD_MAP_PATH")
    if configured:
        return configured
    here = os.path.dirname(__file__)
    real = os.path.join(here, "device_field_map.json")
    if os.path.exists(real):
        return real
    return os.path.join(here, "device_field_map.example.json")


def load_field_map() -> dict:
    with open(_field_map_path()) as f:
        return json.load(f)


def _get_by_path(body: dict, dotted_path: str):
    node = body
    for part in dotted_path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _map_channels(body: dict, channel_spec: dict) -> dict:
    result = {}
    for canonical_name, spec in channel_spec.items():
        raw_value = _get_by_path(body, spec["path"])
        if raw_value is None:
            result[canonical_name] = 0.0
            continue
        scale = spec.get("scale", 1.0)
        offset = spec.get("offset", 0.0)
        try:
            result[canonical_name] = float(raw_value) * scale + offset
        except (TypeError, ValueError):
            result[canonical_name] = 0.0
    return result


def parse_payload(body: dict) -> dict:
    """
    Maps a real device payload (arbitrary field names/nesting) into the
    canonical shape the ML pipeline (app.ml.features) expects:

        {"channels": {...10 canonical VOC fields...}, "duration_sec": float}

    for both the breath reading and the baseline, using
    device_field_map.json. This is the ONE place hardware-specific field
    names are referenced — everything downstream (quality control, feature
    extraction, the trained model) is transport-agnostic.

    Also extracts an OPTIONAL "vitals" dict (heart_rate_bpm/spo2_pct/
    body_temp_c/resp_rate_per_min/fvc_pct/fev1_pct) if the field map defines
    a "vitals" section AND the device payload actually has values there —
    fields that resolve to None are simply omitted so the caller can tell
    "the device didn't send this" apart from "the device sent an actual 0".
    """
    field_map = load_field_map()

    duration = _get_by_path(body, field_map["duration_sec_path"])
    try:
        duration = float(duration) if duration is not None else 0.0
    except (TypeError, ValueError):
        duration = 0.0

    breath_channels = _map_channels(body, field_map["breath_channels"])
    baseline_channels = _map_channels(body, field_map["baseline_channels"])

    vitals = {}
    for canonical_name, spec in field_map.get("vitals", {}).items():
        raw_value = _get_by_path(body, spec["path"])
        if raw_value is None:
            continue
        try:
            vitals[canonical_name] = float(raw_value) * spec.get("scale", 1.0) + spec.get("offset", 0.0)
        except (TypeError, ValueError):
            continue

    return {
        "raw_payload": {"channels": breath_channels, "duration_sec": duration},
        "baseline_payload": {"channels": baseline_channels},
        "vitals": vitals,
    }
