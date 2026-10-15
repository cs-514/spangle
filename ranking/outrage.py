"""Outrage boost signal. Lexicon from private config key "outrage":
  {"terms": [...], "intensity": [...], "scale": 3}
Returns 0-1; more matching terms (and intensity words) -> higher score."""
import re
from . import private
NAME = "outrage"


def compute(clusters, settings, ctx):
    cfg = private.load(ctx).get("outrage")
    if not cfg or not cfg.get("terms"):
        return None
    terms = [t.lower() for t in cfg["terms"]]
    intensity = [t.lower() for t in cfg.get("intensity", [])]
    scale = float(cfg.get("scale", 3))
    out = {}
    for c in clusters:
        hits = intens = 0
        for s in c["items"]:
            t = s["title"].lower()
            hits += sum(1 for x in terms if re.search(r"(?<![a-z])" + re.escape(x), t))
            intens += sum(1 for x in intensity if re.search(r"(?<![a-z])" + re.escape(x), t))
        raw = hits + 0.5 * intens
        out[c["id"]] = min(1.0, raw / scale)
    return out
