"""Pluggable ranking engine. Each signal module exposes NAME and
compute(clusters, settings, ctx) -> {cluster_id: score in [0,1]} or None if unavailable."""
from . import private, amplifiers, framing, curated, niche, retreat, outrage, recency, coverage, source, alignment, social_gnews, social_reddit, engagement, consensus, lifestyle, faction, minor, defeatism, clutter, academic, newsworthy

BASE = [recency, coverage, source, alignment, curated, amplifiers, framing, niche, retreat, outrage, lifestyle, faction, minor, defeatism, clutter, academic, newsworthy]
SOCIAL = [social_gnews, social_reddit]  # Hacker News dropped: no signal for this audience
# Computed on ALL clusters after the base signals, because they read the base results (alignment,
# faction, defeatism flags) to decide eligibility.
POST = [engagement, consensus]


def _combine(clusters, results, weights):
    active = {n: r for n, r in results.items() if r is not None and weights.get(n, 0) > 0}
    total = sum(weights[n] for n in active) or 1.0
    for c in clusters:
        c["score"] = sum(weights[n] / total * active[n].get(c["id"], 0.0) for n in active)
        c["signals"] = {n: round(active[n].get(c["id"], 0.0), 3) for n in active}


def rank(clusters, settings, ctx):
    # The private config may override signal weights (key "signal_weights").
    weights = dict(settings["weights"]); weights.update(private.load(ctx).get("signal_weights", {}))
    results = {}
    for m in BASE:
        results[m.NAME] = m.compute(clusters, settings, ctx)
    _combine(clusters, results, weights)
    for m in POST:
        try:
            results[m.NAME] = m.compute(clusters, settings, ctx)
        except Exception as e:  # never let a social source break the build
            print(f"signal {m.NAME}: error {type(e).__name__}")
            results[m.NAME] = None
        if results[m.NAME] is None:
            print(f"signal {m.NAME}: unavailable (weight redistributed)")
    _combine(clusters, results, weights)
    clusters.sort(key=lambda c: c["score"], reverse=True)
    cands = clusters[: settings["social"]["candidates"]]
    for m in SOCIAL:
        try:
            r = m.compute(cands, settings, ctx)
        except Exception as e:  # never let a social source break the build
            print(f"signal {m.NAME}: error {type(e).__name__}")
            r = None
        if r is not None:
            hits = sum(1 for v in r.values() if v > 0)
            print(f"signal {m.NAME}: ok, {hits}/{len(cands)} candidates with activity")
        else:
            print(f"signal {m.NAME}: unavailable (weight redistributed)")
        results[m.NAME] = r
    _combine(clusters, results, weights)
    # score_lead: the score without any fuzzy-only engagement credit (used for the lead's rank term)
    act = {n: r for n, r in results.items() if r is not None and weights.get(n, 0) > 0}
    tot = sum(weights[n] for n in act) or 1.0
    we = weights.get("engagement", 0) if "engagement" in act else 0.0
    for c in clusters:
        fuzzy = max(0.0, c.get("signals", {}).get("engagement", 0.0) - c.get("engagement_exact", 0.0))
        c["score_lead"] = c["score"] - we / tot * fuzzy
    clusters.sort(key=lambda c: c["score"], reverse=True)
    _dump(clusters, results, weights)
    return clusters


def _dump(clusters, results, weights):
    """Local debugging only: RANK_DUMP=<path> writes the final order with and without the post signals."""
    import json, os
    path = os.environ.get("RANK_DUMP")
    if not path:
        return
    post = {m.NAME for m in POST}
    act = {n: r for n, r in results.items() if r is not None and weights.get(n, 0) > 0 and n not in post}
    tot = sum(weights[n] for n in act) or 1.0
    wo = {c["id"]: sum(weights[n] / tot * act[n].get(c["id"], 0.0) for n in act) for c in clusters}
    order_wo = {cid: i for i, cid in enumerate(sorted(wo, key=lambda k: -wo[k]))}
    json.dump([{"rank": i, "rank_without_post": order_wo[c["id"]], "score": round(c["score"], 4),
                "title": c["items"][0]["title"], "signals": c.get("signals", {})} for i, c in enumerate(clusters)],
              open(path, "w"), indent=1, ensure_ascii=False)
