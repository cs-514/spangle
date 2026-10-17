"""Obscure-acronym rule: only well-known acronyms in headlines; others are queued for rewrite."""
import json, os, unittest
from _helpers import ROOT, story, NOW
from ranking import headline as h
import aggregator as A


class Lists(unittest.TestCase):
    def test_split_lists(self):
        a = json.load(open(os.path.join(ROOT, "headline_style.json")))["acronyms"]
        self.assertTrue({"FBI", "DOJ", "CIA", "ICE", "GOP", "SCOTUS", "NATO", "DOGE", "NCAA"} <= set(a["well_known"]))
        self.assertTrue({"SJSU", "CENTCOM"} <= set(a["case_only"]))
        self.assertFalse(set(a["well_known"]) & set(a["case_only"]))

    def test_case_only_keeps_casing(self):
        self.assertEqual(h.clean("EX-SJSU COACH SUES")[0], "Ex-SJSU Coach Sues")
        self.assertEqual(h.clean("CENTCOM chief speaks")[0], "CENTCOM Chief Speaks")


class Detect(unittest.TestCase):
    def test_flags_obscure(self):
        self.assertEqual(h.obscure_acronyms("Ex-SJSU Coach Sues over ‘Trump Lover’ Barbs"), ["SJSU"])
        self.assertEqual(h.obscure_acronyms("NRSC Ad Mocks Rival"), ["NRSC"])
        self.assertEqual(h.obscure_acronyms("FBI Probes Letters with DSA-Linked Address"), ["DSA"])
        self.assertEqual(h.obscure_acronyms("CENTCOM Chief: Strait Open"), ["CENTCOM"])
        self.assertEqual(h.obscure_acronyms("CFA’s Chicken Sandwich"), ["CFA"])
        self.assertEqual(h.obscure_acronyms("NC Dem Hosts Festival"), ["NC"])

    def test_well_known_pass(self):
        for t in ("FBI, DOJ and CIA Brief GOP on ICE Raids", "SCOTUS Hears NATO Case", "U.S.-China Talks Resume",
                  "AI-Generated Icon Sparks Debate", "F-35 Crash Probed", "Pays $275K", "World War II Vet Honored",
                  "JD Vance Wants 6 Promises", "MS Now’s Host Stumbles", "AR-15s Banned", "S.C. Abortion Ban Upheld",
                  "NCAA Sues Ohio’s GOP Governor", "LGBTQ+ Activists Rally", "AT&T Outage Spreads"):
            self.assertEqual(h.obscure_acronyms(t), [], t)


class Queue(unittest.TestCase):
    def test_placement_queues_obscure(self):
        s = story("Ex-SJSU Coach Sues over Barbs Amid Scandal", link="https://example.com/coach")
        lead = story("Border Bill Passes Senate", link="https://example.com/lead")
        clusters = [{"id": 1, "items": [lead]}, {"id": 2, "items": [s]}]
        qpath = os.path.join(ROOT, "..", "rewrite_queue.json")
        bak = open(qpath).read() if os.path.exists(qpath) else None
        try:
            A.decorate_headlines(lead, [s], [[]], clusters)
            q = json.load(open(qpath))["items"]
        finally:
            if bak is not None:
                open(qpath, "w").write(bak)
        it = [x for x in q if x["reason"] == "obscure_acronym"]
        self.assertEqual(len(it), 1)
        self.assertEqual(it[0]["acronyms"], ["SJSU"])
        self.assertIn("College’s", it[0]["framing"])

    def test_sjsu_override(self):
        ov = json.load(open(os.path.join(ROOT, "headline_overrides.json")))
        v = ov["https://www.breitbart.com/sports/2026/10/16/former-san-jose-state-volleyball-coach-sues-over-reported-trump-lover-barbs-amid-trans-scandal/"]
        self.assertEqual(h.clean(v)[0], "College’s Ex-Coach Sues over ‘Trump Lover’ Barbs Amid Trans Scandal")
        self.assertEqual(h.obscure_acronyms(v), [])
        self.assertFalse(h.too_long(h.clean(v)[0]))

    def test_no_override_uses_obscure_acronym(self):
        ov = json.load(open(os.path.join(ROOT, "headline_overrides.json")))
        bad = {k: v for k, v in ov.items() if isinstance(v, str) and h.obscure_acronyms(h.clean(v)[0])}
        self.assertEqual(bad, {})


if __name__ == "__main__":
    unittest.main()
