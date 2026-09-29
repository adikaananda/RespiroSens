import io
import os

import qrcode
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def generate_referral_pdf(
    output_dir: str,
    referral_code: str,
    verification_url: str,
    patient_name: str,
    nik_masked: str,
    facility_name: str,
    target_facility_name: str,
    risk_score: float,
    risk_category: str,
    screening_date: str,
) -> str:
    """Renders a one-page E-Surat Rujukan PDF and returns its file path."""
    os.makedirs(output_dir, exist_ok=True)
    filename = f"rujukan_{referral_code}.pdf"
    path = os.path.join(output_dir, filename)

    qr_img = qrcode.make(verification_url)
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    c = canvas.Canvas(path, pagesize=A5)
    width, height = A5

    y = height - 20 * mm
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(width / 2, y, "E-SURAT RUJUKAN SKRINING")
    y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, y, "Sistem RespiroSens — Skrining Berbasis Breathomics dan AI")
    y -= 4 * mm
    c.line(15 * mm, y, width - 15 * mm, y)

    y -= 10 * mm
    c.setFont("Helvetica", 10)
    lines = [
        ("Nomor Rujukan", referral_code),
        ("Nama Pasien", patient_name),
        ("NIK", nik_masked or "-"),
        ("Tanggal Skrining", screening_date),
        ("Faskes Asal", facility_name or "-"),
        ("Faskes Tujuan", target_facility_name or "Puskesmas / RS rujukan terdekat"),
    ]
    for label, value in lines:
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(15 * mm, y, f"{label}")
        c.setFont("Helvetica", 9.5)
        c.drawString(55 * mm, y, f": {value}")
        y -= 6 * mm

    y -= 4 * mm
    c.setFillColorRGB(0.95, 0.85, 0.4 if risk_category == "kuning" else 0.4)
    box_color = {"kuning": (1, 0.85, 0.4), "merah": (1, 0.6, 0.6)}.get(risk_category, (0.85, 0.85, 0.85))
    c.setFillColorRGB(*box_color)
    c.rect(15 * mm, y - 14 * mm, width - 30 * mm, 14 * mm, fill=1, stroke=0)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2, y - 6 * mm, f"KATEGORI: {risk_category.upper()}  (Skor: {risk_score})")
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, y - 11 * mm, "Rekomendasi: pemeriksaan konfirmasi klinis / uji Xpert MTB-RIF (TCM)")

    y -= 22 * mm
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(15 * mm, y, "Hasil ini adalah skor skrining/triase AI, BUKAN diagnosis medis definitif.")
    y -= 5 * mm
    c.drawString(15 * mm, y, "Wajib ditindaklanjuti dengan pemeriksaan konfirmasi baku oleh tenaga kesehatan.")

    qr_size = 30 * mm
    c.drawImage(
        io_to_imagereader(qr_buf), width - 15 * mm - qr_size, 15 * mm, qr_size, qr_size
    )
    c.setFont("Helvetica", 7)
    c.drawRightString(width - 15 * mm, 12 * mm, "Pindai untuk verifikasi rujukan")

    c.showPage()
    c.save()
    return path


def io_to_imagereader(buf: io.BytesIO):
    from reportlab.lib.utils import ImageReader
    return ImageReader(buf)
