#!/usr/bin/env python3
"""Spangle: fetch free RSS/Atom feeds, cluster and rank stories, render a static page."""
import json, os, re, html, sys, urllib.request, urllib.parse, concurrent.futures as cf
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET_TZ = ZoneInfo("America/New_York")  # NOT "ET": that name is xml.etree.ElementTree


def fmt_et(d):
    """Display-only: UTC datetime -> 'Oct 15, 4:13 PM' in US Eastern (DST-aware)."""
    return d.astimezone(ET_TZ).strftime("%b %-d, %-I:%M %p")
from email.utils import parsedate_to_datetime
import shutil
import ranking
from ranking.util import canon
from ranking import archive
from ranking import lead as lead_mod
from ranking import headline as headline_mod
from ranking import lean
import curators
from ranking import coverage
from ranking import opinion as opinion_mod

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120 Safari/537.36 Spangle/1.0"}
HERE = os.path.dirname(os.path.abspath(__file__))

FEED_UA = {"User-Agent": "Feedly/1.0 (+http://www.feedly.com/fetcher.html; compatible; Spangle/1.0)"}

# (name, url, opinion_only_feed[, headers[, options]])
# options: byline filter, max_age_hours override, substack_free_only
FEEDS = [
    ("The Federalist", "https://thefederalist.com/feed/", False),
    ("Daily Wire", "https://www.dailywire.com/feeds/rss.xml", False),
    ("Washington Examiner", "https://www.washingtonexaminer.com/feed/", False),
    ("Daily Signal", "https://www.dailysignal.com/feed/", False),
    ("Townhall", "https://townhall.com/feed/", False),
    ("PJ Media", "https://pjmedia.com/feed", False),
    ("RedState", "https://redstate.com/feed", False),
    ("Hot Air", "https://hotair.com/feed", False),
    ("The Blaze", "https://www.theblaze.com/feeds/feed.rss", False),
    ("Breitbart", "https://feeds.feedburner.com/breitbart", False),
    ("NY Post", "https://nypost.com/feed/", False),
    ("NY Post Opinion", "https://nypost.com/opinion/feed/", True),
    ("Fox News", "https://moxie.foxnews.com/google-publisher/latest.xml", False),
    ("Fox News Politics", "https://moxie.foxnews.com/google-publisher/politics.xml", False),
    ("Fox News Opinion", "https://moxie.foxnews.com/google-publisher/opinion.xml", True),
    ("Washington Free Beacon", "https://freebeacon.com/feed/", False),
    ("The American Conservative", "https://www.theamericanconservative.com/feed/", False),
    ("First Things", "https://www.firstthings.com/rss", False),
    # RCP's own commentary; lean filter (settings.lean_filter) keeps right-favorable pieces.
    ("RealClearPolitics", "https://www.realclearpolitics.com/articles/index.xml", True),
    ("Christian Post", "https://www.christianpost.com/rss", False),
    ("Daily Caller", "https://dailycaller.com/feed/", False),
    ("Just the News", "https://justthenews.com/rss.xml", False),
    # Accountability/investigations section (Drupal taxonomy term 3); the main feed carries only 20 items.
    ("Just the News", "https://justthenews.com/taxonomy/term/3/feed", False),
    ("SCOTUSblog", "https://www.scotusblog.com/feed/", False),
    ("Volokh Conspiracy", "https://reason.com/volokh/feed/", True),
    # Cato and Heritage return 403 to browser-like agents but serve feed readers.
    ("Cato Institute", "https://www.cato.org/rss/recent-opeds", True, FEED_UA),
    ("Cato Institute", "https://www.cato.org/rss/blog", True, FEED_UA),
    ("Heritage Foundation", "https://www.heritage.org/rss", False, FEED_UA),
    ("AEI", "https://www.aei.org/feed/", False, FEED_UA),
    # Further feeds (with byline / Substack options and tiers) come from the private config
    # key "private_feeds"; see private_feed_list(). Their names are never logged.
    ("Judicial Watch", "https://www.judicialwatch.org/feed/", False),
    # O’Keefe Media Group has RSS disabled; its public WordPress REST API lists posts. Paid
    # "full-access" posts (category 210) are skipped; the site 403s browser agents but serves feed readers.
    ("O’Keefe Media Group", "https://okeefemediagroup.com/wp-json/wp/v2/posts?per_page=20&_fields=date_gmt,link,title,excerpt,categories",
     False, FEED_UA, {"format": "wp_json", "exclude_categories": [210], "max_age_hours": 168}),
    # Imprimis (Hillsdale) is monthly: only the current/most recent issue (<= 35 days), exempt from the
    # 36h column limit, never lead/Top, and guaranteed one reserved column slot (see place()).
    ("Imprimis", "https://imprimis.hillsdale.edu/feed/", True, FEED_UA,
     {"max_age_hours": 840, "column_age_hours": 840, "no_front": True, "reserved_slot": True}),
    ("LifeZette", "https://www.lifezette.com/feed/", False),
    ("Courthouse News", "https://www.courthousenews.com/feed/", False),
    ("Not the Bee", "https://notthebee.com/feed", True),  # satirical commentary on real news
]

# Paywalled feeds: ingested ONLY when archive fallback is on. They count toward cross-outlet
# coverage and can appear only via an existing archive snapshot, never as a direct link.
PAYWALLED_FEEDS = [
    ("Wall Street Journal", "https://feeds.content.dowjones.io/public/rss/RSSUSnews", False),
    ("Wall Street Journal", "https://feeds.content.dowjones.io/public/rss/socialpoliticsfeed", False),
    ("New York Times", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", False),
    ("New York Times", "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml", False),
]

PAYWALL_DOMAINS = {
    # hard paywalls
    "wsj.com", "nytimes.com", "washingtonpost.com", "bloomberg.com", "ft.com",
    "theatlantic.com", "economist.com", "barrons.com", "newyorker.com",
    "latimes.com", "bostonglobe.com", "thetimes.co.uk", "businessinsider.com",
    "foreignaffairs.com", "theinformation.com",
    # registration, meter or premium walls (audited Oct 2026)
    "theepochtimes.com", "telegraph.co.uk", "newsweek.com", "spectator.co.uk",
    "thespectator.com", "spectator.com.au", "dailycaller.com",
}
# Per-article wall markers, matched case-insensitively against the raw HTML. Only specific
# phrases and structured-data flags are used; generic words like "subscribe" or "paywall"
# appear on many free pages (newsletter boxes, unused ad-tech mounts) and would give false positives.
WALL_PATTERNS = [re.compile(p) for p in [
    r'"isaccessibleforfree"\s*:\s*"?false',            # schema.org paywalled-content flag
    r"subscribe to (continue|keep) reading", r"subscribe now to (continue|keep) reading",
    r"subscribe to read the full (article|story)",
    r"create a free account to (continue|read|keep reading|unlock)",
    r"register (for free |now )?to (continue|read|keep) reading",
    r"(sign|log) in to (continue|keep) reading", r"(sign|log) in to read (the|this) (full )?(article|story)",
    r"this (article|story|content) is (only )?(available )?(exclusively )?(to|for) (paid )?(subscribers|members)",
    r"you('ve| have) reached (your )?(free )?(article|story) limit", r"you('ve| have) reached premium content",
    r"continue reading for \$\d", r"topic-premium",              # Blaze Media premium pieces (sailthru tag)
    r"sections:\s*\[[^\]]*'premium'", r"'post_sections':\s*\"\[[^\]]*'premium'",  # Blaze+ section in page context
    r"nr-plus|nrplus",                                         # National Review Plus pieces
    r'"audience"\s*:\s*"only_paid"',                          # Substack paid posts
]]


def wall_marker(body):
    b = body.lower()
    for p in WALL_PATTERNS:
        if p.search(b):
            return p.pattern
    return None


def domain(u):
    h = urllib.parse.urlparse(u).netloc.lower()
    return h[4:] if h.startswith("www.") else h

def is_paywalled_domain(u):
    d = domain(u)
    return any(d == p or d.endswith("." + p) for p in PAYWALL_DOMAINS)

def txt(el, *names):
    for n in names:
        x = el.find(n)
        if x is not None:
            if x.text and x.text.strip():
                return x.text.strip()
            if x.get("href"):
                return x.get("href")
    return ""

def parse_date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d

A = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/elements/1.1/}"

FEED_STATS = {"ok": 0, "fail": 0}
MIN_FEEDS_OK, MIN_LINKS = 20, 40  # build guard: never deploy a gutted page


