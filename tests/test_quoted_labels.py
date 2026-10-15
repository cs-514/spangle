import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ranking.headline import clean, trim_quoted_labels


class QuotedLabels(unittest.TestCase):
    def test_user_example(self):
        self.assertEqual(clean("Trump says Abdul el Sayed is ‘100%’ a ‘Muslim Brotherhood guy’")[0],
                         "Trump says Abdul el Sayed is ‘100%’ ‘Muslim Brotherhood’")
        self.assertEqual(clean("Trump says Abdul el Sayed is '100%' a 'Muslim Brotherhood guy'")[0],
                         "Trump says Abdul el Sayed is ‘100%’ ‘Muslim Brotherhood’")

    def test_prefix_and_keep(self):
        self.assertEqual(trim_quoted_labels("Biden Calls Plan ‘kind of a joke’"), "Biden Calls Plan ‘joke’")
        for t in ["Senator Is a ‘Guy’", "Trump: ‘We Won’", "He’s a ‘tough guy’ now".replace("tough guy", "tough")]:
            self.assertEqual(trim_quoted_labels(t), t)
        # possessive apostrophes are not treated as quotes
        self.assertEqual(trim_quoted_labels("Omar’s ‘Family Business’ Probed"), "Omar’s ‘Family Business’ Probed")


if __name__ == "__main__":
    unittest.main()
