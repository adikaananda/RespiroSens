import hashlib
import re
import secrets


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    if not digits.startswith("62"):
        digits = "62" + digits
    return digits


def hash_phone(raw: str, pepper: str) -> tuple:
    """Returns (hash, last4) — only the hash is ever persisted for lookups /
    audit; the last 4 digits are kept purely for display in the nakes UI."""
    normalized = normalize_phone(raw)
    digest = hashlib.sha256((pepper + normalized).encode("utf-8")).hexdigest()
    return digest, normalized[-4:]


def generate_referral_code() -> str:
    return f"RS-{secrets.token_hex(4).upper()}"
