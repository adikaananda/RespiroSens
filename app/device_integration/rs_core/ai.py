import json, os, re, urllib.request

SYSTEM = (
    "Kamu peninjau independen (validator #2) untuk riset skrining TBC berbasis napas. Input: fitur ringkas dan "
    "pratinjau deret waktu 60 detik dari alat: BME688 (gas_resistance kOhm; turun = VOC naik), ENS160 "
    "(eCO2 ppm, TVOC ppb), sensor NH3 (mV), kelembapan RH, suhu. Kamu TIDAK diberi label atau identitas; jangan menebak. "
    "Biomarker napas TBC masih riset awal dan sinyal sangat dipengaruhi kelembapan, sisa napas di chamber, dan baseline. "
    "Bila sinyal tidak cukup informatif atau kualitas data meragukan, jawab tidak_dapat_ditentukan. Ini bukan diagnosis. "
    'Balas HANYA JSON: {"risk_level":"rendah|sedang|tinggi|tidak_dapat_ditentukan","confidence":0.0-1.0,'
    '"reasons":["maks 4 poin singkat, Bahasa Indonesia"],"data_concerns":["..."],"retest_recommended":true|false}'
)
LEVELS = ("rendah", "sedang", "tinggi", "tidak_dapat_ditentukan")


def _provider():
    """Pilih penyedia AI. AI_PROVIDER=gemini|anthropic. Default: gemini bila GEMINI_API_KEY ada,
    kalau tidak dan ANTHROPIC_API_KEY ada -> anthropic, selain itu gemini."""
    p = os.environ.get("AI_PROVIDER", "").strip().lower()
    if p in ("gemini", "anthropic"):
        return p
    if not os.environ.get("GEMINI_API_KEY") and os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "gemini"


def _post_json(url, headers, body, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _call_gemini(key, model, payload, timeout):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}],
        # maxOutputTokens dibuat longgar: model "thinking" menghitung token berpikir di batas ini.
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048,
                             "responseMimeType": "application/json"},
    }
    data = _post_json(url, {"x-goog-api-key": key}, body, timeout)
    cand = (data.get("candidates") or [{}])[0]
    parts = (cand.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not text.strip():
        raise ValueError(f"respons kosong (finishReason={cand.get('finishReason')})")
    return text


def _call_anthropic(key, model, payload, timeout):
    body = {"model": model, "max_tokens": 700, "system": SYSTEM,
            "messages": [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]}
    data = _post_json("https://api.anthropic.com/v1/messages",
                      {"x-api-key": key, "anthropic-version": "2023-06-01"}, body, timeout)
    return data["content"][0]["text"]


def review(feat, prev, qc_result):
    provider = _provider()
    key_name = "GEMINI_API_KEY" if provider == "gemini" else "ANTHROPIC_API_KEY"
    key = os.environ.get(key_name)
    if not key:
        return {"available": False, "error": f"{key_name} belum diset"}
    default_model = "gemini-2.5-flash" if provider == "gemini" else "claude-sonnet-5-5"
    model = os.environ.get("AI_MODEL", default_model)
    payload = {"features": feat, "preview_12_titik": prev,
               "catatan_qc": [c for c in qc_result["checks"] if c["status"] != "ok"]}
    call = _call_gemini if provider == "gemini" else _call_anthropic
    try:
        text = call(key, model, payload, float(os.environ.get("AI_TIMEOUT", "25")))
        out = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        if out.get("risk_level") not in LEVELS:
            raise ValueError("risk_level tidak valid")
        return {"available": True, "risk_level": out["risk_level"],
                "confidence": max(0.0, min(1.0, float(out.get("confidence", 0)))),
                "reasons": [str(x)[:200] for x in out.get("reasons", [])][:4],
                "data_concerns": [str(x)[:200] for x in out.get("data_concerns", [])][:4],
                "retest": bool(out.get("retest_recommended")),
                "provider": provider, "model": model}
    except Exception as e:
        return {"available": False, "error": f"{type(e).__name__}: {e}"[:200]}


def decide(qc_status, ai, label):
    if qc_status == "fail":
        d, msg = "ulang_tes", "Gagal validasi data (#1). Ulangi pengambilan napas."
    elif not ai.get("available"):
        d, msg = "menunggu_ai", "Validasi AI (#2) belum tersedia."
    elif ai["risk_level"] == "tidak_dapat_ditentukan" or ai["confidence"] < 0.6 or ai["retest"]:
        d, msg = "review_nakes", "Sinyal/kualitas meragukan. Wajib ditinjau nakes atau diulang."
    else:
        d, msg = "lolos_ganda", "Kedua validasi lolos. Tetap rekomendasi; keputusan ada di nakes."
    mapped = {"tinggi": "TBC", "rendah": "Sehat"}.get(ai.get("risk_level"))
    match = mapped == label if (mapped and label in ("TBC", "Sehat")) else None
    return {"decision": d, "message": msg, "ground_truth": label, "ai_maps_to": mapped, "agrees_with_label": match}
