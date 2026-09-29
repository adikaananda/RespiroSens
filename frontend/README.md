# RespiroSens — Frontend

Server-rendered by Flask (`app/__init__.py` serves this folder as static
files, no build step / bundler needed). Just edit and refresh.

## Struktur folder

```
frontend/
├── index.html              Shell tipis saja: ikon SVG, mount point login, mount point halaman
├── pages/                   Satu file per LAYAR — bukan semua di-index lagi
│   ├── login.html
│   ├── nakes-dashboard.html
│   ├── nakes-skrining.html      Wizard 4 langkah + kamera KTP + device real-time
│   ├── dinkes-dashboard.html
│   ├── dinkes-faskes.html
│   ├── admin-dashboard.html
│   └── admin-users.html
├── css/                     Satu file per area
│   ├── tokens.css           Warna, spacing, font — dimuat PALING AWAL
│   ├── login.css
│   ├── forms.css
│   ├── shell.css            Sidebar, topbar, layout kartu/grid umum
│   ├── patient-card.css     Kartu dashboard Nakes
│   ├── table.css
│   ├── dinkes-admin.css
│   ├── screening-flow.css   Wizard skrining + kamera KTP + panel device
│   └── modal.css
├── js/
│   ├── config.js / state.js / api.js / utils.js
│   ├── auth.js / nav.js / search.js
│   ├── app.js                Bootstrap — dimuat PALING AKHIR
│   └── pages/
│       ├── nakes-dashboard.js
│       ├── nakes-skrining.js
│       ├── dinkes.js
│       └── admin.js
└── legacy/                  Versi lama, hanya referensi
```

### Bagaimana halaman dimuat

`index.html` **tidak lagi berisi semua layar**. Ia cuma punya dua slot kosong:
`#loginScreen` dan `#pageContent`. `js/nav.js` — fungsi `goPage(key)` —
mem-fetch `pages/<key>.html` lalu menyuntikkannya ke `#pageContent` saat
pengguna pindah halaman (hasil fetch di-cache supaya kunjungan berikutnya
tidak fetch ulang). Login juga begitu: `js/app.js` mem-fetch
`pages/login.html` ke `#loginScreen` saat aplikasi pertama kali dibuka.

Cari sesuatu? Nama file = isinya. Mau ubah halaman dashboard Nakes → langsung
`pages/nakes-dashboard.html` + `js/pages/nakes-dashboard.js`. Tidak perlu
scroll satu file HTML 600 baris lagi.

## Tidak ada data statis

Setiap angka yang tampil (nama pasien, usia, tinggi/berat/IMT, vital, gejala,
skor risiko, grafik tren) diambil dari API Flask (`/api/...`). Memilih baris
di tabel "Riwayat Skrining" — atau mencari nama pasien — mengganti pasien
yang ditampilkan di kartu-kartu ringkasan.

## Skrining: kamera KTP + perangkat real-time

`pages/nakes-skrining.html` + `js/pages/nakes-skrining.js`:

- **Langkah 1 (Data Diri):** dua mode — "Ambil Foto" (buka kamera perangkat
  via `getUserMedia`, ambil foto dari video langsung ke `<canvas>`, kirim ke
  `/api/patients/ocr-scan`) atau "Unggah File" (mode lama, tetap ada sebagai
  fallback). Keduanya jalan lewat helper yang sama (`scanKtpBlob`).
- **Langkah 3 (Vital & Napas):** **tidak ada input manual lagi sebagai jalur
  utama.** Tombol "Mulai Pembacaan Perangkat" memanggil
  `POST /screening/sessions/<id>/breath-test`, yang di backend
  (`app/device_integration/`) sekarang mengembalikan **vital sekaligus
  pembacaan VOC** dalam satu panggilan — lihat `BreathSampleResult.vitals`.
  Field yang tidak dikirim perangkat (mis. hardware belum punya modul
  vitals) baru menampilkan input manual sebagai **fallback**, bukan default.
- **Langkah 4 (Hasil):** panel validasi (sumber sampel, kualitas sampel,
  durasi embusan, versi model), grafik batang SHAP horizontal
  merah/biru, dan catatan klinis — dirancang mengikuti mockup "Explainable
  AI" di proposal.

Catatan jujur: rangkaian sensor RespiroSens (BME688/SGP41/SHT40/SCD40 +
amonia) adalah array VOC napas, bukan alat vital sign. Di **Simulation
Mode** (`DEVICE_MODE=simulation`, default demo), backend men-generate vital
sintetis yang koheren dengan kategori risiko supaya alur ini bisa dites
end-to-end. Di **Hardware Mode** (`DEVICE_MODE=http`), vital hanya terisi
otomatis jika rig fisik memang punya modul vitals yang dipetakan di
`app/device_integration/device_field_map.json` (lihat
`device_field_map.example.json` bagian `"vitals"`) — kalau tidak ada, field
itu otomatis jatuh ke input manual, bukan mengarang angka.

## Login demo

Pilih tab role (Nakes / Dinkes / Admin) di halaman login lalu klik "Masuk" —
kredensial demo terisi otomatis (lihat `js/config.js` → `DEMO_CREDENTIALS`,
harus cocok dengan akun yang dibuat `init_db.py`).
