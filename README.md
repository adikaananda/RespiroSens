RespiroSens

VOC-based screening and triage prototype integrating Flask backend, machine learning, device integration, and healthcare workflows.

Clinical Notice:
RespiroSens produces a risk score, not a diagnosis. Every prediction must be reviewed by a clinician before referral. All datasets and demo accounts are synthetic DEMO/SIMULATION data.

Features

* Flask REST API with authentication and role-based access
* Patient registration and KTP OCR
* VOC preprocessing and feature extraction
* XGBoost risk classification with SHAP explanations
* Simulation Mode and real-device HTTP integration
* WhatsApp notification integration
* E-Surat Rujukan with QR code
* Leaflet/OpenStreetMap dashboard and heatmap
* Nakes, Dinkes, and Admin workflows
* SQLite and MySQL/MariaDB support

Quick Start

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env

python -m app.ml.generate_demo_dataset
python -m app.ml.train
python init_db.py --with-demo-sessions
python run.py

Open:
http://localhost:5000

Windows

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
Copy-Item .env.example .env

python -m app.ml.generate_demo_dataset
python -m app.ml.train
python init_db.py --with-demo-sessions
python run.py

Demo Accounts

Nakes
Email: [nakes.demo@respirosens.id](mailto:nakes.demo@respirosens.id)
Password: nakes123

Dinkes
Email: [dinkes.demo@respirosens.id](mailto:dinkes.demo@respirosens.id)
Password: dinkes123

Admin
Email: [admin.demo@respirosens.id](mailto:admin.demo@respirosens.id)
Password: admin123

Workflow

Patient
↓
VOC Measurement
↓
Preprocessing
↓
XGBoost Risk Classification
↓
SHAP Explanation
↓
Clinician Review
↓
Referral / Follow-up
↓
Dinkes Dashboard

Technology

Backend: Flask / Python
ML: XGBoost + SHAP
Database: SQLite / MySQL / MariaDB
OCR: OpenCV + Tesseract
Maps: Leaflet + OpenStreetMap
Device: HTTP + HMAC-SHA256
Frontend: HTML / CSS / JavaScript

Important

The current ML model is trained on synthetic data and is not clinically validated. It is intended for prototype, testing, and demonstration purposes only.
<<<<<<< HEAD

## Integrasi alat RespiroSens via Firebase (DEVICE_MODE=firebase)

Alur: Nakes klik *Mulai Pembacaan* -> alat (ESP32) push ke Firebase `/dataset` -> backend
polling (`GET /api/screening/sessions/<id>`) mengambil rekaman pertama yang dibuat SETELAH
tombol ditekan -> QC -> `POST .../predict` menjalankan **QC deterministik + AI reviewer**
(bukan model XGBoost demo) -> hasil kategori -> review nakes -> rujukan.

- Setup: salin isi `.env.example` ke `.env`, lalu `python run.py`. Tes: `pytest tests/`.
- `GET /api/screening/sessions/<id>/device-analysis`: QC + fitur + AI + deret waktu.
- `python export_firebase_dataset.py` -> `data/firebase_features.csv` untuk melatih ulang model dari data alat.
- Skor 0-100 pada hasil alat hanyalah pita ordinal (15/45/80), bukan probabilitas; UI menampilkan kategori.
- Tanpa API key AI (`GEMINI_API_KEY`, atau `ANTHROPIC_API_KEY` bila `AI_PROVIDER=anthropic`), `/predict` mengembalikan 503 `ai_unavailable` (sengaja: tidak ada hasil tanpa validator #2).
=======
>>>>>>> 7c8f94f08c39755d85d4ff7654fcd79d2d4a503e
