"""Generic lean filter. Per-source mode in settings.json "lean_filter.sources":
  "all"        keep everything (default)
  "right_only" keep only items whose lean score >= threshold

Score = outlet lean (+/-outlet_weight) + author lean (+/-author_weight) + lexicon hits (+/-1 each)
over title + description. Public defaults are deliberately generic; the real lexicon and
author lists live in the PRIVATE config (ALIGNMENT_CONFIG key "lean"), merged over the
public settings. Never logs list contents."""
import json, os, re

STATS = {}
_CFG = None


def _private():
    raw = os.environ.get("ALIGNMENT_CONFIG", "").strip()
    try:
        return (json.loads(raw) or {}).get("lean") or {} if raw else {}
    except Exception:
        return {}


def config(settings):
    global _CFG
    if _CFG is None:
        pub = dict(settings.get("lean_filter") or {})
        priv = _private()
        cfg = dict(pub)
        for k, v in priv.items():
            if isinstance(v, list):
                cfg[k] = list(dict.fromkeys(list(pub.get(k, [])) + v))
            else:
                cfg[k] = v
        _CFG = cfg
    return _CFG


def mode(source, settings):
    return (config(settings).get("sources") or {}).get(source, "all")


def _hits(text, terms):
    return sum(1 for t in terms if re.search(r"(?<![a-z])" + re.escape(t.lower()) + r"(?![a-z])", text))


def score(item, cfg, outlet=None, author=None):
    text = f"{item.get('title', '')} {item.get('desc', '')}".lower()
    out = (outlet or "").lower()
    au = (author if author is not None else item.get("author") or "").lower()
    s = 0
    ow, aw = cfg.get("outlet_weight", 2), cfg.get("author_weight", 2)
    if out and any(o.lower() == out for o in cfg.get("right_outlets", [])):
        s += ow
    if out and any(o.lower() == out for o in cfg.get("left_outlets", [])):
        s -= ow
    if au and any(a.lower() in au for a in cfg.get("right_authors", [])):
        s += aw
    if au and any(a.lower() in au for a in cfg.get("left_authors", [])):
        s -= aw
    s += _hits(text, cfg.get("right_terms", [])) - _hits(text, cfg.get("left_terms", []))
    return s


def keep(item, source, settings, outlet=None, author=None):
    m = mode(source, settings)
    st = STATS.setdefault(source, [0, 0])  # kept, filtered
    if m != "right_only":
        st[0] += 1
        return True
    cfg = config(settings)
    ok = score(item, cfg, outlet, author) >= cfg.get("threshold", 1)
    st[0 if ok else 1] += 1
    return ok
