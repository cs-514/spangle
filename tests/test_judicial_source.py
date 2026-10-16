import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import aggregator as A


class JudicialSource(unittest.TestCase):
    def test_format_and_strip_cites(self):
        q = {"author": "Antonin Scalia", "work": "District of Columbia v. Heller", "locator": "554 U.S. 570 (2008)",
             "quote": "Q.", "verification_url": "https://www.law.cornell.edu/supct/html/07-290.ZO.html"}
        s = A.quote_as_story(q)
        self.assertEqual(s["source"], "Antonin Scalia, District of Columbia v. Heller (2008)")
        self.assertEqual(s["source_html"], "Antonin Scalia, <i>District of Columbia v. Heller</i> (2008)")
        self.assertEqual(s["link"], q["verification_url"])  # opinion link kept
        h = A.render(s, [], [[s], [], []], A.datetime(2026, 10, 16, tzinfo=A.timezone.utc), [], {"placement": {}})
        self.assertIn("<i>District of Columbia v. Heller</i> (2008)", h)
        self.assertNotIn("554 U.S.", h)

    def test_other_reporters(self):
        for work, loc, want in [("Marbury v. Madison (1803)", "5 U.S. 137", "John Marshall, Marbury v. Madison (1803)"),
                                ("Ollman v. Evans", "750 F.2d 970, 993 (D.C. Cir. 1984) (concurring)", "John Marshall, Ollman v. Evans (1984)"),
                                ("Morrison v. Olson, 487 U.S. 654, 699", "1988", "John Marshall, Morrison v. Olson (1988)")]:
            self.assertEqual(A.judicial_source({"author": "John Marshall", "work": work, "locator": loc})[0], want)

    def test_non_case_unchanged(self):
        self.assertIsNone(A.judicial_source({"author": "C. S. Lewis", "work": "Mere Christianity", "locator": "Book I"}))
        self.assertEqual(A.quote_as_story({"author": "C. S. Lewis", "work": "Mere Christianity", "locator": "Book I", "quote": "Q."})["source"],
                         "C. S. Lewis · Mere Christianity, Book I")
