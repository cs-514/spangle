#!/usr/bin/env python3
"""Rampart Report: fetch free RSS/Atom feeds, score stories, render a static page."""
import json, os, re, html, sys, urllib.request, urllib.parse, concurrent.futures as cf
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120 Safari/537.36 RampartReport/1.0"}

# (name, url, kind) kind: news | opinion
FEEDS = [
    ("The Federalist", "https://thefederalist.com/feed/", "opinion"),
    ("Daily Wire", "https://www.dailywire.com/feeds/rss.xml", "news"),
    ("Washington Examiner", "https://www.washingtonexaminer.com/feed/", "news"),
    ("Daily Signal", "https://www.dailysignal.com/feed/", "news"),
    ("Townhall", "https://townhall.com/feed/", "opinion"),
    ("PJ Media", "https://pjmedia.com/feed", "opinion"),
    ("RedState", "https://redstate.com/feed", "opinion"),
    ("Hot Air", "https://hotair.com/feed", "opinion"),
    ("The Blaze", "https://www.theblaze.com/feeds/feed.rss", "news"),
    ("Breitbart", "https://feeds.feedburner.com/breitbart", "news"),
    ("NY Post", "https://nypost.com/feed/", "news"),
    ("NY Post Opinion", "https://nypost.com/opinion/feed/", "opinion"),
    ("Fox News", "https://moxie.foxnews.com/google-publisher/latest.xml", "news"),
    ("Fox News Politics", "https://moxie.foxnews.com/google-publisher/politics.xml", "news"),
    ("Fox News Opinion", "https://moxie.foxnews.com/google-publisher/opinion.xml", "opinion"),
    ("Washington Free Beacon", "https://freebeacon.com/feed/", "news"),
    ("The American Conservative", "https://www.theamericanconservative.com/feed/", "opinion"),
    ("First Things", "https://www.firstthings.com/rss", "opinion"),
    ("Christian Post", "https://www.christianpost.com/rss", "news"),
    ("Daily Caller", "https://dailycaller.com/feed/", "news"),
    ("Just the News", "https://justthenews.com/rss.xml", "news"),
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

DEFAULT_CONFIG = {
    "boost_keywords": {"breaking": 2, "exclusive": 2, "senate": 1, "congress": 1, "supreme court": 2},
    "demote_keywords": {"horoscope": -5, "celebrity": -2, "recipe": -5, "deals": -4, "sponsored": -6},
    "authors": {},
    "sources": {},
    "lead_topics": ["breaking", "supreme court", "white house"],
    "recency_half_life_hours": 8,
}

def load_config():
    raw = os.environ.get("ALIGNMENT_CONFIG", "").strip()
    cfg = dict(DEFAULT_CONFIG)
    if raw:
        try:
            cfg.update(json.loads(raw))
            print("Loaded custom scoring config.")
        except Exception:
            print("Custom scoring config invalid; using defaults.")
    else:
        print("Using default scoring config.")
    return cfg

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
    name, url, kind = feed
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
                        cats=cats, when=when, source=name, kind=kind))
    print(f"FEED OK {name}: {len(out)} items")
    return out

def score(s, cfg, now):
    hay = f"{s['title']} {s['desc']} {s['cats']}".lower()
    sc = 0.0
    for k, w in cfg.get("boost_keywords", {}).items():
        if k.lower() in hay:
            sc += w * (2 if k.lower() in s["title"].lower() else 1)
    for k, w in cfg.get("demote_keywords", {}).items():
        if k.lower() in hay:
            sc += w
    for a, w in cfg.get("authors", {}).items():
        if a.lower() in (s["author"] or "").lower():
            sc += w
    sc += cfg.get("sources", {}).get(s["source"], 0)
    if s["when"]:
        age = max(0.0, (now - s["when"]).total_seconds() / 3600)
        sc += 6 * 0.5 ** (age / cfg.get("recency_half_life_hours", 8))
    s["lead_hit"] = any(t.lower() in s["title"].lower() for t in cfg.get("lead_topics", []))
    return sc

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

def render(lead, top, cols, opinion, now, sources):
    e = html.escape
    def li(s):
        ts = s["when"].strftime("%b %d %H:%M UTC") if s["when"] else ""
        return (f'<li><a href="{e(s["link"])}" target="_blank" rel="noopener">{e(s["title"].upper())}</a>'
                f' <span class="src">{e(s["source"])} {e(ts)}</span></li>')
    col_html = "".join(f'<div class="col"><ul>{"".join(li(s) for s in c)}</ul></div>' for c in cols)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="1800"><title>RAMPART REPORT</title>
