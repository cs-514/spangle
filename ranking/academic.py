"""Academic / explainer-style posts (Volokh Conspiracy by default): law-review notices, docket-name
headlines, legal retrospectives. Every such cluster gets c["academic"] = True, which routes its
headline through the rewrite queue (reason "academic": rewrite around the news hook, popular case
name, not the docket name). A cluster with no news hook in its headline and no saved override is
kept out of the lead and Top Stories (or dropped when "drop" is set) and scored `penalty`.
Configured via settings.json "academic"; weight "academic"."""
import re
from . import headline
NAME = "academic"

DEFAULT_HOOKS = ["trump", "biden", "scotus", "supreme court rules", "strikes down", "upholds", "blocks", "ruling",
                 "ruled", "sues", "lawsuit", "indicted", "charged", "arrested", "nominee", "congress", "senate",
                 "election", "border", "ban", "censorship", "fired", "today"]


def is_source(s, sources):
    src = s.get("source", "").lower()
    return any(x in src for x in sources) or any(x in s.get("link", "").lower() for x in ("reason.com/volokh",))


def hooked(title, hooks):
    t = title.lower().replace("’", "'")
    return any(re.search(r"(?<![a-z])" + re.escape(h) + r"(?![a-z])", t) for h in hooks)


def compute(clusters, settings, ctx):
    cfg = settings.get("academic") or {}
    if not cfg.get("enabled", True):
        return None
    sources = [s.lower() for s in cfg.get("sources", ["Volokh Conspiracy"])]
    hooks = [h.lower() for h in cfg.get("news_hooks", DEFAULT_HOOKS)]
    penalty, hooked_score = float(cfg.get("penalty", 0.2)), float(cfg.get("hooked_score", 0.6))
    try:
        ov = headline.overrides()
    except Exception:
        ov = {}
    has_ov = lambda s: bool(ov.get(s.get("link", "")) or ov.get(s.get("link", "").split("?", 1)[0]))
    out, n, demoted = {}, 0, 0
    for c in clusters:
        items = c["items"]
        if not items or not all(is_source(s, sources) for s in items):
            out[c["id"]] = 1.0  # mainstream coverage exists: it is news, not an academic post
            continue
        c["academic"] = True; n += 1
        if any(has_ov(s) or hooked(s["title"], hooks) for s in items):
            out[c["id"]] = hooked_score
            continue
        out[c["id"]] = penalty; demoted += 1
        c["lead_excluded"] = c["top_excluded"] = True
        if cfg.get("drop"):
            c["dropped"] = True
    print(f"signal academic: {n} flagged, {demoted} without a news hook kept out of lead/Top")
    return out
