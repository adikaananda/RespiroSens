from flask import current_app

from app.device_integration.simulation_adapter import SimulationAdapter
from app.device_integration.http_adapter import HttpDeviceAdapter


def get_device_adapter():
    mode = current_app.config.get("DEVICE_MODE", "simulation")
    if mode == "simulation":
        return SimulationAdapter()
    if mode == "http":
        return HttpDeviceAdapter()
    raise ValueError(f"Unknown DEVICE_MODE: {mode}")
