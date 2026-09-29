import statistics as st

NOTE_TXT = {
    "tvoc_reconstructed": ("Kolom TVOC", "kosong dari firmware; dihitung dari Ratio x eCO2 (verifikasi ke firmware)"),
    "ratio_gas_recomputed": ("Ratio gas/baseline", "selalu 0 dari firmware; dihitung ulang dari baseline_gas"),
}


def _v(xs):
    return [x for x in xs if x is not None]


def _med(xs):
    return round(st.median(xs), 2) if xs else None


def _mean(xs):
    v = _v(xs)
    return round(st.mean(v), 2) if v else None


def despike(xs, k=5):
    v = _v(xs)
    if len(v) < 8:
        return xs, 0
    m = st.median(v)
    lim = m + k * 1.4826 * (st.median([abs(x - m) for x in v]) or 1e-9)
    n = sum(1 for x in xs if x is not None and x > lim)
    return [m if (x is not None and x > lim) else x for x in xs], n


def qc(rec):
    """Validasi #1 (deterministik). Ambang = titik awal dari 8 rekaman; kalibrasi ulang saat data bertambah."""
    s, checks = rec["series"], []
    t, gas, eco = _v(s["t"]), _v(s["gas"]), _v(s["eco2"])
    n = len(t)

    def add(i, label, status, detail):
        checks.append({"id": i, "label": label, "status": status, "detail": detail})

    span = (t[-1] - t[0]) / 1000 if n > 1 else 0
    add("samples", "Jumlah sampel", "ok" if n >= 50 else "warn" if n >= 30 else "fail", f"{n} baris")
    add("duration", "Durasi rekaman", "ok" if span >= 55 else "warn" if span >= 40 else "fail", f"{span:.0f} dtk")
    gap = max([b - a for a, b in zip(t, t[1:])] or [0])
    add("gaps", "Kontinuitas waktu", "ok" if gap <= 3000 else "warn", f"jeda terpanjang {gap:.0f} ms")
    emax = max(eco) if eco else 0
    add("breath", "Napas terdeteksi", "ok" if emax >= 700 else "warn" if emax >= 500 else "fail",
        f"eCO2 puncak {emax:.0f} ppm (ambang 700; <500 = kemungkinan chamber kosong)")
    stuck = len(gas) < 2 or st.pstdev(gas) < 0.05 or (len(eco) > 1 and st.pstdev(eco) < 1)
    add("stuck", "Sensor merespons", "fail" if stuck else "ok", "sinyal datar" if stuck else "sinyal bervariasi")
    _, ns = despike(s["nh3"])
    add("nh3", "Lonjakan NH3", "ok" if ns <= 0.1 * max(n, 1) else "warn", f"{ns} lonjakan")
    b, g0 = rec["baseline_gas"], _med(gas[:5])
    if b and g0:
        good = abs(g0 - b) / b <= 0.5
        add("baseline", "Baseline vs awal rekaman", "ok" if good else "warn",
            f"baseline {b} vs awal {g0} kOhm" + ("" if good else " (baseline kemungkinan basi)"))
    else:
        add("baseline", "Baseline vs awal rekaman", "warn", "baseline_gas tidak ada")
    rh = _mean(s["rh"]) or 0
    add("humidity", "Kelembapan", "warn" if rh > 85 else "ok", f"rata-rata {rh:.0f}% RH")
    add("device", "Device ID", "ok" if rec["device_id"] else "warn", rec["device_id"] or "tidak dikirim firmware")
    for nt in rec["notes"]:
        add(nt, *[NOTE_TXT[nt][0], "info", NOTE_TXT[nt][1]])
    if not _v(s["tvoc"]):
        add("tvoc_missing", "Kolom TVOC", "warn", "kosong dan tidak bisa direkonstruksi")
    status = "fail" if any(c["status"] == "fail" for c in checks) else \
             "warn" if any(c["status"] == "warn" for c in checks) else "ok"
    return {"status": status, "checks": checks}


def features(rec):
    s = rec["series"]
    gas, eco, tv = _v(s["gas"]), _v(s["eco2"]), _v(s["tvoc"])
    if len(gas) < 10 or len(eco) < 10:
        return {}
    nh3, p, t0 = _v(despike(s["nh3"])[0]), _v(s["p"]), s["t"][0]

    def at(xs, fn):
        i = fn([(x, i) for i, x in enumerate(xs) if x is not None])[1]
        return round((s["t"][i] - t0) / 1000, 1)

    g0, g1 = _med(gas[:5]), _med(gas[-5:])
    return {
        "eco2_start_ppm": _med(eco[:5]), "eco2_max_ppm": max(eco), "eco2_peak_at_s": at(s["eco2"], max),
        "eco2_end_ppm": _med(eco[-5:]), "tvoc_max_ppb": max(tv) if tv else None, "tvoc_mean_ppb": _mean(tv),
        "gas_start_kohm": g0, "gas_min_kohm": min(gas), "gas_min_at_s": at(s["gas"], min), "gas_end_kohm": g1,
        "gas_drop_pct": round((g0 - min(gas)) / g0 * 100, 1) if g0 else None,
        "gas_net_change_pct": round((g1 - g0) / g0 * 100, 1) if g0 else None,
        "nh3_mean_mv": _mean(nh3), "nh3_std_mv": round(st.pstdev(nh3), 1) if len(nh3) > 1 else None,
        "rh_mean_pct": _mean(s["rh"]), "abs_hum_mean": _mean(s["ah"]), "temp_mean_c": _mean(s["temp"]),
        "pressure_std_hpa": round(st.pstdev(p), 2) if len(p) > 1 else None,
    }


def preview(rec, bins=12):
    s, out = rec["series"], {}
    for k in ("gas", "eco2", "tvoc", "nh3", "rh"):
        xs = despike(s[k])[0] if k == "nh3" else s[k]
        step = max(1, len(xs) // bins)
        out[k] = [_mean(xs[i:i + step]) for i in range(0, len(xs), step)][:bins]
    return out
