"""Ekspor dataset Firebase berlabel -> CSV fitur (untuk melatih ulang model dari data alat NYATA).

    python export_firebase_dataset.py            # -> data/firebase_features.csv
Hanya rekaman berlabel TBC/Sehat dan lolos QC (bukan 'fail') yang diekspor.
Catatan: label 'Sehat'/'TBC' di nama rekaman adalah label lapangan (klinis/bakteriologis);
cek kolom dx_basis sebelum dipakai sebagai ground truth.
"""
import csv, os
from dotenv import load_dotenv
load_dotenv()
from app.device_integration.rs_core import analysis, firebase, parse

node = firebase._get(firebase._node()) or {}
rows = []
for key, raw in sorted(node.items()):
    if not isinstance(raw, dict) or not raw.get("csv"):
        continue
    rec = parse.build(key, raw)
    if rec["label"] == "Blind" or (rec["name"] or "").lower().startswith("chamber"):
        continue
    qc = analysis.qc(rec)
    if qc["status"] == "fail":
        continue
    nm = rec["name"].lower()
    rows.append({"id": key, "label": rec["label"], "qc": qc["status"], "device_id": rec["device_id"],
                 "dx_basis": "bakteriologis" if "bakteriologis" in nm else "klinis" if "klinis" in nm else "",
                 **analysis.features(rec)})
os.makedirs("data", exist_ok=True)
cols = sorted({k for r in rows for k in r}, key=lambda c: (c not in ("id", "label", "qc", "device_id", "dx_basis"), c))
with open("data/firebase_features.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
print(f"{len(rows)} rekaman -> data/firebase_features.csv")
