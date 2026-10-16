import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ranking import defeatism

# Fictional lexicon: the real one lives in the private config.
CFG = {"terms": ["can't win", "doomed", "blow to", "in disarray"], "always": ["zz-genre"],
       "own_subjects": ["blue team", "blue"], "other_subjects": ["red team", "red"], "window_words": 6}


def cl(i, t):
    return {"id": i, "items": [{"title": t}]}


class Defeatism(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(defeatism.classify("Blue Can’t Win by Throwing Allies Under the Bus", CFG), "exclude")
        self.assertEqual(defeatism.classify("Tariff Ruling a Blow to Blue", CFG), "exclude")
        self.assertEqual(defeatism.classify("Blue Team in Disarray Over Spending", CFG), "exclude")
        self.assertEqual(defeatism.classify("A ZZ-Genre Essay on the Midterms", CFG), "exclude")
        self.assertEqual(defeatism.classify("Red Can’t Win Without the Working Class", CFG), "boost")
        self.assertEqual(defeatism.classify("Blue Says Red Is Doomed", CFG), "boost")
        self.assertIsNone(defeatism.classify("Blue Signs Border Bill", CFG))

    def test_excluded_and_boosted(self):
        cs = [cl(1, "Blue Can’t Win"), cl(2, "Red Team Is Doomed"), cl(3, "Senate Passes Bill")]
        out = defeatism.compute(cs, {}, {"alignment_cfg": {"defeatism": CFG}})
        self.assertTrue(cs[0].get("excluded"))
        self.assertFalse(cs[1].get("excluded") or cs[2].get("excluded"))
        self.assertGreater(out[2], out[3])

    def test_off_without_config(self):
        self.assertIsNone(defeatism.compute([cl(1, "x")], {}, {"alignment_cfg": {}}))
