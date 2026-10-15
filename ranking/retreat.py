"""Retreat signal: demotes stories where configured actors back down / walk back /
rule out / cave. Lexicons live in the private config key "retreat":
  {"actors": [...], "verbs": [...], "demotion": 0.35, "lead_exclude": true}
Returns 1.0 (fine) or demotion (flagged). Sets c["lead_excluded"] when lead_exclude."""
import re
from . import private
NAME = "retreat"


def _hit(title, actors, verbs, win):
    words = re.findall(r"[a-z0-9'.-]+", title.lower())
    text = " ".join(words)
    apos = []
    for a in actors:
        for m in re.finditer(r"\b" + re.escape(a) + r"\b", text):
            apos.append(len(text[: m.start()].split()))
    vpos = []
    for v in verbs:
        for m in re.finditer(r"\b" + re.escape(v), text):
            vpos.append(len(text[: m.start()].split()))
    return bool(apos and vpos and any(abs(a - b) <= win for a in apos for b in vpos))


def compute(clusters, settings, ctx):
    cfg = private.load(ctx).get("retreat")
    if not cfg or not cfg.get("actors"):
        return None
    actors = [a.lower() for a in cfg["actors"]]
    verbs = [v.lower() for v in cfg["verbs"]]
    win = int(cfg.get("window_words", 8))
    demotion = float(cfg.get("demotion", 0.35))
    out, n = {}, 0
    for c in clusters:
        flagged = any(_hit(s["title"], actors, verbs, win) for s in c["items"])
        if flagged:
            n += 1
            out[c["id"]] = demotion
            if cfg.get("lead_exclude", True):
                c["lead_excluded"] = True
        else:
            out[c["id"]] = 1.0
    print(f"signal retreat: {n} clusters flagged")
    return out
