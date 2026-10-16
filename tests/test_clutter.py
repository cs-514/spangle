import os, sys, unittest
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ranking import clutter as C

P = "<p>" + "Word " * 400 + "</p>"


class Clutter(unittest.TestCase):
    def setUp(self):
        self._s = C._S
        C._S = {"clean.com": {"score": 0.9}, "messy.com": {"score": 0.2},
                "amp.com": {"score": 0.4, "variant": {"type": "suffix", "value": "/amp/"}},
                "rel.com": {"score": 0.4, "variant": {"type": "amphtml"}}}

    def tearDown(self):
        C._S = self._s

    def test_scores_and_signal(self):
        self.assertEqual(C.clean_score("https://www.clean.com/a"), 0.9)
        self.assertEqual(C.clean_score("https://news.messy.com/a"), 0.2)  # parent domain
        self.assertEqual(C.clean_score("https://unknown.org/a"), 0.5)
        cs = [{"id": 1, "items": [{"link": "https://messy.com/x"}, {"link": "https://clean.com/y"}]}]
        self.assertEqual(C.compute(cs, {}, {})[1], 0.9)

    def test_link_score_prefers_clean_at_equal_tier(self):
        now = datetime(2026, 10, 16, tzinfo=timezone.utc)
        a = {"source": "A", "link": "https://messy.com/x", "when": now - timedelta(hours=1)}
        b = {"source": "B", "link": "https://clean.com/y", "when": now - timedelta(hours=1)}
        t = {"A": 0.7, "B": 0.7}
        self.assertGreater(C.link_score(b, t, 0.5, now), C.link_score(a, t, 0.5, now))

    def test_lighter_variant_validated(self):
        u = "https://amp.com/story/"
        ok = lambda url: (200, url, "<html>" + P + "</html>")
        self.assertEqual(C.lighter(u, get=ok), "https://amp.com/story/amp/")
        short = lambda url: (200, url, "<html>" + (P if not url.endswith("/amp/") else "<p>teaser</p>") + "</html>")
        self.assertIsNone(C.lighter(u, get=short))  # not the full article -> keep canonical
        wall = lambda url: (200, url, P + ("Subscribe to continue reading" if url.endswith("/amp/") else ""))
        self.assertIsNone(C.lighter(u, get=wall))
        def err(url):
            if url.endswith("/amp/"):
                raise OSError("404")
            return 200, url, P
        self.assertIsNone(C.lighter(u, get=err))
        self.assertIsNone(C.lighter("https://clean.com/a", get=ok))  # no variant rule

    def test_amphtml_from_page(self):
        def g(url):
            if "amp.rel.com" in url:
                return 200, url, P
            return 200, url, '<link rel="amphtml" href="https://amp.rel.com/s">' + P
        self.assertEqual(C.lighter("https://rel.com/s", get=g), "https://amp.rel.com/s")
