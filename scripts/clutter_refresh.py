#!/usr/bin/env python3
"""Refresh clutter_scores.json: per outlet domain, fetch the newest article from each PUBLIC feed in
aggregator.FEEDS and measure page clutter. Also tests lighter URL variants (AMP / print) and records
a variant rule only if it returns the full article text without a login.

  python3 scripts/clutter_refresh.py            # writes clutter_scores.json

Score = cleanliness in [0, 1] (1 = clean). Components (each 0..1, 1 = clean):
  weight   page bytes          (<=150 KB -> 1, >=2.5 MB -> 0)
  scripts  <script> tags       (<=10 -> 1, >=120 -> 0)
  ads      ad/tracker hosts    (0 -> 1, >=25 -> 0)
  autoplay autoplay video      (none -> 1, else 0)
  modals   newsletter/interstitial/paywall markers (0 -> 1, >=6 -> 0)
  text     text-to-HTML ratio  (>=10% -> 1, <=1% -> 0)
"""
import json, os, re, sys, html, concurrent.futures as cf, urllib.request
from datetime import datetime, timezone
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "clutter_scores.json")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120 Safari/537.36"}

AD_HOSTS = ["doubleclick.net", "googlesyndication.com", "googletagservices.com", "googletagmanager.com",
            "google-analytics.com", "adservice.google", "amazon-adsystem.com", "taboola.com", "outbrain.com",
            "criteo", "pubmatic.com", "rubiconproject.com", "openx.net", "adnxs.com", "casalemedia.com",
            "moatads.com", "scorecardresearch.com", "quantserve.com", "chartbeat", "parsely", "permutive",
            "connatix", "primis", "jwplayer", "brightcove", "teads", "sharethrough", "33across", "indexww",
            "adthrive", "raptive", "mediavine", "ezoic", "admiral", "piano.io", "tinypass", "zergnet",
            "revcontent", "mgid.com", "facebook.net", "hotjar", "newrelic", "segment.com", "optimizely",
            "kargo", "gumgum", "sovrn", "lijit", "yieldmo", "triplelift", "springserve", "aniview", "vidazoo"]
MODAL = [r"newsletter", r"interstitial", r"\bmodal\b", r"paywall", r"subscribe-?wall", r"regwall", r"popup",
         r"pop-up", r"exit-?intent", r"adblock", r"sign up for", r"meter(ed)?-?wall"]


def lin(x, good, bad):
    return max(0.0, min(1.0, (bad - x) / (bad - good))) if bad != good else 1.0


def get(url, n=4_000_000):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.geturl(), r.read(n).decode("utf-8", "ignore")


def article_text(h):
    body = re.sub(r"(?is)<(script|style|noscript|svg|nav|header|footer|aside)\b.*?</\1>", " ", h)
    ps = re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", body)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", " ".join(ps)))).strip()


