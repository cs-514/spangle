import json, os, unittest
from _helpers import ROOT
from ranking import headline as h

SISTER_SRC = ("Why Obama Admin Put Abdul El-Sayed’s Sister-in-Law on Terror Watch List — "
              "As He Insists ‘She Did Nothing Wrong’")


class CompleteThought(unittest.TestCase):
    def test_sister_in_law_cut_is_caught(self):
        cut = "Why Obama Admin Put Abdul El-Sayed’s Sister-in-Law"
        self.assertEqual(h.incomplete(cut), "missing_complement")  # caught even as a bare override
        self.assertTrue(h.fragment(cut, SISTER_SRC))

    def test_shorten_never_produces_it(self):
        out = h.shorten(SISTER_SRC)
        self.assertIsNone(h.incomplete(out, SISTER_SRC), out)
        self.assertIn("Watch List", out)

    def test_noun_phrases_flagged(self):
        for t in ("The Inherent Right of Self-Defense", "‘Vast Majority’ of Iran’s Attempted Attacks",
                  "Socialism’s Persistent, Disturbing Rise", "Trump’s Big Week", "Dems’ Southern Strategy",
                  "Inside France’s Explosive ‘Chaos Inc.’ Web of Communists"):
            self.assertEqual(h.incomplete(t), "no_finite_verb", t)

    def test_dangling_relative_flagged(self):
        self.assertEqual(h.incomplete("Racist Claim That Arab Mothers"), "cut_off")

    def test_cut_explainer(self):
        src = "How Biden’s Team Hid His Decline from Voters for Four Years"
        self.assertEqual(h.incomplete("How Biden’s Team Hid His Decline", src), "cut_explainer")

    def test_headline_ese_accepted(self):
        for t in ("Ex-Coach Arrested in Fraud Probe", "Talarico’s Adoptive Dad Tied to X Account Mocking Christianity",
                  "Homan: ‘We Are Coming’", "WSJ: Fed Weighs Rate Cut", "Trump to Sign Border Bill",
                  "Man Shot Dead on Manhattan Subway Platform", "Dems Approach a Perfect 2028 Storm",
                  "Elitist Media Still Impose a Dominant Partisan Narrative", "Justices Grant 3 Cases",
                  "Pain-Gain Formula Working Against Trump", "Netanyahu and Obama Reignite Decade-Old Feud",
                  "Is It True That if You’re Explaining, You’re Losing?", "Witkoff, Kushner Make Bold Bid for Peace",
                  "El-Sayed’s Sister Co-Wrote Book Dreaming of ‘Final Intifada’",
                  "Trump Reportedly Reconsidering Livestreaming Execution",
                  "Abdul El-Sayed Admits Sister-in-Law Landed on Terrorist Watchlist",
                  "Anti-Trump Demonstrations Under the ‘No Kings’ Banner Take Place",
                  "El-Sayed Defends Sister-in-Law Put on Obama-Era Terror Watch List",
                  "Judges Who Look Outside the Constitution See Only Themselves",
                  "Tom Homan Says New Worksite Crackdown Is Coming for Employers Who Hire Illegal Workers"):
            self.assertIsNone(h.incomplete(t), t)


class Queue(unittest.TestCase):
    def _story(self, title, link):
        return {"title": title, "link": link, "source": "Example", "items": []}

    def test_every_displayed_headline_checked_including_overrides(self):
        import tempfile, aggregator as A
        link = "https://example.com/a"
        lead = {"title": "Trump Signs Border Bill", "link": "https://example.com/lead", "source": "Example"}
        frag = {"title": "Trump Signs Something Else Today", "link": link, "source": "Example"}
        clusters = [{"items": [lead]}, {"items": [frag]}]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "o.json")
            json.dump({link: "Why Obama Admin Put Abdul El-Sayed’s Sister-in-Law"}, open(p, "w"))
            orig = h.overrides
            h.overrides = lambda: json.load(open(p))
            qpath = os.path.join(ROOT, "..", "rewrite_queue.json")
            bak = open(qpath, "rb").read() if os.path.exists(qpath) else None
            try:
                _l, _t, _c, st = A.decorate_headlines(lead, [], [[frag]], clusters)
            finally:
                h.overrides = orig
                if bak is not None:
                    open(qpath, "wb").write(bak)
        q = [x for x in st["queue"] if x["url"] == link]
        self.assertEqual([x["reason"] for x in q], ["fragment"])
        self.assertEqual(q[0]["fragment_kind"], "missing_complement")
        self.assertTrue(q[0]["override"])
