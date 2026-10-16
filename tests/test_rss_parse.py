import os, sys, tempfile, unittest, xml.etree.ElementTree
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import aggregator as A

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>
<item><title>Senate Passes Border Bill</title><link>https://example.com/a</link>
<description>Body</description><pubDate>Thu, 15 Oct 2026 20:13:00 GMT</pubDate></item>
<item><title>Second Story Here</title><link>https://example.com/b</link></item>
</channel></rss>"""


class RealFetchPath(unittest.TestCase):
    def test_parses_sample_rss(self):
        # Regression: a tz constant named ET once shadowed xml.etree.ElementTree and broke every RSS feed.
        self.assertIs(A.ET, xml.etree.ElementTree)
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as f:
            f.write(RSS)
        try:
            before = A.FEED_STATS["ok"]
            items = A.fetch(("Sample", "file://" + f.name, False))
        finally:
            os.unlink(f.name)
        self.assertEqual([i["title"] for i in items], ["Senate Passes Border Bill", "Second Story Here"])
        self.assertIsInstance(items[0]["when"], datetime)
        self.assertEqual(A.FEED_STATS["ok"], before + 1)
        self.assertEqual(A.fmt_et(items[0]["when"]), "Oct 15, 4:13 PM")

    def test_build_guard_thresholds(self):
        self.assertGreaterEqual(A.MIN_FEEDS_OK, 20)
        self.assertGreaterEqual(A.MIN_LINKS, 40)