def measure(h):
    nbytes = len(h.encode("utf-8", "ignore"))
    scripts = len(re.findall(r"(?i)<script\b", h))
    srcs = " ".join(re.findall(r'(?i)(?:src|href)=["\']([^"\']+)', h)) + " " + " ".join(re.findall(r"(?is)<script\b[^>]*>(.*?)</script>", h))[:400000]
    ads = sum(len(re.findall(re.escape(a), srcs, re.I)) for a in AD_HOSTS)
    autoplay = bool(re.search(r"(?i)<video[^>]*\bautoplay|autoplay=1|\"autoplay\"\s*:\s*true|data-autoplay=\"true\"", h))
    modals = sum(len(re.findall(p, h, re.I)) > 0 for p in MODAL) + min(3, len(re.findall(r"(?i)class=\"[^\"]*(modal|overlay)[^\"]*\"", h)) // 3)
    text = article_text(h)
    ratio = len(text) / max(1, len(h))
    comp = {"weight": lin(nbytes, 150_000, 2_500_000), "scripts": lin(scripts, 10, 120), "ads": lin(ads, 0, 25),
            "autoplay": 0.0 if autoplay else 1.0, "modals": lin(modals, 0, 6), "text": lin(ratio, 0.10, 0.01)}
    w = {"weight": 0.2, "scripts": 0.2, "ads": 0.25, "autoplay": 0.1, "modals": 0.1, "text": 0.15}
    score = sum(comp[k] * w[k] for k in w)
    return {"score": round(score, 3), "kb": nbytes // 1024, "scripts": scripts, "ad_hits": ads, "autoplay": autoplay,
            "modal_markers": modals, "text_ratio": round(ratio, 4), "text_chars": len(text)}


def variants(url, h):
    v = []
    m = re.search(r'(?i)<link[^>]+rel=["\']amphtml["\'][^>]*href=["\']([^"\']+)', h) or \
        re.search(r'(?i)<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']amphtml', h)
    if m:
        v.append(("amphtml", html.unescape(m.group(1))))
    base = url.split("?", 1)[0].split("#", 1)[0]
    v += [("outputType=amp", base + "?outputType=amp"), ("/amp/", base.rstrip("/") + "/amp/"),
          ("amp/ prefix", re.sub(r"^(https?://[^/]+)/", r"\1/amp/", base))]
    return v


def rule_for(kind, url, vurl):
    """A transform the build can apply to other URLs of the same outlet."""
    base = url.split("?", 1)[0].split("#", 1)[0]
    if vurl == base + "?outputType=amp":
        return {"type": "query", "value": "outputType=amp"}
    if vurl == base.rstrip("/") + "/amp/" or vurl == base.rstrip("/") + "/amp":
        return {"type": "suffix", "value": "/amp/"}
    pre = re.sub(r"^(https?://[^/]+)/", r"\1/amp/", base)
    if vurl.split("?")[0] == pre:
        return {"type": "prefix", "value": "/amp/"}
    if kind == "amphtml":
        return {"type": "amphtml"}  # per-article <link rel=amphtml>; the build reads it from the page
    return None


def full_article(vh, canon_text):
    t = article_text(vh)
    login = re.search(r"(?i)(log ?in|sign ?in|subscribe) to (continue|read)", vh)
    return len(t) >= max(600, 0.8 * len(canon_text)) and not login


def outlet(feed):
    import aggregator as A
    name, url = feed[0], feed[1]
    items = A.fetch(feed)  # real fetch/parse path
    links = [i["link"] for i in sorted(items, key=lambda i: i.get("when") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)]
    for link in links[:3]:
        try:
            st, final, h = get(link)
        except Exception:
            continue
        if st != 200 or len(h) < 5000:
            continue
        m = measure(h)
        res = {"outlet": name, "sample": final, **m, "variant": None}
        canon_text = article_text(h)
        for kind, vurl in variants(final, h):
            try:
                vst, vfinal, vh = get(vurl)
            except Exception:
                continue
            if vst == 200 and full_article(vh, canon_text):
                vm = measure(vh)
                rule = rule_for(kind, final, vurl)
                if rule and vm["score"] > m["score"] + 0.05:
                    res["variant"] = {**rule, "score": vm["score"], "kb": vm["kb"], "tested": vurl}
                    break
        return urlsplit(final).netloc.lower().removeprefix("www."), res
    return None


def main():
    import aggregator as A
    feeds = [f for f in A.FEEDS]
    out = {}
    with cf.ThreadPoolExecutor(8) as ex:
        for r in ex.map(outlet, feeds):
            if r:
                dom, res = r
                if dom not in out or res["score"] < out[dom]["score"]:
                    out[dom] = res
    doc = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "method": "scripts/clutter_refresh.py; score 0..1, 1 = clean", "domains": dict(sorted(out.items()))}
    json.dump(doc, open(OUT, "w"), indent=1, ensure_ascii=False)
    print(f"wrote {OUT}: {len(out)} domains")
    for d, r in sorted(out.items(), key=lambda kv: -kv[1]["score"]):
        print(f"{r['score']:.3f} {d:32} {r['kb']:5}KB scripts={r['scripts']:3} ads={r['ad_hits']:3} "
              f"autoplay={int(r['autoplay'])} modals={r['modal_markers']} text={r['text_ratio']:.3f} "
              f"variant={(r['variant'] or {}).get('type')}")


if __name__ == "__main__":
    main()
