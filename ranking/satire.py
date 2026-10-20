"""Satire detection. Satire may run in the columns but is never the lead or a Top Story.

Classified per item, not only per outlet, since mostly-real outlets run satire sections:
  - outlet: the item's source or link domain is a satire outlet (settings satire.outlets / domains);
  - URL:    a path segment such as /satire/ or /parody/ (satire.url_segments);
  - feed:   an RSS category or tag such as "Satire" or "Parody" (satire.categories);
  - title:  an explicit label ("Satire:", "(Satire)", "[Parody]");
  - summary: an explicit disclaimer ("This is satire", "a work of parody").
A summary that merely mentions satire (a book review about comedy) does not count.
Commentary outlets that report real stories with a wry tone (Not the Bee) are not satire.
"""
import re
import urllib.parse

DEFAULT = {
    "outlets": ["The Babylon Bee", "Babylon Bee", "The Onion", "Duffel Blog", "The Hard Times", "ClickHole",
                "Reductress", "The Beaverton", "Genesius Times", "The Daily Mash", "Waterford Whispers News",
                "The Borowitz Report", "Hard Drive", "The Mideast Beast", "Satirical Times"],
    "domains": ["babylonbee.com", "theonion.com", "duffelblog.com", "thehardtimes.net", "clickhole.com",
                "reductress.com", "thebeaverton.com", "genesiustimes.com", "thedailymash.co.uk",
                "waterfordwhispersnews.com", "hard-drive.net", "themideastbeast.com"],
    "url_segments": ["satire", "parody", "humor-satire", "satirical"],
    "categories": ["satire", "parody", "satirical", "spoof"],
}

_LABEL = re.compile(r"^\s*[\[(]?\s*(satire|parody|spoof)\s*[\]):|—-]|[\[(]\s*(satire|parody|spoof)\s*[\])]\s*$", re.I)
_DISCLAIMER = re.compile(r"\b(this|the following) (is|was) (a )?(work of )?(satire|parody)\b"
                         r"|\ba work of (satire|parody)\b|\b(satire|parody) (piece|column) by\b|\bsatire alert\b", re.I)


def cfg(settings):
    c = dict(DEFAULT)
    c.update((settings or {}).get("satire") or {})
    return c


def _domain(u):
    h = urllib.parse.urlparse(u or "").netloc.lower()
    return h[4:] if h.startswith("www.") else h


def signal(item, settings=None):
    """The first satire signal that fires ('outlet', 'url', 'category', 'title', 'summary') or None."""
    c = cfg(settings)
    if not c.get("enabled", True):
        return None
    src = (item.get("source") or "").strip().lower()
    link = item.get("link") or ""
    d = _domain(link)
    if src in {o.lower() for o in c["outlets"]} or any(d == x or d.endswith("." + x) for x in c["domains"]):
        return "outlet"
    segs = [s.lower() for s in urllib.parse.urlparse(link).path.split("/") if s]
    if set(segs[:-1] if len(segs) > 1 else []) & set(c["url_segments"]):
        return "url"
    tags = {str(t).strip().lower() for t in item.get("tags") or []}
    if tags & set(c["categories"]):
        return "category"
    cats = (item.get("cats") or "").lower()  # space-joined categories when no tag list is kept
    if not tags and any(re.search(r"(?<![a-z])" + re.escape(x) + r"(?![a-z])", cats) for x in c["categories"]):
        return "category"
    if _LABEL.search(item.get("title") or ""):
        return "title"
    if _DISCLAIMER.search(item.get("desc") or ""):
        return "summary"
    return None


def is_satire(item, settings=None):
    return signal(item, settings) is not None
