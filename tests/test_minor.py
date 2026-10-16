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

    def test_sitting_senators_and_governors_exempt(self):
        self.assertIsNone(minor.classify([it("Georgia’s Democratic Senator Jon Ossoff Says He Has ‘Zero Interest’ in 2028 Run")], []))
        self.assertIsNone(minor.classify([it("Sen. Pat Rook Says He Backs Court Expansion", "the Democrat said in a debate")], []))
        self.assertIsNone(minor.classify([it("Rook Says He Backs Court Expansion", "Sen. Pat Rook (D-GA) said during a debate")], []))
        self.assertIsNone(minor.classify([it("Gov. Lee Ward Says State Will Sue", "the governor said")], []))
        # a state senator or a Senate candidate is still minor
        self.assertEqual(minor.classify([it("State Senator Ann Pike Says She Backs Abolishing ICE", "state senator")], []), "minor")
        self.assertEqual(minor.classify([it("Pike Says She Backs Abolishing ICE", "Senate candidate Ann Pike, a former senator aide, said")], []), "minor")

    def test_senator_mentioned_but_not_speaking(self):
        d = "Sen. Ann Quill (R-ME) rejected it after Democrat Troy Jackson said during a Senate debate"
        self.assertEqual(minor.classify([it("Quill Pushes Back as Jackson Says He’s Open to Expanding Supreme Court", d)], []), "minor")

    def test_polls_are_data(self):
        self.assertIsNone(minor.classify([it("Poll Shows Tight Race in Virginia’s 2nd Congressional District", "a candidate leads")], []))
        self.assertIsNone(minor.classify([it("Candidate Says New Poll Shows Her Ahead", "Senate race candidate")], []))

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
