import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ranking import minor, headline
import aggregator as A


def it(title, desc=""):
    return {"title": title, "desc": desc}


DESC = "during Thursday's Senate debate, Democrat Troy Jackson said he was open to adding justices"


class MinorFigures(unittest.TestCase):
    def test_troy_jackson_style_downranked(self):
        cs = [{"id": 1, "outlets": ["Breitbart"], "items": [it("Rival Pushes Back as Jackson Says He’s Open to Expanding Supreme Court", DESC)]},
              {"id": 2, "outlets": ["Breitbart"], "items": [it("Border Bill Passes Senate")]}]
        out = minor.compute(cs, {}, {})
        self.assertLess(out[1], 0.2)
        self.assertTrue(cs[0]["lead_excluded"] and cs[0]["top_excluded"])
        self.assertEqual(out[2], 1.0)

    def test_leadership_not_downranked(self):
        for t in ["Schumer Backs Court-Packing Push", "Jeffries Says He’s Open to Expanding Supreme Court"]:
            self.assertIsNone(minor.classify([it(t, "Democrat leader said during a debate")], ["Fox News"]), t)

    def test_exceptions(self):
        d = "state senator and candidate"
        self.assertIsNone(minor.classify([it("State Senator Charged After Saying He Backs Fraud", d)], []))  # action
        self.assertIsNone(minor.classify([it("Candidate Says He Wants to Abolish ICE", d)],
                                         ["Fox News", "NY Post", "Daily Wire", "Townhall", "RedState"]))  # wide coverage
        self.assertEqual(minor.classify([it("Senate Candidate Says Leaked Texts Were ‘Jokes’", d)], []), "minor_scandal")

    def test_suppress_hashed_url(self):
        u = "https://example.com/story/"
        self.assertTrue(A.suppressed(u + "?x=1", {"suppress_urls": [headline.url_key(u)]}))
        self.assertFalse(A.suppressed("https://example.com/other/", {"suppress_urls": [headline.url_key(u)]}))
