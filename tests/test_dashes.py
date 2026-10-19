import json, unittest
from _helpers import ROOT
from ranking import headline as h, qotd_headline as Q
import aggregator as A


class Dashes(unittest.TestCase):
    def test_normalize(self):
        for src, want in (("Trump Wins -- and More", "Trump Wins—and More"), ("Trump Wins--and More", "Trump Wins—and More"),
                          ("A — B", "A—B"), ("A —B", "A—B"), ("A – B", "A—B"), ("Ages 10–12", "Ages 10–12"),
                          ("Ages 10 – 12", "Ages 10–12"), ("Harris–Walz Ticket", "Harris–Walz Ticket"),
                          ("Ex-SJSU Coach", "Ex-SJSU Coach"), ("A---B", "A—B")):
            self.assertEqual(h.dashes(src), want, src)

    def test_clean_closes_and_is_idempotent(self):
        c = h.clean("Trump wins -- and Dems melt down over the result in Ohio")[0]
        self.assertEqual(c, "Trump Wins—and Dems Melt Down over the Result in Ohio")
        self.assertEqual(h.clean(c)[0], c)
        self.assertEqual(h.clean("Polls show 10 – 12 point lead")[0], "Polls Show 10–12 Point Lead")

    def test_outlet_tail_still_stripped(self):
        self.assertEqual(h.clean("Senate Passes Border Bill — NY Post")[0], "Senate Passes Border Bill")

    def test_shorten_strips_closed_dash_tail(self):
        src = h.clean("Why Obama admin put Abdul El-Sayed’s sister-in-law on terror watch list — as he insists ‘she did nothing wrong’")[0]
        self.assertIn("List—as He", src)
        out = h.shorten("Senate Passes Sweeping Border Security Bill in Late Vote—Democrats Vow to Fight Back Hard")
        self.assertEqual(out, "Senate Passes Sweeping Border Security Bill in Late Vote")

    def test_tokens_split_at_dash(self):
        self.assertIsNone(h.incomplete("Trump Wins—and Dems Melt Down"))
        self.assertEqual(h.title_case(h.dashes("Biden Out — on the Record", closed=False)), "Biden Out — on the Record")


class AfterDash(unittest.TestCase):
    def test_minor_words_lowercase_after_dash(self):
        self.assertEqual(h.clean("What the OCC’s Debanking Report Shows—And Leaves Unanswered")[0],
                         "What the OCC’s Debanking Report Shows—and Leaves Unanswered")
        self.assertEqual(h.clean("Market falls -- the worst day in years")[0], "Market Falls—the Worst Day in Years")
        self.assertEqual(h.clean("Rally—With Thousands—Draws Crowd")[0], "Rally—with Thousands—Draws Crowd")

    def test_major_words_capitalized_after_dash(self):
        self.assertEqual(h.clean("Europe is burning—is America next?")[0], "Europe Is Burning—Is America Next?")
        self.assertEqual(h.clean("Exclusive—secretary Rubio speaks")[0], "Exclusive—Secretary Rubio Speaks")

    def test_sentence_break_and_colon_unchanged(self):
        self.assertEqual(h.clean("Abortions. but why?")[0], "Abortions. But Why?")
        self.assertEqual(h.clean("Homan: the wall works")[0], "Homan: The Wall Works")


class Orphans(unittest.TestCase):
    def test_glue_after_dash(self):
        self.assertEqual(A.no_orphan_text("Watch List—As He Insists"), "Watch List—As He\u00a0Insists")
        self.assertEqual(A.no_orphan_html("Watch List—As He Insists"), "Watch List—As He&nbsp;Insists")

    def test_break_after_dash_allowed(self):
        self.assertEqual(A.no_orphan_text("He Did Nothing—Wrong"), "He Did Nothing—Wrong")  # no glue across the dash
        self.assertEqual(A._wrap_lines("Aaaaaaaaaa—Bbbbbbbbbb", 12), 2)
        self.assertEqual(A._wrap_lines("Aaaa Bbbb Cc", 12), 1)


class Quote(unittest.TestCase):
    def test_qotd_rendering(self):
        s = A.quote_as_story({"quote": "Equality -- and resentment", "author": "X", "headline": "A — B Wins"})
        self.assertEqual(s["quote_text"], "Equality—and resentment")
        self.assertEqual(s["display"], "A—B Wins")

    def test_validator(self):
        self.assertTrue(Q.problems("Courage Is Every Virtue -- at the Testing Point"))
        self.assertEqual(Q.problems("Courage Is Every Virtue—at the Testing Point"), [])

    def test_bank_closed_dashes(self):
        for q in json.load(open(f"{ROOT}/qotd_bank.json"))["quotes"]:
            self.assertEqual(h.dashes(q["quote"]), q["quote"], q["id"])
