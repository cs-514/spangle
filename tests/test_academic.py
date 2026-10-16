import json, os, unittest
from _helpers import ROOT, story
from ranking import academic, headline
import aggregator as A

MATAL = "https://reason.com/volokh/2026/10/16/journal-of-free-speech-law-how-matal-v-tam-became-a-first-amendment-case-the-record-and-the-reality-by-simon-tam/"
S = {"academic": {"enabled": True, "sources": ["Volokh Conspiracy"], "penalty": 0.2, "hooked_score": 0.6}}


def cl(i, *items):
    return {"id": i, "outlets": sorted({s["source"] for s in items}), "items": list(items)}


class Academic(unittest.TestCase):
    def test_retrospective_kept_off_front(self):
        cs = [cl(1, story("Journal of Free Speech Law: “The Record and the Reality” by Someone", source="Volokh Conspiracy",
                          link="https://reason.com/volokh/2026/10/16/some-retrospective/"))]
        out = academic.compute(cs, S, {})
        self.assertEqual(out[1], 0.2)
        self.assertTrue(cs[0]["academic"] and cs[0]["lead_excluded"] and cs[0]["top_excluded"])
        self.assertFalse(cs[0].get("dropped"))
        cs[0].pop("dropped", None)
        academic.compute(cs, {"academic": dict(S["academic"], drop=True)}, {})
        self.assertTrue(cs[0]["dropped"])

    def test_news_hook_or_override_saves_front_eligibility(self):
        cs = [cl(1, story("Judge Blocks Trump Order on Federal Unions", source="Volokh Conspiracy")),
              cl(2, story("How Matal v. Tam Became a First Amendment Case", source="Volokh Conspiracy", link=MATAL + "?outputType=amp"))]
        out = academic.compute(cs, S, {})
        for c in cs:
            self.assertTrue(c["academic"]); self.assertFalse(c.get("top_excluded"))
            self.assertEqual(out[c["id"]], 0.6)

    def test_mainstream_cluster_not_flagged(self):
        cs = [cl(1, story("Court Strikes Down Law", source="Volokh Conspiracy"), story("Court Strikes Down Law", source="Fox News"))]
        self.assertEqual(academic.compute(cs, S, {})[1], 1.0)
        self.assertFalse(cs[0].get("academic"))

    def test_matal_override(self):
        ov = json.load(open(os.path.join(ROOT, "headline_overrides.json")))
        h = ov[MATAL]
        self.assertIn("Slants", h); self.assertNotIn("Matal", h); self.assertNotIn("'", h)
        self.assertEqual(headline.clean(h)[0], h)  # already in house style

    def test_academic_routed_to_rewrite_queue(self):
        s = story("Some Docket v. Name Retrospective", source="Volokh Conspiracy", link="https://reason.com/volokh/x/", academic=True)
        lead = story("Border Bill Passes Senate", link="https://example.com/lead")
        _, _, _, st = A.decorate_headlines(lead, [], [[s]], [cl(1, s), cl(2, lead)])
        q = [x for x in st["queue"] if x["url"] == s["link"]]
        self.assertEqual(q[0]["reason"], "academic")
        self.assertIn("popular name", q[0]["framing"])


if __name__ == "__main__":
    unittest.main()
