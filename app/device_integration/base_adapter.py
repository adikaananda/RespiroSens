"""
Device adapter contract.

Every adapter (simulation, HTTP, MQTT, USB/serial, ...) must expose the same
interface so the rest of the backend never needs to know which transport is
in use. When the real RespiroSens device protocol is supplied, implement a
new adapter class here (or in http_adapter.py / mqtt_adapter.py) that fills
in `acquire_breath_sample`; nothing else in the codebase has to change.
"""

from abc import ABC, abstractmethod


class BreathSampleResult:
    """Normalized result returned by any adapter, regardless of transport."""

    def __init__(self, raw_payload: dict, baseline_payload: dict, device_id: str,
                 source: str, is_simulated: bool, quality_flag: str = "valid",
                 vitals: dict = None):
        self.raw_payload = raw_payload
        self.baseline_payload = baseline_payload
        self.device_id = device_id
        self.source = source
        self.is_simulated = is_simulated
        self.quality_flag = quality_flag
        # Optional: heart_rate_bpm / spo2_pct / body_temp_c / resp_rate_per_min /
        # fvc_pct / fev1_pct, if the physical rig includes a vitals module (or,
        # in Simulation Mode, a synthetic stand-in). None/absent means the
        # device didn't supply that reading — the nakes app falls back to
        # manual entry for whichever fields are missing, it never fabricates
        # a number on the caller's behalf.
        self.vitals = vitals or {}

    def to_dict(self):
        return {
            "raw_payload": self.raw_payload,
            "baseline_payload": self.baseline_payload,
            "device_id": self.device_id,
            "source": self.source,
            "is_simulated": self.is_simulated,
            "quality_flag": self.quality_flag,
            "vitals": self.vitals,
        }


class DeviceAdapter(ABC):
    """Base class every RespiroSens device transport adapter must implement."""

    name = "base"

    @abstractmethod
    def acquire_breath_sample(self, session_id: str, **kwargs) -> BreathSampleResult:
        """Run (or simulate) one purge -> sample -> upload cycle and return a
        BreathSampleResult with raw VOC channel readings."""
        raise NotImplementedError

    def health_check(self) -> dict:
        return {"adapter": self.name, "status": "unknown"}