def fetch(feed, settings=None):
    out = _fetch(feed, settings)
    FEED_STATS["ok" if out is not None else "fail"] += 1
    return out or []


def _fetch(feed, settings=None):
    name, url, op_feed = feed[:3]
    headers = feed[3] if len(feed) > 3 else UA
    opts = feed[4] if len(feed) > 4 else {}
    try:
        data = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=25).read()
        if opts.get("format") == "wp_json":
            return wp_json_items(json.loads(data), name, op_feed, opts, settings)
        root = ET.fromstring(data)
    except Exception as e:
        print(f"FEED FAIL {opts.get('log_name', name)}: {e!r}"[:160])
        return None
    out = []
    items = root.findall(".//item") or root.findall(f".//{A}entry")
    for it in items:
        title = html.unescape(re.sub(r"<[^>]+>", "", txt(it, "title", f"{A}title")))
        feed_link = txt(it, "link", f"{A}link")
        link = headline_mod.strip_tracking(feed_link)
        if not title or not link.startswith("http"):
            continue
        desc = re.sub(r"<[^>]+>", " ", txt(it, "description", f"{A}summary"))[:600]
        author = txt(it, f"{DC}creator", "author", f"{A}author/{A}name")
        cats = " ".join((c.text or c.get("term") or "") for c in it.findall("category") + it.findall(f"{A}category"))
        when = parse_date(txt(it, "pubDate", f"{DC}date", f"{A}updated", f"{A}published"))
        if opts.get("substack_free_only") and not substack_free(link):
            continue
        if opts.get("byline") and opts["byline"].lower() not in (author or "").lower():
            continue
        item = dict(max_age_hours=opts.get("max_age_hours"), column_age_hours=opts.get("column_age_hours"),
                    no_front=bool(opts.get("no_front")), reserved_slot=bool(opts.get("reserved_slot")),
                    title=title, link=link, feed_link=feed_link, desc=html.unescape(desc), author=author,
                    cats=cats, when=when, source=name, opinion=op_feed or "/opinion/" in link or "/commentary/" in link)
        if settings is not None and not lean.keep(item, name, settings, outlet=name, author=author):
            continue
        out.append(item)
    print(f"FEED OK {opts.get('log_name', name)}: {len(out)} items")
    return out

def wp_json_items(posts, name, op_feed, opts, settings=None):
    """Items from a WordPress REST API post list (for sites with RSS turned off)."""
    skip = set(opts.get("exclude_categories") or [])
    out = []
    for p in posts if isinstance(posts, list) else []:
        if skip & set(p.get("categories") or []):
            continue
        title = html.unescape(re.sub(r"<[^>]+>", "", (p.get("title") or {}).get("rendered", ""))).strip()
        link = p.get("link") or ""
        if not title or not link.startswith("http"):
            continue
        desc = html.unescape(re.sub(r"<[^>]+>", " ", (p.get("excerpt") or {}).get("rendered", "")))[:600]
        when = parse_date((p.get("date_gmt") or "") + "+00:00") if p.get("date_gmt") else None
        item = dict(max_age_hours=opts.get("max_age_hours"), title=title, link=link, desc=desc, author="", cats="",
                    when=when, source=name, opinion=op_feed)
        if settings is not None and not lean.keep(item, name, settings, outlet=name, author=""):
            continue
        out.append(item)
    print(f"FEED OK {opts.get('log_name', name)}: {len(out)} items")
    return out


def private_feed_list(cfg):
    """Feeds from the private config key "private_feeds":
    [{"name", "url", "opinion", "ua": "feed"|"browser", "options": {...}}]. Logged only as "private feed #n"."""
    out = []
    for i, f in enumerate(cfg.get("private_feeds") or [], 1):
        if not isinstance(f, dict) or not f.get("url") or not f.get("name"):
            continue
        opts = dict(f.get("options") or {}); opts["log_name"] = f"private feed #{i}"
        out.append((f["name"], f["url"], bool(f.get("opinion")), FEED_UA if f.get("ua") == "feed" else UA, opts))
    return out


def substack_free(link):
    """True only if Substack's public post API says the post is open to everyone."""
    p = urllib.parse.urlparse(link)
    slug = p.path.rstrip("/").split("/p/")[-1]
    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request(
            f"{p.scheme}://{p.netloc}/api/v1/posts/{slug}", headers=UA), timeout=10).read())
        return d.get("audience") == "everyone"
    except Exception:
        return False


WALL_CACHE = {}  # link -> True (free) / False (walled or gone), shared by every link check in one build


def link_free(x, settings):
    """A sibling about to replace a placed link must pass the same wall check as the original pick
    (a Blaze+ teaser once came back via a sibling swap after place() dropped it)."""
    if x.get("paywalled"):
        return False
    if x.get("archived") or not (settings or {}).get("placement", {}).get("check_links"):
        return True
    return url_ok(x)


def url_ok(s):
    if s["link"] in WALL_CACHE:
        if not WALL_CACHE[s["link"]]:
            s["paywalled"] = True
        return WALL_CACHE[s["link"]]
    ok = _url_ok(s)
    WALL_CACHE[s["link"]] = ok
    if not ok:
        s["paywalled"] = True  # every later swap path skips paywalled items
    return ok


