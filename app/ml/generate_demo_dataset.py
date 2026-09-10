"""
Generates data/demo/synthetic_voc_dataset.csv.

*** THIS IS DEMO/SIMULATION DATA. IT IS NOT REAL PATIENT DATA. ***

It exists so the ML pipeline (preprocessing -> XGBoost -> SHAP) can be built,
tested, and demonstrated end-to-end before a real clinical dataset (per the
proposal's planned validation with UPTD Puskesmas Kuta Selatan and ethics
clearance) is available. Any accuracy/sensitivity/specificity numbers
computed from this file describe how well the model fits SYNTHETIC data,
not clinical performance, and must never be reported as research results.

Run: python -m app.ml.generate_demo_dataset
"""

import csv
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.device_integration.simulation_adapter import SimulationAdapter  # noqa: E402
from app.ml.features import FEATURE_NAMES, extract_features  # noqa: E402

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "demo", "synthetic_voc_dataset.csv")
N_PER_CLASS = 400
LABEL_NOISE = 0.08  # fraction of labels randomly flipped so the dataset isn't trivially separable


def main():
    rng = random.Random(42)
    adapter = SimulationAdapter()
    rows = []

    plan = (
        [("low", 0)] * N_PER_CLASS
        + [("moderate", 1)] * (N_PER_CLASS // 2)
        + [("moderate", 0)] * (N_PER_CLASS // 2)
        + [("high", 1)] * N_PER_CLASS
    )
    rng.shuffle(plan)

    for i, (risk_hint, label) in enumerate(plan):
        sample = adapter.acquire_breath_sample(session_id=f"demo-{i}", risk_hint=risk_hint)
        if sample.quality_flag != "valid":
            continue
        features = extract_features(sample.raw_payload, sample.baseline_payload)
        if rng.random() < LABEL_NOISE:
            label = 1 - label
        row = {name: features[name] for name in FEATURE_NAMES}
        row["label_tb_suspect_demo"] = label
        rows.append(row)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FEATURE_NAMES + ["label_tb_suspect_demo"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} DEMO/SIMULATION rows to {OUT_PATH}")
    print("Reminder: this is synthetic data for software testing only, not a clinical dataset.")


if __name__ == "__main__":
    main()
