"""Consensus signal: stories linked or mentioned by several distinct tracked accounts.

Reads the AMPLIFIER_ITEMS env var (same private secret as the amplifier signal). The off-repo helper
groups posts by story (same link, or strongly overlapping text), counts DISTINCT accounts per group with a
per-account cap (a prolific account's weight is spread over its many links, so it can't fake consensus),
and stamps each item with "consensus" (0..1) and "consensus_accounts" (n). Groups with fewer than
min_accounts distinct accounts carry 0. Per cluster: best consensus of any matching item (exact link, or
headline-term overlap at 0.6x). Logs counts only."""
from .util import tokens
from .engagement import ucanon, _overlap
from . import amplifiers

NAME = "consensus"


def compute(clusters, settings, ctx):
    items = []
    import json, os
    raw = os.environ.get("AMPLIFIER_ITEMS", "").strip()
    try:
        data = json.loads(raw) if raw else []
    except Exception:
        data = []
    for it in data if isinstance(data, list) else []:
        if isinstance(it, dict) and float(it.get("consensus") or 0) > 0:
            items.append((ucanon(it.get("url") or ""), set(tokens(it.get("text") or "")), float(it["consensus"])))
    if not items:
        return None
    out, n = {}, 0
    for c in clusters:
        links = {ucanon(s["link"]) for s in c["items"]}
        tt = set().union(*(set(tokens(s.get("title") or "")) for s in c["items"]))
        best = 0.0
        for u, toks, sc in items:
            if u and u in links:
                best = max(best, sc)
            elif _overlap(tt, toks) >= 0.6:
                best = max(best, 0.6 * sc)
        out[c["id"]] = best
        n += best > 0
    print(f"signal consensus: {len(items)} consensus items; {n} clusters matched")
    return out
