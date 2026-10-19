"""Amplifier signal: stories linked to or echoed by configured public feeds
(e.g. a public figure's post archive RSS). Feed list and weights come from the
private config key "amplifiers": [{"name", "url", "weight", "max_age_hours"}].
Optional AMPLIFIER_ITEMS env var supplies a JSON list of
[{"url", "text", "ts", "weight"}] posts, or {"generated_at", "sources_blocked", "items": [...]} (per-item weight; default from private "amplifier_items_weight").
Exact link match = full credit; strong headline-term overlap = partial credit."""
import json, os, re, html, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from .util import UA, canon, tokens
from . import private
NAME = "amplifiers"


def _posts(feed, timeout):
    data = urllib.request.urlopen(urllib.request.Request(feed["url"], headers=UA), timeout=timeout).read()
    root = ET.fromstring(data)
    now = datetime.now(timezone.utc)
    out = []
    for it in root.findall(".//item"):
        try:
            when = parsedate_to_datetime(it.findtext("pubDate") or "")
        except Exception:
            when = None
        if when and (now - when).total_seconds() > feed.get("max_age_hours", 48) * 3600:
            continue
        body = html.unescape(f'{it.findtext("title") or ""} {it.findtext("description") or ""}')
        links = {canon(u) for u in re.findall(r'href="(https?://[^"]+)"', body)}
        text = re.sub(r"<[^>]+>", " ", body)
        links |= {canon(u) for u in re.findall(r"https?://\S+", text)}
        out.append((links, set(tokens(text))))
    return out


def newest_age_hours(data, now=None):
    """Age in hours of the newest timestamped item, or None if no item has a readable ts."""
    now = now or datetime.now(timezone.utc)
    ages = []
    for it in data if isinstance(data, list) else []:
        try:
            ages.append((now - datetime.fromisoformat(str(it["ts"]).replace("Z", "+00:00"))).total_seconds() / 3600)
        except Exception:
            pass
    return min(ages) if ages else None


def _payload(raw):
    """AMPLIFIER_ITEMS is either a bare list of items (legacy) or {"generated_at", "items", "sources_blocked"}."""
    data = json.loads(raw)
    if isinstance(data, dict):
        return data.get("items") if isinstance(data.get("items"), list) else [], data
    return data, {}


def _age_h(ts, now=None):
    try:
        return ((now or datetime.now(timezone.utc)) - datetime.fromisoformat(str(ts).replace("Z", "+00:00"))).total_seconds() / 3600
    except Exception:
        return None


def staleness(stale_hours=6):
    """Warn (GitHub Actions annotation) when the AMPLIFIER_ITEMS harvest is missing or too old. Freshness is the
    harvest time (generated_at), not the newest post: a quiet hour or one blocked source is not staleness, and
    each item is still aged out on its own (amplifier_items_max_age_hours)."""
    raw = os.environ.get("AMPLIFIER_ITEMS", "").strip()
    try:
        items, meta = _payload(raw) if raw else ([], {})
    except Exception:
        items, meta = [], {}
    newest = newest_age_hours(items)
    harvest = _age_h(meta.get("generated_at")) if meta.get("generated_at") else newest
    blocked = int(meta.get("sources_blocked") or 0)
    note = f"newest item {newest:.1f}h old" if newest is not None else "no dated items"
    if blocked:
        note += f"; {blocked} source(s) blocked, their last items kept until they age out"
    if harvest is None or harvest > stale_hours:
        msg = "missing or undated" if harvest is None else f"harvest {harvest:.1f}h old, {note}"
        print(f"::warning::amplifier data stale ({msg}; limit {stale_hours}h). Refresh the AMPLIFIER_ITEMS secret.")
        return True
    print(f"  amplifier items fresh: harvest {harvest:.1f}h old, {note}")
    return False


def _items_from_env(max_age_hours=48):
    raw = os.environ.get("AMPLIFIER_ITEMS", "").strip()
    if not raw:
        return []
    try:
        data, _ = _payload(raw)
    except Exception:
        print("  amplifier items: invalid JSON")
        return []
    if not isinstance(data, list):
        print("  amplifier items: expected a JSON list")
        return []
    now = datetime.now(timezone.utc)
    out = []
    for it in data:
        if not isinstance(it, dict):
            continue
        url = (it.get("url") or "").strip()
        text = (it.get("text") or "").strip()
        if not url and not text:
            continue
        ts = it.get("ts")
        if ts:
            try:
                when = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                if (now - when).total_seconds() > max_age_hours * 3600:
                    continue
            except Exception:
                pass
        links = {canon(url)} if url else set()
        try:
            w = float(it["weight"]) if "weight" in it else None
        except Exception:
            w = None
        out.append((w, links, set(tokens(text or url))))
    return out


def compute(clusters, settings, ctx):
    cfg = private.load(ctx)
    feed_cfg = cfg.get("amplifiers", [])
    timeout = settings.get("social", {}).get("timeout_seconds", 10)
    feeds, ok = [], 0
    for i, f in enumerate(feed_cfg):
        try:
            feeds.append((f.get("weight", 1.0), _posts(f, timeout))); ok += 1
            print(f"  amplifier feed {i + 1}: ok, {len(feeds[-1][1])} recent posts")
        except Exception as e:
            print(f"  amplifier feed {i + 1}: unavailable ({getattr(e, 'code', type(e).__name__)})")
    ctx["amplifier_stale"] = staleness(float(settings.get("amplifier_stale_hours", 6)))
    items = _items_from_env(cfg.get("amplifier_items_max_age_hours", 48))
    if items:
        # Items may carry their own weight; group them so each weight counts as one source.
        default_w = float(cfg.get("amplifier_items_weight", 1.0))
        groups = {}
        for w, links, toks in items:
            groups.setdefault(default_w if w is None else w, []).append((links, toks))
        for w, posts in sorted(groups.items(), reverse=True):
            feeds.append((w, posts))
        ok += 1
        print(f"  amplifier items: ok, {len(items)} recent posts in {len(groups)} weight groups")
    if not ok:
        return None
    total_w = sum(w for w, _ in feeds) or 1.0
    out = {}
    for c in clusters:
        links = {canon(s["link"]) for s in c["items"]}
        tt = set(tokens(c["items"][0]["title"]))
        score = 0.0
        for w, posts in feeds:
            best = 0.0
            for plinks, ptoks in posts:
                if links & plinks:
                    best = 1.0; break
                if len(tt) >= 4:
                    ov = len(tt & ptoks)
                    if ov >= 3 and ov / len(tt) >= 0.5:
                        best = max(best, 0.5)
            score += w * best
        out[c["id"]] = min(1.0, score / total_w)
    print(f"signal amplifiers: {sum(1 for v in out.values() if v > 0)} clusters matched")
    return out
