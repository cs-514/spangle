"""Override data is routine-edited: content checks warn (never fail the deploy); the code paths are strict."""
import json, os, tempfile, unittest
from _helpers import ROOT
from ranking import headline as h
from ranking.override_lint import sanitize, lint, summary


class OverrideData(unittest.TestCase):
    def test_lint_report_never_fails(self):
        try:
            with open(os.path.join(ROOT, "headline_overrides.json")) as f:
                d = json.load(f)
        except Exception as ex:
            print(f"::warning::headline_overrides.json unreadable ({type(ex).__name__}); build runs without overrides")
            return
        s = summary(d)
        if s != "none":
            print(f"::warning::override data warnings: {s}")

    def test_sanitize_drops_invalid(self):
        good, dropped = sanitize({"https://a.com/1": "Fine Headline Here", "https://a.com/2": "", "https://a.com/3": None,
                                  "https://a.com/4": 5, "": "No Key", "https://a.com/5": "  Spaced   Out  "})
        self.assertEqual(good, {"https://a.com/1": "Fine Headline Here", "https://a.com/5": "Spaced Out"})
        self.assertEqual(len(dropped), 4)

    def test_lint_flags_content(self):
        issues = lint({"https://a.com/1": "Ex-SJSU Coach Sues", "https://a.com/2": 'Mayor Calls Plan "Insane"',
                       "https://a.com/3": "Senate Passes the", "https://a.com/4": "Trump Feuds With Rivals",
                       "https://a.com/5": "Senate Passes Border Bill"})
        self.assertEqual(issues["obscure_acronym"], ["https://a.com/1"])
        self.assertEqual(issues["double_quotes"], ["https://a.com/2"])
        self.assertEqual(issues["fragment"], ["https://a.com/3"])
        self.assertEqual(issues["capitalized_preposition"], ["https://a.com/4"])
        self.assertFalse(any("https://a.com/5" in v for v in issues.values()))

    def _load(self, text):
        old_cfg, old_here = h._OVERRIDES, h.HERE
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "headline_overrides.json"), "w") as f:
            f.write(text)
        h._OVERRIDES, h.HERE = None, d
        try:
            return dict(h.overrides())
        finally:
            h._OVERRIDES, h.HERE = old_cfg, old_here

    def test_broken_file_never_raises(self):
        self.assertEqual(self._load("{not json"), {})
        self.assertEqual(self._load("[1, 2]"), {})

    def test_bad_entry_dropped_rest_kept(self):
        got = self._load(json.dumps({"https://a.com/1": "Good One Here", "https://a.com/2": None}))
        self.assertEqual(got, {"https://a.com/1": "Good One Here"})


if __name__ == "__main__":
    unittest.main()
