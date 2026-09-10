"""
Inference pipeline used by the /api/screening/*/predict route.

Loads the trained XGBoost model + its saved normalization stats, applies the
SAME feature extraction used in training (app.ml.features), predicts a 0-100
risk score, buckets it into Hijau/Kuning/Merah, and explains the prediction
with SHAP so the clinician-facing UI can show per-VOC contributions.
"""

import json
import os
import threading

import numpy as np
import shap
from xgboost import XGBClassifier

from app.ml.features import FEATURE_NAMES

_lock = threading.Lock()
_state = {"model": None, "explainer": None, "metadata": None}


class ModelNotTrainedError(RuntimeError):
    pass


def _model_paths(app_config):
    model_dir = app_config["MODEL_DIR"]
    return (
        os.path.join(model_dir, app_config["MODEL_FILE"]),
        os.path.join(model_dir, app_config["MODEL_METADATA_FILE"]),
    )


def load_model(app_config):
    """Lazily loads (and caches) the model, its metadata, and a SHAP explainer."""
    with _lock:
        if _state["model"] is not None:
            return _state["model"], _state["explainer"], _state["metadata"]

        model_path, metadata_path = _model_paths(app_config)
        if not (os.path.exists(model_path) and os.path.exists(metadata_path)):
            raise ModelNotTrainedError(
                "No trained model found. Run `python -m app.ml.generate_demo_dataset` "
                "then `python -m app.ml.train` (see README_INSTALL.md)."
            )

        model = XGBClassifier()
        model.load_model(model_path)

        with open(metadata_path) as f:
            metadata = json.load(f)

        explainer = shap.TreeExplainer(model)

        _state.update(model=model, explainer=explainer, metadata=metadata)
        return model, explainer, metadata


def reset_cache():
    """Used by tests / after retraining to force a reload."""
    with _lock:
        _state.update(model=None, explainer=None, metadata=None)


def _normalize(vector, metadata):
    mean = np.array(metadata["normalization"]["mean"])
    std = np.array(metadata["normalization"]["std"])
    return (np.array(vector) - mean) / std


def _score_to_category(score: float) -> str:
    # Thresholds are placeholders pending the Youden-index calibration the
    # proposal calls for once real clinical data is available.
    if score >= 60:
        return "merah"
    if score >= 30:
        return "kuning"
    return "hijau"


def predict(features: dict, app_config) -> dict:
    model, explainer, metadata = load_model(app_config)

    vector = [float(features.get(name, 0.0)) for name in FEATURE_NAMES]
    norm_vector = _normalize(vector, metadata)

    proba = float(model.predict_proba(norm_vector.reshape(1, -1))[0, 1])
    score = round(proba * 100, 1)
    category = _score_to_category(score)

    shap_values = explainer.shap_values(norm_vector.reshape(1, -1))
    if isinstance(shap_values, list):  # older shap API returns a list per class
        shap_values = shap_values[-1]
    shap_row = np.array(shap_values).reshape(-1)

    contributions = {
        name: round(float(val), 4) for name, val in zip(FEATURE_NAMES, shap_row)
    }
    # Sorted by absolute contribution, descending, for a friendlier UI payload.
    contributions_sorted = dict(
        sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)
    )

    return {
        "risk_score": score,
        "risk_category": category,
        "shap_values": contributions_sorted,
        "model_version": metadata.get("model_version"),
        "trained_on_demo_data": metadata.get("trained_on_demo_data", True),
    }
