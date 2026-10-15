import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ranking.headline import clean, title_case


class TitleCase(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(clean("DOGE Gets Its Day at the Supreme Court As Justices Take Up Trump Administration Appeal")[0],
                         "DOGE Gets Day at SCOTUS as Justices Take Up Trump Administration Appeal")
        self.assertEqual(title_case("Netanyahu rival vows to end Hamas rule within 18 months if elected"),
                         "Netanyahu Rival Vows to End Hamas Rule Within 18 Months if Elected")
        self.assertEqual(clean("Netflix to lay off 1,000 employees")[0], "Netflix to Lay Off 1,000 Employees")

    def test_preserve(self):
        self.assertEqual(clean("Trump says Abdul el Sayed is ‘100%’ a ‘Muslim Brotherhood guy’")[0],
                         "Trump Says Abdul el Sayed Is ‘100%’ ‘Muslim Brotherhood’")
        self.assertEqual(title_case("McConnell slams iPhone ban by DEMS and GOP"), "McConnell Slams iPhone Ban by DEMS and GOP")
        self.assertEqual(title_case("the end of an era"), "The End of an Era")       # first word
        self.assertEqual(title_case("what are they fighting for"), "What Are They Fighting For")  # last word
        self.assertEqual(title_case("Trump: the comeback"), "Trump: The Comeback")    # after colon
        self.assertEqual(title_case("ICE says no to live-stream rules"), "ICE Says No to Live-Stream Rules")
        self.assertEqual(title_case("Gov. won’t back down"), "Gov. Won’t Back Down")


if __name__ == "__main__":
    unittest.main()
