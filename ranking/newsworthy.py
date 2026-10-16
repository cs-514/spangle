"""Newsworthiness gate + celebrity filter. Lexicons live in the private config key "newsworthiness"
(with the "lifestyle" hooks, "outrage" terms and boost keywords also counted as core criteria).

- Celebrity / entertainment stories (celebrity terms in the headline, or an entertainment URL path)
  are DROPPED unless
    (a) a conservative celebrity is speaking out  -> kept and scored favorably, or
    (b) a Hollywood/celebrity figure makes a fool of themselves on politics or geopolitics
        (a politics term plus a backlash/ridicule term)  -> kept.
- Major business / tech breakthroughs and wins by conservative-aligned figures (private list) are core
  criteria and qualify for the lead and Top Stories (exempt from the business/tech soft gate); a story that
  hits both scores highest.
- Every other story must hit at least one core criterion (political, policy, culture-war, legal,
  national-security or outrage angle) to be featured. Stories with none are kept out of the lead and
  Top Stories and scored `penalty` (heavily downranked in the columns).
Flags: c["celebrity"] = "conservative" | "fool" ; c["off_criteria"] = True ; c["dropped"] = True."""
import re
from . import private
NAME = "newsworthy"


def _rx(words):
    words = [w.lower() for w in words if w]
    if not words:
        return None
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")")


def lexicon(ctx):
    pc = private.load(ctx)
    nw = pc.get("newsworthiness") or {}
    if not nw.get("enabled"):
        return None
    core = list(nw.get("core_terms", [])) + list((pc.get("lifestyle") or {}).get("hooks", [])) \
        + list((pc.get("outrage") or {}).get("terms", [])) + list(pc.get("boost_keywords") or {})
    return {"core": _rx(core), "celeb": _rx(nw.get("celebrity_terms", [])),
            "paths": [p.lower() for p in nw.get("entertainment_paths", [])],
            "cons": _rx(nw.get("conservative_celebs", [])), "speak": _rx(nw.get("speaking_out_terms", [])),
            "fool": _rx(nw.get("fool_terms", [])), "pol": _rx(nw.get("politics_terms", [])),
            "biz": _rx(nw.get("business_terms", [])), "fig": _rx(nw.get("aligned_figures", [])),
            "win": _rx(nw.get("win_terms", [])), "scores": {"core": 0.85, "business_or_aligned": 0.9, "both": 1.0,
                                                           **(nw.get("scores") or {})},
            "penalty": float(nw.get("penalty", 0.15)), "cons_score": float(nw.get("conservative_celeb_score", 1.0))}


def _hit(rx, text):
    return bool(rx and rx.search(text))


def classify(item, lx):
    """-> "conservative" | "fool" | "drop" (celebrity cases), "core" or "off" (everything else)."""
    t = item["title"].lower().replace("’", "'")
    hay = f"{t} {(item.get('desc') or '').lower()}".replace("’", "'")
    link = (item.get("link") or "").lower()
    celeb = _hit(lx["celeb"], t) or any(p in link for p in lx["paths"]) or t.startswith("review:")
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
    return "core" if _hit(lx["core"], hay) else "off"


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
        elif "core" in kinds:
            k = "core"
        elif all(x == "drop" for x in kinds):
            k = "drop"
        else:
            k = "off"
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
