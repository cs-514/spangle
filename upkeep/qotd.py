"""Quote of the Day: pick one unused, verified quote from qotd_bank.json and publish it.

  python -m upkeep.qotd            # pick + apply: write quote_of_the_day.json and usage state, commit, push, build
  python -m upkeep.qotd --dry-run  # show the pick only

Rules (see docs/UPKEEP.md): rotate authors (never the same author two days running), never reuse a quote id,
exact bank text only (primary-source verified entries), favor famous high-impact lines (bank "impact" 1-5,
"low_impact" status only as a last resort), de-weighted authors less often (bank author_weights). With LLM_API_KEY set, an LLM
chooses from a short list of eligible quotes the one that best fits today's top stories; it can only return a
bank id, never new text. Without a key the pick is deterministic (hash of the Eastern date, weighted).
No per-quote headline: the page shows the QUOTE OF THE DAY label, the quote, and the linked attribution.
"""
import hashlib, html, json, os, re, sys
from collections import defaultdict
from .common import ROOT, STATE, load_json, save_json, now_et, commit_and_push, dispatch_build, llm_config, \
    llm_json, http_get, warn

sys.path.insert(0, ROOT)
from ranking.headline import dashes  # noqa: E402

BANK = os.path.join(ROOT, "qotd_bank.json")
USED = os.path.join(STATE, "quote_used.json")
OUT = os.path.join(ROOT, "quote_of_the_day.json")
SITE = "https://cs-514.github.io/spangle/"
GUEST_WEIGHT = 0.25
SHORTLIST = 24


def word_limit(q):
    return 90 if q.get("public_domain") else 60


def prefix(q):
    return q["id"].split("-")[0]


def eligible(bank, used):
    rotation = {a.get("id_prefix") for a in bank.get("authors") or [] if a.get("id_prefix")} or None
    used_ids = set(used.get("used_ids") or [])
    out = []
    for q in bank["quotes"]:
        if not q.get("verified") or q.get("source_type") not in ("primary", "column") or q.get("status") == "retired":
            continue
        if rotation and prefix(q) not in rotation:
            continue
        if q["id"] in used_ids or len(q["quote"].split()) > word_limit(q):
            continue
        out.append(q)
    return out


def recent_authors(used, today):
    """Authors to avoid today: the last one published (never two days running)."""
    hist = [h for h in used.get("history") or [] if h.get("date") != today]
    last = hist[-1]["author"] if hist else used.get("last_author")
    return {last} if last else set()


def author_weight(qs, bank):
    base = max(float(q.get("weight", GUEST_WEIGHT if q["id"].startswith("guest-") else 1)) for q in qs)
    return base * float((bank.get("author_weights") or {}).get(prefix(qs[0]), 1))


def quote_weight(q):
    return float(q.get("impact", q.get("weight", 1)))


def weighted(items, weights, h):
    ws = [max(0, int(round(w * 1000))) for w in weights]
    if not sum(ws):
        return items[h % len(items)]
    r = h % sum(ws)
    for it, w in zip(items, ws):
        if r < w:
            return it
        r -= w
    return items[-1]


def by_author_pool(bank, used, today):
    pool = defaultdict(list)
    for q in eligible(bank, used):
        pool[q["author"]].append(q)
    if not pool:
        raise SystemExit("no unused verified quotes left: add verified quotes to qotd_bank.json")
    avoid = recent_authors(used, today)
    authors = sorted(a for a in pool if a not in avoid) or sorted(pool)
    return {a: pool[a] for a in authors}


def best_quotes(qs):
    return [q for q in qs if q.get("status") != "low_impact"] or qs


def deterministic_pick(bank, used, today):
    pool = by_author_pool(bank, used, today)
    h = int(hashlib.sha256(today.encode()).hexdigest(), 16)
    authors = list(pool)
    author = weighted(authors, [author_weight(pool[a], bank) for a in authors], h)
    qs = best_quotes(pool[author])
    return weighted(qs, [quote_weight(q) for q in qs], h)


