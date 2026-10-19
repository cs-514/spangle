import json, os, unittest
from _helpers import ROOT
from ranking.headline import clean

URL = "https://thefederalist.com/2026/10/15/shane-gillis-outcry-shows-we-need-more-public-shaming-at-the-gym-and-everywhere/"
H = "Gym Booty Shorts Are Lululemon Set’s Version of Homeless Guy Dropping Deuce in Park"


class BestLine(unittest.TestCase):
    def test_gillis_override_house_style(self):
        self.assertEqual(clean(H)[0], H)  # style rules leave it as written
        self.assertNotIn("Gillis", H)       # the line is the writer's, not attributed to Gillis


if __name__ == "__main__":
    unittest.main()
