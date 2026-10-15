"""Confidentiality guard. Reads the private term lists from ALIGNMENT_CONFIG at runtime (never stored
in the repo) and fails if any appear in tracked files or in the built page's non-headline text.
Skips when the secret is not available (e.g. a fork). Never prints the matched terms."""
import json, os, re, subprocess, unittest
from _helpers import ROOT


def private_terms():
    raw = os.environ.get("ALIGNMENT_CONFIG", "").strip()
    if not raw:
        return None
    c = json.loads(raw)
    bank = json.load(open(os.path.join(ROOT, "qotd_bank.json")))["quotes"]
    public = {q["author"].lower() for q in bank} | {q["author"].split()[-1].lower() for q in bank}
    names = {a for a in (c.get("authors") or {}) if a.lower() not in public}
    handles = {h for h in (c.get("truth_accounts") or {}) if not re.fullmatch(r"[A-Z][a-z]+", h)}
    urls = {f["url"] for f in c.get("private_feeds") or []} | {a.get("url", "") for a in c.get("amplifiers") or [] if isinstance(a, dict)}
    bylines = {(f.get("options") or {}).get("byline", "") for f in c.get("private_feeds") or []}
    return {t for t in names | handles | urls | bylines if t and len(t) > 3}


class Confidentiality(unittest.TestCase):
    def setUp(self):
        self.terms = private_terms()
        if self.terms is None:
            self.skipTest("ALIGNMENT_CONFIG not set")

    def test_repo(self):
        files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
        n = 0
        for f in files:
            p = os.path.join(ROOT, f)
            if not os.path.isfile(p):
                continue
            body = open(p, errors="ignore").read().lower()
            n += sum(1 for t in self.terms if t.lower() in body)
        self.assertEqual(n, 0, f"{n} private term hit(s) in tracked files")

    def test_built_page(self):
        p = os.path.join(ROOT, "site", "index.html")
        if not os.path.exists(p):
            self.skipTest("site not built")
        h = open(p, errors="ignore").read()
        # story text (headlines, outlet names, quote) is public news; check everything else
        chrome = re.sub(r"<li>.*?</li>|<div class=\"lead\">.*?</div></div>", "", h, flags=re.S).lower()
        n = sum(1 for t in self.terms if t.lower() in chrome)
        n += sum(1 for t in self.terms if t.startswith("http") and t.lower() in h.lower())
        self.assertEqual(n, 0, f"{n} private term hit(s) in built page")


if __name__ == "__main__":
    unittest.main()
