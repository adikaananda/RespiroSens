"""
Trains the RespiroSens risk-classification model.

*** By default this trains on data/demo/synthetic_voc_dataset.csv, which is
SYNTHETIC DEMO DATA (see generate_demo_dataset.py). The resulting model and
any metrics printed below describe fit on synthetic data only — they are NOT
clinical accuracy/sensitivity/specificity claims. Do not present them as
research results. ***

To train on a real, ethics-cleared clinical dataset once available, point
DATASET_PATH at that CSV (same column schema as FEATURE_NAMES +
label_tb_suspect_demo) and set DEMO_DATA=false — the script will then label
the saved metadata accordingly instead of tagging it as demo.

Run: python -m app.ml.train
"""

import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.ml.features import FEATURE_NAMES  # noqa: E402

HERE = os.path.dirname(__file__)
DATASET_PATH = os.environ.get(
    "DATASET_PATH", os.path.join(HERE, "..", "..", "data", "demo", "synthetic_voc_dataset.csv")
)
DEMO_DATA = os.environ.get("DEMO_DATA", "true").lower() == "true"
MODEL_DIR = os.environ.get("MODEL_DIR", os.path.join(HERE, "model_store"))
MODEL_FILE = os.path.join(MODEL_DIR, "xgb_respirosens_demo.json")
METADATA_FILE = os.path.join(MODEL_DIR, "model_metadata.json")


def main():
    if not os.path.exists(DATASET_PATH):
        raise SystemExit(
            f"Dataset not found at {DATASET_PATH}.\n"
            f"Run `python -m app.ml.generate_demo_dataset` first, or set DATASET_PATH "
            f"to a real (ethics-cleared) clinical dataset with the same columns."
        )

    df = pd.read_csv(DATASET_PATH)
    missing = [c for c in FEATURE_NAMES if c not in df.columns]
    if missing:
        raise SystemExit(f"Dataset is missing required feature columns: {missing}")

    X = df[FEATURE_NAMES].values
    y = df["label_tb_suspect_demo"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    mean = X_train.mean(axis=0)
    std = X_train.std(axis=0)
    std[std == 0] = 1.0

    X_train_norm = (X_train - mean) / std
    X_test_norm = (X_test - mean) / std

    # Regularized, shallow trees — appropriate for a small tabular dataset per
    # the proposal's justification for XGBoost over deep learning here.
    model = XGBClassifier(
        n_estimators=150,
        max_depth=3,
        learning_rate=0.08,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.5,
        reg_lambda=1.5,
        eval_metric="logloss",
        early_stopping_rounds=15,
        random_state=42,
    )
    model.fit(
        X_train_norm, y_train,
        eval_set=[(X_test_norm, y_test)],
        verbose=False,
    )

    y_pred = model.predict(X_test_norm)
    y_proba = model.predict_proba(X_test_norm)[:, 1]

    metrics = {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        "recall_sensitivity": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, y_proba)), 4),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
    }

    os.makedirs(MODEL_DIR, exist_ok=True)
    model.save_model(MODEL_FILE)

    metadata = {
        "model_version": "demo-v0.1",
        "trained_on_demo_data": DEMO_DATA,
        "dataset_path": os.path.relpath(DATASET_PATH, os.path.join(HERE, "..", "..")),
        "feature_names": FEATURE_NAMES,
        "normalization": {"mean": mean.tolist(), "std": std.tolist()},
        "metrics": metrics,
        "metrics_disclaimer": (
            "Metrics above were computed on SYNTHETIC/DEMO data and describe model "
            "fit to that synthetic data only. They are NOT clinical accuracy, "
            "sensitivity, specificity, or AUC and must not be cited as research "
            "results. Real performance can only be established through the clinical "
            "validation described in the proposal (ethics clearance + UPTD Puskesmas "
            "Kuta Selatan)."
            if DEMO_DATA else
            "Metrics computed on the dataset at dataset_path."
        ),
    }
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f, indent=2)

    print(json.dumps(metrics, indent=2))
    print(f"\nModel saved to {MODEL_FILE}")
    print(f"Metadata saved to {METADATA_FILE}")
    if DEMO_DATA:
        print("\nREMINDER: this model was trained on DEMO/SIMULATION data. Do not deploy "
              "its scores as validated clinical predictions.")


if __name__ == "__main__":
    main()
