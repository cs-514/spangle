"""curated_by_aggregators: weighted count of human-curated aggregators (Bongino Report,
RealClearPolitics, ...) currently linking to any article in the cluster.
Per-curator weights: settings.curated.weights {label: weight} (default 1.0)."""
NAME = "curated_by_aggregators"

def compute(clusters, settings, ctx):
    if not settings.get("curators"):
        return None
    cur = settings.get("curated", {})
    sat = max(1, cur.get("saturation_curators", 1))
    w = cur.get("weights", {})
    out = {}
    for c in clusters:
        names = {n for s in c["items"] for n in s.get("curated", [])}
        out[c["id"]] = min(1.0, sum(w.get(n, 1.0) for n in names) / sat)
    return out
