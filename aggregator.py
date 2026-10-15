#!/usr/bin/env python3
"""Spangle: fetch free RSS/Atom feeds, cluster and rank stories, render a static page."""
import json, os, re, html, sys, urllib.request, urllib.parse, concurrent.futures as cf
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
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
    r"continue reading for \$\d", r"topic-premium",              # Blaze Media premium pieces
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

def fetch(feed, settings=None):
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
        return []
    out = []
    items = root.findall(".//item") or root.findall(f".//{A}entry")
    for it in items:
        title = html.unescape(re.sub(r"<[^>]+>", "", txt(it, "title", f"{A}title")))
        link = txt(it, "link", f"{A}link")
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
                    title=title, link=link, desc=html.unescape(desc), author=author,
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


def url_ok(s):
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
                      key=lambda x: (tiers.get(x["source"], d), x["when"].timestamp() if x["when"] else 0), reverse=True)
        s = next((x for x in alts[:2] if x.get("archived") or not pl["check_links"] or url_ok(x)), None)
        if s is None:
            continue
        s["outlets_n"] = len(c["outlets"])
        s["lifestyle"] = bool(c.get("lifestyle"))
        s["top_excluded"] = bool(c.get("top_excluded"))
        life_n += s["lifestyle"]
        picked.append(s); count[OUTLET(s)] = count.get(OUTLET(s), 0) + 1
    picked = apply_manual(picked, settings)
    manual = {id(x) for x in picked if x.get("manual")}
    ok_front = lambda x, slot: id(x) in manual or (not x.get("lifestyle") and not x.get("top_excluded") and fits(x, slot, settings, now))
    lead = next((x for x in picked if ok_front(x, "lead") and not x.get("opinion")), None)  # lead = reported news
    if lead is None:
        lead = next((x for x in picked if ok_front(x, "lead")), None)
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


