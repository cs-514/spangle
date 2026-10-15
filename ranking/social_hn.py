"""Hacker News via Algolia (keyless): points+comments for submissions of the URL.
Reliable but rarely covers political news, so weight is small."""
import urllib.parse
from .util import get_json, saturate
NAME = "hackernews"

def compute(cands, settings, ctx):
    cfg = settings["social"]["hackernews"]
    if not cfg.get("enabled"):
        return None
    out, ok = {}, 0
    for c in cands:
        u = c["items"][0]["link"]
        q = urllib.parse.urlencode({"query": u, "restrictSearchableAttributes": "url", "tags": "story"})
        try:
            d = get_json(f"https://hn.algolia.com/api/v1/search?{q}", settings["social"]["timeout_seconds"]); ok += 1
        except Exception:
            continue
        out[c["id"]] = saturate(sum(h.get("points", 0) + h.get("num_comments", 0) for h in d.get("hits", [])), cfg["saturation"])
    return out if ok else None
