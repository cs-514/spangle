"""Headline rewrites: find bland/over-long/fragment headlines on the page, have an LLM write punchy,
faithful Drudge-style replacements, gate them, and commit them to headline_overrides.json.

  python -m upkeep.rewrite            # queue -> LLM -> gates -> tests + confidentiality guard -> commit, push, build
  python -m upkeep.rewrite --queue    # only build and summarize the queue (no LLM, no commit)

Needs LLM_API_KEY (plus optional LLM_BASE_URL / LLM_MODEL) for the LLM step; without it the job reports
the queue size and stops (degraded mode, the site keeps its current headlines). Extra private guidance can
be supplied in the REWRITE_GUIDANCE secret; it is sent to the LLM only, never printed.
"""
import html, json, os, re, sys, urllib.request
from .common import ROOT, TMP, load_json, private_config, run_checks, commit_and_push, dispatch_build, \
    llm_config, llm_json, http_get, warn

sys.path.insert(0, ROOT)
from ranking.headline import dashes, smartquotes, obscure_acronyms, incomplete  # noqa: E402
from ranking.defeatism import classify  # noqa: E402

QUEUE = os.path.join(TMP, "rewrite_queue.json")
OVERRIDES = os.path.join(ROOT, "headline_overrides.json")
STYLE = os.path.join(ROOT, "docs", "STYLE.md")
MAX_ITEMS = 30
MAX_WORDS = 10

OBSCURE_FEW_SHOT = [
    {"before": "Ex-SJSU Coach Sues over ‘Trump Lover’ Barbs Amid Trans Scandal",
     "after": "College’s Ex-Coach Sues over ‘Trump Lover’ Barbs Amid Trans Scandal"},
    {"before": "NRSC Ad Mocks Peltola", "after": "GOP Senate Arm’s Ad Mocks Peltola"},
    {"before": "FBI Probes Letters with DSA-Linked Address", "after": "FBI Probes Letters with Socialist-Linked Address"},
    {"before": "CENTCOM Says Strait Stays Open", "after": "U.S. Military Says Strait Stays Open"},
    {"before": "AFT Boss Defends Closures", "after": "Teachers Union Boss Defends Closures"},
]
IMPRIMIS_FEW_SHOT = [{"before": "The Rise of Democratic Socialism", "after": "Socialism’s Persistent, Disturbing Rise"}]

GUIDANCE = """You write display headlines for Spangle, a one-page, Drudge-style conservative news aggregator.
For each queued story write ONE punchy, faithful headline:
- At most 10 words (Imprimis essays: 3-6 words). Active voice, strong verb, the news first.
- FAITHFUL: never misstate the article. Use only facts in the title, excerpt or article text given. If the
  article text does not match the title, or you are unsure, return "" for that URL (skip it).
- Never defeatist framing about conservatives, the right or its leaders; feature the opponent or the action.
  Don't make an in-party defector the hero.
- Compress: no leading The/A/An, cut linking verbs between parallel phrases, keep the action verb.
- Quotable line (rare): only when the article has a genuinely outrageous, eye-catching quote or writer's line
  that clearly beats a normal rewrite, build the headline from it, with accurate attribution.
- Academic/explainer items (reason "academic"): rewrite around the news hook with the case's popular name or
  the issue, never the docket name; with no current hook return "".
- Obscure acronyms (reason "obscure_acronym"): only acronyms every national reader knows (FBI, DOJ, CIA, ICE,
  GOP, SCOTUS, NATO, DOGE, NCAA); replace others with a plain descriptor, same length or shorter.
- Fragments (reason "fragment"): a complete thought with a subject and a finite verb. Participle predicates
  ('Ex-Coach Arrested'), 'X to Sign' and speaker colons are fine.
- Imprimis (reason "imprimis"): find the thesis in the opening; 1-2 sharp evaluative words, no articles.
- House style: AP/Chicago title case, single curly quotes ‘ ’ and apostrophes ’, 'with'/'to'/'over'
  lowercase, Dems (never DEMS), closed em dashes (Word—Word), numerals.
The full house style manual follows. Reply with JSON only: {"rewrites": {"<url>": "<headline or empty>"}}.
"""


def article_text(url, n=3, limit=1500):
    """og:title + og:description + the first paragraphs, so the model can check the facts."""
    try:
        body = http_get(url, timeout=15, limit=1_500_000)
    except Exception:
        return ""
    def meta(prop):
        m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]+content=["\']([^"\']+)' % prop, body, re.I)
        return html.unescape(m.group(1)).strip() if m else ""
    ps = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", p))).strip()
          for p in re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", body)]
    ps = [p for p in ps if len(p) > 80][:n]
    return "\n".join(x for x in [meta("og:title"), meta("og:description")] + ps if x)[:limit]


