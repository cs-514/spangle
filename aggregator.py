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
    # AEI author pages have no working feed; use AEI's site-search feed filtered to the byline.
    # Author output is infrequent, so items stay eligible longer.
    ("AEI", "https://example.invalid/private-feed", False, FEED_UA, {"byline": "private feed", "max_age_hours": 336}),
    # Substack: paid-only posts are skipped (checked via the public post API).
    ("private feed", "https://example.invalid/private-feed", True, UA, {"substack_free_only": True, "max_age_hours": 168}),
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
        root = ET.fromstring(data)
    except Exception as e:
        print(f"FEED FAIL {name}: {e!r}"[:160])
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
        item = dict(max_age_hours=opts.get("max_age_hours"), title=title, link=link, desc=html.unescape(desc), author=author,
                    cats=cats, when=when, source=name, opinion=op_feed or "/opinion/" in link or "/commentary/" in link)
        if settings is not None and not lean.keep(item, name, settings, outlet=name, author=author):
            continue
        out.append(item)
    print(f"FEED OK {name}: {len(out)} items")
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
        out.insert(pos.get(l.get("position", "top"), 1), s); n += 1
    print(f"manual links: {n} pinned")
    return out


def best_item(c, tiers, default):
    return max(c["items"], key=lambda s: (tiers.get(s["source"], default), s["when"].timestamp() if s["when"] else 0))


