import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ranking import faction

# Fictional names only: the real list lives in the private config.
CFG = {"members": ["Zed Quill", "Quill", "Varn"],
       "favorable_terms": ["pushes back", "defends", "hailed"],
       "defect_terms": ["breaks with", "votes against", "blocks", "slams trump"],
       "critic_terms": ["primary", "challenger", "censure", "rino"],
       "attack_terms": ["slams", "rips"],
       "scores": {"critic": 1.0, "defect": 0.85, "neutral": 0.5, "favorable": 0.05}}


def cl(i, *titles):
    return {"id": i, "items": [{"title": t} for t in titles]}


class Faction(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(faction.classify("Quill Pushes Back as Dem Says He’s Open to Packing SCOTUS", CFG), "favorable")
        self.assertEqual(faction.classify("Senate Vote Delayed After Quill Hailed by Media", CFG), "favorable")
        self.assertEqual(faction.classify("Varn Breaks With Trump on Border Bill", CFG), "defect")
        self.assertEqual(faction.classify("Varn Slams Trump", CFG), "defect")
        self.assertEqual(faction.classify("Trump Rips Quill Over Vote", CFG), "critic")
        self.assertEqual(faction.classify("Quill Faces Primary Challenger", CFG), "critic")
        self.assertEqual(faction.classify("Senate Passes Bill; Few Words From Quill", CFG), "mention")
        self.assertIsNone(faction.classify("Border Bill Passes", CFG))

    def test_treatment(self):
        cs = [cl(1, "Quill Pushes Back on Court Plan"), cl(2, "Varn Votes Against Tax Cuts"),
              cl(3, "Quill Faces Primary Challenger"), cl(4, "Border Bill Passes")]
        out = faction.compute(cs, {}, {"alignment_cfg": {"faction": CFG}})
        self.assertTrue(cs[0]["lead_excluded"] and cs[0]["top_excluded"])
        self.assertTrue(cs[1].get("faction_defect"))
        self.assertTrue(out[3] > out[2] > out[4] > out[1])
        self.assertFalse(cs[2].get("lead_excluded") or cs[3].get("top_excluded"))

    def test_disabled_without_config(self):
        self.assertIsNone(faction.compute([cl(1, "x")], {}, {"alignment_cfg": {}}))


class HashedOverride(unittest.TestCase):
    def test_sha256_key(self):
        from ranking import headline as H
        u = "https://example.com/politics/quill-story/"
        ov = H._Overrides({H.url_key(u): "Hand Headline"})
        self.assertIn(u, ov)
        self.assertEqual(ov.get(u), "Hand Headline")
        self.assertEqual(ov[u], "Hand Headline")
        self.assertIsNone(ov.get("https://example.com/other"))
