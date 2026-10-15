#!/usr/bin/env python3
"""Spangle: fetch free RSS/Atom feeds, cluster and rank stories, render a static page."""
import json, os, re, html, sys, urllib.request, urllib.parse, concurrent.futures as cf
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import ranking
from ranking.util import canon
from ranking import archive
import curators
from ranking import coverage

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120 Safari/537.36 Spangle/1.0"}
HERE = os.path.dirname(os.path.abspath(__file__))

# (name, url, opinion_only_feed)
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
    ("Christian Post", "https://www.christianpost.com/rss", False),
    ("Daily Caller", "https://dailycaller.com/feed/", False),
    ("Just the News", "https://justthenews.com/rss.xml", False),
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
    "wsj.com", "nytimes.com", "washingtonpost.com", "bloomberg.com", "ft.com",
    "theatlantic.com", "economist.com", "barrons.com", "newyorker.com",
    "latimes.com", "bostonglobe.com", "thetimes.co.uk", "telegraph.co.uk",
    "businessinsider.com", "foreignaffairs.com", "theinformation.com",
}
PAYWALL_MARKERS = [
    '"isAccessibleForFree":false', '"isAccessibleForFree": false',
    'class="paywall', "id=\"paywall", "subscribe to continue reading",
    "this article is for subscribers", "nr-plus", "nrplus",
]

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

def fetch(feed):
    name, url, op_feed = feed
    try:
        data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read()
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
        out.append(dict(title=title, link=link, desc=html.unescape(desc), author=author,
                        cats=cats, when=when, source=name, opinion=op_feed or "/opinion/" in link))
    print(f"FEED OK {name}: {len(out)} items")
    return out

