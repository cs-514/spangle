"""Newsworthiness gate + celebrity filter. Lexicons live in the private config key "newsworthiness"
(with the "lifestyle" hooks, "outrage" terms and boost keywords also counted as core criteria).

- Celebrity / entertainment stories (celebrity terms in the headline, an entertainment URL path, or
  celebrity personal-life / gossip cues with no political or national hook in the headline) are DROPPED unless
    (a) a conservative celebrity is speaking out  -> kept and scored favorably, or
    (b) a Hollywood/celebrity figure makes a fool of themselves on politics or geopolitics
        (a politics term plus a backlash/ridicule term)  -> kept.
- Major business / tech breakthroughs and wins by conservative-aligned figures (private list) are core
  criteria and qualify for the lead and Top Stories (exempt from the business/tech soft gate); a story that
  hits both scores highest.
- Routine local crime/court items (bond hearings, arraignments, local sentencing: only routine court words)
  don't count as core unless they carry a national hook (prominent person, illegal-immigration, political or
  culture-war angle) or have 4+ outlets; otherwise they are dropped.
- Every other story must hit at least one core criterion (political, policy, culture-war, legal,
  national-security or outrage angle) to be featured. Stories with none are kept out of the lead and
  Top Stories and scored `penalty` (heavily downranked in the columns).
Flags: c["celebrity"] = "conservative" | "fool" ; c["off_criteria"] = True ; c["dropped"] = True."""
import re
from . import private
NAME = "newsworthy"


_SUFFIX = r"(?:s|es|ed|d|ing|er|ers|ship|ism|ist|ists|ly)?(?![a-z0-9])"


def _rx(words, open_end=True):
    """Word-start match (lexicons rely on prefixes: a term matches any word it begins). With
    open_end=False a term may only take a common suffix ('tribute' -> 'tributes') and never runs into
    another word ('beau' never matches 'beautiful'); used for the gossip cues."""
    words = [w.lower() for w in words if w]
    if not words:
        return None
    alt = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(r"(?<![a-z0-9])(?:" + alt + r")" + ("" if open_end else _SUFFIX))


def lexicon(ctx):
    pc = private.load(ctx)
    nw = pc.get("newsworthiness") or {}
    if not nw.get("enabled"):
        return None
    core = list(nw.get("core_terms", [])) + list((pc.get("lifestyle") or {}).get("hooks", [])) \
        + list((pc.get("outrage") or {}).get("terms", [])) + list(pc.get("boost_keywords") or {})
    return {"core": _rx(core), "celeb": _rx(nw.get("celebrity_terms", [])),
            "gossip": _rx(nw.get("celebrity_gossip_terms", []), open_end=False),
            "paths": [p.lower() for p in nw.get("entertainment_paths", [])],
            "cons": _rx(nw.get("conservative_celebs", [])), "speak": _rx(nw.get("speaking_out_terms", [])),
            "fool": _rx(nw.get("fool_terms", [])), "pol": _rx(nw.get("politics_terms", [])),
            "biz": _rx(nw.get("business_terms", [])), "fig": _rx(nw.get("aligned_figures", [])),
            "win": _rx(nw.get("win_terms", [])), "scores": {"core": 0.85, "business_or_aligned": 0.9, "both": 1.0,
                                                           **(nw.get("scores") or {})},
            "routine": _rx(nw.get("routine_court_terms", [])), "routine_set": {w.lower() for w in nw.get("routine_court_terms", [])},
            "hooks": _rx(nw.get("national_hooks", []) + nw.get("politics_terms", []) + nw.get("aligned_figures", [])),
            "routine_min": int(nw.get("routine_min_outlets", 4)), "routine_drop": bool(nw.get("routine_drop", True)),
            "penalty": float(nw.get("penalty", 0.15)), "cons_score": float(nw.get("conservative_celeb_score", 1.0))}


def _hit(rx, text):
    return bool(rx and rx.search(text))


def _news_hook(item, lx):
    """A political / national hook in the headline that is not itself a celebrity term."""
    t = item["title"].lower().replace("’", "'")
    return any(not _hit(lx["celeb"], m.group(0)) for m in lx["hooks"].finditer(t)) if lx.get("hooks") else False


