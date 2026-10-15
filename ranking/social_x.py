"""Optional X (Twitter) API v2 recent-counts signal. Disabled by default.
Runs only if settings.social.x.enabled is true AND an X_BEARER_TOKEN env var exists.
X API is pay-per-use (~$0.005 per counts request); max_requests caps spend per run."""
import os, urllib.parse
from .util import get_json, saturate
NAME = "x"

def compute(cands, settings, ctx):
    cfg = settings["social"]["x"]
    tok = os.environ.get("X_BEARER_TOKEN")
    if not cfg.get("enabled") or not tok:
        return None
    out, used = {}, 0
    for c in cands:
        if used >= cfg["max_requests"]:
            break
        q = urllib.parse.urlencode({"query": f'url:"{c["items"][0]["link"]}"', "granularity": "day"})
        try:
            d = get_json(f"https://api.x.com/2/tweets/counts/recent?{q}", 10, {"Authorization": f"Bearer {tok}"})
        except Exception:
            continue
        finally:
            used += 1
        out[c["id"]] = saturate(d.get("meta", {}).get("total_tweet_count", 0), cfg["saturation"])
    return out or None
