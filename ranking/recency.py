NAME = "recency"
def compute(clusters, settings, ctx):
    hl = settings["recency"]["half_life_hours"]
    out = {}
    for c in clusters:
        w = c["newest"]
        out[c["id"]] = 0.5 ** (max(0.0, (ctx["now"] - w).total_seconds() / 3600) / hl) if w else 0.3
    return out
