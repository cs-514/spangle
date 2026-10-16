"""Faction signal: treatment of a configured, private list of in-party figures
(private config key "faction"; the names never appear in public code):
  {"members": [...],                 # surnames or full names; extend freely
   "favorable_terms": [...],         # praise / protagonist language near a member
   "defect_terms": [...],            # member breaks ranks / obstructs the agenda
   "critic_terms": [...],            # criticism of a member, primary challenges
   "attack_terms": [...],            # slams/rips...: someone ELSE before the member = critic,
                                     # the member before it = member as protagonist
   "protagonist_words": 3,           # member named in the first N words = protagonist
   "scores": {"critic": 1.0, "defect": 0.85, "neutral": 0.5, "favorable": 0.1}}
Per cluster: critic -> boosted; defect -> outrage material (c["faction_defect"], siblings/rewrites
that feature the other side preferred); favorable/protagonist -> downranked and kept out of the
lead and Top Stories. Clusters that mention no member get the neutral score."""
import re
from . import private
NAME = "faction"


def _pos(text, terms, prefix=False):
    return [len(text[:m.start()].split()) for t in terms
            for m in re.finditer(r"\b" + re.escape(t) + ("" if prefix else r"\b"), text)]


def classify(title, cfg):
    """'critic' | 'defect' | 'favorable' | 'mention' | None for one headline."""
    text = " ".join(re.findall(r"[a-z0-9'.-]+", title.lower().replace("’", "'")))
    m = _pos(text, [x.lower() for x in cfg.get("members", [])])
    if not m:
        return None
    near = lambda terms, w=6: any(abs(a - b) <= w for a in m for b in _pos(text, [t.lower() for t in terms], True))
    if near(cfg.get("critic_terms", [])):
        return "critic"
    atk = _pos(text, [t.lower() for t in cfg.get("attack_terms", [])], True)
    if any(0 < a - v <= 4 for a in m for v in atk) and not any(0 <= v - a <= 4 for a in m for v in atk):
        return "critic"  # "<someone> Slams <member>"
    if near(cfg.get("defect_terms", [])):
        return "defect"
    if near(cfg.get("favorable_terms", [])) or min(m) < int(cfg.get("protagonist_words", 3)):
        return "favorable"
    return "mention"


def members(ctx):
    return [x.lower() for x in (private.load(ctx).get("faction") or {}).get("members", [])]


def compute(clusters, settings, ctx):
    cfg = private.load(ctx).get("faction")
    if not cfg or not cfg.get("members"):
        return None
    sc = {"critic": 1.0, "defect": 0.85, "neutral": 0.5, "favorable": 0.1, **(cfg.get("scores") or {})}
    out, n = {}, {"critic": 0, "defect": 0, "favorable": 0}
    for c in clusters:
        kinds = {classify(s["title"], cfg) for s in c["items"]} - {None, "mention"}
        k = next((k for k in ("critic", "defect", "favorable") if k in kinds), None)
        out[c["id"]] = sc[k] if k else sc["neutral"]
        if k == "defect":
            c["faction_defect"] = True
        if k == "favorable":
            c["lead_excluded"] = c["top_excluded"] = True
        if k:
            n[k] += 1
    print(f"signal faction: {n['critic']} boosted, {n['defect']} defection, {n['favorable']} demoted")
    return out