def classify(item, lx):
    """-> "conservative" | "fool" | "drop" (celebrity cases), "core" or "off" (everything else)."""
    t = item["title"].lower().replace("’", "'")
    hay = f"{t} {(item.get('desc') or '').lower()}".replace("’", "'")
    link = (item.get("link") or "").lower()
    celeb = _hit(lx["celeb"], t) or any(p in link for p in lx["paths"]) or t.startswith("review:")
    if not celeb and lx.get("gossip"):
        # celebrity personal-life / gossip story with no named celebrity term ('X Shares Heartbreaking
        # Tribute After Son's Death', 'Y Beams as Z Makes Dazzling Debut'): celebrity unless the headline
        # carries a political / national hook outside the gossip cue itself ('Custody Wars' is no war);
        # two gossip cues outweigh an incidental core word
        gm = list(lx["gossip"].finditer(t))
        inside = lambda m: any(g.start() <= m.start() < g.end() for g in gm)
        hook = any(not inside(m) for m in lx["hooks"].finditer(t)) if lx.get("hooks") else False
        core_out = any(not inside(m) for m in lx["core"].finditer(t)) if lx.get("core") else False
        g = {m.group(0) for m in gm}
        celeb = bool(g) and not hook and (len(g) >= 2 or not core_out)
    cons = _hit(lx["cons"], t)
    if cons and (_hit(lx["speak"], t) or _hit(lx["pol"], hay)):
        return "conservative"
    if celeb:
        if _hit(lx["pol"], hay) and _hit(lx["fool"], hay):
            return "fool"
        return "drop"
    biz = _hit(lx.get("biz"), t)                                    # major business / tech breakthrough
    ally = _hit(lx.get("fig"), hay) and _hit(lx.get("win"), t)      # win by a conservative-aligned figure
    if biz and ally:
        return "both"
    if biz or ally:
        return "business_or_aligned"
    if not lx["core"]:
        return "off"
    hits = {m.group(0) for m in lx["core"].finditer(hay)}
    if not hits:
        return "off"
    rs = lx.get("routine_set") or set()
    if rs and all(h in rs or any(h.startswith(r) for r in rs) for h in hits):
        # only routine crime/court words (bond hearing, arraignment, local sentencing): needs a national hook
        return "core" if _hit(lx.get("hooks"), hay) else "routine"
    return "core"


def compute(clusters, settings, ctx):
    lx = lexicon(ctx)
    if lx is None:
        return None
    out, n = {}, {"drop": 0, "off": 0, "conservative": 0, "fool": 0}
    for c in clusters:
        kinds = [classify(s, lx) for s in c["items"]]
        if "conservative" in kinds:
            k = "conservative"
        elif "both" in kinds:
            k = "both"
        elif "business_or_aligned" in kinds:
            k = "business_or_aligned"
        elif "fool" in kinds:
            k = "fool"
        elif "drop" in kinds and not any(_news_hook(s, lx) for s in c["items"]):
            # one sibling already identifies it as a celebrity story (siblings are the same story; a
            # bare-name sibling like 'X and Daughter Honor Y' can hit an incidental core word in its blurb)
            k = "drop"
        elif "core" in kinds:
            k = "core"
        elif "routine" in kinds:  # local crime/court item: national only with wide coverage
            k = "core" if len(c.get("outlets") or []) >= lx["routine_min"] else ("drop" if lx["routine_drop"] else "off")
        elif all(x == "drop" for x in kinds):
            k = "drop"
        else:
            k = "off"
        if k != "drop" and "drop" in kinds and len(kinds) > 1:
            # kept on a news angle: the celebrity-gossip siblings never supply its headline or link
            c["items"] = [x for x, kk in zip(c["items"], kinds) if kk != "drop"] or c["items"]
        if k == "drop":
            c["dropped"] = True; out[c["id"]] = 0.0
        elif k == "off":
            c["off_criteria"] = c["lead_excluded"] = c["top_excluded"] = True; out[c["id"]] = lx["penalty"]
        elif k in ("conservative", "fool"):
            c["celebrity"] = k; out[c["id"]] = lx["cons_score"] if k == "conservative" else 0.8
            c.pop("lifestyle", None)  # allowed celebrity stories are not capped as lifestyle filler
        else:
            out[c["id"]] = lx["scores"].get(k, lx["scores"]["core"])
            if k in ("both", "business_or_aligned"):
                c["featured_ok"] = True  # business/tech is otherwise soft-gated out of Top Stories
                c.pop("lifestyle", None)
                n["biz"] = n.get("biz", 0) + 1
        if k in n:
            n[k] += 1
    print(f"signal newsworthy: {n['drop']} celebrity dropped, {n['off']} off-criteria kept off front, "
          f"{n['conservative']} conservative-celebrity, {n['fool']} celebrity-politics backlash, "
          f"{n.get('biz', 0)} business/tech or aligned-figure wins")
    return out
