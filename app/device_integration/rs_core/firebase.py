import json, os, re, urllib.parse, urllib.request

ID_RE = re.compile(r"^-[0-9A-Za-z_-]{19}$")
PUSH = "-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"


def _get(path, params=None):
    base = os.environ.get("FIREBASE_URL", "https://tbc-ai-database-default-rtdb.firebaseio.com").rstrip("/")
    q = dict(params or {})
    if os.environ.get("FIREBASE_AUTH"):
        q["auth"] = os.environ["FIREBASE_AUTH"]
    url = f"{base}/{path}.json" + ("?" + urllib.parse.urlencode(q) if q else "")
    with urllib.request.urlopen(url, timeout=8) as r:
        return json.loads(r.read().decode())


def _node():
    return os.environ.get("FIREBASE_NODE", "dataset")


def recent(limit=40):
    """N rekaman terbaru saja (bukan seluruh node) -> hemat kuota download Firebase."""
    data = _get(_node(), {"orderBy": '"$key"', "limitToLast": int(limit)}) or {}
    return dict(sorted(data.items()))


def one(key):
    return _get(f"{_node()}/{key}") if ID_RE.match(key or "") else None


def push_ts_ms(key):
    """Push-ID Firebase menyimpan waktu pembuatan (ms) di 8 karakter pertama."""
    t = 0
    for c in key[:8]:
        t = t * 64 + PUSH.index(c)
    return t
