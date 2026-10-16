import json, os, unittest
from _helpers import ROOT
from ranking.headline import clean, headline_quotes, smartquotes


class HeadlineQuotes(unittest.TestCase):
    def test_double_to_single(self):
        self.assertEqual(clean("Dems’ “Affordability” Pitch Is Utter Nonsense")[0], "Dems’ ‘Affordability’ Pitch Is Utter Nonsense")
        self.assertEqual(clean('Trump: "Massive" Oil Hunt to Begin')[0], "Trump: ‘Massive’ Oil Hunt to Begin")

    def test_nested_becomes_double(self):
        self.assertEqual(clean("He Said “I Won’t Say ‘Never’” to Reporters")[0], "He Said ‘I Won’t Say “Never”’ to Reporters")

    def test_apostrophes_untouched(self):
        for t in ["Kids’ ‘Day Off’", "The ’90s ‘Return’", "Rogan: DEMS Lost Me Because ‘Open Border Was Insane’"]:
            self.assertEqual(clean(t)[0], t)

    def test_idempotent(self):
        t = clean("He Said “I Won’t Say ‘Never’” to Reporters")[0]
        self.assertEqual(clean(t)[0], t)

    def test_overrides_have_no_double_quotes(self):
        ov = json.load(open(os.path.join(ROOT, "headline_overrides.json")))
        self.assertEqual([v for v in ov.values() if any(c in v for c in '“”"')], [])

    def test_qotd_body_untouched(self):
        self.assertEqual(smartquotes('He said "no."'), "He said “no.”")  # body text path keeps double quotes


if __name__ == "__main__":
    unittest.main()
