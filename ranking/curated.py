"""curated_by_aggregators: 1.0 if a human-curated aggregator (e.g. Bongino Report)
currently links to any article in the cluster; scaled by number of curators."""
NAME = "curated_by_aggregators"

def compute(clusters, settings, ctx):
    if not settings.get("curators"):
        return None
    sat = max(1, settings.get("curated", {}).get("saturation_curators", 1))
    out = {}
    for c in clusters:
        names = {n for s in c["items"] for n in s.get("curated", [])}
        out[c["id"]] = min(1.0, len(names) / sat)
    return out
