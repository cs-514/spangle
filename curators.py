"""Pull headline links from curating aggregators (e.g. Bongino Report) and resolve
them to the ORIGINAL article URLs. Their picks feed the curated_by_aggregators signal."""
import re, html, urllib.request, urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120 Safari/537.36 Spangle/1.0"}
SKIP_HOSTS = ("rumble.com", "spotify.com", "apple.com", "youtube.com", "youtu.be", "x.com", "twitter.com",
              "facebook.com", "instagram.com", "tiktok.com", "truthsocial.com", "cdn.", "fonts.")

# Known outlet names by domain, so curated links merge with the matching feed source.
OUTLETS = {
    "foxnews.com": "Fox News", "nypost.com": "NY Post", "dailycaller.com": "Daily Caller",
    "justthenews.com": "Just the News", "thefederalist.com": "The Federalist", "dailywire.com": "Daily Wire",
    "washingtonexaminer.com": "Washington Examiner", "dailysignal.com": "Daily Signal", "townhall.com": "Townhall",
    "pjmedia.com": "PJ Media", "redstate.com": "RedState", "hotair.com": "Hot Air", "theblaze.com": "The Blaze",
    "breitbart.com": "Breitbart", "freebeacon.com": "Washington Free Beacon", "christianpost.com": "Christian Post",
    "theamericanconservative.com": "The American Conservative", "firstthings.com": "First Things",
    "newsmax.com": "Newsmax", "amgreatness.com": "American Greatness", "newsbusters.org": "NewsBusters",
    "thepostmillennial.com": "The Post Millennial", "washingtontimes.com": "Washington Times",
    "twitchy.com": "Twitchy", "nationalreview.com": "National Review", "realclearpolitics.com": "RealClearPolitics",
    "interestingengineering.com": "Interesting Engineering", "zerohedge.com": "ZeroHedge",
    "americanthinker.com": "American Thinker", "city-journal.org": "City Journal", "thefp.com": "The Free Press",
    "spectator.org": "The American Spectator", "realclearmarkets.com": "RealClearMarkets",
    "realclearworld.com": "RealClearWorld", "realclearinvestigations.com": "RealClearInvestigations",
    "lifezette.com": "LifeZette", "hollywoodintoto.com": "Hollywood in Toto", "westernjournal.com": "The Western Journal",
    "bizpacreview.com": "BizPac Review", "thegatewaypundit.com": "The Gateway Pundit", "dailymail.co.uk": "Daily Mail",
    "foxbusiness.com": "Fox Business", "outkick.com": "OutKick", "apnews.com": "AP", "reuters.com": "Reuters",
    "cbsnews.com": "CBS News", "nbcnews.com": "NBC News", "abcnews.go.com": "ABC News", "cnn.com": "CNN",
    "politico.com": "Politico", "thehill.com": "The Hill", "axios.com": "Axios", "mrctv.org": "MRCTV",
    "cnsnews.com": "CNS News", "catholicvote.org": "CatholicVote", "lifenews.com": "LifeNews", "cbn.com": "CBN News",
    "campusreform.org": "Campus Reform", "thecollegefix.com": "The College Fix", "unherd.com": "UnHerd",
    "semafor.com": "Semafor", "nationalpost.com": "National Post", "dailywire.com": "Daily Wire",
    "notthebee.com": "Not the Bee", "babylonbee.com": "The Babylon Bee", "courthousenews.com": "Courthouse News", "scotusblog.com": "SCOTUSblog",
    "reason.com": "Reason", "cato.org": "Cato Institute", "heritage.org": "Heritage Foundation", "aei.org": "AEI",
    "washingtonpost.com": "Washington Post", "wsj.com": "Wall Street Journal", "nytimes.com": "New York Times",
    "theepochtimes.com": "The Epoch Times", "newsweek.com": "Newsweek", "foxnews.com": "Fox News",
    "dailycallernewsfoundation.org": "Daily Caller News Foundation", "conservativebrief.com": "Conservative Brief",
    "insidesources.com": "InsideSources", "thenationalpulse.com": "The National Pulse", "humanevents.com": "Human Events",
    "thedispatch.com": "The Dispatch", "freebeacon.com": "Washington Free Beacon", "pjmedia.com": "PJ Media",
    "summit.news": "Summit News", "modernity.news": "Modernity", "rumble.com": "Rumble", "youtube.com": "YouTube",
    "judicialwatch.org": "Judicial Watch", "okeefemediagroup.com": "O’Keefe Media Group",
    "imprimis.hillsdale.edu": "Imprimis",
    "x.com": "X", "twitter.com": "X", "truthsocial.com": "Truth Social",
}


