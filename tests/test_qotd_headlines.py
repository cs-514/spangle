import json, unittest
from _helpers import ROOT
from ranking import qotd_headline as Q


class Validator(unittest.TestCase):
    def test_rejects_fragments(self):
        self.assertTrue(Q.problems("The Inherent Right of Self-Defense"))
        self.assertTrue(Q.problems("How Politics Curdled Equality into Resentment"))
        self.assertTrue(Q.problems("Facts That Matter Most"))

    def test_accepts_complete_thoughts(self):
        for h in ("Every Virtue Faces the Same Exam",
                  "Those Who Flee Find No Glory",
                  "Power Grabs Rarely Announce Themselves",
                  "Politics Turned Equality into Resentment",
                  "Hell Rarely Comes as a Cliff",
                  "Know When to Fight"):
            self.assertEqual(Q.problems(h), [], h)

    def test_length_cap(self):
        # at most 8 words and 50 characters: a short framing, never the quote's opening copied out
        self.assertTrue(Q.problems("It Must Be Frightening to Have Your Own Independent Counsel"))  # 10 words
        self.assertTrue(Q.problems("Those Who Flee the Battle Find No Glory Anywhere"))             # 9 words
        self.assertEqual(Q.problems("Courage Is Every Virtue at the Testing Point"), [])            # 8 words: at the cap
        self.assertTrue(Q.problems("Extraordinarily Unaccountable Administrators Overwhelm Institutions"))  # > 50 chars
        self.assertEqual(Q.problems("Sample Rulers Fear Open Debate"), [])
        self.assertEqual(Q.MAX_WORDS, 8)
        self.assertEqual(Q.MAX_CHARS, 50)

    def test_rejects_punchline_headlines(self):
        quote = ("Sample officials always promise restraint before they act. But the sample river "
                 "always finds the sea.")
        self.assertTrue(Q.spoils("The Sample River Always Finds the Sea", quote))      # closing line verbatim
        self.assertTrue(Q.problems("The River Finds the Sea", quote=quote))            # closing line paraphrased
        self.assertFalse(Q.spoils("Promises Rarely Survive Power", quote))            # a framing, not the payoff
        self.assertEqual(Q.problems("Promises Rarely Survive Power", quote=quote), [])
        # the most quotable short line counts too, even when it isn't the last sentence
        punchy = "Sample counsel arrive with good intentions. Power. Then the sample paperwork never ends."
        self.assertFalse(Q.spoils("Sample Power Grabs Begin Quietly", punchy))  # one shared word is not a spoiler
        self.assertTrue(Q.spoils("Sample Paperwork Never Ends", punchy))
        # without a quote the check is skipped (headline-only callers)
        self.assertEqual(Q.problems("The River Finds the Sea"), [])

    def test_house_style(self):
        self.assertTrue(Q.problems('The "Right" of Self-Defense Is Inherent'))
        self.assertTrue(Q.problems("Duty to Say What the Law Is..."))
        self.assertTrue(Q.problems("A Thought"))


class BankHeadlines(unittest.TestCase):
    def test_every_curated_headline_is_a_complete_thought(self):
        bank = json.load(open(f"{ROOT}/qotd_bank.json"))
        for q in bank["quotes"]:
            if q.get("status") == "retired":
                continue
            self.assertTrue(q.get("headline"), q["id"])
            self.assertEqual(Q.problems(q["headline"], quote=q["quote"]), [], q["id"])

    def test_todays_quote_headline_frames_not_spoils(self):
        today = json.load(open(f"{ROOT}/quote_of_the_day.json"))
        self.assertEqual(Q.problems(today["headline"], quote=today["quote"]), [])

    def test_fallback_never_derives_from_quote_opening(self):
        import aggregator as A
        bank = {q["id"]: q for q in json.load(open(f"{ROOT}/qotd_bank.json"))["quotes"]}
        for d in range(1, 29):
            q = A.fallback_quote(f"2026-03-{d:02d}")
            self.assertEqual(q["headline"], bank[q["id"]]["headline"])

    def test_sowell_rotation_cut(self):
        bank = json.load(open(f"{ROOT}/qotd_bank.json"))
        self.assertLessEqual(bank["author_weights"]["ts"], 0.4)

    def test_retired_never_picked(self):
        import aggregator as A
        seen = set()
        for d in range(1500):
            seen.add(A.fallback_quote(f"2026-{(d // 28) % 12 + 1:02d}-{(d % 28) + 1:02d}")["id"])
        retired = {q["id"] for q in json.load(open(f"{ROOT}/qotd_bank.json"))["quotes"]
                   if q.get("status") in ("retired", "low_impact")}
        self.assertFalse(seen & retired)
