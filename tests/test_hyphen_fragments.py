"""Hyphenated compounds (Chicago), acronyms inside compounds, and fragment detection."""
import json, os, unittest
from _helpers import ROOT
from ranking import headline as h
from ranking.headline import clean


class Hyphens(unittest.TestCase):
    def test_second_element_capitalized(self):
        self.assertEqual(clean("Fast-moving SoCal wildfire grows overnight")[0], "Fast-Moving SoCal Wildfire Grows Overnight")
        self.assertEqual(clean("Trump-appointed judge rules")[0], "Trump-Appointed Judge Rules")
        self.assertEqual(clean("Killing of 9-year-old girl")[0], "Killing of 9-Year-Old Girl")

    def test_middle_small_words_lowercase(self):
        self.assertEqual(clean("Minnesota Soft-On-Crime Board")[0], "Minnesota Soft-on-Crime Board")
        self.assertEqual(clean("Up-to-date list")[0], "Up-to-Date List")
        self.assertEqual(clean("Mother-in-law sues")[0], "Mother-in-Law Sues")

    def test_internal_capitals_kept(self):
        for t in ("U.S.-China Talks Resume", "COVID-19 Rules Return", "MS-13 Gang Members Arrested", "Chick-fil-A Opens Store"):
            self.assertEqual(clean(t)[0], t)

    def test_acronym_parts(self):
        self.assertEqual(clean("Ex-SJSU Coach Sues over ‘Trump Lover’ Barbs Amid Trans Scandal")[0],
                         "Ex-SJSU Coach Sues over ‘Trump Lover’ Barbs Amid Trans Scandal")
        self.assertEqual(clean("EX-SJSU COACH SUES")[0], "Ex-SJSU Coach Sues")
        self.assertEqual(clean("Ex-NTSB chief warns")[0], "Ex-NTSB Chief Warns")   # consonant-only part
        self.assertEqual(clean("NRSC launches ad")[0], "NRSC Launches Ad")
        self.assertEqual(clean("CENTCOM chief speaks")[0], "CENTCOM Chief Speaks")

    def test_overrides_survive_cleaning(self):
        ov = json.load(open(os.path.join(ROOT, "headline_overrides.json")))
        for v in ov.values():
            if isinstance(v, str) and v:
                self.assertNotIn("Sjsu", clean(v)[0])
                self.assertNotRegex(clean(v)[0], r"-(On|Of|To|In|And|The)-")


class Fragments(unittest.TestCase):
    VAST = "‘Vast majority’ of Iran’s attempted attacks on Strait of Hormuz are unsuccessful, CENTCOM spokesman says"

    def test_detects_fragments(self):
        self.assertTrue(h.fragment("‘Vast Majority’ of Iran’s Attempted Attacks", self.VAST))
        self.assertTrue(h.fragment("Mayor’s Racist Claim That Local Voters",
                                   "Mayor’s Racist Claim That Local Voters Are Less Informed Than Others"))
        self.assertTrue(h.fragment("Rally Comes Days", "Rally Comes Days After Terror Plot Foiled"))
        self.assertTrue(h.fragment("Senate Passes the"))

    def test_complete_headlines_pass(self):
        self.assertFalse(h.fragment("Jewish Support for Dems Falls from 36%", "Jewish Support for Dems Falls From 36% — and CNN Is Shocked"))
        self.assertFalse(h.fragment("Ex-NFL Punter Dies at 35", "Ex-NFL Punter Dies at 35"))
        self.assertFalse(h.fragment("Hidden Tax on Your Energy Bill That No One Voted For", "The Hidden Tax On Your Energy Bill That No One Voted For"))
        self.assertFalse(h.fragment("Board Rules Against Her", "Board Rules Against Her"))

    def test_shorten_never_leaves_fragment(self):
        out = h.shorten(clean(self.VAST)[0])
        self.assertFalse(h.fragment(out, self.VAST))
        self.assertIn("Unsuccessful", out)

    def test_placement_queues_fragments(self):
        import inspect, aggregator
        self.assertIn('"reason": "fragment"', inspect.getsource(aggregator))

    def test_hormuz_override_has_verb(self):
        ov = json.load(open(os.path.join(ROOT, "headline_overrides.json")))
        v = ov["https://redstate.com/bobhoge/2026/10/16/centcom-chief-strait-of-hormuz-open-for-business-while-desperate-iran-cant-even-pay-own-troops-n2208242"]
        self.assertTrue(h.has_strong_verb(v))
        self.assertFalse(h.fragment(v))
        self.assertFalse(h.too_long(clean(v)[0]))


if __name__ == "__main__":
    unittest.main()
