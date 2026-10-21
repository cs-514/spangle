"""Multi-sentence headlines: the shortener never drops the payoff sentence, and the fragment QC flags
period-split stubs, trailing 'Now'/'Then', and a later sentence whose verb lost its object. Also: one story
told two ways ('X claimed the agency took his wife' / 'husband claims agency nabbed her ... murder') merges."""
import unittest
from _helpers import story
from ranking import headline as H, coverage as C
import aggregator as A

SRC1 = "This local man claimed ZEA took his wife. He’s now been charged with killing her and burning the body."
SRC2 = "Wife goes missing, and husband claims ZEA nabbed her. Now, he is under arrest for murder."


class Sentences(unittest.TestCase):
    def test_split(self):
        self.assertEqual(H.sentences("Mayor Did This. Now Council Is Angry."), ["Mayor Did This.", "Now Council Is Angry."])

    def test_abbreviations_are_not_breaks(self):
        for t in ["U.S. Says Talks Are Over", "Gov. Smith Signs Bill", "J.D. Roe Wins Primary"]:
            self.assertEqual(H.sentences(t), [t])


class ShortenKeepsPayoff(unittest.TestCase):
    def test_never_cuts_the_second_sentence(self):
        for src in (SRC1, SRC2):
            c = H.clean(src)[0]
            out = H.shorten(c)
            self.assertIsNone(H.incomplete(out, src), out)
            self.assertTrue(out.rstrip(".").endswith(("Body", "Murder")), out)

    def test_single_sentence_still_trimmed(self):
        t = "Mayor Calls Budget Plan ‘Insane’ After Council Members Argue Over Spending Cuts for Hours, Officials Say"
        self.assertLess(len(H.shorten(t)), len(t))

    def test_too_long_payoff_headline_queued_not_cut(self):
        lead = story(SRC2, 1, link="https://example.com/news/wife-missing")
        l, _, _, st = A.decorate_headlines(lead, [], [[], [], []], [{"items": [lead]}])
        self.assertIsNone(H.incomplete(l["display"], SRC2), l["display"])
        self.assertTrue(l["display"].rstrip(".").endswith("Murder"), l["display"])
        self.assertTrue(any(q["url"] == lead["link"] for q in st["queue"]))  # queued for a rewrite


class FragmentQC(unittest.TestCase):
    def test_period_split_stub(self):
        self.assertEqual(H.incomplete("Wife Goes Missing, and Husband Claims ZEA Nabbed Her. Now"), "cut_off")
        self.assertEqual(H.incomplete("Wife Goes Missing, and Husband Claims ZEA Nabbed Her. Now", SRC2), "cut_off")

    def test_trailing_then_stub(self):
        self.assertEqual(H.incomplete("Council Rejected the Plan, Then"), "cut_off")
        self.assertEqual(H.incomplete("Council Rejected the Plan and Then", "Council Rejected the Plan and Then Reversed Itself"), "cut_off")

    def test_trailing_conjunctions(self):
        for t in ["Mayor Slams Plan, and", "Mayor Slams Plan but", "Mayor Slams Plan, So"]:
            self.assertEqual(H.incomplete(t), "cut_off", t)

    def test_object_cut_from_later_sentence(self):
        self.assertEqual(H.incomplete("This Local Man Claimed ZEA Took His Wife. He’s Been Charged", SRC1), "cut_off")

    def test_needs_object_participle(self):
        self.assertEqual(H.incomplete("Ex-Aide Charged", "Ex-Aide Charged with Fraud in Ohio"), "cut_off")

    def test_complete_headlines_pass(self):
        for t in ["Trump Is Winning Now", "It Was Bad. It Got Worse.", "Man Who Claimed ZEA Took His Wife Charged with Murdering Her",
                  "Ex-Aide Charged", "U.S. Says Talks Are Over"]:
            self.assertIsNone(H.incomplete(t), t)


class SameEventMerge(unittest.TestCase):
    FILLER = [f"Filler Story Number {w} About Topic {w}" for w in
              "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike november oscar papa "
              "quebec romeo sierra tango uniform victor whiskey xray yankee zulu".split()] * 3

    def test_same_event_worded_differently_merges(self):
        heads = [SRC1, SRC2] + self.FILLER
        stories = [{"title": t} for t in heads]
        cl = [{"items": [{"title": t}], "title_tokens": set()} for t in heads]
        out = C.event_merge(cl, stories)
        merged = [c for c in out if any(x["title"] == SRC1 for x in c["items"])][0]
        self.assertIn(SRC2, [x["title"] for x in merged["items"]])

    def test_lowercase_three_letter_word_is_not_an_acronym_term(self):
        a, b = "Man claims the cat took his car. Now he is charged.", "Wife says the cat ate her lunch, police say."
        heads = [a, b] + self.FILLER
        out = C.event_merge([{"items": [{"title": t}], "title_tokens": set()} for t in heads], [{"title": t} for t in heads])
        merged = [c for c in out if any(x["title"] == a for x in c["items"])][0]
        self.assertNotIn(b, [x["title"] for x in merged["items"]])


if __name__ == "__main__":
    unittest.main()
