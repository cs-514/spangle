"""Social engagement signal (replaces the old, never-configured social-counts stub).

Data: the ENGAGEMENT_DATA env var (a private Actions secret refreshed hourly by an off-repo routine):
  {"generated_at": ISO, "urls": [{"url", "score" 0..1, "text"}], "terms": [{"term", "score" 0..1, "kind"}]}
Per cluster, in order of strength:
  1. any item URL equals an engaged URL            -> that URL's score
  2. the engaged URL's slug or post text names the same story (strong title-term overlap) -> 0.8 x score
  3. a trending topic/term matches the headline     -> term score x term_boost (smaller)
The whole cluster gets the best match. Only aligned stories are eligible: no boost for excluded
(defeatist), in-party-favorable, left-leaning, lifestyle/celebrity or otherwise gated clusters, or
alignment below min_alignment. Settings (private config key "engagement", generic defaults here):
  url_boost, term_boost, min_alignment, stale_hours. Logs counts only, never URLs or terms."""
import json, os, re, urllib.parse
from datetime import datetime, timezone
from .util import tokens
from . import private, lean

NAME = "engagement"
DEFAULTS = {"url_boost": 1.0, "term_boost": 0.35, "min_alignment": 0.5, "stale_hours": 4}


def ucanon(u):
    """host + path, without www./m./amp. prefixes, AMP suffixes, query or trailing slash."""
    p = urllib.parse.urlparse((u or "").strip())
    host = p.netloc.lower()
    for pre in ("www.", "m.", "amp."):
        host = host.removeprefix(pre)
    path = re.sub(r"(/amp)?/?$", "", re.sub(r"\.amp$", "", p.path))
    return host + path


def slug_tokens(u):
    path = urllib.parse.urlparse(u if "://" in u else "https://" + u).path
    words = re.split(r"[-_/]+", path.lower())
    return set(tokens(" ".join(w for w in words if not w.isdigit() and not re.fullmatch(r"n?\d+|[a-z]?\d+[a-z]*", w))))


def load(env=None, now=None, stale_hours=4):
    raw = (env if env is not None else os.environ.get("ENGAGEMENT_DATA", "")).strip()
    if not raw:
        return None
    try:
        d = json.loads(raw)
    except Exception:
        print("  engagement data: invalid JSON")
        return None
    if not isinstance(d, dict):
        return None
    try:
        age = ((now or datetime.now(timezone.utc)) - datetime.fromisoformat(str(d["generated_at"]).replace("Z", "+00:00"))).total_seconds() / 3600
    except Exception:
        age = None
    if age is None or age > stale_hours:
        print(f"::warning::engagement data stale ({'unknown age' if age is None else f'{age:.1f}h old'}; limit {stale_hours}h)")
        return None
    return d


def config(ctx):
    cfg = dict(DEFAULTS)
    cfg.update(private.load(ctx).get("engagement") or {})
    return cfg


def eligible(c, settings, cfg):
    """Aligned, newsworthy clusters only (reuses the defeatism / faction / lean / gate flags)."""
    if c.get("excluded") or c.get("dropped") or c.get("lifestyle") or c.get("celebrity") or c.get("off_criteria"):
        return False
    sg = c.get("signals") or {}
    if sg.get("faction", 0.5) < 0.5:          # in-party-favorable (the faction signal demoted it)
        return False
    if sg.get("alignment", 0.5) < float(cfg.get("min_alignment", 0.5)):
        return False
    lc = lean.config(settings)
    leans = [lean.score(s, lc, outlet=s.get("source")) for s in c["items"]]
    if leans and sum(leans) / len(leans) < 0:  # left-leaning framing
        return False
    return True


def _overlap(a, b):
    if not a or not b:
        return 0.0
    n = len(a & b)
    return n / min(len(a), len(b)) if n >= 3 else 0.0


def match(c, data, cfg):
    """Best engagement value for a cluster (before eligibility)."""
    links = {ucanon(s["link"]) for s in c["items"]}
    tt = set().union(*(set(tokens(s.get("title") or "")) for s in c["items"]))
    best = 0.0
    for u in data.get("urls") or []:
        sc = float(u.get("score", 0))
        if sc <= best:
            continue
        if ucanon(u.get("url", "")) in links:
            best = sc; continue
        st = slug_tokens(u.get("url", "")) | set(tokens(u.get("text") or ""))
        if _overlap(tt, st) >= 0.6:
            best = max(best, 0.8 * sc)
    best *= float(cfg.get("url_boost", 1.0))
    head = set(tokens(c["items"][0].get("title") or ""))
    for t in data.get("terms") or []:
        tk = set(tokens(t.get("term") or ""))
        if not tk:
            continue
        # short trend names must appear whole; long topic names need half their terms (and >= 3) in the headline
        hit = tk <= head if len(tk) <= 2 else len(tk & head) >= max(3, 0.5 * len(tk))
        if hit:
            best = max(best, float(t.get("score", 0)) * float(cfg.get("term_boost", 0.35)))
    return min(1.0, best)


def compute(clusters, settings, ctx):
    cfg = config(ctx)
    data = load(stale_hours=float(cfg.get("stale_hours", 4)))
    if data is None:
        return None
    out, n_url, n_gated = {}, 0, 0
    for c in clusters:
        v = match(c, data, cfg)
        if v and not eligible(c, settings, cfg):
            v = 0.0; n_gated += 1
        out[c["id"]] = v
        n_url += v > 0
    print(f"signal engagement: {len(data.get('urls') or [])} engaged URLs, {len(data.get('terms') or [])} terms; "
          f"{n_url} clusters boosted, {n_gated} matched but not eligible")
    return out
