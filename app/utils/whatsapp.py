"""
WhatsApp Business Cloud API client.

If WHATSAPP_ENABLED=false (the default) or credentials are missing, this
falls back to "console mode": the message is logged and returned as if sent,
so the whole registration -> result -> referral flow can be tested end to
end without a real Meta Business/WhatsApp account. Flip WHATSAPP_ENABLED=true
and fill in WHATSAPP_TOKEN / WHATSAPP_PHONE_NUMBER_ID in .env to send for
real once those credentials exist.
"""

import logging

import requests

logger = logging.getLogger("respirosens.whatsapp")


class WhatsAppClient:
    def __init__(self, app_config):
        self.enabled = app_config.get("WHATSAPP_ENABLED", False)
        self.token = app_config.get("WHATSAPP_TOKEN", "")
        self.phone_number_id = app_config.get("WHATSAPP_PHONE_NUMBER_ID", "")
        self.api_version = app_config.get("WHATSAPP_API_VERSION", "v20.0")

    def _console_send(self, to_number_hash: str, message: str, attachment_path: str = None) -> dict:
        logger.info("[WHATSAPP:console-mode] to=%s message=%r attachment=%s",
                     to_number_hash, message, attachment_path)
        return {"status": "logged_only", "mode": "console", "to": to_number_hash}

    def send_result_notification(self, to_number: str, to_number_hash: str, patient_name: str,
                                  risk_score: float, risk_category: str, referral_pdf_path: str = None) -> dict:
        category_label = {"hijau": "HIJAU - Observasi", "kuning": "KUNING - Rujukan Prioritas",
                           "merah": "MERAH - Rujukan Segera"}.get(risk_category, risk_category.upper())

        message = (
            f"Halo Bpk/Ibu {patient_name},\n\n"
            f"Hasil analisis udara ekshalasi (skrining napas) Anda:\n"
            f"Kategori: {category_label}\n"
            f"Skor Risiko: {risk_score}/100\n\n"
        )
        if risk_category in ("kuning", "merah"):
            message += (
                "Sistem mendeteksi probabilitas risiko yang perlu ditindaklanjuti. "
                "Silakan tunjukkan E-Surat Rujukan terlampir ke meja pendaftaran Puskesmas "
                "dalam 3 hari ke depan untuk pemeriksaan konfirmasi.\n\n"
            )
        else:
            message += "Tetap jaga kesehatan pernapasan Anda. Segera periksa ke faskes bila gejala memburuk.\n\n"
        message += (
            "Catatan: ini adalah hasil skrining awal, bukan diagnosis medis. "
            "Balas STOP untuk berhenti menerima notifikasi."
        )

        if not self.enabled or not self.token or not self.phone_number_id:
            return self._console_send(to_number_hash, message, referral_pdf_path)

        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": message},
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            resp.raise_for_status()
            return {"status": "sent", "mode": "live", "response": resp.json()}
        except requests.RequestException as exc:
            logger.exception("WhatsApp send failed, falling back to console log")
            fallback = self._console_send(to_number_hash, message, referral_pdf_path)
            fallback["error"] = str(exc)
            return fallback
