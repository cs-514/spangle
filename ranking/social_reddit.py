"""Reddit (keyless): posts in the configured conservative subreddits that link to a story URL.
Tries each listing's public RSS feed (/r/<sub>/<listing>/.rss); with "rss": false, the JSON API.
RSS carries no scores, so a post's credit decays with its rank in the listing. Reddit often blocks
datacenter IPs; the signal then degrades to None (weight redistributed)."""
import re, html, urllib.request
import xml.etree.ElementTree as ET
from .util import get_json, canon, saturate, UA
NAME = "reddit"
A = "{http://www.w3.org/2005/Atom}"


def _rss(sub, listing, timeout):
    data = urllib.request.urlopen(urllib.request.Request(
        f"https://www.reddit.com/r/{sub}/{listing}/.rss?limit=100", headers=UA), timeout=timeout).read()
    out = {}
    for rank, e in enumerate(ET.fromstring(data).findall(f"{A}entry")):
        body = html.unescape(e.findtext(f"{A}content") or "")
        for u in re.findall(r'href="(https?://[^"]+)"', body):
            if "reddit.com" not in u and "redd.it" not in u:
                out[canon(u)] = max(out.get(canon(u), 0.0), 1.0 - rank / 100)
    return out


def compute(cands, settings, ctx):
    cfg = settings["social"]["reddit"]
    if not cfg.get("enabled"):
        return None
    t = settings["social"]["timeout_seconds"]
    links, ok = {}, 0
    for sub in cfg["subreddits"]:
        for listing in ("hot", "new"):
            try:
                if cfg.get("rss", True):
                    for u, v in _rss(sub, listing, t).items():
                        links[u] = max(links.get(u, 0.0), v)
                else:
                    d = get_json(f"https://www.reddit.com/r/{sub}/{listing}.json?limit=100", t)
                    for ch in d.get("data", {}).get("children", []):
                        p = ch.get("data", {})
                        u = canon(p.get("url", ""))
                        links[u] = max(links.get(u, 0.0), saturate(p.get("score", 0) + 2 * p.get("num_comments", 0), cfg["saturation"]))
                ok += 1
            except Exception as e:
                print(f"  reddit r/{sub}/{listing}: {getattr(e, 'code', type(e).__name__)}")
    if not ok:
        return None
    return {c["id"]: max(links.get(canon(s["link"]), 0.0) for s in c["items"]) for c in cands}
