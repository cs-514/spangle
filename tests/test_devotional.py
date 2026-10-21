"""Devotional / church-life gate (same mechanism as the sports gate). Made-up cue words; the real lists are private."""
import copy, unittest
from _helpers import story
from ranking import newsworthy as N
from test_newsworthy import CFG as BASE

CFG = copy.deepcopy(BASE)
NW = CFG["newsworthiness"]
NW["core_terms"] += ["clinton", "church"]
NW.update({
    "devotional_terms": ["vespering", "cantorship", "hymnal circle"],
    "devotional_paths": ["/parish-life/"],
    "devotional_hooks": ["religious liberty", "persecut", "abortion", "supreme court"],
    "devotional_hook_verbs": ["slams", "backs", "sues"],
    "devotional_hooks_include_core": True,
    "devotional_hook_ignore": ["church"],  # faith-life words never count as a political hook
})


def one(title, link=None, desc=""):
    cs = [{"id": 0, "outlets": ["x"], "items": [story(title, link=link, desc=desc)]}]
    out = N.compute(cs, {}, {"alignment_cfg": CFG})
    return cs[0], out[0]


class Devotional(unittest.TestCase):
    def test_pastoral_advice_dropped(self):
        for t in ["‘Good Vespering Is Not Enough’: Pastor Urges Church to Embrace Cantorship",
                  "Why Your Hymnal Circle Needs More Silence"]:
            self.assertTrue(one(t)[0].get("dropped"), t)

    def test_path_alone_dropped(self):
        self.assertTrue(one("Five Ways to Grow This Fall", link="https://news.example/parish-life/five-ways")[0].get("dropped"))

    def test_incidental_core_word_does_not_save_it(self):
        self.assertTrue(one("Church Leaders Urged to Rethink Vespering")[0].get("dropped"))  # 'church' is a core word

    def test_culture_war_hooks_kept(self):
        for t in ["Vespering Group Wins Religious Liberty Case", "Cantorship Leaders Face Persecution Abroad",
                  "Supreme Court Takes Up Vespering Dispute", "Clinton’s Latest Vespering on Policy", "Pastor Slams Democrats Over Vespering Rules"]:
            c, out = one(t)
            self.assertFalse(c.get("dropped"), t); self.assertEqual(out, 0.85, t)

    def test_politician_in_passing_is_not_a_hook(self):
        self.assertTrue(one("Pastor Recalls Vespering Lesson From a Visit Years Before Trump Era")[0].get("dropped"))

    def test_non_devotional_story_unchanged(self):
        c, out = one("Senate Passes Border Bill")
        self.assertFalse(c.get("dropped")); self.assertEqual(out, 0.85)

    def test_disabled_without_cues(self):
        cs = [{"id": 0, "outlets": ["x"], "items": [story("Why Your Hymnal Circle Needs More Silence")]}]
        N.compute(cs, {}, {"alignment_cfg": BASE})
        self.assertFalse(cs[0].get("dropped"))


if __name__ == "__main__":
    unittest.main()