CSS = """
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
.lead{text-align:center;padding:26px 0 22px;border-bottom:1px solid var(--rule)}
.lead a{font-family:var(--display);font-weight:900;color:var(--red);font-size:clamp(28px,4.6vw,52px);line-height:1.12;display:inline;max-width:none;overflow:visible;text-overflow:clip;white-space:normal;hyphens:manual}
.lead a:visited{color:var(--red)}
.lead .meta{margin-top:12px}
.top ul{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:0 28px}
.top li{padding:10px 0 14px;border-bottom:1px solid var(--rule)}
.top a{font-weight:700;font-size:22px;line-height:1.22;overflow:visible;text-overflow:clip;white-space:normal}
.cols{display:grid;grid-template-columns:repeat(3,1fr);gap:0 32px}
.col{border-left:1px solid var(--rule);padding-left:20px} .col:first-child{border-left:0;padding-left:0}
.col ul{list-style:none;margin:0;padding:0}
.col li{padding:11px 0;border-bottom:1px solid var(--rule)}
.col a{font-weight:600;font-size:19px;line-height:1.3;overflow:visible;text-overflow:clip;white-space:normal}
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


def decorate_headlines(lead, top, cols, clusters, settings=None, now=None):
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

    def candidates(s):
        c = by_id.get(id(s)) or by_link.get(s["link"])
        return list(c["items"]) if c else [s]

    def prep(x):
        cleaned, changed = headline_mod.clean(x["title"], sty)
        return cleaned, changed, headline_mod.needs_rewrite(cleaned, sty), headline_mod.too_long(cleaned, sty)

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
        if sl == "lead":  # the lead stays reported news: only non-opinion siblings when any exist
            cands = [x for x in cands if not x.get("opinion")] or cands
        ranked = []
        for x in cands:
            cleaned, changed, bland, long = prep(x)
            # prefer: not bland, not too long, shorter, newer
            ranked.append(((0 if bland else 1), (0 if x.get("opinion") else 1), (0 if long else 1), -len(cleaned),
                           x.get("when").timestamp() if x.get("when") else 0, x, cleaned, changed, bland, long))
        ranked.sort(reverse=True)
        _a, _o, _b, _c, _d, best, cleaned, changed, bland, long = ranked[0]
        all_bland = all(r[8] for r in ranked)
        all_long = all(r[9] for r in ranked)
        # if best is long but a shorter non-bland sibling exists, pick that
        if long:
            shorter = [r for r in ranked if not r[8] and not r[9]]
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
        if headline_mod.contentless(cleaned):
            # siblings with real content beat a bare name / fragment
            alt = next((r for r in ranked if not headline_mod.contentless(r[6])), None)
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
        # queue only when still a problem after sibling pick
        if all_bland or (bland and not any(not r[8] for r in ranked)):
            stats["queued_bland"] += 1
            stats["queue"].append({"url": best["link"], "title": best["title"], "cleaned": cleaned,
                                   "reason": "bland",
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
    print(f"headlines: kept {stats['kept']}, swapped {stats['swapped']}, "
          f"queued_bland {stats['queued_bland']}, queued_too_long {stats['queued_too_long']}, "
          f"styled {stats['styled']}, overrides {stats['override']}, shortened {stats['shortened']}")
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


def fallback_quote(today, bank_file="qotd_bank.json"):
    try:
        with open(os.path.join(HERE, bank_file)) as f:
            bank = [q for q in json.load(f)["quotes"] if q.get("verified") and q.get("source_type") in ("primary", "column")
                    and len(q["quote"].split()) <= 60]
    except Exception:
        return None
    if not bank:
        return None
    import hashlib
    q = dict(bank[int(hashlib.sha256(today.encode()).hexdigest(), 16) % len(bank)])
    words = q["quote"].replace("—", " ").replace(";", ".").split()
    q["headline"] = headline_mod.clean(" ".join(words[:8]).rstrip(".,;:"))[0]
    q["date"] = today
    return q


def quote_as_story(q):
    """Turn quote_of_the_day.json into a column item shaped like any other story."""
    work = (q.get("work") or "").strip()
    loc = (q.get("locator") or q.get("chapter_or_page") or "").strip()
    if work and loc:
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
        "quote_text": quote_text,
        "outlets_n": 1,
    }


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


def render(lead, top, cols, now, sources, settings):
    _sq = headline_mod.smartquotes if headline_mod.style().get("smart_quotes", True) else (lambda x: x)
    e = html.escape          # URLs / raw attributes
    t = lambda x: html.escape(_sq(x or ""))   # visible text (incl. title tooltips)

    def meta(s):
        if s.get("quote_item"):
            return f'<div class="meta">{t(OUTLET(s))}</div>'
        ts = s["when"].strftime("%b %-d, %H:%M UTC") if s["when"] else ""
        extra = s.get("outlets_n", 1) - 1
        more = f' · +{extra} outlet{"s" if extra > 1 else ""}' if extra > 0 else ""
        arc = " · archived copy" if s.get("archived") else ""
        parts = " · ".join(x for x in (OUTLET(s), ts) if x)
        return f'<div class="meta">{t(parts)}{e(more)}{arc}</div>'

    def show(s):
        disp = s.get("display") or s["title"]
        orig = s.get("original_title") or s["title"]
        # Always expose the full quote (or original title) on hover for quote items.
        title_attr = f' title="{t(orig)}"' if orig and orig != disp else ""
        href = s.get("link") or "#"
        return f'<a href="{e(href)}" rel="noopener"{title_attr}>{t(disp)}</a>'

    def li(s):
        if s.get("quote_item"):
            body = f'<div class="qt">“{t(s.get("quote_text", ""))}”</div>' if s.get("quote_text") else ""
            kicker = '<div class="kicker"><span class="tag">Quote</span></div>'
            return f'<li class="qotd">{kicker}{show(s)}{body}{meta(s)}</li>'
        return f'<li>{show(s)}{meta(s)}</li>'

    col_html = "".join(f'<section class="col"><ul>{"".join(li(s) for s in c)}</ul></section>' for c in cols)
    return (f'<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="refresh" content="1800"><title>Spangle</title>{ICONS}{FONTS}<style>{CSS}</style></head><body><div class="wrap">'
            f'<header><h1 class="mast">Spangle</h1><div class="date">{now.strftime("%A, %B %-d, %Y")} · Updated {now.strftime("%H:%M")} UTC</div></header>'
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
        s["paywalled"] = is_paywalled_domain(s["link"])
        if s["paywalled"] and not settings.get("archive", {}).get("enabled"):
            continue
        if s["when"] and (now - s["when"]).total_seconds() > (s.get("max_age_hours") or max_age / 3600) * 3600:
            continue
        seen.update({k, s["link"]}); seen_items[k] = seen_items[s["link"]] = s
        uniq.append(s)
    for s in uniq:
        s["opinion"] = opinion_mod.classify(s)  # internal only; never displayed
    clusters = coverage.cluster(uniq, settings["coverage"]["similarity_threshold"])
    print(f"{len(uniq)} stories in {len(clusters)} clusters; {sum(1 for c in clusters if len(c['outlets']) > 1)} multi-outlet")
    ranking.rank(clusters, settings, ctx)
    lead, top, cols = place(clusters, settings, ctx)
    lead, top, cols, _hl = decorate_headlines(lead, top, cols, clusters, settings, now)
    cols = inject_quote(cols, settings)
    display_outlets([lead] + top + [s for c in cols for s in c])
    allp = [lead] + top + [s for c in cols for s in c]
    sources = sorted({OUTLET(s) for s in allp if not s.get("archived")})
    os.makedirs("site", exist_ok=True)
    if os.path.isdir("static"):
        shutil.copytree("static", "site", dirs_exist_ok=True)
    with open("site/index.html", "w") as f:
        f.write(render(lead, top, cols, now, sources, settings))
    print("archive lookups (found/tried): " + ", ".join(f"{k} {v[0]}/{v[1]}" for k, v in archive.STATS.items()))
    print(f"Wrote site/index.html with {len(allp)} links.")


if __name__ == "__main__":
    sys.exit(main())
