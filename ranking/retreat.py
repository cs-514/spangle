"""Retreat signal: demotes stories where configured actors back down / walk back /
rule out / cave. Lexicons live in the private config key "retreat":
  {"actors": [...], "verbs": [...], "demotion": 0.35, "lead_exclude": true, "top_exclude": true}
Returns 1.0 (fine) or demotion (flagged). Sets c["lead_excluded"] when lead_exclude."""
import re
from . import private
NAME = "retreat"


def _positions(text, terms, prefix_only=False):
    pos = []
    for a in terms:
        pat = r"\b" + re.escape(a) + ("" if prefix_only else r"\b")
        for m in re.finditer(pat, text):
            pos.append(len(text[: m.start()].split()))
    return pos


def _hit(title, actors, verbs, win, blockers=()):
    """Retreat if a configured actor is near a retreat verb AND the verb's subject is the actor.
    If the nearest term BEFORE the verb is a blocker (court/judge/Dem), it's their action
    against the actor (a loss/framing story), not a retreat. With no subject before the verb
    ("..., Trump Says"), an actor after the verb counts."""
    words = re.findall(r"[a-z0-9'.-]+", title.lower().replace("’", "'").replace("‘", "'"))
    text = " ".join(words)
    apos = _positions(text, actors)
    bpos = _positions(text, blockers) if blockers else []
    vpos = _positions(text, verbs, prefix_only=True)
    for v in vpos:
        before = [(v - a, "A") for a in apos if 0 <= v - a <= win] + [(v - b, "B") for b in bpos if 0 < v - b <= win]
        if before:
            if min(before)[1] == "A":
                return True
            continue
        if any(0 < a - v <= win for a in apos):
            return True
    return False


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
        flagged = any(_hit(s["title"], actors, verbs, win, [b.lower() for b in cfg.get("subject_blockers", [])]) for s in c["items"])
        if flagged:
            n += 1
            out[c["id"]] = demotion
            if cfg.get("lead_exclude", True):
                c["lead_excluded"] = True
            if cfg.get("top_exclude", False):
                c["top_excluded"] = True  # placed after all unflagged stories (out of Top Stories, bottom of columns)
        else:
            out[c["id"]] = 1.0
    print(f"signal retreat: {n} clusters flagged")
    return out