def build_queue():
    env = dict(os.environ, SPANGLE_QUEUE_PATH=QUEUE)
    import subprocess
    r = subprocess.run([sys.executable, "-u", "aggregator.py"], cwd=ROOT, env=env, capture_output=True, text=True)
    # aggregator output is already sanitized for public build logs; show only its summary lines
    for line in r.stdout.splitlines():
        if line.startswith(("headlines:", "stories:", "built", "wrote")):
            print(line)
    if r.returncode != 0:
        raise SystemExit(f"aggregator failed (exit {r.returncode})")
    q = load_json(QUEUE, {}) or {}
    ov = load_json(OVERRIDES, {}) or {}
    keys = set(ov) | {k.split("?", 1)[0] for k in ov}

    def urls(it):
        return [u for u in [it.get("url", "")] + [s.get("url", "") for s in it.get("siblings", [])] if u]

    def texts(it):
        return [t for t in (ov.get(u) or ov.get(u.split("?", 1)[0]) for u in urls(it)) if t]

    def keep(it):
        if it.get("reason") == "obscure_acronym":
            t = texts(it); return not (t and all(not obscure_acronyms(x) for x in t))
        if it.get("reason") == "fragment":
            ok = lambda x: incomplete(x) is None or (incomplete(x) == "no_finite_verb" and "imprimis.hillsdale.edu" in it.get("url", ""))
            t = texts(it); return not (t and all(ok(x) for x in t))
        return not any(u in keys or u.split("?", 1)[0] in keys for u in urls(it))
    items = [it for it in q.get("items", []) if keep(it)]
    print(f"queue: {len(q.get('items', []))} flagged, {len(items)} need a rewrite (others have saved overrides)")
    return items


def gate(done, queue_urls, dcfg):
    """Apply the house gates. Returns (accepted {url: headline}, rejected count by reason)."""
    out, rej = {}, {}
    for url, t in done.items():
        if url not in queue_urls or not isinstance(t, str) or not t.strip():
            continue
        t = dashes(t.strip().strip('"'))
        t = smartquotes(t).replace("“", "‘").replace("”", "’")  # house style: single curly quotes
        why = None
        if len(t.split()) > MAX_WORDS + 2:
            why = "too_long"
        elif dcfg and classify(t, dcfg) == "exclude":
            why = "defeatist"
        elif obscure_acronyms(t):
            why = "obscure_acronym"
        else:
            k = incomplete(t)
            if k and not (k == "no_finite_verb" and "imprimis.hillsdale.edu" in url):
                why = "fragment"
        if why:
            rej[why] = rej.get(why, 0) + 1
            print(f"REJECTED ({why}): {url}")
        else:
            out[url] = t
    return out, rej


def main():
    items = build_queue()
    if "--queue" in sys.argv or not items:
        return 0
    cfg = llm_config()
    if not cfg:
        warn(f"LLM_API_KEY not set: {len(items)} headline rewrites skipped (degraded mode)")
        return 0
    items = items[:MAX_ITEMS]
    for it in items:
        if it.get("reason") == "imprimis" and not it.get("opening"):
            it["opening"] = article_text(it["url"], n=4, limit=3000)
        else:
            it["article"] = article_text(it["url"])
        it["few_shot"] = OBSCURE_FEW_SHOT if it.get("reason") == "obscure_acronym" else \
            IMPRIMIS_FEW_SHOT if it.get("reason") == "imprimis" else None
        if not it["few_shot"]:
            it.pop("few_shot")
    system = GUIDANCE + "\n" + os.environ.get("REWRITE_GUIDANCE", "") + "\n\n" + open(STYLE).read()
    try:
        res = llm_json(system, json.dumps({"items": items}, ensure_ascii=False), cfg)
    except Exception as e:
        warn(f"headline rewrites skipped: {e}")
        return 0
    done = res.get("rewrites", res) if isinstance(res, dict) else {}
    queue_urls = {it["url"] for it in items}
    accepted, rej = gate(done, queue_urls, private_config().get("defeatism") or {})
    print(f"rewrites: {len(accepted)} accepted, {sum(rej.values())} rejected {rej or ''}".rstrip())
    if not accepted:
        return 0
    before = open(OVERRIDES, "rb").read() if os.path.exists(OVERRIDES) else None
    ov = load_json(OVERRIDES, {}) or {}
    ov.update(accepted)
    with open(OVERRIDES, "w") as f:
        json.dump(ov, f, indent=1, sort_keys=True)
    for url, t in sorted(accepted.items()):
        print(f"  {t}  <- {url}")
    ok, why = run_checks()
    if not ok:
        if before is None:
            os.remove(OVERRIDES)
        else:
            open(OVERRIDES, "wb").write(before)
        warn(f"rewrites not committed: {why}")
        return 1
    if commit_and_push(["headline_overrides.json"], "Update headline display overrides"):
        dispatch_build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
