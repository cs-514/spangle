import json, unittest
from _helpers import ROOT
from ranking import qotd_headline as Q


class Validator(unittest.TestCase):
    def test_rejects_fragments(self):
        self.assertTrue(Q.problems("The Inherent Right of Self-Defense"))
        self.assertTrue(Q.problems("How Politics Curdled Equality into Resentment"))
        self.assertTrue(Q.problems("Facts That Matter Most"))

    def test_accepts_complete_thoughts(self):
        for h in ("Courage Is Every Virtue at the Testing Point",
                  "Those Who Flee Find No Glory, No Safety",
                  "Teach Every Child Reverence for the Laws",
                  "Politics Turned Equality into Resentment",
                  "The Safest Road to Hell Is the Gradual One",
                  "Know When to Fight"):
            self.assertEqual(Q.problems(h), [], h)

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
            self.assertEqual(Q.problems(q["headline"]), [], q["id"])

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
