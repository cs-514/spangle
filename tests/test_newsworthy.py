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
    "celebrity_gossip_terms": ["heartbreaking tribute", "late son", "beau", "dazzling", "custody wars", "insider claims", "divorce"],
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


class CelebrityFamilyTragedy(unittest.TestCase):
    """A celebrity family member's personal tragedy (addiction, rehab, overdose) is gossip, even with
    crime/news words ('suspected', 'police', 'officials') in the headline or blurb."""
    def cfg(self):
        import copy
        c = copy.deepcopy(CFG); n = c["newsworthiness"]
        n["core_terms"] += ["police"]; n["routine_court_terms"] += ["police", "suspect"]
        n["national_hooks"] += ["police"]
        n["entertainment_paths"] += ["/celebrity-news/"]
        n["celebrity_domains"] = ["gossip.example"]
        n["celebrity_gossip_terms"] += ["sober house", "suspected od", "rehab stint", "brother's death"]
        return c

    def run1(self, title, link="https://news.example/us/x", desc=""):
        s = story(title, link=link, desc=desc)
        cs = [{"id": 0, "outlets": ["x"], "items": [s]}]
        N.compute(cs, {}, {"alignment_cfg": self.cfg()})
        return cs[0]

    BLURB = "Officials responded to a call from the residence in February, per police records."

    def test_sober_house_overdose_dropped(self):
        t = "Sober house where model’s son died had a previous suspected OD call earlier this year: report"
        self.assertTrue(self.run1(t, desc=self.BLURB).get("dropped"))

    def test_celebrity_news_path_dropped(self):
        c = self.run1("Home where heir died had earlier police call", link="https://news.example/2026/10/19/celebrity-news/home")
        self.assertTrue(c.get("dropped"))

    def test_celebrity_outlet_dropped_without_hook(self):
        self.assertTrue(self.run1("Heir’s final weeks revealed", link="https://www.gossip.example/2026/a", desc=self.BLURB).get("dropped"))

    def test_celebrity_outlet_with_political_hook_kept(self):
        self.assertFalse(self.run1("Trump aide’s tax fight revealed", link="https://www.gossip.example/2026/b").get("dropped"))

    def test_overdose_policy_story_kept(self):
        self.assertFalse(self.run1("Border crackdown cuts overdose deaths, police say").get("dropped"))


if __name__ == "__main__":
    unittest.main()


class Gossip(unittest.TestCase):
    """Celebrity personal-life stories with no celebrity term (names aren't in any lexicon)."""
    def test_tribute_dropped(self):
        cs, _ = run("Model Shares Heartbreaking Tribute After Late Son’s Death")
        self.assertTrue(cs[0].get("dropped"))

    def test_gossip_beats_incidental_core_word(self):
        cs, _ = run("Star’s Divorce and Custody Wars Explode as Insider Claims Her Rage Is Out of Control")
        self.assertTrue(cs[0].get("dropped"))  # 'Wars' inside a gossip cue is not a news angle

    def test_political_hook_keeps_it(self):
        cs, _ = run("Trump Pays Heartbreaking Tribute to Fallen Soldiers at Dover")
        self.assertFalse(cs[0].get("dropped"))

    def test_bounded_cue(self):
        cs, _ = run("Beautiful Border Wall Section Opens in Texas")  # 'beau' never matches 'Beautiful'
        self.assertFalse(cs[0].get("dropped"))

    def test_conservative_celebrity_still_kept(self):
        cs, _ = run("Jon Voight Slams Democrats in Dazzling Speech")
        self.assertEqual(cs[0].get("celebrity"), "conservative")

    def test_one_celebrity_sibling_drops_the_cluster(self):
        cs = [{"id": 0, "outlets": ["a", "b"], "items": [
            story("Model and Daughter Honor Son After Shooting Death"),   # incidental core word
            story("Model Shares Heartbreaking Tribute After Late Son’s Death")]}]
        N.compute(cs, {}, {"alignment_cfg": CFG})
        self.assertTrue(cs[0].get("dropped"))

    def test_hook_in_a_sibling_keeps_the_cluster(self):
        cs = [{"id": 0, "outlets": ["a", "b"], "items": [
            story("Illegal Alien Charged in Shooting of Model’s Son"),
            story("Model Shares Heartbreaking Tribute After Late Son’s Death")]}]
        N.compute(cs, {}, {"alignment_cfg": CFG})
        self.assertFalse(cs[0].get("dropped"))
        self.assertEqual([x["title"] for x in cs[0]["items"]], ["Illegal Alien Charged in Shooting of Model’s Son"])
