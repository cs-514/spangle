"""Shared helpers for the upkeep jobs: paths, Eastern time, git commit/push, build dispatch, LLM calls.

Everything private comes from environment variables (GitHub Actions secrets). Nothing here may print a
private value: log counts and URLs of public articles only."""
import json, os, subprocess, sys, time, urllib.request, urllib.error
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "upkeep", "state")
ET = ZoneInfo("America/New_York")
TMP = os.environ.get("RUNNER_TEMP") or os.path.join(ROOT, "..")
REPO = os.environ.get("GITHUB_REPOSITORY", "cs-514/spangle")


def now_et():
    return datetime.now(ET)


def warn(msg):
    """GitHub Actions warning annotation (plain print locally)."""
    print(f"::warning::{msg}" if os.environ.get("GITHUB_ACTIONS") else f"warning: {msg}")


def load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data, indent=1):
    with open(path, "w") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
        f.write("\n")


def private_config():
    raw = os.environ.get("ALIGNMENT_CONFIG", "").strip()
    return json.loads(raw) if raw else {}


def sh(cmd, **kw):
    kw.setdefault("cwd", ROOT)
    return subprocess.run(cmd, text=True, **kw)


def run_checks():
    """Unit tests plus the confidentiality guard (with the private config loaded). Returns (ok, reason).
    The guard must actually run: a skipped guard counts as a failure."""
    if not os.environ.get("ALIGNMENT_CONFIG", "").strip():
        return False, "ALIGNMENT_CONFIG is not set, so the confidentiality guard cannot run"
    t = sh([sys.executable, "-m", "unittest", "discover", "-s", "tests"], capture_output=True)
    if t.returncode != 0:
        fails = [l for l in t.stderr.splitlines() if l.startswith(("FAIL:", "ERROR:"))]
        print("\n".join(fails[:20]))
        return False, f"unit tests failed ({len(fails)} failing)"
    c = sh([sys.executable, "-m", "unittest", "-v", "test_confidentiality"], cwd=os.path.join(ROOT, "tests"),
           capture_output=True)
    if c.returncode != 0 or "skipped" in c.stderr.lower():
        return False, "confidentiality guard failed or was skipped"  # never print the matched terms
    return True, ""


def commit_and_push(paths, message, attempts=4):
    """Commit the given repo paths and push to main, rebasing on concurrent pushes. Returns True if pushed."""
    if not os.environ.get("GITHUB_ACTIONS") and os.environ.get("UPKEEP_PUSH") != "1":
        print(f"(local run: not committing {', '.join(paths)}; set UPKEEP_PUSH=1 to push)")
        return False
    sh(["git", "config", "user.name", os.environ.get("GIT_AUTHOR_NAME", "spangle-upkeep[bot]")])
    sh(["git", "config", "user.email", os.environ.get("GIT_AUTHOR_EMAIL",
                                                      "41898282+github-actions[bot]@users.noreply.github.com")])
    sh(["git", "add", "--"] + paths, check=True)
    if not sh(["git", "diff", "--cached", "--name-only"], capture_output=True).stdout.strip():
        print("no changes to commit")
        return False
    sh(["git", "commit", "-q", "-m", message], check=True)
    for i in range(attempts):
        if sh(["git", "push", "-q", "origin", "HEAD:main"]).returncode == 0:
            print(f"pushed: {message}")
            return True
        time.sleep(3 + 5 * i)
        sh(["git", "pull", "-q", "--rebase", "origin", "main"], check=True)
    raise SystemExit("push failed after retries")


def dispatch_build():
    """Queue a Build and deploy run (GITHUB_TOKEN may dispatch workflows)."""
    if not os.environ.get("GH_TOKEN"):
        print("(no GH_TOKEN: build not dispatched)")
        return False
    r = sh(["gh", "workflow", "run", "build.yml", "-R", REPO, "--ref", "main"], capture_output=True)
    print("dispatched Build and deploy" if r.returncode == 0 else f"build dispatch failed: {r.stderr.strip()[:200]}")
    return r.returncode == 0


def http_get(url, headers=None, timeout=20, limit=2_000_000):
    h = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120 Safari/537.36"}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        return r.read(limit).decode("utf-8", "ignore")


# ---- LLM (any OpenAI-compatible chat completions endpoint) ----

def llm_config():
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not key:
        return None
    return {"key": key,
            "base": (os.environ.get("LLM_BASE_URL") or "https://api.openai.com/v1").strip().rstrip("/"),
            "model": (os.environ.get("LLM_MODEL") or "gpt-4o-mini").strip()}


def llm_json(system, user, cfg, max_tokens=4000, retries=2):
    """Ask the model for a JSON object. Returns the parsed object or raises."""
    body = {"model": cfg["model"], "max_tokens": max_tokens, "temperature": 0.3,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    last = None
    for i in range(retries + 1):
        req = urllib.request.Request(cfg["base"] + "/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                out = json.loads(r.read())
            text = out["choices"][0]["message"]["content"] or ""
            usage = out.get("usage") or {}
            print(f"LLM: {usage.get('prompt_tokens', '?')} tokens in, {usage.get('completion_tokens', '?')} out")
            s = text[text.find("{"): text.rfind("}") + 1]
            return json.loads(s)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
        except Exception as e:
            last = type(e).__name__
        time.sleep(5 * (i + 1))
    raise RuntimeError(f"LLM call failed ({last})")
