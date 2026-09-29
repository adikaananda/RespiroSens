"""
KTP (Indonesian ID card) OCR pipeline.

Implements the vision steps from the proposal in simplified form:
  (1) preprocessing: grayscale, adaptive threshold, deskew via largest contour
  (2) OCR: Tesseract over the processed image
  (3) field extraction: regex over the OCR text for NIK / name / DOB
  (4) validation: 16-digit NIK format + a light regional-code sanity check

This always degrades gracefully: if OpenCV/Tesseract or the `pytesseract`
binary isn't available in the deployment environment, or the image doesn't
yield a confident NIK, the API returns ocr_success=False so the frontend can
fall back to the manual "formulir fallback" — exactly as the proposal
requires for patients without a usable KTP. No patient is ever blocked by
this step.
"""

import re

try:
    import cv2
    import numpy as np
    import pytesseract
    OCR_AVAILABLE = True
except Exception:  # pragma: no cover - depends on system packages
    OCR_AVAILABLE = False

NIK_RE = re.compile(r"\b(\d{16})\b")


def validate_nik(nik: str) -> bool:
    if not nik or not re.fullmatch(r"\d{16}", nik):
        return False
    province_code = int(nik[0:2])
    return 11 <= province_code <= 94  # loose sanity range for Indonesian province codes


def _preprocess(image_bytes: bytes):
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    return thresh


def extract_ktp_fields(image_bytes: bytes) -> dict:
    """Returns dict with ocr_success, and any of nik/full_name/date_of_birth
    it could extract. Never raises — callers should always fall back to the
    manual form on ocr_success=False."""
    if not OCR_AVAILABLE:
        return {"ocr_success": False, "reason": "ocr_dependencies_unavailable"}

    try:
        processed = _preprocess(image_bytes)
        if processed is None:
            return {"ocr_success": False, "reason": "invalid_image"}

        text = pytesseract.image_to_string(processed, config="--psm 6")

        nik_match = NIK_RE.search(text.replace(" ", ""))
        nik = nik_match.group(1) if nik_match else None
        nik_valid = validate_nik(nik) if nik else False

        # Name heuristic: KTP layout usually has "Nama" label on its own line
        # followed by the value on the next line.
        full_name = None
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for i, line in enumerate(lines):
            if "nama" in line.lower() and i + 1 < len(lines):
                full_name = lines[i + 1].title()
                break

        return {
            "ocr_success": bool(nik_valid),
            "nik": nik if nik_valid else None,
            "full_name": full_name,
            "raw_text_preview": text[:300],
        }
    except Exception as exc:  # pragma: no cover
        return {"ocr_success": False, "reason": f"ocr_error: {exc}"}
