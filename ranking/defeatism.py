"""Defeatism rule. Private config key "defeatism" (lexicons never in the repo):
  {"terms": [...],            # "can't win", "doomed", "will lose", "blow to", ...
   "always": [...],           # phrases flagged regardless of subject (e.g. a commentary genre label)
   "own_subjects": [...],     # side whose defeat is asserted -> story excluded from the page
   "other_subjects": [...],   # side whose defeat is fine -> boosted
   "window_words": 6, "boost": 1.0}
classify(title, cfg) -> "exclude" | "boost" | None. The nearest subject to the term decides
(a subject before the term wins ties: "X Can't Win"; "Blow to X" looks after).
compute() sets c["excluded"] (dropped before placement) and returns a boost score."""
import re
from . import private
NAME = "defeatism"


def _norm(t):
    return " ".join(re.findall(r"[a-z0-9'.-]+", t.lower().replace("’", "'").replace("‘", "'")))


def _pos(text, terms):
    return [(len(text[:m.start()].split()), len(t.split())) for t in terms
            for m in re.finditer(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", text)]


def classify(title, cfg):
    if not cfg:
        return None
    text = _norm(title)
    low = lambda k: [x.lower().replace("’", "'") for x in cfg.get(k, [])]
    if _pos(text, low("always")):
        return "exclude"
    hits = _pos(text, low("terms"))
    if not hits:
        return None
    win = int(cfg.get("window_words", 6))
    own = [(p, "own") for p, _ in _pos(text, low("own_subjects"))]
    oth = [(p, "other") for p, _ in _pos(text, low("other_subjects"))]
    best = None
    for tp, tl in hits:
        for p, side in own + oth:
            d = tp - p if p < tp else p - (tp + tl) + 1  # before the term, or after it
            if 0 <= d <= win:
                key = (d + (0 if p < tp else 0.5), side)  # prefer the subject before the term
                best = min(best, key) if best else key
    if not best:
        return None
    return "exclude" if best[1] == "own" else "boost"


def compute(clusters, settings, ctx):
    cfg = private.load(ctx).get("defeatism")
    if not cfg or not cfg.get("terms"):
        return None
    out, ex, bo = {}, 0, 0
    for c in clusters:
        kinds = {classify(s["title"], cfg) for s in c["items"]}
        if "exclude" in kinds:
            c["excluded"] = True; ex += 1
        out[c["id"]] = float(cfg.get("boost", 1.0)) if ("boost" in kinds and "exclude" not in kinds) else 0.5
        bo += out[c["id"]] > 0.5
    print(f"signal defeatism: {ex} excluded, {bo} boosted")
    return out
