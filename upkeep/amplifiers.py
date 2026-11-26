"""Refresh the private amplifier items the build reads from the AMPLIFIER_ITEMS secret.

Which accounts are followed, on which services, and their weights are PRIVATE. They come only from the
AMPLIFIER_SOURCES secret (JSON, shape below) and are never printed, committed or written to the page.
This script logs counts only.

AMPLIFIER_SOURCES = {
  "max_age_hours": 48,                       # drop items older than this
  "skip_hosts": ["example.com", ...],        # links to these hosts are not news (video, shops, donations)
  "consensus": {"min_accounts": 2, "per_account_link_cap": 6, "saturation": 2.5},
  "feeds": [
    {"id": "a", "kind": "mastodon", "api": "https://<host>/api/v1", "accounts": {"<handle>": 1.0},
     "ids": {"<handle>": "<account id>"}, "consensus": true},
    {"id": "b", "kind": "x", "accounts": {"<handle>": 0.7}, "ids": {"<handle>": "<user id>"},
     "lookback_hours": 26, "max_posts": 25}
  ]
}

A feed that is blocked (e.g. HTTP 403 from GitHub's runners) or has no credentials keeps its previous
items (read back from the current AMPLIFIER_ITEMS secret); the build ages each item out on its own.
"x" feeds need the X_BEARER_TOKEN secret (X API, pay per use). Writing the result back to the
AMPLIFIER_ITEMS secret needs the SECRETS_PAT secret (GITHUB_TOKEN cannot write secrets); without it the
run only reports what it would have written.

  python -m upkeep.amplifiers [--push]
"""
import html, json, os, re, subprocess, sys, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
from .common import REPO, TMP, warn

UA = "Mozilla/5.0 (X11; Linux x86_64) Chrome/120 Safari/537.36"
DROP_PARAMS = re.compile(r"^(utm_|fbclid|gclid|mc_|ref$|src_|cmpid|smid|s$|t$)")
SOCIAL = ("x.com", "twitter.com", "t.co")
STOP = set("a an the and or of to in on for with at by from as is are was were be been it its this that these those after "
           "before over into about says said new how why what who will can not no his her their they he she we you your our "
           "has have had more than up out just".split())
LIMIT = 46000  # Actions secrets max out at 48 KB


def mask(values):
    """Ask the Actions runner to redact these values from all later log output (defense in depth)."""
    if os.environ.get("GITHUB_ACTIONS"):
        for v in values:
            if v and len(str(v)) > 2:
                print(f"::add-mask::{v}")


def get_json(url, headers=None, timeout=15):
    h = {"User-Agent": UA, "Accept": "application/json"}
    h.update(headers or {})
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout).read())


def expand(url):
    """Follow redirects (shorteners, tracking hops) to the article URL; strip tracking params."""
    final = url
    for method in ("HEAD", "GET"):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}, method=method), timeout=8) as r:
                final = r.geturl()
            break
        except urllib.error.HTTPError as e:
            final = e.geturl() or url
            if e.code not in (403, 405):
                break
        except Exception:
            break
    p = urllib.parse.urlparse(final)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query) if not DROP_PARAMS.match(k)]
    return urllib.parse.urlunparse(p._replace(query=urllib.parse.urlencode(q), fragment=""))


def skip(url, skip_hosts):
    host = urllib.parse.urlparse(url).netloc.lower()
    return not host or any(h in host for h in skip_hosts)


def tokens(t):
    return [w for w in re.findall(r"[a-z0-9']+", (t or "").lower()) if w not in STOP and len(w) > 2]


def canon(u):
    p = urllib.parse.urlparse(u or "")
    host = p.netloc.lower()
    for pre in ("www.", "m.", "amp."):
        host = host.removeprefix(pre)
    return host + re.sub(r"(/amp)?/?$", "", re.sub(r"\.amp$", "", p.path))


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_ts(ts):
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


# ---- feeds ----

def fetch_mastodon(feed, now, max_age, skip_hosts):
    """Mastodon-compatible API (public account statuses). Returns (items, n_ok, n_blocked)."""
    api = feed["api"].rstrip("/")
    ids = feed.setdefault("ids", {})
    items, ok, blocked = [], 0, 0
    for handle, weight in (feed.get("accounts") or {}).items():
        try:
            if handle not in ids:
                ids[handle] = get_json(f"{api}/accounts/lookup?acct={urllib.parse.quote(handle)}")["id"]
            statuses = get_json(f"{api}/accounts/{ids[handle]}/statuses?limit=40&exclude_replies=true")
        except Exception:
            blocked += 1
            continue
        ok += 1
        seen = set()
        for st in statuses:
            s = st.get("reblog") or st
            when = parse_ts(s.get("created_at") or st.get("created_at"))
            if not when or now - when > max_age:
                continue
            card = s.get("card") or {}
            urls = [(card["url"], card.get("title") or "")] if card.get("url") else []
            urls += [(html.unescape(h), card.get("title") or "") for h in re.findall(r'href="(https?://[^"]+)"', s.get("content") or "")]
            text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s.get("content") or ""))).strip()
            linked = False
            for u, title in urls:
                if skip(u, skip_hosts):
                    continue
                final = expand(u)
                if skip(final, skip_hosts) or final in seen:
                    continue
                seen.add(final)
                items.append({"url": final, "text": (title or text)[:300], "ts": iso(when), "weight": float(weight),
                              "_acct": handle, "_w": float(weight)})
                linked = True
            if not linked and len(tokens(text)) >= 6:  # a mention without a link counts toward consensus only
                items.append({"url": "", "text": text[:300], "ts": iso(when), "weight": 0.0, "mention": True,
                              "_acct": handle, "_w": float(weight)})
    return items, ok, blocked


