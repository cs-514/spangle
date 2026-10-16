"""Page-clutter signal and clean-link helpers. Scores come from the public clutter_scores.json
(refreshed by scripts/clutter_refresh.py): per outlet domain, cleanliness in [0, 1], 1 = clean
(page weight, script count, ad/tracker hosts, autoplay video, modal markers, text-to-HTML ratio).
Signal: the cleanest item in the cluster (unknown domains = neutral 0.5); weight is modest."""
import html, json, os, re, urllib.request
from urllib.parse import urlsplit
NAME = "clutter"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_S = None
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120 Safari/537.36"}


def scores():
    global _S
    if _S is None:
        try:
            _S = json.load(open(os.path.join(HERE, "clutter_scores.json"))).get("domains") or {}
        except Exception:
            _S = {}
    return _S


def domain(url):
    return urlsplit(url or "").netloc.lower().removeprefix("www.")


def clean_score(url, default=0.5):
    d = domain(url)
    s = scores()
    while d and d not in s and "." in d:
        d = d.split(".", 1)[1]  # subdomain -> parent
    return float(s[d]["score"]) if d in s else default


def compute(clusters, settings, ctx):
    if not scores():
        return None
    return {c["id"]: max(clean_score(s["link"]) for s in c["items"]) for c in clusters}


def link_score(item, tiers, default_tier, now=None):
    """Which sibling to LINK: tier + cleanliness + freshness (headline choice is separate)."""
    fresh = 0.5
    if now is not None and item.get("when"):
        fresh = max(0.0, 1.0 - (now - item["when"]).total_seconds() / (36 * 3600))
    return 0.45 * tiers.get(item["source"], default_tier) + 0.40 * clean_score(item["link"]) + 0.15 * fresh


# ---- lighter URL variants (AMP / print), used only after validation ----

def _get(url, n=3_000_000, timeout=10):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.status, r.geturl(), r.read(n).decode("utf-8", "ignore")


def article_chars(h):
    body = re.sub(r"(?is)<(script|style|noscript|svg|nav|header|footer|aside)\b.*?</\1>", " ", h)
    return len(re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", " ".join(re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", body))))).strip())


def variant_url(url, rule):
    base = url.split("?", 1)[0].split("#", 1)[0]
    t = (rule or {}).get("type")
    if t == "query":
        return base + "?" + rule["value"]
    if t == "suffix":
        return base.rstrip("/") + "/amp/"
    if t == "prefix":
        return re.sub(r"^(https?://[^/]+)/", r"\1/amp/", base)
    return None  # "amphtml": needs the canonical page


def lighter(url, get=_get):
    """Return a validated lighter URL for this article, or None (caller keeps the canonical URL).
    Valid = HTTP 200, no login/subscribe wall, and the full article text (>= 80% of the canonical's)."""
    rule = (scores().get(domain(url)) or {}).get("variant")
    if not rule:
        return None
    try:
        st, _, canon = get(url)
        if st != 200:
            return None
        cchars = article_chars(canon)
        v = variant_url(url, rule)
        if rule.get("type") == "amphtml":
            m = re.search(r'(?i)<link[^>]+rel=["\']amphtml["\'][^>]*href=["\']([^"\']+)', canon) or \
                re.search(r'(?i)<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']amphtml', canon)
            v = html.unescape(m.group(1)) if m else None
        if not v:
            return None
        vst, vfinal, vh = get(v)
        if vst != 200 or re.search(r"(?i)(log ?in|sign ?in|subscribe) to (continue|read)", vh):
            return None
        if article_chars(vh) < max(600, 0.8 * cchars):
            return None
        return vfinal
    except Exception:
        return None
