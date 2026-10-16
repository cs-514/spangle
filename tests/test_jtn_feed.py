import unittest
from _helpers import ROOT
import aggregator as A
from ranking import headline

JTN = "https://justthenews.com/nation/crime/x-story?utm_source=justthenews.com&utm_medium=feed&utm_campaign=external-news-aggregators"


class JustTheNewsFeeds(unittest.TestCase):
    def test_accountability_feed_same_outlet(self):
        jtn = [f for f in A.FEEDS if f[0] == "Just the News"]
        self.assertIn("https://justthenews.com/taxonomy/term/3/feed", [f[1] for f in jtn])
        self.assertEqual(len(jtn), 2)

    def test_strip_tracking(self):
        self.assertEqual(headline.strip_tracking(JTN), "https://justthenews.com/nation/crime/x-story")
        self.assertEqual(headline.strip_tracking("https://a.com/p?id=7&utm_source=x"), "https://a.com/p?id=7")
        self.assertEqual(headline.strip_tracking("https://a.com/p"), "https://a.com/p")

    def test_utm_keyed_override_matches_stripped_link(self):
        ov = headline._Overrides({JTN: "Hand Headline"})
        self.assertEqual(ov.get("https://justthenews.com/nation/crime/x-story"), "Hand Headline")
        self.assertIn(JTN, ov)

    def test_feed_parse_strips_utm(self):
        xml = (b'<rss><channel><item><title>Declassified memos challenge 2019 testimony</title>'
               b'<link>' + JTN.replace("&", "&amp;").encode() + b'</link></item></channel></rss>')
        import urllib.request, io
        orig = urllib.request.urlopen
        urllib.request.urlopen = lambda *a, **k: io.BytesIO(xml)
        try:
            out = A._fetch(("Just the News", "https://justthenews.com/taxonomy/term/3/feed", False))
        finally:
            urllib.request.urlopen = orig
        self.assertEqual(out[0]["link"], "https://justthenews.com/nation/crime/x-story")
        self.assertEqual(out[0]["source"], "Just the News")


if __name__ == "__main__":
    unittest.main()
