import json, os, unittest
from _helpers import ROOT
from ranking.headline import clean

URL = "https://thefederalist.com/2026/10/15/shane-gillis-outcry-shows-we-need-more-public-shaming-at-the-gym-and-everywhere/"
H = "Gillis Was Right: Gym Booty Shorts Are Lululemon Set’s Version of Homeless Guy Dropping Deuce in Park"


class BestLine(unittest.TestCase):
    def test_gillis_override_house_style(self):
        ov = json.load(open(os.path.join(ROOT, "headline_overrides.json")))
        self.assertEqual(ov[URL], H)
        self.assertEqual(clean(H)[0], H)  # style rules leave it as written


if __name__ == "__main__":
    unittest.main()
