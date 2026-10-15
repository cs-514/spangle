import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ranking.headline import clean, numerals, title_case


class NumeralsCase(unittest.TestCase):
    def test_talarico(self):
        self.assertEqual(clean("5 Positions Talarico Abandoned In One Night")[0], "5 Positions Talarico Abandoned in 1 Night")

    def test_numerals(self):
        self.assertEqual(numerals("Three Arrested After Two Attacks"), "3 Arrested After 2 Attacks")
        for t in ["No One Is Safe", "One of Them Lied", "They Blame One Another", "Someone Did It", "Trump Wins by One"]:
            self.assertEqual(numerals(t), t, t)

    def test_lowercase(self):
        self.assertEqual(title_case("The Tribal Story Of The Year At A Glance"),
                         "The Tribal Story of the Year at a Glance")
        self.assertEqual(title_case("Biden: The End"), "Biden: The End")
        self.assertEqual(title_case("Trump Picks Plan A"), "Trump Picks Plan A")
        self.assertEqual(title_case("BREAKING IN THE NEWS"), "BREAKING IN THE NEWS")


if __name__ == "__main__":
    unittest.main()
