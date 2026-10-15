NAME = "source"
def compute(clusters, settings, ctx):
    t, d = settings["sources"]["tiers"], settings["sources"]["default_tier"]
    return {c["id"]: max(t.get(s["source"], d) for s in c["items"]) for c in clusters}
