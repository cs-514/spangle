import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ranking.headline import smartquotes, smartquotes_html, clean


class SmartQuotes(unittest.TestCase):
    def test_apostrophes(self):
        self.assertEqual(smartquotes("Omar's Husband Isn't Talking"), "Omar’s Husband Isn’t Talking")
        self.assertEqual(smartquotes("Rock of the '90s"), "Rock of the ’90s")
        self.assertEqual(smartquotes("Get 'em"), "Get ’em")
        self.assertEqual(smartquotes("the Joneses' house"), "the Joneses’ house")

    def test_quotes(self):
        self.assertEqual(smartquotes('Trump: "We Won"'), "Trump: “We Won”")
        self.assertEqual(smartquotes("He said 'no' today"), "He said ‘no’ today")
        self.assertEqual(smartquotes('("Nasty Flu")'), "(“Nasty Flu”)")
        self.assertEqual(smartquotes('Ban—"Now"'), "Ban—“Now”")
        self.assertEqual(smartquotes('"Woman" arrested'), "“Woman” arrested")

    def test_entities_and_idempotent(self):
        self.assertEqual(smartquotes("&#39;Suspicious&#39; mail &quot;now&quot;"), "‘Suspicious’ mail “now”")
        once = smartquotes("Here's \"it\"")
        self.assertEqual(smartquotes(once), once)

    def test_html_text_nodes_only(self):
        out = smartquotes_html('<a href="https://x.com/it\'s" title="a">Don\'t "go"</a>')
        self.assertIn('href="https://x.com/it\'s"', out)
        self.assertIn("Don’t “go”", out)

    def test_clean_applies(self):
        self.assertEqual(clean("Kamala's 'Pack the Supreme Court' Plan")[0], "Kamala’s ‘Pack SCOTUS’ Plan")


if __name__ == "__main__":
    unittest.main()