def outlet_name(url):
    host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    for d, n in OUTLETS.items():
        if host == d or host.endswith("." + d):
            return n
    return host


def pretty_host(host):
    """Last-resort display name for an unknown domain: "some-site.com" -> "Some Site"."""
    label = host.split(".")[-2] if host.count(".") >= 1 else host
    return " ".join(w.capitalize() for w in label.replace("-", " ").split()) or host


def fetch_bongino(cfg):
    url = cfg.get("url", "https://bonginoreport.com/")
    try:
        page = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read().decode("utf-8", "ignore")
    except Exception as e:
        print(f"CURATOR FAIL Bongino Report: {e!r}"[:160])
        return []
    own = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    out, seen = [], set()
    # Walk the page keeping track of the current section heading (to detect OPINION).
    section = ""
    for m in re.finditer(r'<h[1-6][^>]*>(.*?)</h[1-6]>|<a\s([^>]*)>(.*?)</a>', page, re.S):
        if m.group(1) is not None:
            section = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip().upper()
            continue
        attrs, text = m.group(2), html.unescape(re.sub(r"<[^>]+>", " ", m.group(3)))
        text = re.sub(r"\s+", " ", text).strip()
        h = re.search(r'href="(https?://[^"]+)"', attrs)
        if not h or len(text) < 20:
            continue
        link = html.unescape(h.group(1))
        host = urllib.parse.urlparse(link).netloc.lower()
        if own in host or any(s in host for s in SKIP_HOSTS) or link in seen:
            continue
        seen.add(link)
        out.append(dict(title=text, link=link, desc="", author="", cats=section, when=None,
                        source=outlet_name(link), opinion=section == "OPINION" or "/opinion/" in link,
                        curated=["Bongino Report"]))
    print(f"CURATOR OK Bongino Report: {len(out)} original links")
    return out


def fetch_rcp(cfg, settings=None, blocked=None):
    """RealClearPolitics link lists (RSS). Each item carries <originalLink> (the source
    article) and <author>"Name, Outlet"</author>. Keep only free, right-leaning or
    right-favorable picks (lean filter, source "RealClearPolitics Picks")."""
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime
    from ranking import lean
    label = cfg.get("label", "RealClearPolitics")
    out, seen, skipped_wall, total = [], set(), 0, 0
    for url in cfg.get("feeds", ["https://www.realclearpolitics.com/index.xml"]):
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read()
            root = ET.fromstring(data)
        except Exception as e:
            print(f"CURATOR FAIL {label} {url[:60]}: {e!r}"[:160]); continue
        for it in root.findall(".//item"):
            orig = (it.findtext("originalLink") or "").strip()
            title = html.unescape((it.findtext("title") or "").strip())
            if not orig.startswith("http") or not title or orig in seen:
                continue
            seen.add(orig); total += 1
            host = urllib.parse.urlparse(orig).netloc.lower()
            if any(s in host for s in SKIP_HOSTS) or "realclear" in host:
                continue
            if (blocked and blocked(orig)) or any(host.endswith(d) for d in cfg.get("skip_domains", [])):
                skipped_wall += 1; continue
            au = html.unescape(it.findtext("author") or "")
            name, _, outlet_txt = au.partition(",")
            item = dict(title=title, link=orig, desc=html.unescape(it.findtext("description") or "").strip(),
                        author=name.strip(), cats=it.findtext("category") or "", when=None,
                        source=outlet_name(orig), opinion="/opinion/" in orig or "/columnists/" in orig,
                        curated=[label])
            try:
                item["when"] = parsedate_to_datetime(it.findtext("pubDate"))
            except Exception:
                pass
            if settings is not None and not lean.keep(item, label + " Picks", settings,
                                                       outlet=item["source"], author=item["author"]):
                continue
            out.append(item)
    print(f"CURATOR OK {label}: {len(out)} kept of {total} picks ({skipped_wall} walled/blocked skipped)")
    return out


CURATORS = {"bongino_report": fetch_bongino, "realclearpolitics": fetch_rcp}


def fetch_all(settings, blocked=None):
    items = []
    for name, cfg in settings.get("curators", {}).items():
        if cfg.get("enabled") and name in CURATORS:
            if name == "realclearpolitics":
                items += fetch_rcp(cfg, settings, blocked)
            else:
                items += CURATORS[name](cfg)
    return items
