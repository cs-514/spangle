"""Google News RSS search (keyless): how many articles across the whole web
match the story's key terms in the last day. Broad, outlet-agnostic buzz proxy."""
import urllib.parse
from .util import get_text, key_terms, saturate
NAME = "google_news"

def compute(cands, settings, ctx):
    cfg = settings["social"]["google_news"]
    if not cfg.get("enabled"):
        return None
    out, ok = {}, 0
    for c in cands:
        terms = key_terms(c["items"][0]["title"], 4)
        if len(terms) < 2:
            out[c["id"]] = 0.0; continue
        q = urllib.parse.quote(" ".join(terms) + " when:1d")
        try:
            x = get_text(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en", settings["social"]["timeout_seconds"]); ok += 1
        except Exception:
            continue
        out[c["id"]] = saturate(x.count("<item>"), cfg["saturation"])
    return out if ok else None