def place(clusters, settings, ctx):
    pl, tiers, d = settings["placement"], settings["sources"]["tiers"], settings["sources"]["default_tier"]
    count, out, budget = {}, [], [0]
    if pl.get("lead_respects_exclusions", True):  # promote the best non-excluded cluster to the lead slot
        i = next((i for i, c in enumerate(clusters) if not c.get("lead_excluded")), 0)
        clusters = [clusters[i]] + clusters[:i] + clusters[i + 1:]
    clusters = lead_mod.order_for_lead(clusters, settings, ctx)
    want = 1 + pl["top_stories"] + pl["column_items"]
    for c in clusters:
        if len(out) >= want:
            break
        cap = pl["max_per_outlet_top"] if len(out) < 1 + pl["top_stories"] else pl["max_per_outlet_total"]
        free = [x for x in c["items"] if not x.get("paywalled")]
        ar = settings.get("archive", {})
        dated = [x for x in c["items"] if x["when"]]
        orig = min(dated, key=lambda x: x["when"]) if dated else c["items"][0]
        if (orig.get("paywalled") or not free) and ar.get("enabled") and len(c["outlets"]) >= ar["min_outlets"] \
                and budget[0] < ar["max_lookups"]:
            p = orig if orig.get("paywalled") else next(x for x in c["items"] if x.get("paywalled"))
            budget[0] += 1
            link, prov = archive.find(p["link"], ar)
            if link:  # original scoop available via an existing snapshot
                free = [dict(p, link=link, archived=prov, paywalled=False)]
        if not free:
            continue
        alts = sorted([x for x in free if count.get(OUTLET(x), 0) < cap],
                      key=lambda x: (tiers.get(x["source"], d), x["when"].timestamp() if x["when"] else 0), reverse=True)
        s = next((x for x in alts[:2] if x.get("archived") or not pl["check_links"] or url_ok(x)), None)
        if s is None:
            continue
        s["outlets_n"] = len(c["outlets"])
        out.append(s); count[OUTLET(s)] = count.get(OUTLET(s), 0) + 1
    out = apply_manual(out, settings)
    lead, top, rest = out[0], out[1:1 + pl["top_stories"]], out[1 + pl["top_stories"]:]
    n = pl["columns"]
    per = -(-len(rest) // n)
    return lead, top, [rest[i * per:(i + 1) * per] for i in range(n)]


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
.qt{font-family:var(--serif);font-style:italic;font-size:16.5px;line-height:1.4;color:var(--ink);margin-top:5px}
.tag{font-weight:800;text-transform:uppercase;letter-spacing:.1em;font-size:10.5px;color:var(--red);margin-right:6px}
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


def decorate_headlines(lead, top, cols, clusters):
    """For each placed story: prefer a non-bland, under-max-length sibling headline
    (and its URL); always apply deterministic style cleanup (never truncate);
    queue a rewrite when every candidate is bland OR the chosen display is still
    over max length. Returns (lead, top, cols, stats)."""
    by_id = {id(s): c for c in clusters for s in c["items"]}
    by_link = {s["link"]: c for c in clusters for s in c["items"]}
    stats = {"kept": 0, "swapped": 0, "queued_bland": 0, "queued_too_long": 0, "styled": 0, "override": 0, "queue": []}
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
        cands = [x for x in candidates(s) if not x.get("paywalled")] or [s]
        ranked = []
        for x in cands:
            cleaned, changed, bland, long = prep(x)
            # prefer: not bland, not too long, shorter, newer
            ranked.append(((0 if bland else 1), (0 if long else 1), -len(cleaned),
                           x.get("when").timestamp() if x.get("when") else 0, x, cleaned, changed, bland, long))
        ranked.sort(reverse=True)
        _a, _b, _c, _d, best, cleaned, changed, bland, long = ranked[0]
        all_bland = all(r[7] for r in ranked)
        all_long = all(r[8] for r in ranked)
        # if best is long but a shorter non-bland sibling exists, pick that
        if long:
            shorter = [r for r in ranked if not r[7] and not r[8]]
            if shorter:
                _a, _b, _c, _d, best, cleaned, changed, bland, long = shorter[0]
        if best["link"] != s["link"]:
            s["link"], s["title"], s["source"], s["opinion"] = best["link"], best["title"], best["source"], best.get("opinion", False)
            if best.get("when"):
                s["when"] = best["when"]
            stats["swapped"] += 1
        else:
            stats["kept"] += 1
        if changed:
            stats["styled"] += 1
        s["display"], s["original_title"] = cleaned, best["title"]
        # queue only when still a problem after sibling pick
        if all_bland or (bland and not any(not r[7] for r in ranked)):
            stats["queued_bland"] += 1
            stats["queue"].append({"url": best["link"], "title": best["title"], "cleaned": cleaned,
                                   "reason": "bland",
                                   "siblings": [{"url": x["link"], "title": x["title"]} for x in cands]})
        elif long or (all_long and not any(not r[8] for r in ranked)):
            # display stays full (no truncation); ask for a trim rewrite
            stats["queued_too_long"] += 1
            stats["queue"].append({"url": best["link"], "title": best["title"], "cleaned": cleaned,
                                   "reason": "too_long", "chars": len(cleaned), "words": len(cleaned.split()),
                                   "siblings": [{"url": x["link"], "title": x["title"]} for x in cands]})
    print(f"headlines: kept {stats['kept']}, swapped {stats['swapped']}, "
          f"queued_bland {stats['queued_bland']}, queued_too_long {stats['queued_too_long']}, "
          f"styled {stats['styled']}, overrides {stats['override']}")
    try:
        with open(os.path.join(HERE, "..", "rewrite_queue.json"), "w") as f:
            json.dump({"generated": datetime.now(timezone.utc).isoformat(), "items": stats["queue"]}, f, indent=1)
    except Exception as ex:
        print(f"rewrite queue write skipped: {type(ex).__name__}")
    return lead, top, cols, stats


def load_daily_quote(filename="quote_of_the_day.json"):
    path = os.path.join(HERE, filename)
    try:
        with open(path) as f:
            q = json.load(f)
        if not q.get("quote") or not q.get("author"):
            return None
        return q
    except Exception:
        return None


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
    tag = settings["placement"]["opinion_tag"]

    def meta(s):
        if s.get("quote_item"):
            return f'<div class="meta"><span class="tag">Quote</span>{t(OUTLET(s))}</div>'
        ts = s["when"].strftime("%b %-d, %H:%M UTC") if s["when"] else ""
        more = f' · {s["outlets_n"]} outlets' if s.get("outlets_n", 1) > 1 else ""
        op = '<span class="tag">Opinion</span>' if tag and s["opinion"] else ""
        arc = " · archived copy" if s.get("archived") else ""
        parts = " · ".join(x for x in (OUTLET(s), ts) if x)
        return f'<div class="meta">{op}{t(parts)}{e(more)}{arc}</div>'

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
            return f'<li>{show(s)}{body}{meta(s)}</li>'
        return f'<li>{show(s)}{meta(s)}</li>'

    col_html = "".join(f'<section class="col"><ul>{"".join(li(s) for s in c)}</ul></section>' for c in cols)
    return (f'<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="refresh" content="1800"><title>Spangle</title>{ICONS}{FONTS}<style>{CSS}</style></head><body><div class="wrap">'
            f'<header><h1 class="mast">Spangle</h1><div class="date">{now.strftime("%A, %B %-d, %Y")} · Updated {now.strftime("%H:%M")} UTC</div></header>'
            f'<div class="lead">{show(lead)}{meta(lead)}</div>'
            f'<div class="label">Top Stories</div><div class="top"><ul>{"".join(li(s) for s in top)}</ul></div>'
            f'<div class="label">More Headlines</div><div class="cols">{col_html}</div>'
            f'<footer>Every headline links to its original publisher. Free-to-read sources only. Updated hourly.<br>'
            f'Sources: {t(", ".join(sources))}.</footer></div></body></html>')


def main():
    with open(os.path.join(HERE, "settings.json")) as f:
        settings = json.load(f)
    now = datetime.now(timezone.utc)
    with cf.ThreadPoolExecutor(12) as ex:
        feeds = FEEDS + (PAYWALLED_FEEDS if settings.get("archive", {}).get("enabled") and settings["archive"].get("ingest_paywalled_feeds") else [])
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
    clusters = coverage.cluster(uniq, settings["coverage"]["similarity_threshold"])
    print(f"{len(uniq)} stories in {len(clusters)} clusters; {sum(1 for c in clusters if len(c['outlets']) > 1)} multi-outlet")
    ctx = {"now": now}
    ranking.rank(clusters, settings, ctx)
    lead, top, cols = place(clusters, settings, ctx)
    lead, top, cols, _hl = decorate_headlines(lead, top, cols, clusters)
    cols = inject_quote(cols, settings)
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
