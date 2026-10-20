"""Quote QC: every displayed headline has balanced opening and closing quotes. Apostrophes (don’t,
Dems’, ’90s) are never mistaken for closing single quotes, and shortening never cuts inside a quotation."""
import os, re, html, unittest
from _helpers import ROOT, story
from ranking import headline as H
import aggregator as A


class Balance(unittest.TestCase):
    def test_balanced(self):
        for t in ["Star’s Pitch Is Anything but ‘Fine, Fine, Fine’", "Dems’ ‘Plan’ Fails", "Don’t Say ‘No’",
                  "The ’90s ‘Return’", "Kids’ Day Off", "He Said ‘I Won’t Say “Never”’ to Reporters",
                  "Rock ‘n’ Roll Mayor Wins", "Senators’ ‘Big, Beautiful Bill’ Passes", "No Quotes Here"]:
            self.assertTrue(H.balanced_quotes(t), t)

    def test_unbalanced(self):
        for t in ["Pitch Is Anything but ‘Fine", "Mayor Calls Plan ‘Insane", "He Said “No", "He Said ”No",
                  "He Said ‘I Won’t Say “Never’"]:
            self.assertFalse(H.balanced_quotes(t), t)

    def test_apostrophe_inside_open_quote_is_not_a_close(self):
        self.assertFalse(H.balanced_quotes("Mayor Calls It ‘Joe’s Mess"))   # Joe’s is an apostrophe
        self.assertTrue(H.balanced_quotes("Mayor Calls It ‘Joe’s Mess’"))

    def test_repair(self):
        self.assertEqual(H.repair_quotes("Pitch Is Anything but ‘Fine"), "Pitch Is Anything but ‘Fine’")
        self.assertEqual(H.repair_quotes("He Said ‘I Won’t Say “Never"), "He Said ‘I Won’t Say “Never”’")
        self.assertEqual(H.repair_quotes("He Said ”No"), "He Said No")
        self.assertEqual(H.repair_quotes("Mayor Slams Plan ‘"), "Mayor Slams Plan")
        for t in ["Dems’ ‘Plan’ Fails", "Kids’ Day Off", "The ’90s ‘Return’"]:
            self.assertEqual(H.repair_quotes(t), t)  # balanced: untouched

    def test_inside_quote(self):
        t = "Pitch Is Anything but ‘Fine, Fine, Fine’ Now"
        self.assertTrue(H.inside_quote(t, t.index(",")))
        self.assertFalse(H.inside_quote(t, t.index(" Now")))


class Shorten(unittest.TestCase):
    T = "Famous Person’s Political Pitch to Voters Is Anything but ‘Fine, Fine, Fine’"

    def test_never_cuts_inside_a_quotation(self):
        out = H.shorten(H.clean(self.T)[0])
        self.assertTrue(H.balanced_quotes(out), out)
        self.assertIn("‘Fine, Fine, Fine’", out)

    def test_still_cuts_outside_quotes(self):
        t = "Mayor Calls Budget Plan ‘Insane’ After Council Members Argue Over Spending Cuts for Hours, Officials Say"
        out = H.shorten(t)
        self.assertTrue(H.balanced_quotes(out), out)
        self.assertLess(len(out), len(t))


class DisplayQC(unittest.TestCase):
    def test_unbalanced_display_repaired(self):
        lead = story("Famous Person’s Political Pitch Is Anything but ‘Fine", 1, link="https://example.com/news/a")
        l, _, _, st = A.decorate_headlines(lead, [], [[], [], []], [{"items": [lead]}])
        self.assertTrue(H.balanced_quotes(l["display"]), l["display"])
        self.assertTrue(l["display"].endswith("‘Fine’"))
        self.assertEqual(st.get("quotes_repaired"), 1)

    def test_balanced_display_untouched(self):
        lead = story("Mayor Calls Budget Plan ‘Insane’", 1, link="https://example.com/news/b")
        l, _, _, st = A.decorate_headlines(lead, [], [[], [], []], [{"items": [lead]}])
        self.assertEqual(l["display"], "Mayor Calls Budget Plan ‘Insane’")
        self.assertFalse(st.get("quotes_repaired"))

    def test_override_values_balanced(self):
        bad = [v for v in H.overrides().values() if v and not H.balanced_quotes(v)]
        self.assertEqual(bad, [])

    def test_built_page_headlines_balanced(self):
        p = os.path.join(ROOT, "site", "index.html")
        if not os.path.exists(p):
            self.skipTest("site not built")
        page = open(p, errors="ignore").read()
        heads = [html.unescape(re.sub(r"<[^>]+>", "", m)).strip() for m in re.findall(r"<a [^>]*>(.*?)</a>", page, re.S)]
        bad = [h for h in heads if h and not H.balanced_quotes(h)]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