def fetch_x(feed, now, max_age, skip_hosts, since=None):
    """X API v2 user timelines (needs X_BEARER_TOKEN). Returns (items, n_ok, n_blocked) or None without a token."""
    token = os.environ.get("X_BEARER_TOKEN", "").strip()
    if not token:
        return None
    auth = {"Authorization": f"Bearer {token}"}
    ids = feed.setdefault("ids", {})
    lookback = timedelta(hours=float(feed.get("lookback_hours", 26)))
    start = max(now - lookback, since) if since else now - lookback
    items, ok, blocked = [], 0, 0
    for handle, weight in (feed.get("accounts") or {}).items():
        try:
            if handle not in ids:
                ids[handle] = get_json(f"https://api.x.com/2/users/by/username/{urllib.parse.quote(handle)}", auth)["data"]["id"]
            q = urllib.parse.urlencode({"max_results": max(5, min(100, int(feed.get("max_posts", 25)))),
                                        "start_time": start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                        "tweet.fields": "created_at,entities"})
            posts = get_json(f"https://api.x.com/2/users/{ids[handle]}/tweets?{q}", auth).get("data") or []
        except Exception:
            blocked += 1
            continue
        ok += 1
        for p in posts:
            when = parse_ts(p.get("created_at"))
            if not when or now - when > max_age:
                continue
            text = re.sub(r"https://t\.co/\w+", "", p.get("text") or "")
            text = re.sub(r"^(RT )?(@\w+:?\s+)+", "", text).strip()
            for e in (p.get("entities") or {}).get("urls") or []:
                u = e.get("unwound_url") or e.get("expanded_url") or e.get("url") or ""
                if not u or "/photo/" in u or "/video/" in u:
                    continue
                final = expand(u) if urllib.parse.urlparse(u).netloc.lower() in ("t.co", "bit.ly", "trib.al", "ow.ly") else u
                host = urllib.parse.urlparse(final).netloc.lower().removeprefix("www.")
                if host in SOCIAL or skip(final, skip_hosts):
                    continue
                items.append({"url": final, "text": (e.get("title") or text)[:200], "ts": iso(when), "weight": float(weight)})
    return items, ok, blocked


def add_consensus(items, ccfg):
    """Stamp items with "consensus" (0..1) and "consensus_accounts": distinct accounts that linked or mentioned
    the same story (same canonical link, or >= 3 shared terms covering >= 50% of the shorter text). One
    prolific account is capped so it cannot fake consensus."""
    min_acc = int(ccfg.get("min_accounts", 2)); cap = int(ccfg.get("per_account_link_cap", 6))
    sat = float(ccfg.get("saturation", 2.5))
    n_by = {}
    for it in items:
        n_by[it["_acct"]] = n_by.get(it["_acct"], 0) + 1
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    by_key = {}
    for i, it in enumerate(items):
        k = canon(it["url"]) if it.get("url") else None
        if k:
            if k in by_key:
                parent[find(i)] = find(by_key[k])
            else:
                by_key[k] = i
    toks = [set(tokens(it.get("text"))) for it in items]
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = toks[i], toks[j]
            if a and b and find(i) != find(j):
                n = len(a & b)
                if n >= 3 and n / min(len(a), len(b)) >= 0.5:
                    parent[find(i)] = find(j)
    groups = {}
    for i in range(len(items)):
        groups.setdefault(find(i), []).append(i)
    n_cons = 0
    for g in groups.values():
        per = {}
        for i in g:
            a = items[i]["_acct"]
            per[a] = max(per.get(a, 0.0), items[i]["_w"] * min(1.0, cap / max(1, n_by[a])))
        score = min(1.0, sum(per.values()) / sat) if len(per) >= min_acc else 0.0
        for i in g:
            items[i]["consensus"] = round(score, 3)
            items[i]["consensus_accounts"] = len(per)
        n_cons += score > 0
    return n_cons


def previous_payload():
    raw = os.environ.get("AMPLIFIER_ITEMS", "").strip()
    try:
        d = json.loads(raw) if raw else {}
    except Exception:
        return {}
    return {"items": d} if isinstance(d, list) else d


