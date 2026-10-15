import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ranking.headline import clean, drop_possessives


class Possessives(unittest.TestCase):
    def test_drops(self):
        self.assertEqual(clean("Omar Probe Aims to Strip Her Citizenship, Deport Her")[0],
                         "Omar Probe Aims to Strip Citizenship, Deport Her")
        self.assertEqual(drop_possessives("Newsom Defends His Record on Crime"), "Newsom Defends Record on Crime")
        self.assertEqual(drop_possessives("Hochul Abandons Her Tax Plan"), "Hochul Abandons Tax Plan")

    def test_keeps(self):
        for t in ["Trump Slams Omar Over Her Remarks",          # after preposition: ambiguous
                  "The Senate Passes Its Budget",               # generic starter
                  "Omar Probe Aims to Deport Her",              # object pronoun at end
                  "Musk Fires His Own Team",
                  "DOGE Gets Its Day at SCOTUS",               # idiom: 'gets its day'
                  "Trump Makes His Mark on Fed",                    # 'own'
                  "She Says Her Plan Works"]:                   # pronoun subject
            self.assertEqual(drop_possessives(t), t, t)

    def test_curly_preserved(self):
        self.assertEqual(clean("Omar’s Ally Defends Her ‘Citizenship’ Claim")[0], "Omar’s Ally Defends Her ‘Citizenship’ Claim")
        # quoted noun after the pronoun: left alone (conservative), quotes curled
        self.assertEqual(clean("Hochul's Aide Quits Her 'Dream' Job")[0], "Hochul’s Aide Quits Her ‘Dream’ Job")
        self.assertEqual(clean("Omar's Probe Aims to Strip Her Citizenship")[0], "Omar’s Probe Aims to Strip Citizenship")


if __name__ == "__main__":
    unittest.main()
