import json, math, re, urllib.request, urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120 Safari/537.36 Spangle/1.0"}
STOP = set("a an the and or of to in on for with at by from as is are was were be been it its this that these those after before over into about says said new how why what who will can not no his her their they he she we you your our has have had more than up out just".split())


def get_json(url, timeout=10, headers=None):
    h = dict(UA); h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def get_text(url, timeout=10):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def tokens(title):
    return [w for w in re.findall(r"[a-z0-9']+", title.lower()) if w not in STOP and len(w) > 2]


def saturate(x, sat):
    """Map a non-negative count to [0,1) with log saturation (x == sat -> ~0.75)."""
    if x <= 0:
        return 0.0
    return min(1.0, math.log1p(x) / math.log1p(sat) * 0.75)


def canon(u):
    p = urllib.parse.urlparse(u)
    host = p.netloc.lower().removeprefix("www.")
    return host + p.path.rstrip("/")


def key_terms(title, n=6):
    t = tokens(title)
    return sorted(set(t), key=lambda w: (-len(w), w))[:n]
