"""Celebrity filter + newsworthiness gate. Uses a small inline lexicon (the real one is private)."""
import unittest
from _helpers import story
from ranking import newsworthy as N

CFG = {"newsworthiness": {
    "enabled": True,
    "core_terms": ["border", "tax", "senate", "court", "democrats", "military"],
    "celebrity_terms": ["actress", "actor", "hollywood", "late-night", "singer"],
    "entertainment_paths": ["/entertainment/"],
    "conservative_celebs": ["jon voight"],
    "speaking_out_terms": ["slams", "says", "warns"],
    "fool_terms": ["backlash", "mocked", "ridicul", "preach"],
    "politics_terms": ["trump", "israel", "democrats", "election", "tax"],
    "penalty": 0.15}}


def run(*titles, link=None):
    cs = [{"id": i, "outlets": ["x"], "items": [story(t, link=link)]} for i, t in enumerate(titles)]
    out = N.compute(cs, {}, {"alignment_cfg": CFG})
    return cs, out


class Celebrity(unittest.TestCase):
    def test_plain_celebrity_dropped(self):
        cs, _ = run("Actress, 52, Confronts Double Standard Over Becoming a Mom Again")
        self.assertTrue(cs[0]["dropped"])

    def test_entertainment_path_dropped(self):
        cs, _ = run("Star Opens Up About New Role", link="https://example.com/entertainment/star-new-role")
        self.assertTrue(cs[0].get("dropped"))

    def test_conservative_celebrity_speaking_out_kept_favorably(self):
        cs, out = run("Jon Voight Slams Democrats Over Border Chaos")
        self.assertFalse(cs[0].get("dropped"))
        self.assertEqual(cs[0]["celebrity"], "conservative")
        self.assertEqual(out[0], 1.0)
        self.assertFalse(cs[0].get("top_excluded"))

    def test_celebrity_fool_on_politics_kept(self):
        cs, _ = run("Hollywood Actor Mocked After Comparing Trump to a Dictator")
        self.assertFalse(cs[0].get("dropped"))
        self.assertEqual(cs[0]["celebrity"], "fool")
        cs, _ = run("Late-Night Host Preaches About Israel, Draws Backlash")
        self.assertEqual(cs[0]["celebrity"], "fool")

    def test_celebrity_politics_without_backlash_dropped(self):
        cs, _ = run("Singer Says She Will Vote in the Election")
        self.assertTrue(cs[0]["dropped"])


class Newsworthiness(unittest.TestCase):
    def test_off_criteria_kept_off_front_and_downranked(self):
        cs, out = run("Tesla Unveils Flying Roadster in Viral Stunt Debut")
        c = cs[0]
        self.assertTrue(c["off_criteria"] and c["lead_excluded"] and c["top_excluded"])
        self.assertFalse(c.get("dropped"))
        self.assertEqual(out[0], 0.15)

    def test_core_story_featured(self):
        cs, out = run("Senate Passes Border Bill")
        self.assertEqual(out[0], 1.0)
        self.assertFalse(cs[0].get("top_excluded"))

    def test_disabled_without_private_config(self):
        self.assertIsNone(N.compute([], {}, {"alignment_cfg": {}}))


if __name__ == "__main__":
    unittest.main()
