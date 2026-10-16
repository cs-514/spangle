import unittest
from _helpers import story, NOW
import aggregator as A
from ranking import clutter

S = {"placement": {"check_links": False}, "originator": {"margin": 0.15},
     "clean_links": {"enabled": True, "min_gain": 0.08}, "sources": {"tiers": {}, "default_tier": 0.5},
     "age_limits": {"lead_hours": 99, "top_hours": 99, "column_hours": 99}}


def cl(*items):
    return {"id": 1, "outlets": sorted({x["source"] for x in items}), "items": list(items)}


class Originator(unittest.TestCase):
    def setUp(self):
        self.orig = clutter.clean_score
        self.sc = {}
        clutter.clean_score = lambda u, default=0.5: next((v for k, v in self.sc.items() if k in u), default)
        A.ranking.clutter.clean_score = clutter.clean_score

    def tearDown(self):
        clutter.clean_score = A.ranking.clutter.clean_score = self.orig

    def items(self):
        jtn = story("Impeaching Impeachment: Declassified memos challenge key witness testimony from 2019 Trump case",
                    hours=21, source="Just the News", link="https://justthenews.com/accountability/declassified")
        ds = story("New Documents Question Key Claims From Trump’s 2019 Impeachment", hours=10, source="Daily Signal",
                   link="https://www.dailysignal.com/documents")
        rs = story("Newly Declassified Records Raise Questions About Impeachment Witness", hours=7, source="RedState",
                   link="https://redstate.com/declassified")
        return jtn, ds, rs

    def test_earliest_is_originator(self):
        jtn, ds, rs = self.items()
        self.assertIs(A.originator(cl(ds, rs, jtn)), jtn)

    def test_citation_beats_earliest(self):
        jtn, ds, rs = self.items()
        rs["desc"] = "The documents were first reported by Daily Signal on Friday."
        self.assertIs(A.originator(cl(ds, rs, jtn)), ds)

    def test_paywalled_skipped(self):
        jtn, ds, rs = self.items()
        jtn["paywalled"] = True
        self.assertIs(A.originator(cl(ds, rs, jtn)), ds)

    def run_decorate(self, *its):
        lead = story("Border Bill Passes Senate", link="https://example.com/lead")
        s = its[1]
        _, _, cols, _ = A.decorate_headlines(lead, [], [[s]], [cl(*its), {"id": 2, "outlets": ["x"], "items": [lead]}], S, NOW)
        A.clean_links(lead, [], cols, [cl(*its)], S, NOW)
        return cols[0][0]

    def test_links_originator(self):
        self.sc = {"justthenews.com": 0.69, "dailysignal.com": 0.5, "redstate.com": 0.54}
        jtn, ds, rs = self.items()
        out = self.run_decorate(jtn, ds, rs)
        self.assertEqual(out["link"], jtn["link"])
        # JTN's series-label headline is bland/over-long, so a sibling headline is kept on the originator's link
        self.assertNotIn("Impeaching Impeachment", out["display"])

    def test_originator_headline_when_not_bland(self):
        self.sc = {"justthenews.com": 0.69, "dailysignal.com": 0.5, "redstate.com": 0.54}
        jtn, ds, rs = self.items()
        jtn["title"] = "Declassified Memos Undercut Key 2019 Impeachment Witness"
        out = self.run_decorate(jtn, ds, rs)
        self.assertEqual((out["link"], out["display"]), (jtn["link"], jtn["title"]))

    def test_clearly_cleaner_sibling_wins(self):
        self.sc = {"justthenews.com": 0.3, "dailysignal.com": 0.5, "redstate.com": 0.9}
        jtn, ds, rs = self.items()
        self.assertNotEqual(self.run_decorate(jtn, ds, rs)["link"], jtn["link"])

    def test_small_clutter_gain_keeps_originator(self):
        self.sc = {"justthenews.com": 0.5, "dailysignal.com": 0.6, "redstate.com": 0.55}
        jtn, ds, rs = self.items()
        self.assertEqual(self.run_decorate(jtn, ds, rs)["link"], jtn["link"])


class ShorterSiblingWallChecked(unittest.TestCase):
    def test_walled_shorter_sibling_not_used(self):
        A.WALL_CACHE.clear(); orig = A._url_ok
        A._url_ok = lambda x: "spectator.com" not in x["link"]
        try:
            settings = dict(S, placement={"check_links": True})
            long_t = "This Is a Very Long Headline About Jack Smith and Merrick Garland That Keeps Going On and On Past the Limit for Display"
            s = story(long_t, hours=1, source="Townhall", link="https://townhall.com/smith")
            sp = story("Garland and Jack Smith’s Plot", hours=5, source="Spectator", link="https://spectator.com/article/smith")
            lead = story("Border Bill Passes Senate", link="https://example.com/lead")
            _, _, cols, _ = A.decorate_headlines(lead, [], [[s]], [cl(s, sp), {"id": 2, "outlets": ["x"], "items": [lead]}], settings, NOW)
            self.assertNotIn("spectator.com", cols[0][0]["link"])
        finally:
            A._url_ok = orig; A.WALL_CACHE.clear()


if __name__ == "__main__":
    unittest.main()