def shortlist(bank, used, today, n=SHORTLIST):
    """Highest-impact eligible quotes, a few per author, de-weighted authors (bank author_weights) get fewer slots."""
    pool = by_author_pool(bank, used, today)
    out = []
    for a, qs in pool.items():
        k = 1 if author_weight(qs, bank) < 0.5 else 3
        out += sorted(best_quotes(qs), key=lambda q: -quote_weight(q))[:k]
    out.sort(key=lambda q: (-quote_weight(q), q["id"]))
    return out[:n]


def top_stories(limit=12):
    """Lead + Top Stories headlines from the live page (public)."""
    try:
        h = http_get(SITE, timeout=20)
    except Exception:
        return []
    m = re.search(r'<div class="lead">(.*?)<div class="cols"', h, re.S)
    block = m.group(1) if m else h[:20000]
    heads = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", a))).strip() for a in re.findall(r"<a [^>]*>(.*?)</a>", block, re.S)]
    return [x for x in heads if x][:limit]


def llm_pick(bank, used, today, cfg):
    cands = shortlist(bank, used, today)
    stories = top_stories()
    sys_prompt = ("You choose Spangle's Quote of the Day from a fixed list of verified quotes. Prefer the author's most "
                  "famous, high-impact lines (higher 'impact' is better) and, when one fits naturally, a quote that "
                  "resonates with today's top stories. Never pick something that would read as mocking a tragedy. "
                  'Reply with JSON only: {"id": "<one id from the list>", "why": "<under 15 words>"}')
    user = json.dumps({"today": today, "top_stories": stories,
                       "quotes": [{"id": q["id"], "author": q["author"], "work": q.get("work", ""), "impact": q.get("impact"),
                                   "quote": q["quote"]} for q in cands]}, ensure_ascii=False)
    res = llm_json(sys_prompt, user, cfg, max_tokens=300)
    pick = next((q for q in cands if q["id"] == str(res.get("id", "")).strip()), None)
    if not pick:
        raise RuntimeError("LLM returned an id outside the list")
    print(f"LLM pick: {pick['id']} ({str(res.get('why', ''))[:100]})")
    return pick


def pick(bank, used, today):
    cfg = llm_config()
    if cfg:
        try:
            return llm_pick(bank, used, today, cfg)
        except Exception as e:
            warn(f"QOTD LLM pick failed ({e}); using the deterministic pick")
    else:
        print("LLM_API_KEY not set: deterministic pick (degraded mode)")
    return deterministic_pick(bank, used, today)


def public_entry(q, today):
    out = {"date": today, "quote": dashes(q["quote"].strip()), "author": q["author"],
           "work": q.get("work") or "", "locator": q.get("locator") or ""}
    if q.get("verification_url"):
        out["verification_url"] = q["verification_url"]
    return out


def record_use(used, q, today):
    used.setdefault("used_ids", [])
    if q["id"] not in used["used_ids"]:
        used["used_ids"].append(q["id"])
    used["last_author"] = q["author"]
    used["history"] = [h for h in used.setdefault("history", []) if h.get("date") != today or h.get("note")]
    used["history"].append({"date": today, "bank_id": q["id"], "author": q["author"]})
    return used


def main():
    today = now_et().strftime("%Y-%m-%d")
    bank = load_json(BANK)
    used = load_json(USED, {"used_ids": [], "last_author": None, "history": []})
    current = load_json(OUT, {}) or {}
    if current.get("date") == today and "--force" not in sys.argv and "--dry-run" not in sys.argv:
        print(f"quote_of_the_day.json is already dated {today}; nothing to do (use --force to re-pick)")
        return 0
    q = pick(bank, used, today)
    entry = public_entry(q, today)
    print(json.dumps(dict(entry, bank_id=q["id"]), indent=1, ensure_ascii=False))
    if "--dry-run" in sys.argv:
        return 0
    save_json(OUT, entry)
    save_json(USED, record_use(used, q, today))
    if commit_and_push(["quote_of_the_day.json", "upkeep/state/quote_used.json"], "Quote of the Day"):
        dispatch_build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
