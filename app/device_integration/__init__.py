from flask import current_app

from app.device_integration.simulation_adapter import SimulationAdapter
from app.device_integration.http_adapter import HttpDeviceAdapter
<<<<<<< HEAD
from app.device_integration.firebase_adapter import FirebaseDeviceAdapter
=======
>>>>>>> 7c8f94f08c39755d85d4ff7654fcd79d2d4a503e


def get_device_adapter():
    mode = current_app.config.get("DEVICE_MODE", "simulation")
    if mode == "simulation":
        return SimulationAdapter()
    if mode == "http":
        return HttpDeviceAdapter()
<<<<<<< HEAD
    if mode == "firebase":
        return FirebaseDeviceAdapter()
=======
>>>>>>> 7c8f94f08c39755d85d4ff7654fcd79d2d4a503e
    raise ValueError(f"Unknown DEVICE_MODE: {mode}")