def _url_ok(s):
    try:
        req = urllib.request.Request(s["link"], headers=UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            if r.status != 200:
                return False
            if is_paywalled_domain(r.geturl()):  # redirected onto a walled domain
                return False
            body = r.read(600000).decode("utf-8", "ignore")
        m = wall_marker(body)
        if m:
            print(f"  link dropped (wall marker {m!r}): {s['link'][:90]}")
        return m is None
    except urllib.error.HTTPError as e:
        # Some sites block bots on HEAD/GET but serve readers fine; only drop clear 4xx gone/paywall codes
        return e.code not in (401, 402, 404, 410)
    except Exception:
        return True  # network hiccup: keep, the feed itself is free

def norm(t):
    return re.sub(r"[^a-z0-9 ]", "", t.lower())[:70]

OUTLET = lambda s: s["source"].replace(" Politics", "").replace(" Opinion", "")


def apply_manual(out, settings):
    m = settings.get("manual_links", {})
    if not m.get("enabled"):
        return out
    try:
        with open(os.path.join(HERE, m.get("file", "manual_links.json"))) as f:
            links = json.load(f).get("links", [])
    except Exception as e:
        print(f"manual links: unreadable ({type(e).__name__})")
        return out
    now = datetime.now(timezone.utc)
    pos = {"lead": 0, "top": 1, "column": 1 + settings["placement"]["top_stories"]}
    n = 0
    for l in reversed(links):
        if is_paywalled_domain(l["url"]) and not l.get("archive_url"):
            print("manual links: skipped a walled-domain pin without archive_url")
            continue
        if l.get("expires") and parse_date(l["expires"]) and parse_date(l["expires"]) < now:
            continue
        s = dict(title=l["title"], link=l.get("archive_url") or l["url"], source=l.get("source", domain(l["url"])),
                 when=parse_date(l.get("time", "")) or now, opinion=bool(l.get("opinion")), archived="manual" if l.get("archive_url") else None)
        out = [x for x in out if x["link"] != s["link"]]
        s["manual"] = True
        out.insert(pos.get(l.get("position", "top"), 1), s); n += 1
    print(f"manual links: {n} pinned")
    return out


def best_item(c, tiers, default):
    return max(c["items"], key=lambda s: (tiers.get(s["source"], default), s["when"].timestamp() if s["when"] else 0))


def age_hours(s, now):
    return (now - s["when"]).total_seconds() / 3600 if s.get("when") else None


def age_limits(settings):
    a = settings.get("age_limits") or {}
    return float(a.get("lead_hours", 12)), float(a.get("top_hours", 18)), float(a.get("column_hours", 36))


def fits(s, slot, settings, now):
    """Age gate per slot. Undated items may appear only in the columns."""
    lead_h, top_h, col_h = age_limits(settings)
    age = age_hours(s, now)
    if slot == "column":
        return age is None or age < (s.get("column_age_hours") or col_h)
    if s.get("no_front"):
        return False
    return age is not None and age < (lead_h if slot == "lead" else top_h)


def place(clusters, settings, ctx):
    pl, tiers, d = settings["placement"], settings["sources"]["tiers"], settings["sources"]["default_tier"]
    now = ctx.get("now") or datetime.now(timezone.utc)
    count, picked, budget = {}, [], [0]
    if pl.get("lead_respects_exclusions", True):  # promote the best non-excluded cluster to the lead slot
        i = next((i for i, c in enumerate(clusters) if not c.get("lead_excluded")), 0)
        clusters = [clusters[i]] + clusters[:i] + clusters[i + 1:]
    clusters = lead_mod.order_for_lead(clusters, settings, ctx)
    clusters = [c for c in clusters if not c.get("dropped")]
    if clusters:  # retreat top_exclude: keep the lead, push flagged stories after everything else
        clusters = [clusters[0]] + [c for c in clusters[1:] if not c.get("top_excluded")] \
            + [c for c in clusters[1:] if c.get("top_excluded")]
    n_top, n_cols = pl["top_stories"], pl["columns"]
    want = 1 + n_top + pl["column_items"]
    life_cap = int((settings.get("lifestyle") or {}).get("max_per_column", 1)) * n_cols
    life_n = 0
    for c in clusters:
        if len(picked) >= want + 8:  # small surplus so age gating can still fill every slot
            break
        cap = pl["max_per_outlet_top"] if len(picked) < 1 + n_top else pl["max_per_outlet_total"]
        if c.get("lifestyle") and life_n >= life_cap:
            continue
        free = [x for x in c["items"] if not x.get("paywalled") and fits(x, "column", settings, now)]
        ar = settings.get("archive", {})
        dated = [x for x in c["items"] if x["when"]]
        orig = min(dated, key=lambda x: x["when"]) if dated else c["items"][0]
        if (orig.get("paywalled") or not free) and ar.get("enabled") and len(c["outlets"]) >= ar["min_outlets"] \
                and budget[0] < ar["max_lookups"] and fits(orig, "column", settings, now):
            p = orig if orig.get("paywalled") else next((x for x in c["items"] if x.get("paywalled")), None)
            if p is not None:
                budget[0] += 1
                link, prov = archive.find(p["link"], ar)
                if link:  # original scoop available via an existing snapshot
                    free = [dict(p, link=link, archived=prov, paywalled=False)]
        if not free:
            continue
        # freshest coverage first among equal tiers, so a live story shows its latest report
        alts = sorted([x for x in free if count.get(OUTLET(x), 0) < cap],
                      key=lambda x: (not x.get("truncated"), tiers.get(x["source"], d), x["when"].timestamp() if x["when"] else 0), reverse=True)
        s = next((x for x in alts[:2] if x.get("archived") or not pl["check_links"] or url_ok(x)), None)
        if s is None:
            continue
        s["outlets_n"] = len(c["outlets"])
        s["lifestyle"] = bool(c.get("lifestyle"))
        s["top_excluded"] = bool(c.get("top_excluded"))
        s["academic"] = bool(c.get("academic"))
        life_n += s["lifestyle"]
        picked.append(s); count[OUTLET(s)] = count.get(OUTLET(s), 0) + 1
    picked = apply_manual(picked, settings)
    manual = {id(x) for x in picked if x.get("manual")}
    ok_front = lambda x, slot: id(x) in manual or (not x.get("lifestyle") and not x.get("top_excluded") and fits(x, slot, settings, now))
    lead = next((x for x in picked if ok_front(x, "lead") and not x.get("opinion") and not x.get("truncated")), None)  # lead = reported news
    if lead is None:
        lead = next((x for x in picked if ok_front(x, "lead") and not x.get("truncated")), None)
    if lead is None:  # nothing fresh enough: the freshest dated, non-lifestyle story
        pool = [x for x in picked if x.get("when") and not x.get("lifestyle")] or picked
        lead = max(pool, key=lambda x: x["when"].timestamp() if x.get("when") else 0)
    rest = [x for x in picked if x is not lead]
    top = [x for x in rest if ok_front(x, "top")][:n_top]
    top_ids = {id(x) for x in top}
    rest = [x for x in rest if id(x) not in top_ids][:pl["column_items"]]
    # Reserved slot: a source flagged reserved_slot (e.g. monthly Imprimis) always gets its freshest
    # eligible piece into the columns, replacing the lowest-ranked column item if needed.
    for src in {x["source"] for c in clusters for x in c["items"] if x.get("reserved_slot")}:
        if any(x["source"] == src for x in [lead] + top + rest):
            continue
        cands = [x for c in clusters if not c.get("dropped") for x in c["items"]
                 if x["source"] == src and fits(x, "column", settings, now)]
        if cands:
            r = max(cands, key=lambda x: x["when"].timestamp() if x.get("when") else 0)
            r.setdefault("outlets_n", 1)
            if len(rest) >= pl["column_items"]:
                rest.pop()
            rest.append(r)
    life = [x for x in rest if x.get("lifestyle")][:life_cap]
    body = [x for x in rest if not x.get("lifestyle")]
    per = -(-len(body) // n_cols) if body else 0
    cols = [body[i * per:(i + 1) * per] for i in range(n_cols)]
    for i, x in enumerate(life):  # at most max_per_column per column, placed low
        cols[i % n_cols].append(x)
    return lead, top, cols


CSS = """.nw{white-space:nowrap}
:root{--ink:#121212;--muted:#5a5a5a;--rule:#dcdcdc;--red:#b00000;
--serif:"Source Serif 4",Georgia,"Times New Roman",serif;--display:"Playfair Display","Source Serif 4",Georgia,serif;
--sans:"Libre Franklin","Helvetica Neue",Arial,sans-serif}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);font-family:var(--serif);font-size:19px;line-height:1.45;-webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px 40px}
a{color:var(--ink);text-decoration:none} a:hover{text-decoration:underline;text-underline-offset:3px} a:visited{color:#4a4a6a}
header{text-align:center;border-bottom:3px double var(--ink);padding:18px 0 10px}
.mast{font-family:var(--display);font-weight:900;font-size:clamp(44px,8vw,84px);letter-spacing:.01em;line-height:1;margin:0}
.date{font-family:var(--sans);font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-top:8px}
.label{font-family:var(--sans);font-weight:800;font-size:12px;letter-spacing:.14em;text-transform:uppercase;border-top:1px solid var(--ink);padding-top:6px;margin:28px 0 4px}
.lead{text-align:center;padding:26px 0 22px}
.lead a{font-family:var(--display);font-weight:900;color:var(--red);font-size:clamp(28px,4.6vw,52px);line-height:1.12;display:inline;max-width:none;overflow:visible;text-overflow:clip;white-space:normal;hyphens:manual}
.lead a:visited{color:var(--red)}
.lead .meta{margin-top:12px}
.top ul{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:0 28px}
.top li{padding:10px 0 14px}
.top a{font-weight:700;font-size:22px;line-height:1.22;overflow:visible;text-overflow:clip;white-space:normal}
.cols{display:grid;grid-template-columns:repeat(3,1fr);gap:0 32px}
.col{border-left:1px solid var(--rule);padding-left:20px} .col:first-child{border-left:0;padding-left:0}
.col ul{list-style:none;margin:0;padding:0}
.col li{padding:11px 0;border-bottom:1px solid var(--rule)}
.col a{font-weight:600;font-size:19px;line-height:1.3;overflow:visible;text-overflow:clip;white-space:normal}
.lead a,.top a,.col a{text-wrap:pretty}
.meta{font-family:var(--sans);font-size:12.5px;color:var(--muted);margin-top:5px;letter-spacing:.02em}
.kicker{font-family:var(--sans);line-height:1;margin-bottom:4px}
.qt{font-family:var(--serif);font-style:italic;font-size:16.5px;line-height:1.4;color:var(--ink);margin-top:5px}
.tag{font-weight:800;text-transform:uppercase;letter-spacing:.1em;font-size:10.5px;color:var(--red);margin-right:2px}
footer{font-family:var(--sans);font-size:13px;color:var(--muted);border-top:3px double var(--ink);margin-top:36px;padding-top:14px;line-height:1.6}
@media(max-width:900px){.cols{grid-template-columns:1fr 1fr}.col:nth-child(3){grid-column:1/-1;border-left:0;padding-left:0}}
@media(max-width:620px){body{font-size:18px}.wrap{padding:0 16px 32px}.cols{grid-template-columns:1fr}.col{border-left:0;padding-left:0}.top a{font-size:21px}}
"""
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@400;600;800&family=Playfair+Display:wght@700;900'
         '&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&display=swap" rel="stylesheet">')


ICONS = ('<link rel="icon" href="favicon.ico" sizes="any"><link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png">'
         '<link rel="apple-touch-icon" href="apple-touch-icon.png"><link rel="manifest" href="manifest.webmanifest">'
         '<meta name="apple-mobile-web-app-title" content="Spangle"><meta name="theme-color" content="#0A3161">')


def suppressed(url, settings):
    """settings["suppress_urls"]: URLs (or sha256:<hex> keys, see headline.url_key) never shown."""
    sup = set(settings.get("suppress_urls") or [])
    return bool(sup) and any(u in sup or headline_mod.url_key(u) in sup for u in (url, url.split("?", 1)[0]))


from ranking.story_match import _STOP, _words, same_story, _GENERIC_CAPS  # noqa: E402 (shared with signals)


def verify_links(placed, clusters, ov=None):
    """Final guard on every placed story, whatever path set its link: the linked article must be the
    headline's own item, or pass same_story() against the headline. Otherwise relink to the item the
    headline came from. Overrides are keyed by URL; one whose text shares nothing with its article is logged."""
    ov = ov if ov is not None else headline_mod.overrides()
    items = {x["link"]: x for c in clusters for x in c["items"]}
    by_title = {}
    for c in clusters:
        for x in c["items"]:
            by_title.setdefault(x["title"], x)
    n = 0
    for s in placed:
        if s.get("quote_item") or s.get("manual"):
            continue
        url = s.get("canonical") or s["link"]
        if url in ov or url.split("?", 1)[0] in ov:
            tgt = items.get(url)
            if tgt and not _words(ov.get(url) or ov.get(url.split("?", 1)[0]) or "") & _words(f"{tgt['title']} {tgt.get('desc', '')} {url}"):
                print(f"  override check: headline shares no words with its article: {url[:90]}")
            continue
        head = s.get("original_title") or s.get("title")
        tgt = items.get(url)
        if tgt is None or tgt["title"] == head:
            continue
        if same_story(s.get("display") or head, tgt) or same_story(head, tgt):
            continue
        own = by_title.get(head)
        if own is not None and not own.get("paywalled"):
            print(f"  link reverted (different story): {(s.get('display') or head)[:60]} -> {own['source']}")
            s["link"], s["source"] = own["link"], own["source"]
            s.pop("canonical", None)
            n += 1
    return n


ORIGINATOR_MARGIN = 0.15  # a sibling must be this much cleaner (clutter_scores.json, 0-1) to beat the originator
_CITE = r"(?:first reported by|originally reported by|as reported by|reported by|according to|first reported|told|via|scoop by|exclusive(?:ly)? to)"


def originator(c):
    """The outlet that broke the story: the item other items credit ('first reported by X', 'according to X',
    a link to X's domain), else the earliest published item. Paywalled items are skipped."""
    items = [x for x in c["items"] if not x.get("paywalled")]
    if not items:
        return None
    def cites(x):
        name, dom = OUTLET(x).lower(), ranking.clutter.domain(x["link"])
        n = 0
        for y in items:
            if y is x or OUTLET(y) == OUTLET(x):
                continue
            hay = f"{y['title']} {y.get('desc', '')}".lower()
            if (dom and dom in hay) or re.search(_CITE + r"\s+(?:the\s+)?" + re.escape(name), hay):
                n += 1
        return n
    far = datetime.max.replace(tzinfo=timezone.utc)
    return max(items, key=lambda x: (cites(x), -(x["when"] or far).timestamp() if x.get("when") else float("-inf")))


def _apply_override(s, ov):
    """After a relink, a hand-written headline for the new link wins over the old link's display."""
    u = s["link"]
    disp = ov.get(u) or ov.get(u.split("?", 1)[0])
    if disp:
        s["display"] = headline_mod.clean(disp)[0] or disp
        s["override"] = True


def clean_links(lead, top, cols, clusters, settings, now, get=None):
    """Link the cleanest acceptable sibling (tier + clutter + freshness), keeping the chosen headline;
    then swap in a validated lighter variant (AMP/print) where one exists. Overrides, quotes and
    archived links are left alone. Returns stats."""
    cfg = settings.get("clean_links") or {}
    st = {"relinked": 0, "lighter": 0, "examples": []}
    if not cfg.get("enabled"):
        return st
    tiers, dt = settings["sources"]["tiers"], settings["sources"]["default_tier"]
    ov = headline_mod.overrides()
    by_id = {id(x): c for c in clusters for x in c["items"]}
    by_link = {x["link"]: c for c in clusters for x in c["items"]}
    slot = {id(lead): "lead", **{id(x): "top" for x in top}}
    placed = [lead] + top + [x for c in cols for x in c]
    for s in placed:
        if s.get("quote_item") or s.get("archived") or s["link"] in ov or s["link"].split("?", 1)[0] in ov:
            continue
        c = by_id.get(id(s)) or by_link.get(s["link"])
        if not c or len(c["items"]) < 2:
            continue
        sl = slot.get(id(s), "column")
        heads = [h for h in (s.get("display"), s.get("original_title"), s.get("title")) if h]
        cands = [x for x in c["items"] if not x.get("paywalled") and not x.get("truncated")
                 and fits(x, sl, settings, now)
                 and (x["link"] == s["link"] or any(same_story(h, x) for h in heads))]  # never pair a headline with another story
        if sl == "lead":
            cands = [x for x in cands if not x.get("opinion")] or cands
        if not cands:
            continue
        org = originator(c)
        margin = (settings.get("originator") or {}).get("margin", ORIGINATOR_MARGIN)
        cs = ranking.clutter.clean_score
        if org is not None and any(x is org for x in cands):
            cleaner = [x for x in cands if cs(x["link"]) - cs(org["link"]) >= margin]
            if s["link"] == org["link"] and not cleaner:
                continue  # already the originator and nothing clearly cleaner
            if s["link"] != org["link"] and not cleaner and cs(s["link"]) - cs(org["link"]) < margin \
                    and link_free(org, settings):
                st["examples"].append((s["source"], org["source"], s.get("display") or s["title"]))
                s["link"], s["source"] = org["link"], org["source"]
                if org.get("when"):
                    s["when"] = org["when"]
                _apply_override(s, ov)
                st["relinked"] += 1; st["originator"] = st.get("originator", 0) + 1
                continue
        cur = ranking.clutter.link_score(s, tiers, dt, now)
        cands = sorted(cands, key=lambda x: ranking.clutter.link_score(x, tiers, dt, now), reverse=True)
        best = next((x for x in cands if x["link"] == s["link"] or link_free(x, settings)), None)
        if best is None:
            continue
        if best["link"] != s["link"] and ranking.clutter.link_score(best, tiers, dt, now) - cur >= cfg.get("min_gain", 0.08):
            st["examples"].append((s["source"], best["source"], s.get("display") or s["title"]))
            s["link"], s["source"] = best["link"], best["source"]
            if best.get("when"):
                s["when"] = best["when"]
            _apply_override(s, ov)
            st["relinked"] += 1
    if cfg.get("lighter_variants"):
        todo = [s for s in placed if not s.get("quote_item") and (ranking.clutter.scores().get(ranking.clutter.domain(s["link"])) or {}).get("variant")]
        with cf.ThreadPoolExecutor(8) as ex:
            res = list(ex.map(lambda s: ranking.clutter.lighter(s["link"], **({"get": get} if get else {})), todo))
        for s, v in zip(todo, res):
            if v and v != s["link"]:
                s["canonical"], s["link"] = s["link"], v
                st["lighter"] += 1
    st["reverted"] = verify_links(placed, clusters, ov)
    print(f"clean links: {st['relinked']} relinked to a cleaner sibling, {st['lighter']} lighter variants, "
          f"{st['reverted']} mismatched links reverted")
    for a, b, h in st["examples"][:5]:
        print(f"  relink: {a} -> {b}: {h[:70]}")
    return st


FRAGMENT_GUIDANCE = ("Not a complete thought: write a headline with a subject and a finite verb, from the article. "
                     "Accepted headline-ese: a predicate participle ('Ex-Coach Arrested'), the headline future "
                     "('Trump to Sign'), a speaker colon ('Homan: ...'). Never a noun phrase, never an explainer cut "
                     "short ('Why Obama Admin Put X' needs 'on Terror Watch List').")
OBSCURE_ACRONYM_GUIDANCE = (
    "Use only acronyms a general national reader instantly recognizes (FBI, DOJ, CIA, ICE, GOP, SCOTUS, NATO, DOGE, "
    "NCAA). Replace an obscure one (school initials, local agencies, niche orgs) with a plain generic descriptor, "
    "possessive where natural ('College’s', 'State Agency', 'Union'), and keep the headline the same length or "
    "shorter. Example: 'Ex-SJSU Coach Sues over ‘Trump Lover’ Barbs' -> 'College’s Ex-Coach Sues over ‘Trump Lover’ Barbs'.")

IMPRIMIS_GUIDANCE = (
    "Imprimis titles read like lecture/course titles ('The X of Y', 'Understanding Z'). Read the essay's opening "
    "paragraphs, find its thesis and stance, and write a short (3-6 words), punchy, thesis-carrying headline with "
    "1-2 sharp evaluative words (alarming, disturbing, persistent, failed, dangerous, forgotten ...) and no articles, "
    "faithful to the argument. VARY THE FORM and pick whatever is punchiest: possessive ('Socialism’s Persistent, "
    "Disturbing Rise'), parallel fragments, a verb-driven claim, a question, or a quoted line. "
    "Example: 'The Rise of Democratic Socialism' -> 'Socialism’s Persistent, Disturbing Rise'.")

ACADEMIC_GUIDANCE = ("Academic/explainer post: rewrite around the news hook, using the case's popular name or the "
                     "issue, never the docket name (e.g. 'Matal v. Tam' -> 'Slants' case): '‘Slants’ Case Backstory: "
                     "<punchy finding>'. If there is no current, newsworthy hook, leave it unrewritten; it stays out "
                     "of the lead and Top Stories.")


def decorate_headlines(lead, top, cols, clusters, settings=None, now=None, ctx=None):
    """For each placed story: prefer a non-bland, under-max-length sibling headline
    (and its URL); always apply deterministic style cleanup (never truncate);
    queue a rewrite when every candidate is bland OR the chosen display is still
    over max length. Returns (lead, top, cols, stats)."""
    by_id = {id(s): c for c in clusters for s in c["items"]}
    by_link = {s["link"]: c for c in clusters for s in c["items"]}
    stats = {"kept": 0, "swapped": 0, "queued_bland": 0, "queued_too_long": 0, "styled": 0, "override": 0,
             "shortened": 0, "queue": []}
    slot = {id(lead): "lead", **{id(x): "top" for x in top}}
    placed = [lead] + top + [s for col in cols for s in col]
    sty = headline_mod.style()
    ov = headline_mod.overrides()
    fmem = ranking.faction.members(ctx) if ctx is not None else []

    def candidates(s):
        c = by_id.get(id(s)) or by_link.get(s["link"])
        return list(c["items"]) if c else [s]

    def prep(x):
        cleaned, changed = headline_mod.clean(x["title"], sty)
        cut = bool(x.get("truncated")) or headline_mod.truncated(x["title"], x["link"])
        return cleaned, changed, headline_mod.needs_rewrite(cleaned, sty) or cut, \
            headline_mod.too_long(cleaned, sty)

    for s in placed:
        url, base = s["link"], s["link"].split("?", 1)[0]
        if (url in ov and ov[url]) or (base in ov and ov[base]):
            disp = ov.get(url) or ov[base]
            cleaned, _ = headline_mod.clean(disp, sty)
            s["display"], s["original_title"] = cleaned or disp, s["title"]
            stats["override"] += 1
            continue
        sl = slot.get(id(s), "column")
        # a sibling may replace the story only if it also passes the slot's age limit
        cands = [x for x in candidates(s) if not x.get("paywalled")
                 and (x is s or settings is None or fits(x, sl, settings, now))] or [s]
        cl = by_id.get(id(s)) or by_link.get(s["link"])
        if cl and cl.get("faction_defect") and fmem:  # betrayal story: feature the other side, not the defector
            names = lambda x: re.search(r"\b(" + "|".join(map(re.escape, fmem)) + r")\b", x["title"].lower().replace("’", "'"))
            cands = [x for x in cands if not names(x)] or cands
        if sl == "lead":  # the lead stays reported news: only non-opinion siblings when any exist
            cands = [x for x in cands if not x.get("opinion")] or cands
        org = originator({"items": cands})
        if org is not None:
            cs = ranking.clutter.clean_score
            margin = ((settings or {}).get("originator") or {}).get("margin", ORIGINATOR_MARGIN)
            if prep(org)[2] or any(cs(x["link"]) - cs(org["link"]) >= margin and not prep(x)[2] for x in cands):
                org = None  # bland originator headline, or a clearly cleaner sibling: normal choice
        ranked = []
        for x in cands:
            cleaned, changed, bland, long = prep(x)
            # prefer: not bland, not too long, shorter, newer
            ranked.append(((0 if bland else 2) + (1 if x is org else 0), (0 if x.get("opinion") else 1), (0 if long else 1), -len(cleaned),
                           x.get("when").timestamp() if x.get("when") else 0, x, cleaned, changed, bland, long))
        ranked.sort(reverse=True)
        # lazily wall-check siblings that would outrank the placed link; drop the walled ones
        bad = set()
        for r in ranked:
            if r[5] is s or r[5]["link"] == s["link"] or link_free(r[5], settings):
                break
            bad.add(id(r[5]))
        ranked = [r for r in ranked if id(r[5]) not in bad] or ranked
        _a, _o, _b, _c, _d, best, cleaned, changed, bland, long = ranked[0]
        all_bland = all(r[8] for r in ranked)
        all_long = all(r[9] for r in ranked)
        # if best is long but a shorter non-bland sibling exists, pick that
        if long:
            shorter = [r for r in ranked if not r[8] and not r[9]
                       and (r[5] is s or r[5]["link"] == s["link"] or link_free(r[5], settings))]
            if shorter:
                _a, _o, _b, _c, _d, best, cleaned, changed, bland, long = shorter[0]
        if best["link"] != s["link"]:
            s["link"], s["title"], s["source"], s["opinion"] = best["link"], best["title"], best["source"], bool(s.get("opinion") or best.get("opinion"))
            if best.get("when"):
                s["when"] = best["when"]
            stats["swapped"] += 1
        else:
            stats["kept"] += 1
        if changed:
            stats["styled"] += 1
        s["display"], s["original_title"] = cleaned, best["title"]
        fu, fb = s["link"], s["link"].split("?", 1)[0]
        if ov.get(fu) or ov.get(fb):  # the swapped-in sibling has a hand-written headline
            s["display"] = headline_mod.clean(ov.get(fu) or ov[fb], sty)[0]
            stats["override"] += 1
            continue
        if headline_mod.contentless(cleaned):
            # siblings with real content beat a bare name / fragment
            alt = next((r for r in ranked if not headline_mod.contentless(r[6])
                        and (r[5] is s or r[5]["link"] == s["link"] or link_free(r[5], settings))), None)
            if alt:
                best, cleaned = alt[5], alt[6]
                s["link"], s["title"], s["source"] = best["link"], best["title"], best["source"]
                s["display"], s["original_title"] = cleaned, best["title"]
            else:
                pt = headline_mod.page_title(s["link"])
                ptc = headline_mod.clean(pt, sty)[0] if pt else ""
                if ptc and not headline_mod.contentless(ptc):
                    s["display"] = ptc
                else:
                    s["drop"] = True  # never show a bare-name headline
                    stats.setdefault("dropped_contentless", 0)
                    stats["dropped_contentless"] = stats["dropped_contentless"] + 1
                    stats["queue"].append({"url": s["link"], "title": best["title"], "cleaned": cleaned,
                                           "reason": "contentless", "page_title": pt,
                                           "siblings": [{"url": x["link"], "title": x["title"]} for x in cands]})
                    continue
        if s.get("source") == "Imprimis":  # lecture-style titles: fallback recast now, punchy rewrite queued
            s["display"] = headline_mod.imprimis_recast(cleaned) or cleaned
            stats["queued_imprimis"] = stats.get("queued_imprimis", 0) + 1
            stats["queue"].append({"url": best["link"], "title": best["title"], "cleaned": cleaned,
                                   "fallback": s["display"], "reason": "imprimis", "framing": IMPRIMIS_GUIDANCE,
                                   "excerpt": (best.get("desc") or "")[:600],
                                   "siblings": [{"url": x["link"], "title": x["title"]} for x in cands]})
            continue
        if s.get("academic"):  # academic/explainer post: always rewrite around the news hook
            stats["queued_academic"] = stats.get("queued_academic", 0) + 1
            stats["queue"].append({"url": best["link"], "title": best["title"], "cleaned": cleaned,
                                   "reason": "academic", "framing": ACADEMIC_GUIDANCE,
                                   "siblings": [{"url": x["link"], "title": x["title"]} for x in cands]})
            continue
        # queue only when still a problem after sibling pick
        if all_bland or (bland and not any(not r[8] for r in ranked)):
            stats["queued_bland"] += 1
            stats["queue"].append({"url": best["link"], "title": best["title"], "cleaned": cleaned,
                                   "reason": "bland", **({"framing": "feature the opponent; frame as betrayal"} if cl and cl.get("faction_defect") else {}),
                                   "siblings": [{"url": x["link"], "title": x["title"]} for x in cands]})
        elif headline_mod.too_long(s["display"], sty) and \
                not headline_mod.too_long(headline_mod.shorten(s["display"], sty), sty):
            s["display"] = headline_mod.shorten(s["display"], sty)  # safe trims only, never truncation
            stats["shortened"] += 1
        elif long or (all_long and not any(not r[9] for r in ranked)):
            # display stays full (no truncation); ask for a trim rewrite
            stats["queued_too_long"] += 1
            stats["queue"].append({"url": best["link"], "title": best["title"], "cleaned": cleaned,
                                   "reason": "too_long", "chars": len(cleaned), "words": len(cleaned.split()),
                                   "siblings": [{"url": x["link"], "title": x["title"]} for x in cands]})
        why = headline_mod.incomplete(s["display"], best["title"])
        if why and not any(q["url"] == best["link"] for q in stats["queue"]):
            # verbless / cut-off fragment (e.g. a trim that dropped the verb): ask for a real rewrite
            stats["queued_fragment"] = stats.get("queued_fragment", 0) + 1
            stats["queue"].append({"url": best["link"], "title": best["title"], "cleaned": s["display"],
                                   "reason": "fragment", "fragment_kind": why, "framing": FRAGMENT_GUIDANCE,
                                   "siblings": [{"url": x["link"], "title": x["title"]} for x in cands]})
    queued = {q["url"] for q in stats["queue"]}
    for s in placed:  # every displayed headline (source, shortened or override) must be a complete thought
        if s.get("drop") or s.get("quote_item") or not s.get("display") or s["link"] in queued:
            continue
        is_ov = bool(ov.get(s["link"]) or ov.get(s["link"].split("?", 1)[0]))
        why = headline_mod.incomplete(s["display"], None if is_ov else s.get("original_title"))
        if why == "no_finite_verb" and s.get("source") == "Imprimis":
            why = None  # essays keep their possessive / parallel-fragment form (IMPRIMIS_GUIDANCE)
        if why:
            stats["queued_fragment"] = stats.get("queued_fragment", 0) + 1
            c = by_id.get(id(s)) or by_link.get(s["link"])
            stats["queue"].append({"url": s["link"], "title": s.get("original_title") or s["title"], "cleaned": s["display"],
                                   "reason": "fragment", "fragment_kind": why, "override": is_ov, "framing": FRAGMENT_GUIDANCE,
                                   "siblings": [{"url": x["link"], "title": x["title"]} for x in (c["items"] if c else [s])]})
            queued.add(s["link"])
    for s in placed:  # obscure acronyms (school initials, niche orgs): queue for a plain-descriptor rewrite
        if s.get("drop") or s.get("quote_item") or not s.get("display"):
            continue
        obs = headline_mod.obscure_acronyms(s["display"], sty)
        if obs:
            stats["queued_obscure_acronym"] = stats.get("queued_obscure_acronym", 0) + 1
            c = by_id.get(id(s)) or by_link.get(s["link"])
            sibs = [{"url": x["link"], "title": x["title"]} for x in (c["items"] if c else [s])]
            stats["queue"].append({"url": s["link"], "title": s.get("original_title") or s["title"], "cleaned": s["display"],
                                   "reason": "obscure_acronym", "acronyms": obs, "framing": OBSCURE_ACRONYM_GUIDANCE,
                                   "siblings": sibs})
    dcfg = ranking.private.load(ctx).get("defeatism") if ctx is not None else None
    for s in placed:
        if dcfg and s.get("display") and ranking.defeatism.classify(s["display"], dcfg) == "exclude" \
                and ranking.defeatism.classify(s["title"], dcfg) != "exclude":
            s["display"] = headline_mod.clean(s["title"], sty)[0]  # never let a rewrite add defeatist framing
            stats["defeatist_reverted"] = stats.get("defeatist_reverted", 0) + 1
    print(f"headlines: kept {stats['kept']}, swapped {stats['swapped']}, "
          f"queued_bland {stats['queued_bland']}, queued_too_long {stats['queued_too_long']}, "
          f"styled {stats['styled']}, overrides {stats['override']}, shortened {stats['shortened']}, "
          f"fragments {stats.get('queued_fragment', 0)}, obscure_acronyms {stats.get('queued_obscure_acronym', 0)}")
    try:
        with open(os.path.join(HERE, "..", "rewrite_queue.json"), "w") as f:
            json.dump({"generated": datetime.now(timezone.utc).isoformat(), "items": stats["queue"]}, f, indent=1)
    except Exception as ex:
        print(f"rewrite queue write skipped: {type(ex).__name__}")
    top = [s for s in top if not s.get("drop")]
    cols = [[s for s in c if not s.get("drop")] for c in cols]
    if stats.get("dropped_contentless"):
        print(f"headlines: dropped {stats['dropped_contentless']} contentless (queued for rewrite)")
    return lead, top, cols, stats


_SITE_NAME = re.compile(r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']{2,40})["\']', re.I)


def display_outlets(items):
    """No raw domains on the page: map known hosts, else og:site_name, else a prettified host label."""
    for s in items:
        src = s.get("source") or ""
        if s.get("quote_item") or "." not in src or " " in src:
            continue
        name = curators.outlet_name("https://" + src)
        if "." in name:
            try:
                body = urllib.request.urlopen(urllib.request.Request(s["link"], headers=UA), timeout=8).read(200000).decode("utf-8", "ignore")
                m = _SITE_NAME.search(body)
                name = html.unescape(m.group(1)).strip() if m else ""
            except Exception:
                name = ""
            name = name or curators.pretty_host(src)
        s["source"] = name


def load_daily_quote(filename="quote_of_the_day.json", today=None, bank_file="qotd_bank.json"):
    """Today's quote. If the file is missing, invalid, or dated another day (the box routine did not
    run), fall back to a deterministic pick from the public, primary-source-verified bank, so a stale
    quote is never shown."""
    today = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        with open(os.path.join(HERE, filename)) as f:
            q = json.load(f)
        if q.get("quote") and q.get("author") and q.get("date") == today:
            return q
        print(f"quote of the day: file dated {q.get('date')!r}, not {today}; using bank fallback")
    except Exception:
        print("quote of the day: file unreadable; using bank fallback")
    return fallback_quote(today, bank_file)


def quote_word_limit(q):
    """60 words (fair use) for copyrighted works; public-domain texts may run longer to keep the payoff."""
    return 90 if q.get("public_domain") else 60


def weighted_pick(items, h, scale=1000):
    """Deterministic pick by hash h where each item counts its "weight" (default 1); guest entries carry
    weight < 1 so they appear only occasionally."""
    w = [max(0, int(round(float(q.get("weight", 1)) * scale))) for q in items]
    total = sum(w)
    if not total:
        return items[h % len(items)]
    r = h % total
    for q, wi in zip(items, w):
        if r < wi:
            return q
        r -= wi
    return items[-1]


def fallback_quote(today, bank_file="qotd_bank.json"):
    try:
        with open(os.path.join(HERE, bank_file)) as f:
            raw = json.load(f)
        author_w = raw.get("author_weights") or {}
        bank = [q for q in raw["quotes"] if q.get("verified") and q.get("source_type") in ("primary", "column")
                    and q.get("status") not in ("retired", "low_impact")
                    and len(q["quote"].split()) <= quote_word_limit(q)]
    except Exception:
        return None
    if not bank:
        return None
    import hashlib
    # effective weight: guest weight x author rotation weight x impact (1-5, scaled so 4 = 1.0)
    weighted = [dict(q, weight=float(q.get("weight", 1)) * float(author_w.get(q["id"].split("-")[0], 1))
                     * float(q.get("impact", 4)) / 4) for q in bank]
    q = dict(weighted_pick(weighted, int(hashlib.sha256(today.encode()).hexdigest(), 16)))
    words = q["quote"].replace("—", " ").replace(";", ".").split()
    # A curated bank headline is final (the news pipeline would turn "One Omen" into "1 Omen" or drop
    # "His"); only a headline derived from the quote's opening words goes through clean().
    q["headline"] = (q.get("headline") or "").strip() or headline_mod.clean(" ".join(words[:8]).rstrip(".,;:"))[0]
    q["date"] = today
    return q


REPORTER_CITE = re.compile(
    r"\s*,?\s*\b\d+\s+(?:U\.\s?S\.|S\.\s?Ct\.|L\.\s?Ed\.(?:\s?2d)?|F\.(?:\s?(?:2d|3d|4th))?|F\.\s?Supp\.(?:\s?(?:2d|3d))?"
    r"|U\.S\.\s?App\.\s?D\.C\.|Cranch|Wheat\.|Pet\.|How\.)\s+\d+(?:\s*,\s*\d+)?")
CASE = re.compile(r"\b(v\.|vs\.|In re|Ex parte)\s", re.I)


def judicial_source(q):
    """'Author, <i>Case Name</i> (Year)' for court opinions; None when the work isn't a case.
    Reporter citations (554 U.S. 570, F.2d ...) and (dissenting)/(concurring) never display."""
    work = (q.get("work") or "").strip()
    if not CASE.search(work):
        return None
    blob = f"{work} {q.get('locator') or ''} {q.get('year') or ''}"
    years = re.findall(r"\b(1[789]\d\d|20\d\d)\b", REPORTER_CITE.sub(" ", blob))
    case = re.sub(r"\s*\((?:1[789]\d\d|20\d\d)\)\s*$", "", REPORTER_CITE.sub("", work)).strip(" ,")
    year = years[0] if years else ""
    text = f"{q['author']}, {case}" + (f" ({year})" if year else "")
    markup = f"{html.escape(q['author'])}, <i>{html.escape(headline_mod.smartquotes(case))}</i>" + (f" ({year})" if year else "")
    return text, markup


def quote_as_story(q):
    """Turn quote_of_the_day.json into a column item shaped like any other story."""
    work = (q.get("work") or "").strip()
    loc = REPORTER_CITE.sub("", (q.get("locator") or q.get("chapter_or_page") or "")).strip(" ,")
    js = judicial_source(q)
    if js:
        source = js[0]
    elif work and loc:
        source = f"{q['author']} · {work}, {loc}"
    elif work:
        source = f"{q['author']} · {work}"
    else:
        source = q["author"]
    quote_text = q["quote"].strip()
    headline = (q.get("headline") or "").strip()
    if not headline:
        headline = quote_text if len(quote_text.split()) <= 12 else " ".join(quote_text.split()[:10])
    link = (q.get("verification_url") or "").strip() or "#"
    return {
        "title": headline,
        "display": headline,
        "original_title": quote_text,
        "link": link,
        "source": source,
        "when": None,
        "opinion": False,
        "quote_item": True,
        "source_html": js[1] if js else None,
        "quote_text": quote_text,
        "outlets_n": 1,
    }


def _wrap_lines(text, cpl):
    """Lines a headline wraps to at ~cpl characters per line (greedy word wrap, like the browser)."""
    lines, cur = 1, 0
    for w in [x for x in (text or "").split(" ") if x]:  # split on plain spaces only: U+00A0 glues words
        if cur and cur + 1 + len(w) > cpl:
            lines, cur = lines + 1, len(w)
        else:
            cur += (1 if cur else 0) + len(w)
    return lines


def item_height(s, cfg):
    """Estimated rendered height (px) of a column item at desktop width: padding + wrapped headline
    (news items carry no source line)."""
    cfg = cfg or {}
    return cfg.get("item_base_px", 24) + cfg.get("line_px", 27) * _wrap_lines(no_orphan_text(s.get("display") or s.get("title")), cfg.get("chars_per_line", 40))


def qotd_height(story, cfg):
    """Estimated QOTD block height: kicker + attribution + padding, the wrapped headline, and the italic
    quote text (narrower glyphs, ~48 characters per line, 23px lines). Falls back to qotd_px."""
    cfg = cfg or {}
    if not story:
        return cfg.get("qotd_px", 268)
    return (cfg.get("qotd_base_px", 80) + cfg.get("qotd_headline_line_px", 24.7) * _wrap_lines(no_orphan_text(story.get("display") or story.get("title")), cfg.get("chars_per_line", 40))
            + cfg.get("qotd_text_line_px", 23.1) * _wrap_lines(story.get("quote_text") or "", cfg.get("qotd_text_chars_per_line", 48)))


def balance_columns(cols, settings, quote=None):
    """Re-deal column items by estimated rendered height, not count: each item, in rank order, goes to the
    currently shortest column. Lifestyle filler stays last; the QOTD block (inserted later into its fixed
    column) is pre-counted in that column. Rank order still reads roughly top-down across the row."""
    cfg = (settings.get("placement") or {}).get("column_balance") or {}
    if cfg.get("enabled") is False or not cols:
        return cols
    n = len(cols)
    flat = [x for c in cols for x in c if not x.get("lifestyle")] + [x for c in cols for x in c if x.get("lifestyle")]
    h = [0.0] * n
    q = (settings.get("placement") or {}).get("quote_of_the_day") or {}
    if q.get("enabled", True) is not False:
        h[max(0, min(int(q.get("column", 1)), n - 1))] += qotd_height(quote, cfg)
    out = [[] for _ in range(n)]
    for x in flat:
        i = min(range(n), key=lambda k: (h[k], k))
        out[i].append(x); h[i] += item_height(x, cfg)
    # refine: swap one pair (or move one item) among the lowest few items of the tallest and shortest
    # columns when that narrows the spread; lowest-ranked items only, so the reading order barely changes
    k = int(cfg.get("refine_window", 6))
    for _ in range(int(cfg.get("refine_passes", 4))):
        hi, lo = max(range(n), key=lambda j: h[j]), min(range(n), key=lambda j: h[j])
        if hi == lo:
            break
        spread, best = h[hi] - h[lo], None
        for a in range(max(0, len(out[hi]) - k), len(out[hi])):
            ha = item_height(out[hi][a], cfg)
            if not out[hi][a].get("lifestyle") and abs((h[hi] - ha) - (h[lo] + ha)) < spread:
                spread, best = abs((h[hi] - ha) - (h[lo] + ha)), (a, None)
            for b in range(max(0, len(out[lo]) - k), len(out[lo])):
                d = ha - item_height(out[lo][b], cfg)
                if d > 0 and abs((h[hi] - d) - (h[lo] + d)) < spread:
                    spread, best = abs((h[hi] - d) - (h[lo] + d)), (a, b)
        others = [h[j] for j in range(n) if j not in (hi, lo)]
        if best is None:
            break
        a, b = best
        x = out[hi][a]
        if b is None:
            out[hi].pop(a); out[lo].append(x); dh = item_height(x, cfg)
        else:
            y = out[lo][b]; out[hi][a], out[lo][b] = y, x; dh = item_height(x, cfg) - item_height(y, cfg)
        h[hi] -= dh; h[lo] += dh
    return out


def inject_quote(cols, settings):
    """Insert the daily quote into a column at placement.quote_of_the_day.{column,index}."""
    slot = (settings.get("placement") or {}).get("quote_of_the_day") or {}
    if slot.get("enabled") is False:
        return cols
    q = load_daily_quote("quote_of_the_day.json")
    if not q or not cols:
        return cols
    story = quote_as_story(q)
    col_i = int(slot.get("column", 1))
    idx = int(slot.get("index", 7))
    col_i = max(0, min(col_i, len(cols) - 1))
    idx = max(0, min(idx, len(cols[col_i])))
    cols = [list(c) for c in cols]
    cols[col_i].insert(idx, story)
    return cols


ORPHAN_MAX_CHARS = 20  # don't glue longer last pairs: on a ~300px phone column they could overflow


def no_orphan_html(escaped):
    """Style rule: no one-word last line. Join the last two words of an (already escaped) headline
    with &nbsp; unless together they exceed ORPHAN_MAX_CHARS."""
    head, sep, last = (escaped or "").rpartition(" ")
    if not sep or len(html.unescape(head.rsplit(" ", 1)[-1] + " " + last)) > ORPHAN_MAX_CHARS:
        return escaped
    return f"{head}&nbsp;{last}"


def no_orphan_text(text):
    """Plain-text twin of no_orphan_html (with U+00A0), for height estimates."""
    head, sep, last = (text or "").rpartition(" ")
    if not sep or len(head.rsplit(" ", 1)[-1] + " " + last) > ORPHAN_MAX_CHARS:
        return text
    return f"{head}\u00a0{last}"


def render(lead, top, cols, now, sources, settings):
    _sq = headline_mod.smartquotes if headline_mod.style().get("smart_quotes", True) else (lambda x: x)
    e = html.escape          # URLs / raw attributes
    t = lambda x: html.escape(_sq(x or ""))   # visible text (incl. title tooltips)

    def meta(s):
        # Only the Quote of the Day shows an attribution line; news items show no outlet/time line
        # (the outlet stays internal for ranking and appears only in the hover tooltip).
        if s.get("quote_item"):
            return f'<div class="meta">{s.get("source_html") or t(OUTLET(s))}</div>'
        return ""

    def show(s):
        disp = s.get("display") or s["title"]
        orig = s.get("original_title") or s["title"]
        if s.get("quote_item"):
            # Always expose the full quote on hover for quote items.
            tip = orig if orig and orig != disp else ""
        else:
            outlet = OUTLET(s) if s.get("source") else ""
            tip = " — ".join(x for x in ((orig if orig and orig != disp else ""), outlet) if x)
            if s.get("archived"):
                tip = (tip + " · " if tip else "") + "archived copy"
        title_attr = f' title="{t(tip)}"' if tip else ""
        href = s.get("link") or "#"
        return f'<a href="{e(href)}" rel="noopener"{title_attr}>{no_orphan_html(t(disp))}</a>'

    def li(s):
        if s.get("quote_item"):
            body = f'<div class="qt">“{t(s.get("quote_text", ""))}”</div>' if s.get("quote_text") else ""
            kicker = '<div class="kicker"><span class="tag">Quote</span></div>'
            return f'<li class="qotd">{kicker}{show(s)}{body}{meta(s)}</li>'
        return f'<li>{show(s)}{meta(s)}</li>'

    col_html = "".join(f'<section class="col"><ul>{"".join(li(s) for s in c)}</ul></section>' for c in cols)
    return (f'<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="refresh" content="1800"><title>Spangle</title>{ICONS}{FONTS}<style>{CSS}</style></head><body><div class="wrap">'
            f'<header><h1 class="mast">Spangle</h1><div class="date"><span class="nw">{now.astimezone(ET_TZ).strftime("%A, %B %-d, %Y")}</span> · <span class="nw">Updated {now.astimezone(ET_TZ).strftime("%-I:%M %p")}</span></div></header>'
            f'<div class="lead">{show(lead)}{meta(lead)}</div>'
            f'<div class="label">Top Stories</div><div class="top"><ul>{"".join(li(s) for s in top)}</ul></div>'
            f'<div class="label">More Headlines</div><div class="cols">{col_html}</div>'
            f'<footer>Links to original reporting. All rights belong to their respective publishers. © {now.year} Spangle</footer>'
            f'</div></body></html>')


def main():
    with open(os.path.join(HERE, "settings.json")) as f:
        settings = json.load(f)
    now = datetime.now(timezone.utc)
    ctx = {"now": now}
    pcfg = ranking.private.load(ctx)
    try:  # override data problems are warnings, never build failures
        from ranking.override_lint import summary
        print(f"overrides: {len(headline_mod.overrides())} loaded; warnings: {summary(dict(headline_mod.overrides()))}")
    except Exception as ex:
        print(f"overrides: lint skipped ({type(ex).__name__})")
    settings["sources"]["tiers"].update(pcfg.get("source_tiers") or {})  # private feed tiers stay out of settings.json
    if pcfg.get("lifestyle"):
        settings["lifestyle"] = {"max_per_column": pcfg["lifestyle"].get("max_per_column", 1)}
    with cf.ThreadPoolExecutor(12) as ex:
        feeds = FEEDS + private_feed_list(pcfg) + (PAYWALLED_FEEDS if settings.get("archive", {}).get("enabled") and settings["archive"].get("ingest_paywalled_feeds") else [])
        stories = [s for batch in ex.map(lambda f: fetch(f, settings), feeds) for s in batch]
    # Curated aggregator picks: mark matching feed items, add the rest as original-URL items.
    by_link = {canon(s["link"]): s for s in stories}
    added = marked = 0
    for c in curators.fetch_all(settings, blocked=is_paywalled_domain):
        hit = by_link.get(canon(c["link"]))
        if hit:
            hit["curated"] = hit.get("curated", []) + c["curated"]; marked += 1
        else:
            stories.append(c); by_link[canon(c["link"])] = c; added += 1
    print(f"curated picks: {marked} matched feed items, {added} added as new originals")
    for src, (k, f) in sorted(lean.STATS.items()):
        if lean.mode(src, settings) != "all" or src in ("First Things",):
            print(f"LEAN {src}: kept {k}, filtered {f} (mode {lean.mode(src, settings)})")
    seen, uniq, seen_items = set(), [], {}
    max_age = settings["recency"]["max_age_hours"] * 3600
    for s in stories:
        k = norm(s["title"])
        if k in seen or s["link"] in seen:
            first = seen_items.get(k) or seen_items.get(s["link"])
            if first is not None and s.get("curated"):
                first["curated"] = first.get("curated", []) + s["curated"]
            continue
        if suppressed(s["link"], settings) or (s.get("feed_link") and suppressed(s["feed_link"], settings)):
            continue  # editor-removed story
        s["paywalled"] = is_paywalled_domain(s["link"])
        if s["paywalled"] and not settings.get("archive", {}).get("enabled"):
            continue
        if s["when"] and (now - s["when"]).total_seconds() > (s.get("max_age_hours") or max_age / 3600) * 3600:
            continue
        seen.update({k, s["link"]}); seen_items[k] = seen_items[s["link"]] = s
        uniq.append(s)
    vocab = headline_mod.vocabulary(f'{x["title"]} {x.get("desc", "")}' for x in uniq)
    headline_mod.VOCAB = vocab
    fixed = cut = 0
    for s in uniq:
        s["opinion"] = opinion_mod.classify(s)  # internal only; never displayed
        if headline_mod.truncated(s["title"], s["link"], vocab):  # cut-off source title
            r = headline_mod.repair_truncated(s["title"], s["link"], vocab)
            if r:
                s["title"] = r; fixed += 1
            else:
                s["truncated"] = True; cut += 1  # siblings preferred; queued; never the lead
    print(f"headlines: {fixed} cut-off titles repaired, {cut} left flagged")
    clusters = coverage.cluster(uniq, settings["coverage"]["similarity_threshold"])
    print(f"{len(uniq)} stories in {len(clusters)} clusters; {sum(1 for c in clusters if len(c['outlets']) > 1)} multi-outlet")
    ranking.rank(clusters, settings, ctx)
    dropped = [c for c in clusters if c.get("excluded")]
    clusters = [c for c in clusters if not c.get("excluded")]
    if dropped:
        print(f"excluded {len(dropped)} clusters (defeatist framing)")
    lead, top, cols = place(clusters, settings, ctx)
    lead, top, cols, _hl = decorate_headlines(lead, top, cols, clusters, settings, now, ctx)
    _q = load_daily_quote("quote_of_the_day.json")
    cols = balance_columns(cols, settings, quote_as_story(_q) if _q else None)
    cols = inject_quote(cols, settings)
    clean_links(lead, top, cols, clusters, settings, now)
    display_outlets([lead] + top + [s for c in cols for s in c])
    allp = [lead] + top + [s for c in cols for s in c]
    sources = sorted({OUTLET(s) for s in allp if not s.get("archived")})
    print(f"feeds: {FEED_STATS['ok']} OK, {FEED_STATS['fail']} failed; {len(allp)} links")
    if FEED_STATS["ok"] < MIN_FEEDS_OK or len(allp) < MIN_LINKS:
        print(f"BUILD GUARD: need >= {MIN_FEEDS_OK} feeds OK and >= {MIN_LINKS} links; refusing to write the page")
        return 1
    os.makedirs("site", exist_ok=True)
    if os.path.isdir("static"):
        shutil.copytree("static", "site", dirs_exist_ok=True)
    with open("site/index.html", "w") as f:
        f.write(render(lead, top, cols, now, sources, settings))
    print("archive lookups (found/tried): " + ", ".join(f"{k} {v[0]}/{v[1]}" for k, v in archive.STATS.items()))
    print(f"Wrote site/index.html with {len(allp)} links.")


if __name__ == "__main__":
    sys.exit(main())
