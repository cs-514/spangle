"""Pluggable ranking engine. Each signal module exposes NAME and
compute(clusters, settings, ctx) -> {cluster_id: score in [0,1]} or None if unavailable."""
from . import private, amplifiers, framing, curated, recency, coverage, source, alignment, social_gnews, social_reddit, social_hn, social_x

BASE = [recency, coverage, source, alignment, curated, amplifiers, framing]
SOCIAL = [social_gnews, social_reddit, social_hn, social_x]


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
    clusters.sort(key=lambda c: c["score"], reverse=True)
    return clusters
