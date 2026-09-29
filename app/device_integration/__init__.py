from flask import current_app

from app.device_integration.simulation_adapter import SimulationAdapter
from app.device_integration.http_adapter import HttpDeviceAdapter
from app.device_integration.firebase_adapter import FirebaseDeviceAdapter
    raise ValueError(f"Unknown DEVICE_MODE: {mode}")
