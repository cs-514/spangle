import json, os, unittest
from _helpers import ROOT, story, NOW
import aggregator as A
from ranking.headline import imprimis_recast, clean


class ImprimisRecast(unittest.TestCase):
    def test_fallbacks(self):
        cases = {"The Rise of Democratic Socialism": "Democratic Socialism’s Rise",
                 "The Hard Truth About the Sanctuary Movement": "Sanctuary Movement’s Hard Truth",
                 "Recovering the Lost Art of Diplomacy": "Diplomacy’s Lost Art",
                 "Learning From Minnesota’s Somali Fraud Scandal": "Lessons of Minnesota’s Somali Fraud Scandal",
                 "The Crisis of the American University": "American University’s Crisis"}
        for t, want in cases.items():
            self.assertEqual(imprimis_recast(clean(t)[0]), want, t)

    def test_unsafe_left_alone(self):
        for t in ["Why We Shouldn’t Cancel SCOTUS", "Launching a Second Scientific Revolution",
                  "Are We Subjects or Citizens? Birthright Citizenship and the Constitution",
                  "Dangers of Undermining U.S. Civil–Military Relations"]:
            self.assertEqual(imprimis_recast(t), t)

    def run_decorate(self, link):
        s = story("The Rise of Democratic Socialism", source="Imprimis", link=link)
        lead = story("Border Bill Passes Senate", link="https://example.com/lead")
        _, _, cols, st = A.decorate_headlines(lead, [], [[s]], [{"id": 1, "outlets": ["Imprimis"], "items": [s]},
                                                             {"id": 2, "outlets": ["x"], "items": [lead]}], None, NOW)
        return cols[0][0], st

    def test_queued_with_guidance_and_fallback(self):
        s, st = self.run_decorate("https://imprimis.hillsdale.edu/some-new-essay/")
        self.assertEqual(s["display"], "Democratic Socialism’s Rise")
        q = [x for x in st["queue"] if x["reason"] == "imprimis"][0]
        self.assertIn("VARY THE FORM", q["framing"])
        self.assertIn("Socialism’s Persistent, Disturbing Rise", q["framing"])

    def test_override_wins(self):
        url = "https://imprimis.hillsdale.edu/the-rise-of-democratic-socialism/"
        old = A.headline_mod._OVERRIDES
        A.headline_mod._OVERRIDES = A.headline_mod._Overrides({url: "Socialism’s Persistent, Disturbing Rise"})
        try:
            s, st = self.run_decorate(url)
        finally:
            A.headline_mod._OVERRIDES = old
        self.assertEqual(s["display"], "Socialism’s Persistent, Disturbing Rise")
        self.assertFalse([x for x in st["queue"] if x["reason"] == "imprimis"])


if __name__ == "__main__":
    unittest.main()
