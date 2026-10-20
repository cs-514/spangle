import unittest
from ranking import headline as h


class SourceAcronyms(unittest.TestCase):
    def c(self, t):
        return h.clean(t)[0]

    def test_wnba_and_sports_orgs(self):
        self.assertIn("WNBA Finals", self.c("Unhinged Libs Went Bananas over These T-Shirts at Game 1 of the WNBA Finals"))
        for a in ("WNBA", "NBA", "NFL", "MLB", "NHL", "MLS", "NCAA", "ESPN", "UFC", "PGA", "NASCAR", "WWE", "FIFA"):
            self.assertIn(a, h.acronyms(kind="well_known"), a)
            self.assertEqual(self.c(f"{a} Announces New Season Schedule"), f"{a} Announces New Season Schedule")
            self.assertEqual(h.obscure_acronyms(f"{a} Announces New Season Schedule"), [])

    def test_unknown_isolated_caps_kept_and_flagged(self):
        t = self.c("New ZOOX Robotaxi Debuts in Vegas")
        self.assertIn("ZOOX", t)  # never 'Zoox'-by-accident or 'Wnba'-style
        self.assertEqual(h.obscure_acronyms(t), ["ZOOX"])
        self.assertIn("Navy-UTSA", self.c("U.S. Airman Dies During Pregame Ceremony at Navy-UTSA Game"))

    def test_shouting_titles_still_fixed(self):
        self.assertEqual(self.c("TRUMP EVISCERATES BIDEN OVER BORDER"), "Trump Eviscerates Biden over Border")
        self.assertEqual(self.c("TRUMP SLAMS THE FBI"), "Trump Slams the FBI")

    def test_emphasis_runs_and_shout_words(self):
        self.assertEqual(self.c("JOE ROSS: 2026 election could come down to one voter")[:9], "Joe Ross:")
        self.assertTrue(self.c("SMITH, JONES: Democrats could be riding a wave").startswith("Smith, Jones:"))
        self.assertEqual(self.c("Trump SLAMS Dems over Shutdown"), "Trump Slams Dems over Shutdown")
        self.assertEqual(self.c("Dems WATCH as Bill Fails"), "Dems Watch as Bill Fails")

    def test_known_phrases_not_flagged(self):
        self.assertEqual(h.obscure_acronyms(self.c("Reconciliation Is the Strategy to Pass the SAVE America Act")), [])
        self.assertEqual(h.obscure_acronyms(self.c("Senator Opposes the SAVE Act")), [])