def build_payload(src, prev, now=None, fetchers=None):
    """Fetch every feed and merge with the previous payload. Pure apart from the fetchers (testable)."""
    now = now or datetime.now(timezone.utc)
    fetchers = fetchers or {"mastodon": fetch_mastodon, "x": fetch_x}
    max_age = timedelta(hours=float(src.get("max_age_hours", 48)))
    skip_hosts = tuple(src.get("skip_hosts") or ())
    feeds = src.get("feeds") or []
    first_masto = next((f["id"] for f in feeds if f.get("kind") == "mastodon"), None)
    prev_items = prev.get("items") or []
    fetched = dict(prev.get("fetched") or {})
    out, blocked_feeds, report = [], 0, []
    for feed in feeds:
        fid, kind = feed["id"], feed.get("kind")
        old = [it for it in prev_items if isinstance(it, dict) and it.get("feed", first_masto) == fid]
        old = [it for it in old if (parse_ts(it.get("ts")) or now) >= now - max_age]
        fn = fetchers.get(kind)
        res = None
        if fn:
            if kind == "x":
                res = fn(feed, now, max_age, skip_hosts, parse_ts(fetched.get(fid)))
            else:
                res = fn(feed, now, max_age, skip_hosts)
        if res is None:
            report.append(f"feed {fid} ({kind}): not fetched (no credentials or unknown kind); kept {len(old)} previous items")
            out += old
            continue
        items, ok, blocked = res
        if ok == 0 and blocked:
            blocked_feeds += 1
            report.append(f"feed {fid} ({kind}): all {blocked} accounts blocked or failing; kept {len(old)} previous items")
            out += old
            continue
        if feed.get("consensus"):
            add_consensus(items, src.get("consensus") or {})
            items = [it for it in items if not it.get("mention") or it.get("consensus")]
        for it in items:
            it.pop("_acct", None); it.pop("_w", None)
            if not it.get("consensus"):
                it.pop("consensus", None); it.pop("consensus_accounts", None)
            it["feed"] = fid
        if kind == "x":  # incremental: keep earlier items still inside the window, new ones win on URL
            urls = {it["url"] for it in items}
            items += [it for it in old if it.get("url") not in urls]
        fetched[fid] = iso(now)
        report.append(f"feed {fid} ({kind}): {ok} accounts ok, {blocked} failing, {len(items)} items")
        out += items
    payload = {"generated_at": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "sources_blocked": blocked_feeds, "fetched": fetched, "items": out}
    for cut in (300, 200, 140, 100, 70):
        for it in out:
            it["text"] = (it.get("text") or "")[:cut]
        if len(json.dumps(payload, ensure_ascii=False).encode()) < LIMIT:
            break
    while len(json.dumps(payload, ensure_ascii=False).encode()) >= LIMIT and out:
        out.sort(key=lambda it: it.get("ts") or ""); out.pop(0)  # oldest first
    return payload, report


def push_secret(payload):
    pat = os.environ.get("SECRETS_PAT", "").strip()
    if not pat:
        warn("AMPLIFIER_ITEMS not updated: add a SECRETS_PAT secret (fine-grained token, this repo, Secrets: read and write)")
        return False
    env = dict(os.environ, GH_TOKEN=pat)
    r = subprocess.run(["gh", "secret", "set", "AMPLIFIER_ITEMS", "-R", REPO], input=json.dumps(payload, ensure_ascii=False),
                       text=True, capture_output=True, env=env)
    print("AMPLIFIER_ITEMS secret updated" if r.returncode == 0 else f"AMPLIFIER_ITEMS update FAILED (exit {r.returncode})")
    return r.returncode == 0


def main():
    raw = os.environ.get("AMPLIFIER_SOURCES", "").strip()
    if not raw:
        warn("AMPLIFIER_SOURCES secret not set: amplifier refresh skipped (the build keeps the current AMPLIFIER_ITEMS)")
        return 0
    try:
        src = json.loads(raw)
    except Exception:
        warn("AMPLIFIER_SOURCES is not valid JSON: amplifier refresh skipped")
        return 0
    terms = []
    for f in src.get("feeds") or []:
        terms += [f.get("api")] + list((f.get("accounts") or {}).keys()) + list((f.get("ids") or {}).values())
    mask([t for t in terms if t])
    prev = previous_payload()
    try:
        payload, report = build_payload(src, prev)
    except Exception as e:  # never let a traceback print private URLs
        warn(f"amplifier refresh failed ({type(e).__name__}); the build keeps the current AMPLIFIER_ITEMS")
        return 0
    for line in report:
        print(line)
    n_new = sum(1 for it in payload["items"] if it.get("ts") and it.get("feed"))
    print(f"amplifier items: {len(payload['items'])} total ({n_new} tagged), {payload['sources_blocked']} feed(s) blocked")
    with open(os.path.join(TMP, "amplifier_items.json"), "w") as f:
        json.dump(payload, f, ensure_ascii=False)
    if "--push" in sys.argv:
        push_secret(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