def url_ok(s):
    try:
        req = urllib.request.Request(s["link"], headers=UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            if r.status != 200:
                return False
            body = r.read(400000).decode("utf-8", "ignore").lower()
        return not any(m.lower() in body for m in PAYWALL_MARKERS)
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


def place(clusters, settings):
    pl, tiers, d = settings["placement"], settings["sources"]["tiers"], settings["sources"]["default_tier"]
    count, out, budget = {}, [], [0]
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
.lead a{font-family:var(--display);font-weight:900;color:var(--red);font-size:clamp(32px,5.4vw,60px);line-height:1.08;display:inline-block;max-width:22ch}
.lead a:visited{color:var(--red)}
.lead .meta{margin-top:12px}
.top ul{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:0 28px}
.top li{padding:10px 0 14px;border-bottom:1px solid var(--rule)}
.top a{font-weight:700;font-size:22px;line-height:1.22}
.cols{display:grid;grid-template-columns:repeat(3,1fr);gap:0 32px}
.col{border-left:1px solid var(--rule);padding-left:20px} .col:first-child{border-left:0;padding-left:0}
.col ul{list-style:none;margin:0;padding:0}
.col li{padding:11px 0;border-bottom:1px solid var(--rule)}
.col a{font-weight:600;font-size:19px;line-height:1.3}
.meta{font-family:var(--sans);font-size:12.5px;color:var(--muted);margin-top:5px;letter-spacing:.02em}
.tag{font-weight:800;text-transform:uppercase;letter-spacing:.1em;font-size:10.5px;color:var(--red);margin-right:6px}
footer{font-family:var(--sans);font-size:13px;color:var(--muted);border-top:3px double var(--ink);margin-top:36px;padding-top:14px;line-height:1.6}
@media(max-width:900px){.cols{grid-template-columns:1fr 1fr}.col:nth-child(3){grid-column:1/-1;border-left:0;padding-left:0}}
@media(max-width:620px){body{font-size:18px}.wrap{padding:0 16px 32px}.cols{grid-template-columns:1fr}.col{border-left:0;padding-left:0}.top a{font-size:21px}}
"""
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@400;600;800&family=Playfair+Display:wght@700;900'
         '&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&display=swap" rel="stylesheet">')


def render(lead, top, cols, now, sources, settings):
    e = html.escape
    tag = settings["placement"]["opinion_tag"]

    def meta(s):
        ts = s["when"].strftime("%b %-d, %H:%M UTC") if s["when"] else ""
        more = f' · {s["outlets_n"]} outlets' if s.get("outlets_n", 1) > 1 else ""
        op = '<span class="tag">Opinion</span>' if tag and s["opinion"] else ""
        arc = " · archived copy" if s.get("archived") else ""
        parts = " · ".join(x for x in (OUTLET(s), ts) if x)
        return f'<div class="meta">{op}{e(parts)}{e(more)}{arc}</div>'

    def li(s):
        return f'<li><a href="{e(s["link"])}" rel="noopener">{e(s["title"])}</a>{meta(s)}</li>'

    col_html = "".join(f'<section class="col"><ul>{"".join(li(s) for s in c)}</ul></section>' for c in cols)
    return (f'<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="refresh" content="1800"><title>Spangle</title>{FONTS}<style>{CSS}</style></head><body><div class="wrap">'
            f'<header><h1 class="mast">Spangle</h1><div class="date">{now.strftime("%A, %B %-d, %Y")} · Updated {now.strftime("%H:%M")} UTC</div></header>'
            f'<div class="lead"><a href="{e(lead["link"])}" rel="noopener">{e(lead["title"])}</a>{meta(lead)}</div>'
            f'<div class="label">Top Stories</div><div class="top"><ul>{"".join(li(s) for s in top)}</ul></div>'
            f'<div class="label">More Headlines</div><div class="cols">{col_html}</div>'
            f'<footer>Every headline links to its original publisher. Free-to-read sources only. Updated hourly.<br>'
            f'Sources: {e(", ".join(sources))}.</footer></div></body></html>')


def main():
    with open(os.path.join(HERE, "settings.json")) as f:
        settings = json.load(f)
    now = datetime.now(timezone.utc)
    with cf.ThreadPoolExecutor(12) as ex:
        feeds = FEEDS + (PAYWALLED_FEEDS if settings.get("archive", {}).get("enabled") and settings["archive"].get("ingest_paywalled_feeds") else [])
        stories = [s for batch in ex.map(fetch, feeds) for s in batch]
    # Curated aggregator picks: mark matching feed items, add the rest as original-URL items.
    by_link = {canon(s["link"]): s for s in stories}
    added = marked = 0
    for c in curators.fetch_all(settings):
        hit = by_link.get(canon(c["link"]))
        if hit:
            hit["curated"] = hit.get("curated", []) + c["curated"]; marked += 1
        else:
            stories.append(c); by_link[canon(c["link"])] = c; added += 1
    print(f"curated picks: {marked} matched feed items, {added} added as new originals")
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
        if s["when"] and (now - s["when"]).total_seconds() > max_age:
            continue
        seen.update({k, s["link"]}); seen_items[k] = seen_items[s["link"]] = s
        uniq.append(s)
    clusters = coverage.cluster(uniq, settings["coverage"]["similarity_threshold"])
    print(f"{len(uniq)} stories in {len(clusters)} clusters; {sum(1 for c in clusters if len(c['outlets']) > 1)} multi-outlet")
    ranking.rank(clusters, settings, {"now": now})
    lead, top, cols = place(clusters, settings)
    allp = [lead] + top + [s for c in cols for s in c]
    sources = sorted({OUTLET(s) for s in allp if not s.get("archived")})
    os.makedirs("site", exist_ok=True)
    with open("site/index.html", "w") as f:
        f.write(render(lead, top, cols, now, sources, settings))
    print("archive lookups (found/tried): " + ", ".join(f"{k} {v[0]}/{v[1]}" for k, v in archive.STATS.items()))
    print(f"Wrote site/index.html with {len(allp)} links.")


if __name__ == "__main__":
    sys.exit(main())