<style>
body{{font-family:"Courier New",Courier,monospace;background:#fff;color:#000;margin:0 auto;max-width:1200px;padding:12px}}
a{{color:#000;text-decoration:underline}} a:visited{{color:#551a8b}}
.top ul{{list-style:none;padding:0;text-align:center}} .top li{{margin:6px 0;font-size:1.05em}}
.lead{{text-align:center;margin:18px 0}} .lead a{{color:#c00;font-size:2.6em;font-weight:bold;line-height:1.1}}
.mast{{text-align:center;font-size:3.4em;font-weight:bold;letter-spacing:2px;margin:10px 0 0}}
.ts{{text-align:center;font-size:.85em}} hr{{border:0;border-top:2px solid #000}}
.cols{{display:flex;gap:24px}} .col{{flex:1}} .col ul{{list-style:none;padding:0}} .col li{{margin:0 0 12px;font-size:.92em}}
.src{{display:block;color:#666;font-size:.75em}} h2{{text-align:center;font-size:1.3em}}
.op ul{{columns:2;list-style:none;padding:0}} .op li{{margin:0 0 10px;font-size:.92em;break-inside:avoid}}
footer{{font-size:.75em;text-align:center;color:#555;margin:24px 0}}
@media(max-width:800px){{.cols{{display:block}}.op ul{{columns:1}}.lead a{{font-size:1.8em}}}}
</style></head><body>
<div class="top"><ul>{"".join(li(s) for s in top)}</ul></div>
<div class="lead"><a href="{e(lead["link"])}" target="_blank" rel="noopener">{e(lead["title"].upper())}</a>
<div class="src">{e(lead["source"])}</div></div>
<div class="mast">RAMPART REPORT</div>
<div class="ts">UPDATED {now.strftime("%a %b %d, %Y %H:%M UTC").upper()}</div><hr>
<div class="cols">{col_html}</div><hr>
<div class="op"><h2>OPINION &amp; OP-EDS</h2><ul>{"".join(li(s) for s in opinion)}</ul></div><hr>
<footer>Links go to the original publishers. Free-to-read sources only. Sources: {e(", ".join(sources))}.</footer>
</body></html>"""

def main():
    cfg = load_config()
    now = datetime.now(timezone.utc)
    with cf.ThreadPoolExecutor(12) as ex:
        stories = [s for batch in ex.map(fetch, FEEDS) for s in batch]
    seen, uniq = set(), []
    for s in stories:
        k = norm(s["title"])
        if k in seen or s["link"] in seen or is_paywalled_domain(s["link"]):
            continue
        if s["when"] and (now - s["when"]).total_seconds() > 72 * 3600:
            continue
        seen.update({k, s["link"]})
        s["score"] = score(s, cfg, now)
        uniq.append(s)
    uniq.sort(key=lambda s: s["score"], reverse=True)

    def pick(pool, n, per_source=4):
        out, cnt = [], {}
        for s in pool:
            if len(out) >= n:
                break
            if cnt.get(s["source"], 0) >= per_source:
                continue
            if url_ok(s):
                out.append(s); cnt[s["source"]] = cnt.get(s["source"], 0) + 1
        return out

    leads = [s for s in uniq if s["lead_hit"] and s["kind"] == "news"] or [s for s in uniq if s["kind"] == "news"] or uniq
    lead = pick(leads, 1)[0]
    rest = [s for s in uniq if s is not lead]
    news = [s for s in rest if s["kind"] == "news"]
    ops = [s for s in rest if s["kind"] == "opinion"]
    top = pick(news, 4, 1)
    opinion = pick(ops, 20, 3)
    used = {id(s) for s in top + opinion}
    body = pick([s for s in rest if id(s) not in used], 45, 5)
    cols = [body[i::3] for i in range(3)]
    sources = sorted({s["source"] for s in [lead] + top + opinion + body})
    os.makedirs("site", exist_ok=True)
    with open("site/index.html", "w") as f:
        f.write(render(lead, top, cols, opinion, now, sources))
    print(f"Wrote site/index.html with {1 + len(top) + len(opinion) + len(body)} links.")

if __name__ == "__main__":
    sys.exit(main())
