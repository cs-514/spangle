"""Reddit public JSON (keyless): score+comments of posts linking to the story URL
in the configured (conservative) subreddits only. Reddit often blocks datacenter IPs; degrades to None."""
from .util import get_json, canon, saturate
NAME = "reddit"

def compute(cands, settings, ctx):
    cfg = settings["social"]["reddit"]
    if not cfg.get("enabled"):
        return None
    links, ok = {}, 0
    for sub in cfg["subreddits"]:
        for listing in ("hot", "new"):
            try:
                d = get_json(f"https://www.reddit.com/r/{sub}/{listing}.json?limit=100", settings["social"]["timeout_seconds"]); ok += 1
            except Exception as e:
                print(f"  reddit r/{sub}/{listing}: {getattr(e, 'code', type(e).__name__)}")
                continue
            for ch in d.get("data", {}).get("children", []):
                p = ch.get("data", {})
                u = canon(p.get("url", ""))
                links[u] = max(links.get(u, 0), p.get("score", 0) + 2 * p.get("num_comments", 0))
    if not ok:
        return None
    return {c["id"]: saturate(max(links.get(canon(s["link"]), 0) for s in c["items"]), cfg["saturation"]) for c in cands}
