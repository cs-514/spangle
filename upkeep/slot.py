"""DST-proof schedule guard. GitHub cron is UTC only, so each workflow is scheduled at both candidate UTC
hours (EDT and EST) and this guard lets the run through only when the US Eastern clock is in the slot's
window and the slot has not already run today. GitHub often starts scheduled runs late, so the window is
a few hours wide; the per-day stamp in upkeep/state/slots.json prevents a second run.

  python -m upkeep.slot check <slot> <et_hour> [window_hours]   # prints run=true/false to $GITHUB_OUTPUT
  python -m upkeep.slot stamp <slot> [--commit]                  # records today's run (scheduled runs only)
"""
import os, sys
from .common import STATE, load_json, save_json, now_et, commit_and_push

SLOTS = os.path.join(STATE, "slots.json")


def due(slot, hour, window=3, now=None, stamps=None):
    now = now or now_et()
    stamps = load_json(SLOTS, {}) if stamps is None else stamps
    today = now.strftime("%Y-%m-%d")
    if stamps.get(slot) == today:
        return False, f"{slot} already ran today ({today} ET)"
    if not (hour <= now.hour < hour + window):
        return False, f"{now:%H:%M} ET is outside the {slot} window ({hour}:00-{hour + window}:00 ET)"
    return True, f"{slot} due ({now:%Y-%m-%d %H:%M} ET)"


def stamp(slot):
    stamps = load_json(SLOTS, {})
    stamps[slot] = now_et().strftime("%Y-%m-%d")
    save_json(SLOTS, dict(sorted(stamps.items())))


def _out(key, val):
    print(f"{key}={val}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"{key}={val}\n")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "check":
        if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
            print("manual run: guard bypassed"); _out("run", "true"); sys.exit(0)
        ok, why = due(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else 3)
        print(why); _out("run", "true" if ok else "false")
    elif cmd == "stamp":
        if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
            print("manual run: slot not stamped (the scheduled run still happens)"); sys.exit(0)
        stamp(sys.argv[2])
        if "--commit" in sys.argv:
            commit_and_push(["upkeep/state/slots.json"], f"Upkeep: {sys.argv[2]} slot ran")
    else:
        print(__doc__); sys.exit(2)
