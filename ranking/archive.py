"""Archive fallback for big stories whose only links are paywalled.
Read-only lookups of EXISTING snapshots; never submits captures.
Providers: archive.today (/newest/ redirect) then Wayback availability API."""
import re, json, urllib.request, urllib.parse
from datetime import datetime, timezone
from .util import UA

STATS = {"archive_today": [0, 0], "wayback": [0, 0]}  # [found, tried]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def archive_today(url, timeout):
    STATS["archive_today"][1] += 1
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        r = opener.open(urllib.request.Request(f"https://archive.ph/newest/{url}", headers=UA), timeout=timeout)
        loc = r.headers.get("Location") or (r.geturl() if r.geturl() != f"https://archive.ph/newest/{url}" else None)
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location") if e.code in (301, 302, 303, 307) else None
    except Exception:
        return None
    m = re.search(r"archive\.[a-z]+/(\d{14})/", loc or "")
    if not m:
        return None
    ts = datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    if ts > datetime.now(timezone.utc):  # placeholder/captcha redirects use future stamps
        return None
    STATS["archive_today"][0] += 1
    return loc


def wayback(url, timeout):
    STATS["wayback"][1] += 1
    try:
        with urllib.request.urlopen(urllib.request.Request(
                "https://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe=""), headers=UA), timeout=timeout) as r:
            d = json.loads(r.read())
    except Exception:
        return None
    snap = d.get("archived_snapshots", {}).get("closest", {})
    if snap.get("available") and str(snap.get("status", "200")) == "200":
        STATS["wayback"][0] += 1
        return snap["url"].replace("http://", "https://", 1)
    return None


PROVIDERS = {"archive_today": archive_today, "wayback": wayback}


def find(url, cfg):
    for name in cfg.get("providers", ["archive_today", "wayback"]):
        link = PROVIDERS[name](url, cfg.get("timeout_seconds", 6))
        if link:
            return link, name
    return None, None
