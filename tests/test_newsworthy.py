"""Celebrity filter + newsworthiness gate. Uses a small inline lexicon (the real one is private)."""
import unittest
from _helpers import story
from ranking import newsworthy as N

CFG = {"newsworthiness": {
    "enabled": True,
    "core_terms": ["judge", "murder", "convicted", "sentenced", "charged", "shooting", "border", "tax", "senate", "court", "democrats", "military"],
    "celebrity_terms": ["actress", "actor", "hollywood", "late-night", "singer"],
    "entertainment_paths": ["/entertainment/"],
    "conservative_celebs": ["jon voight"],
    "speaking_out_terms": ["slams", "says", "warns"],
    "fool_terms": ["backlash", "mocked", "ridicul", "preach"],
    "politics_terms": ["trump", "israel", "democrats", "election", "tax"],
    "business_terms": ["unveils", "flying roadster", "breakthrough", "chip"],
    "aligned_figures": ["tesla", "acme founder"],
    "win_terms": ["unveils", "wins", "launches"],
    "routine_court_terms": ["bond", "judge", "murder", "convicted", "sentenced", "arraign", "charged", "shooting"],
    "national_hooks": ["illegal", "official", "teacher"],
    "routine_min_outlets": 4, "routine_drop": True,
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
        cs, out = run("College Football’s Best Untold Story Is at Oregon State")
        c = cs[0]
        self.assertTrue(c["off_criteria"] and c["lead_excluded"] and c["top_excluded"])
        self.assertFalse(c.get("dropped"))
        self.assertEqual(out[0], 0.15)

    def test_core_story_featured(self):
        cs, out = run("Senate Passes Border Bill")
        self.assertEqual(out[0], 0.85)
        self.assertFalse(cs[0].get("top_excluded"))

    def test_business_and_aligned_win_featured_and_boosted(self):
        cs, out = run("Tesla Unveils Flying Roadster in Viral Stunt Debut",   # both
                      "Startup Unveils Chip Breakthrough",                    # business only
                      "Acme Founder Wins Key Contract")                       # aligned-figure win only
        for c in cs:
            self.assertTrue(c["featured_ok"]); self.assertFalse(c.get("top_excluded")); self.assertFalse(c.get("dropped"))
        self.assertEqual(out[0], 1.0)
        self.assertEqual(out[1], 0.9); self.assertEqual(out[2], 0.9)

    def test_business_story_passes_soft_gate(self):
        from ranking import lead
        cfg = {"soft_gate_paths": ["/tech/"]}
        s = story("Tesla Unveils Flying Roadster", link="https://example.com/tech/roadster")
        self.assertTrue(lead.gated(s, cfg, soft=True))  # the gate itself still matches; featured_ok exempts it in order_for_lead

    def test_routine_local_court_dropped(self):
        cs, _ = run("Colorado Judge Denies Bond to Woman Convicted in 2008 of Murdering Her Children")
        self.assertTrue(cs[0]["dropped"])

    def test_routine_with_national_hook_kept(self):
        for t in ["Illegal Alien Sentenced for Murder of Teen", "Trump Blasts Judge After Shooting Suspect Released",
                  "School Official Charged in Abuse Case"]:
            cs, out = run(t)
            self.assertFalse(cs[0].get("dropped"), t); self.assertEqual(out[0], 0.85, t)

    def test_routine_with_wide_coverage_kept(self):
        it = [story("Gunman Kills Four in Mall Shooting", source=f"o{i}") for i in range(4)]
        cs = [{"id": 0, "outlets": [f"o{i}" for i in range(4)], "items": it}]
        out = N.compute(cs, {}, {"alignment_cfg": CFG})
        self.assertFalse(cs[0].get("dropped")); self.assertEqual(out[0], 0.85)

    def test_disabled_without_private_config(self):
        self.assertIsNone(N.compute([], {}, {"alignment_cfg": {}}))


if __name__ == "__main__":
    unittest.main()
