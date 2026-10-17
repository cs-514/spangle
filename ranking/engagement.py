"""Social engagement signal (replaces the old, never-configured social-counts stub).

Data: the ENGAGEMENT_DATA env var (a private Actions secret refreshed hourly by an off-repo routine):
  {"generated_at": ISO, "urls": [{"url", "score" 0..1, "text"}], "terms": [{"term", "score" 0..1, "kind"}]}
Per cluster, in order of strength:
  1. any item URL equals an engaged URL            -> that URL's score
  2. an engaged URL no cluster owns names the same story: strong term overlap AND same_story() AND no
     opposing action verbs (waives vs imposes)             -> 0.8 x score (Top Stories only, never the lead)
  3. a trending topic/term matches the headline     -> term score x term_boost (smaller)
The whole cluster gets the best match. Only aligned stories are eligible: no boost for excluded
(defeatist), in-party-favorable, left-leaning, lifestyle/celebrity or otherwise gated clusters, or
alignment below min_alignment. Settings (private config key "engagement", generic defaults here):
  url_boost, term_boost, min_alignment, stale_hours. Logs counts only, never URLs or terms."""
import json, os, re, urllib.parse
from datetime import datetime, timezone
from .util import tokens
from . import private, lean
from .story_match import same_story, opposed

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
    if sg.get("retreat", 1.0) < 1.0:          # retreat framing is never boosted
        return False
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


def _exact(c, data):
    links = {ucanon(s["link"]) for s in c["items"]}
    best, hit = 0.0, set()
    for u in data.get("urls") or []:
        k = ucanon(u.get("url", ""))
        if k in links:
            hit.add(k)
            best = max(best, float(u.get("score", 0)))
    return best, hit


def _fuzzy(c, u):
    """Engaged URL u names the same story as cluster c without being one of its links: strong term overlap,
    same_story() on every check, and no opposing action (waives vs imposes)."""
    text = u.get("text") or ""
    slug = " ".join(sorted(slug_tokens(u.get("url", ""))))
    tt = set().union(*(set(tokens(s.get("title") or "")) for s in c["items"]))
    if _overlap(tt, slug_tokens(u.get("url", "")) | set(tokens(text))) < 0.6:
        return False
    head = c["items"][0].get("title") or ""
    probe = {"title": text or slug, "link": u.get("url", "")}
    if not same_story(head, probe):
        return False
    return not any(opposed(s.get("title") or "", f"{text} {slug}") for s in c["items"])


def match(c, data, cfg, claimed=frozenset()):
    """(value, exact) for a cluster before eligibility. exact = best score of an engaged URL that is one of
    the cluster's own links (the only kind that counts toward the lead). Fuzzy matches (0.8x) only use URLs
    no cluster owns, so the boost goes to the cluster that actually contains the engaged article."""
    exact, _ = _exact(c, data)
    best = exact
    for u in data.get("urls") or []:
        sc = 0.8 * float(u.get("score", 0))
        if sc <= best or ucanon(u.get("url", "")) in claimed:
            continue
        if _fuzzy(c, u):
            best = sc
    ub = float(cfg.get("url_boost", 1.0))
    best, exact = best * ub, exact * ub
    head = set(tokens(c["items"][0].get("title") or ""))
    for t in data.get("terms") or []:
        tk = set(tokens(t.get("term") or ""))
        if not tk:
            continue
        # short trend names must appear whole; long topic names need half their terms (and >= 3) in the headline
        hit = tk <= head if len(tk) <= 2 else len(tk & head) >= max(3, 0.5 * len(tk))
        if hit and not opposed(c["items"][0].get("title") or "", t.get("term") or ""):
            best = max(best, float(t.get("score", 0)) * float(cfg.get("term_boost", 0.35)))
    return min(1.0, best), min(1.0, exact)


def compute(clusters, settings, ctx):
    cfg = config(ctx)
    data = load(stale_hours=float(cfg.get("stale_hours", 4)))
    if data is None:
        return None
    claimed = set()
    for c in clusters:
        claimed |= _exact(c, data)[1]
    out, n_url, n_gated, n_exact = {}, 0, 0, 0
    for c in clusters:
        v, ex = match(c, data, cfg, claimed)
        if v and not eligible(c, settings, cfg):
            v = ex = 0.0; n_gated += 1
        out[c["id"]] = v
        c["engagement_exact"] = ex   # only exact/cluster-member URL matches count toward the lead
        n_url += v > 0; n_exact += ex > 0
    print(f"signal engagement: {len(data.get('urls') or [])} engaged URLs, {len(data.get('terms') or [])} terms; "
          f"{n_url} clusters boosted ({n_exact} by their own URL), {n_gated} matched but not eligible")
    return out
