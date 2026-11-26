"""Deploy health check and self-healing trigger.

GitHub often skips or delays scheduled runs for an hour or more. This check looks at the live page's age and
the recent Build and deploy runs. If the page is older than STALE_MINUTES (default 90) or the last finished
build failed, and no build is already queued or running, it dispatches one. If the site stays down
(page older than ALERT_MINUTES, default 180, or the last 3 builds failed) it opens one GitHub issue labelled
"site-outage" (GitHub emails the repo owner), and closes it once the site is healthy again.

  python -m upkeep.health
"""
import json, os, subprocess, sys, urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from .common import REPO, warn

SITE = "https://cs-514.github.io/spangle/"
LABEL = "site-outage"


def gh(*args):
    r = subprocess.run(["gh", *args, "-R", REPO], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def page_age_minutes():
    try:
        req = urllib.request.Request(SITE, method="HEAD", headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=20) as r:
            lm = r.headers.get("Last-Modified")
        return (datetime.now(timezone.utc) - parsedate_to_datetime(lm)).total_seconds() / 60 if lm else None
    except Exception:
        return None


def builds():
    out = gh("run", "list", "--workflow", "build.yml", "-L", "6", "--json", "status,conclusion,createdAt,databaseId,url")
    return json.loads(out) if out else []


def outage_issue(open_it, why):
    out = gh("issue", "list", "--label", LABEL, "--state", "open", "--json", "number")
    issues = json.loads(out) if out else []
    if open_it and not issues:
        gh("label", "create", LABEL, "--color", "B60205", "--description", "Live site is not updating")
        body = (f"Automatic alert from the upkeep health check: {why}.\n\n"
                "The health check has already re-triggered **Build and deploy**. Check the latest run in the "
                "Actions tab for the error. This issue closes itself when the site is fresh again.")
        gh("issue", "create", "--title", "Spangle site is not updating", "--label", LABEL, "--body", body)
        print("opened site-outage issue")
    elif not open_it:
        for i in issues:
            gh("issue", "close", str(i["number"]), "--comment", "Site is updating again; closing automatically.")
            print(f"closed site-outage issue #{i['number']}")


def main():
    stale = float(os.environ.get("STALE_MINUTES", 90))
    alert = float(os.environ.get("ALERT_MINUTES", 180))
    age = page_age_minutes()
    runs = builds()
    active = [r for r in runs if r["status"] in ("queued", "in_progress", "waiting", "pending", "requested")]
    done = [r for r in runs if r["status"] == "completed"]
    last_failed = bool(done) and done[0]["conclusion"] not in ("success", "skipped", "cancelled")
    fails = 0
    for r in done:
        if r["conclusion"] == "success":
            break
        fails += r["conclusion"] == "failure"
    print(f"live page age: {'unknown' if age is None else f'{age:.0f} min'}; builds active: {len(active)}; "
          f"last finished build: {done[0]['conclusion'] if done else 'none'} ({done[0]['url'] if done else ''})")
    need = (age is None or age > stale) or last_failed
    if need and not active:
        why = "last build failed" if last_failed else f"page is {age or 0:.0f} min old (limit {stale:.0f})"
        print(f"re-triggering Build and deploy: {why}")
        if subprocess.run(["gh", "workflow", "run", "build.yml", "-R", REPO, "--ref", "main"]).returncode != 0:
            warn("could not dispatch Build and deploy")
    elif need:
        print("a build is already queued or running; not dispatching another")
    else:
        print("site healthy")
    down = (age is not None and age > alert) or fails >= 3
    if os.environ.get("GITHUB_ACTIONS"):
        why = f"live page is {age:.0f} min old" if age and age > alert else f"the last {fails} builds failed"
        outage_issue(down, why)
    if down:
        warn("site appears down; see the site-outage issue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
