import re
from . import firebase

ALIAS = {
    "timestamp": "t", "timestampms": "t", "gasresistance": "gas", "gasresistancekohm": "gas",
    "temperature": "temp", "temperaturec": "temp", "humidity": "rh", "pressure": "p", "pressurehpa": "p",
    "abshum": "ah", "abshumgm3": "ah", "tvoc": "tvoc", "enstvocppb": "tvoc", "eco2": "eco2",
    "enseco2ppm": "eco2", "aqi": "aqi", "ensaqi": "aqi", "nh3adc": "nh3_adc", "nh3voltage": "nh3",
    "nh3voltmv": "nh3", "ratiotvoceco2": "r_tvoc", "ratiogasbaseline": "r_gas", "devicestate": "state",
}
KEYS = ("t", "gas", "temp", "rh", "p", "ah", "tvoc", "eco2", "aqi", "nh3_adc", "nh3", "r_tvoc", "r_gas", "state")


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _has(xs):
    return any(v is not None for v in xs)


def parse_csv(text):
    lines = [l for l in (text or "").strip().splitlines() if l.strip()]
    if len(lines) < 2:
        return []
    head = [ALIAS.get(re.sub(r"[^a-z0-9]", "", h.lower())) for h in lines[0].split(",")]
    return [{k: _f(v) for k, v in zip(head, l.split(",")) if k} for l in lines[1:]]


def build(key, rec):
    """Record Firebase mentah -> struktur kanonik. Menerima header format Firebase maupun CSV rapi."""
    rows = parse_csv(rec.get("csv"))
    s = {k: [r.get(k) for r in rows] for k in KEYS}
    base, notes = _f(rec.get("baseline_gas")), []
    if not _has(s["tvoc"]) and _has(s["r_tvoc"]):
        s["tvoc"] = [round(a * b, 1) if a is not None and b is not None else None
                     for a, b in zip(s["r_tvoc"], s["eco2"])]
        notes.append("tvoc_reconstructed")
    if base and _has(s["gas"]) and not any(s["r_gas"]):
        s["r_gas"] = [round(g / base, 3) if g is not None else None for g in s["gas"]]
        notes.append("ratio_gas_recomputed")
    try:
        ts = firebase.push_ts_ms(key)
    except (ValueError, IndexError):
        ts = None
    lab = (rec.get("label") or "").strip().lower()
    return {
        "id": key, "ts_ms": ts, "name": rec.get("nama") or "",
        "label": "TBC" if lab in ("tbc", "tb") else "Sehat" if lab == "sehat" else "Blind",
        "device_id": rec.get("device_id"), "baseline_gas": base,
        "duration_ms": _f(rec.get("duration_ms")), "series": s, "notes": notes,
    }
