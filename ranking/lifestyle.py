"""Sports / celebrity / lifestyle filter. Lexicon lives in the private config key "lifestyle":
  {"terms": [...], "hooks": [...], "max_per_column": 1}
A cluster is flagged (c["lifestyle"] = True) when a headline matches a term and no political
hook (e.g. a policy or culture-war angle) saves it. Flagged stories never lead or enter Top
Stories and are capped at max_per_column in the columns (see aggregator.place). Not a score."""
import re
from . import private
NAME = "lifestyle"


def _has(text, words):
    return any(re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", text) for w in words)


def flag(title, terms, hooks):
    t = title.lower().replace("’", "'")
    return _has(t, terms) and not _has(t, hooks)


def compute(clusters, settings, ctx):
    cfg = private.load(ctx).get("lifestyle") or settings.get("lifestyle") or {}
    terms = [x.lower() for x in cfg.get("terms", [])]
    if not terms:
        return None
    hooks = [x.lower() for x in cfg.get("hooks", [])]
    n = 0
    for c in clusters:
        if sum(flag(s["title"], terms, hooks) for s in c["items"]) * 2 >= len(c["items"]):
            c["lifestyle"] = True; n += 1
    print(f"signal lifestyle: {n} clusters flagged")
    return None
