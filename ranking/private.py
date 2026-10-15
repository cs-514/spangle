"""Loads the private ranking config from the ALIGNMENT_CONFIG env var (JSON).
Never logs its contents."""
import json, os

def load(ctx):
    if "alignment_cfg" in ctx:
        return ctx["alignment_cfg"]
    raw = os.environ.get("ALIGNMENT_CONFIG", "").strip()
    cfg = {}
    if raw:
        try:
            cfg = json.loads(raw); print("Loaded custom scoring config.")
        except Exception:
            print("Custom scoring config invalid; using defaults.")
    else:
        print("Using default scoring config.")
    ctx["alignment_cfg"] = cfg
    return cfg
