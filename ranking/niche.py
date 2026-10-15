"""Niche / inside-baseball demotion for scholarly and legal-academic posts.
Returns a 0-1 score (1 = fully general-interest). Combined into the ranking
weights under the name "niche". Configured via settings.json "niche"."""
import re
NAME = "niche"


def compute(clusters, settings, ctx):
    cfg = settings.get("niche") or {}
    if not cfg.get("enabled", True):
        return None
    sources = {s.lower() for s in cfg.get("sources", [])}
    terms = [t.lower() for t in cfg.get("terms", [])]
    hooks = [h.lower() for h in cfg.get("national_hooks", [])]
    demotion = float(cfg.get("demotion", 0.55))  # score when flagged
    drop_terms = [t.lower() for t in cfg.get("drop_terms", [])] if cfg.get("drop", False) else []
    drop_hooks = [h.lower() for h in cfg.get("drop_hooks", hooks)]
    out, dropped = {}, 0
    for c in clusters:
        flagged = False
        saved = False
        drop_hit = drop_saved = False
        for s in c["items"]:
            if s["source"].lower() not in sources and not any(src in s["source"].lower() for src in sources):
                continue
            hay = f"{s['title']} {s.get('cats','')} {s.get('desc','')}".lower()
            if any(t in hay for t in terms):
                flagged = True
            if any(re.search(r"(?<![a-z])" + re.escape(h) + r"(?![a-z])", hay) for h in hooks):
                saved = True
            title = s["title"].lower()
            if drop_terms and any(re.search(r"(?<![a-z])" + re.escape(d) + r"(?![a-z])", title) for d in drop_terms):
                drop_hit = True
                if any(re.search(r"(?<![a-z])" + re.escape(h) + r"(?![a-z])", title) for h in drop_hooks):
                    drop_saved = True
        if drop_hit and not drop_saved:
            c["dropped"] = True; dropped += 1
        if flagged and not saved:
            out[c["id"]] = demotion
        else:
            out[c["id"]] = 1.0
    if drop_terms:
        print(f"signal niche: {dropped} clusters dropped")
    return out
