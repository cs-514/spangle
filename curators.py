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
}


def outlet_name(url):
    host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    for d, n in OUTLETS.items():
        if host == d or host.endswith("." + d):
            return n
    return host


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


CURATORS = {"bongino_report": fetch_bongino}


def fetch_all(settings):
    items = []
    for name, cfg in settings.get("curators", {}).items():
        if cfg.get("enabled") and name in CURATORS:
            items += CURATORS[name](cfg)
    return items
