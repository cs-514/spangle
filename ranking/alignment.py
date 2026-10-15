"""Editorial alignment. Reads private weights from the ALIGNMENT_CONFIG env var
(JSON); falls back to generic defaults. Never logs the config contents."""
import json, math, os
NAME = "alignment"

DEFAULT = {
    "boost_keywords": {"breaking": 2, "exclusive": 2, "senate": 1, "congress": 1, "supreme court": 2},
    "demote_keywords": {"horoscope": -5, "celebrity": -2, "recipe": -5, "deals": -4, "sponsored": -6},
    "authors": {}, "sources": {}, "lead_topics": [], "scale": 8,
}

def load():
    raw = os.environ.get("ALIGNMENT_CONFIG", "").strip()
    cfg = dict(DEFAULT)
    if raw:
        try:
            cfg.update(json.loads(raw)); print("Loaded custom scoring config.")
            return cfg
        except Exception:
            print("Custom scoring config invalid; using defaults.")
    else:
        print("Using default scoring config.")
    return cfg

def raw_score(s, cfg):
    title = s["title"].lower()
    hay = f"{title} {s['desc']} {s['cats']}".lower()
    sc = 0.0
    for k, w in cfg.get("boost_keywords", {}).items():
        if k.lower() in hay:
            sc += w * (2 if k.lower() in title else 1)
    for k, w in cfg.get("demote_keywords", {}).items():
        if k.lower() in hay:
            sc += w
    for a, w in cfg.get("authors", {}).items():
        if a.lower() in (s["author"] or "").lower():
            sc += w
    sc += cfg.get("sources", {}).get(s["source"], 0)
    if any(t.lower() in title for t in cfg.get("lead_topics", [])):
        sc += cfg.get("lead_topic_bonus", 4)
    return sc

def compute(clusters, settings, ctx):
    cfg = ctx.setdefault("alignment_cfg", load())
    scale = cfg.get("scale", 8)
    out = {}
    for c in clusters:
        r = max(raw_score(s, cfg) for s in c["items"])
        out[c["id"]] = 0.5 + 0.5 * math.tanh(r / scale)
    return out
