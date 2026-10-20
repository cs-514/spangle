"""Pure-sports gate in the newsworthiness module. Uses a small inline lexicon with made-up team and league
names (the real cue lists are private)."""
import copy, unittest
from _helpers import story
from ranking import newsworthy as N
from test_newsworthy import CFG as BASE

CFG = copy.deepcopy(BASE)
NW = CFG["newsworthiness"]
NW["core_terms"] += ["police", "ice", "white house"]
NW["politics_terms"] += ["police", "ice", "union", "president"]
NW["routine_court_terms"] += ["police", "arrested"]
NW.update({
    "sports_terms": ["gbl", "zorbball", "alphas", "bravo city bravos", "metro union", "sidelined for the year", "lead trainer"],
    "sports_team_terms": ["generals", "bravos"],
    "sports_paths": ["/games-desk/"],
    "sports_hooks": ["anthem", "trans athlete", "women's sports", "white house", "dei", "woke", "executive order"],
    "sports_hook_verbs": ["slams", "praises", "meets", "bans", "sues"],
    "sports_hook_ignore": ["president", "ice"],
})


def one(title, link=None, desc=""):
    cs = [{"id": 0, "outlets": ["x"], "items": [story(title, link=link, desc=desc)]}]
    out = N.compute(cs, {}, {"alignment_cfg": CFG})
    return cs[0], out[0]


class PureSports(unittest.TestCase):
    def test_injury_story_dropped(self):
        c, _ = one("Alphas’ Star Passer Sidelined for the Year After Medical Scare")
        self.assertTrue(c.get("dropped"))

    def test_sports_path_alone_dropped(self):
        c, _ = one("Star Passer Done for the Year", link="https://news.example/games-desk/2026/10/star-passer")
        self.assertTrue(c.get("dropped"))

    def test_trade_and_coach_drama_dropped(self):
        for t in ["Alphas Trade Veteran Guard Ahead of Deadline", "GBL Lead Trainer Fired After Locker-Room Feud"]:
            self.assertTrue(one(t)[0].get("dropped"), t)

    def test_ambiguous_nickname_alone_is_not_sports(self):
        c, out = one("Generals Warn Senate Over Military Readiness")
        self.assertFalse(c.get("dropped")); self.assertEqual(out, 0.85)

    def test_ambiguous_nickname_corroborated_by_blurb_dropped(self):
        c, _ = one("Generals Rally Late to Stun Rivals", desc="The GBL club scored twice in the final minute.")
        self.assertTrue(c.get("dropped"))

    def test_hook_inside_a_team_name_does_not_count(self):
        c, _ = one("Metro Union Beat Alphas in Overtime Thriller")  # 'union' is a politics word here only as a team name
        self.assertTrue(c.get("dropped"))

    def test_non_sports_story_unchanged(self):
        c, out = one("Senate Passes Border Bill")
        self.assertFalse(c.get("dropped")); self.assertEqual(out, 0.85)


class SportsHooks(unittest.TestCase):
    def test_culture_war_hooks_kept(self):
        for t in ["Alphas Player Kneels During National Anthem",
                  "GBL Lets Trans Athlete Compete, Sparking Women’s Sports Fight",
                  "Champion Alphas Visit the White House",
                  "GBL Unveils New DEI Hiring Mandate",
                  "Executive Order Targets GBL Broadcast Deal"]:
            c, out = one(t)
            self.assertFalse(c.get("dropped"), t); self.assertEqual(out, 0.85, t)
            self.assertFalse(c.get("top_excluded"), t)

    def test_player_criticizing_or_praising_politician_kept(self):
        for t in ["Alphas Star Slams Trump Over Tariffs", "Alphas Star Praises Trump After Win", "Trump Slams GBL Over Ratings"]:
            self.assertFalse(one(t)[0].get("dropped"), t)

    def test_government_action_kept(self):
        self.assertFalse(one("Democrats Sue GBL Over Stadium Subsidy")[0].get("dropped"))

    def test_incidental_trump_is_not_a_hook(self):
        c, _ = one("Alphas Rout Bravo City Bravos in Blowout as Trump Watches From Suite")
        self.assertTrue(c.get("dropped"))

    def test_incidental_police_is_not_a_hook(self):
        for t in ["Alphas Star Arrested After Police Chase", "Police Escort Alphas Bus to Zorbball Final"]:
            self.assertTrue(one(t)[0].get("dropped"), t)

    def test_ignored_generic_words_are_not_hooks(self):
        for t in ["President of the Alphas Fires Lead Trainer", "Ice Storm Delays Alphas Game"]:
            self.assertTrue(one(t)[0].get("dropped"), t)

    def test_hook_must_be_in_the_headline(self):
        c, _ = one("Alphas Win Again", desc="Trump attended the game and praised the team.")
        self.assertTrue(c.get("dropped"))


class SportsClusters(unittest.TestCase):
    def run_cluster(self, *titles):
        cs = [{"id": 0, "outlets": [f"o{i}" for i in range(len(titles))], "items": [story(t) for t in titles]}]
        N.compute(cs, {}, {"alignment_cfg": CFG})
        return cs[0]

    def test_all_sports_siblings_drop_the_cluster(self):
        c = self.run_cluster("Alphas Star Sidelined for the Year", "Alphas Fans Blast Team After Star’s Injury",
                             "Medical Scare Ends Alphas Star’s Year")  # third headline has no cue, majority rules
        self.assertTrue(c.get("dropped"))

    def test_hooked_sibling_keeps_the_cluster(self):
        c = self.run_cluster("Alphas Star Skips Anthem Ceremony", "Alphas Star Sidelined for the Year")
        self.assertFalse(c.get("dropped"))

    def test_political_majority_keeps_cluster_and_sheds_sports_sibling(self):
        c = self.run_cluster("Senate Votes to Cut Stadium Tax Breaks", "Democrats Fight Over Stadium Tax Plan",
                             "Alphas Sidelined for the Year Amid Turmoil")
        self.assertFalse(c.get("dropped"))
        self.assertNotIn("Alphas Sidelined for the Year Amid Turmoil", [x["title"] for x in c["items"]])

    def test_disabled_without_sports_cues(self):
        cs = [{"id": 0, "outlets": ["x"], "items": [story("Alphas Star Sidelined for the Year")]}]
        N.compute(cs, {}, {"alignment_cfg": BASE})
        self.assertFalse(cs[0].get("dropped"))


if __name__ == "__main__":
    unittest.main()
